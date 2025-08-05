#!/usr/bin/env python3
"""
Backend IA Chatbot - Architecture Séparée avec JWT
Ce script fonctionne de manière totalement indépendante et communique uniquement via FastAPI

1. Validation robuste des arguments JWT
2. Gestion sécurisée des permissions
3. Communication FastAPI avec retry
4. Logging amélioré sans crash
"""

import sys
import json
import os
import logging
import requests
import time
import traceback
from contextlib import redirect_stdout
import io
from dotenv import load_dotenv
from typing import List


# ========================================
# CONFIGURATION ET SETUP
# ========================================

def setup_environment():
    """Configuration de l'environnement backend avec validation"""
    try:
        load_dotenv()

        # Configuration du projet
        original_dir = os.getcwd()
        project_dir = os.getenv("PROJECT_DIR", original_dir)

        if project_dir and project_dir != original_dir:
            os.chdir(project_dir)
            if project_dir not in sys.path:
                sys.path.insert(0, project_dir)

        # Configuration logging renforcée
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            stream=sys.stderr
        )

        return original_dir

    except Exception as e:
        print(f"Erreur setup environnement: {e}", file=sys.stderr)
        return None


# ========================================
# COMMUNICATION AVEC FASTAPI
# ========================================

FASTAPI_URL = "http://localhost:8000/api/v1/messages"


def send_to_fastapi(session_id: str, message_type: str, content: str, metadata: dict = None):
    """
    Envoie un message vers FastAPI avec gestion d'erreur robuste

    Args:
        session_id: ID de session
        message_type: 'progress', 'final', 'error'
        content: Le message à envoyer
        metadata: Métadonnées optionnelles
    """
    if not session_id:
        print("Pas de session_id, message non envoyé", file=sys.stderr)
        return False

    try:
        payload = {
            'sessionId': session_id,
            'type': message_type,
            'content': content,
            'metadata': metadata or {
                'timestamp': time.time(),
                'source': 'backend_chatbot'
            }
        }

        response = requests.post(
            FASTAPI_URL,
            json=payload,
            timeout=10,
            headers={'Content-Type': 'application/json'}
        )

        if response.status_code == 200:
            print(f"Message envoyé: {message_type} - {content[:50]}...", file=sys.stderr)
            return True
        else:
            print(f"Erreur FastAPI {response.status_code}: {response.text}", file=sys.stderr)
            return False

    except requests.exceptions.ConnectionError:
        print(f"FastAPI non accessible sur {FASTAPI_URL}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"Erreur envoi FastAPI: {e}", file=sys.stderr)
        return False


def send_progress(session_id: str, message: str):
    """Envoie un message de progression"""
    return send_to_fastapi(session_id, 'progress', message)


def send_final(session_id: str, message: str):
    """Envoie la réponse finale"""
    return send_to_fastapi(session_id, 'final', message)


def send_error(session_id: str, error: str):
    """Envoie un message d'erreur"""
    return send_to_fastapi(session_id, 'error', f"ERREUR: {error}")


def send_log(session_id: str, log_message: str, log_level: str = "INFO"):
    """
    Envoie un log détaillé vers le frontend

    Args:
        session_id: ID de session
        log_message: Le vrai log de votre backend
        log_level: INFO, ERROR, WARNING, SUCCESS
    """
    formatted_message = f"{log_message}"

    return send_to_fastapi(session_id, 'progress', formatted_message, {
        'log_level': log_level,
        'timestamp': time.time(),
        'source': 'backend_log'
    })


# ========================================
# INTÉGRATION AVEC LES AGENTS ET JWT
# ========================================

def initialize_chatbot_with_permissions(session_id: str, user_permissions: List[str], user_role: str):
    """
    Initialise le chatbot avec prise en compte des permissions JWT

    Validation robuste des permissions et gestion d'erreurs
    """
    try:
        from src.core.chatbot import ChatbotMarocSessionId
        from src.rag.indexer import RAGTableIndex

        send_progress(session_id, f"Chargement base vectorielle (niveau: {user_role})...")

        # Configuration RAG avec permissions
        chroma_db_path = "./chroma_db"
        if not os.path.exists(chroma_db_path):
            chroma_db_path = "../chroma_db"

        # Passer les permissions au RAG
        rag_index = RAGTableIndex(
            db_path=str(chroma_db_path)
        )

        send_progress(session_id, f"Agents IA configurés pour rôle: {user_role}")

        # Créer chatbot avec permissions JWT
        chatbot = ChatbotMarocSessionId(
            rag_index,
            user_permissions=user_permissions,
            user_role=user_role
        )

        send_progress(session_id, f"Chatbot prêt - Accès niveau {user_role}")
        return chatbot

    except ImportError as e:
        send_error(session_id, f"Module non trouvé: {e}")
        raise
    except Exception as e:
        send_error(session_id, f"Erreur initialisation avec permissions: {e}")
        raise


def process_question_with_permissions(chatbot, question: str, session_id: str, user_permissions: List[str]):
    """
    Traite la question avec les agents en utilisant les permissions JWT

    CORRECTION: Capture robuste des outputs et gestion d'erreurs
    """
    try:
        send_progress(session_id, f"Traitement avec niveau d'accès pour: '{question[:50]}...'")

        # Capturer les sorties des agents
        captured_output = io.StringIO()

        with redirect_stdout(captured_output):
            response = chatbot.poser_question_with_permissions(
                question,
                session_id=session_id,
                user_permissions=user_permissions
            )

        # Récupérer les logs capturés
        captured_text = captured_output.getvalue()
        if captured_text.strip():
            # Envoyer les logs capturés ligne par ligne
            for line in captured_text.strip().split('\n'):
                if line.strip():
                    send_log(session_id, line.strip(), "INFO")

        send_progress(session_id, "Génération de la réponse finale terminée")

        return response

    except Exception as e:
        send_error(session_id, f"Erreur traitement avec permissions: {str(e)}")
        raise


# ========================================
# VALIDATION DES ARGUMENTS JWT
# ========================================

def valider_arguments_jwt(args):
    """
    NOUVEAU: Valide les arguments JWT de manière robuste

    Votre format: python chatbot_wrapper.py <question> <session_id> <permissions> <role>

    Returns:
        Dict avec les arguments validés ou erreur
    """
    if len(args) < 5:
        return {
            'error': True,
            'message': "Usage: python chatbot_wrapper.py <question> <session_id> <permissions> <role>"
        }

    try:
        user_message = args[1].strip()
        session_id = args[2].strip()
        user_permissions_str = args[3].strip()
        user_role = args[4].strip()

        # Validation de la question
        if not user_message or len(user_message) > 2000:
            return {'error': True, 'message': "Question invalide: vide ou trop longue"}

        # Validation du session_id
        if not session_id:
            return {'error': True, 'message': "Session ID invalide"}

        # Parsing des permissions JWT
        if user_permissions_str and user_permissions_str.lower() != 'none':
            user_permissions = [p.strip() for p in user_permissions_str.split(",") if p.strip()]
        else:
            user_permissions = ["read_public_docs"]  # Défaut sécurisé

        # Validation du rôle JWT
        roles_valides = ['public', 'employee', 'admin']
        if user_role.lower() not in roles_valides:
            print(f"Rôle '{user_role}' non reconnu, défaut à 'public'", file=sys.stderr)
            user_role = 'public'

        return {
            'error': False,
            'user_message': user_message,
            'session_id': session_id,
            'user_permissions': user_permissions,
            'user_role': user_role.lower()
        }

    except Exception as e:
        return {'error': True, 'message': f"Erreur validation arguments: {e}"}


# ========================================
# FONCTION PRINCIPALE AVEC JWT
# ========================================

def main():
    """Point d'entrée principal du backend séparé avec JWT"""

    # Validation robuste des arguments JWT
    validation_result = valider_arguments_jwt(sys.argv)

    if validation_result['error']:
        error_response = {
            "success": False,
            "error": validation_result['message'],
            "backend": "separated_with_auth"
        }
        print(json.dumps(error_response, ensure_ascii=False))
        sys.exit(1)

    # Extraction des arguments validés
    user_message = validation_result['user_message']
    session_id = validation_result['session_id']
    user_permissions = validation_result['user_permissions']
    user_role = validation_result['user_role']

    original_dir = None

    print(f"Chatbot démarré pour {user_role} - Session: {session_id}", file=sys.stderr)
    print(f"Permissions: {user_permissions}", file=sys.stderr)

    try:
        # 1. Setup de l'environnement
        original_dir = setup_environment()
        send_progress(session_id, f"Chatbot initialisé pour utilisateur {user_role}")

        # 2. Test de connexion FastAPI
        if not send_progress(session_id, "Test de connexion à FastAPI..."):
            raise Exception("Impossible de communiquer avec FastAPI")

        # 3. Initialisation du chatbot AVEC permissions JWT
        chatbot = initialize_chatbot_with_permissions(session_id, user_permissions, user_role)

        # 4. Traitement de la question avec permissions JWT
        send_progress(session_id, f"Traitement avec niveau d'accès: {user_role}")
        response = process_question_with_permissions(chatbot, user_message, session_id, user_permissions)

        # 5. Envoi de la réponse finale
        send_final(session_id, response)

        # 6. Succès
        result = {
            "success": True,
            "response": response,
            "session_id": session_id,
            "user_role": user_role,
            "permissions_used": user_permissions,
            "backend": "separated_with_auth"
        }
        print(json.dumps(result, ensure_ascii=False))

        print(f"Traitement terminé avec succès pour {user_role} - Session: {session_id}", file=sys.stderr)

    except Exception as e:
        # Gestion d'erreur globale
        error_msg = f"Erreur backend: {str(e)}"
        send_error(session_id, error_msg)

        # Log détaillé pour debugging
        print(f"Erreur complète: {traceback.format_exc()}", file=sys.stderr)

        error_result = {
            "success": False,
            "error": error_msg,
            "session_id": session_id,
            "user_role": user_role,
            "backend": "separated_with_auth"
        }
        print(json.dumps(error_result, ensure_ascii=False))

        sys.exit(1)

    finally:
        # Nettoyage
        if original_dir:
            try:
                os.chdir(original_dir)
            except Exception:
                pass


if __name__ == "__main__":
    main()
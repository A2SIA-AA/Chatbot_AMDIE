#!/usr/bin/env python3
"""
Backend IA Chatbot - Architecture avec MCP
"""

import sys
import json
import os
import logging
import time
import traceback
import asyncio
from contextlib import redirect_stdout
import io
from dotenv import load_dotenv
from typing import List, Optional


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
# COMMUNICATION MCP CORRIGÉE
# ========================================

# Variables globales pour MCP
MCP_BACKEND_URL = os.getenv("MCP_BACKEND_URL", "http://localhost:8090/mcp")
FALLBACK_FASTAPI_URL = os.getenv("FASTAPI_URL", "http://localhost:8000/api/v1/messages")


def setup_mcp_path():
    """Ajoute le chemin vers mcp_client_utils si nécessaire"""
    # Chercher mcp_client_utils dans les répertoires parents
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dirs = [
        current_dir,
        os.path.join(current_dir, '..'),
        os.path.join(current_dir, '../message_fastapi'),
        os.path.join(current_dir, '../../message_fastapi'),
        '/home/aissa/Bureau/Projet_Chatbot/Chatbot_AMDIE/chatbot_maroc/message_fastapi',  # Chemin absolu de secours
    ]

    for parent_dir in parent_dirs:
        mcp_client_path = os.path.join(parent_dir, 'mcp_client_utils.py')
        if os.path.exists(mcp_client_path):
            if parent_dir not in sys.path:
                sys.path.insert(0, parent_dir)
            print(f"[MCP] Client trouvé: {mcp_client_path}", file=sys.stderr)
            return True

    print(f"[MCP] ATTENTION: mcp_client_utils.py non trouvé", file=sys.stderr)
    return False


# Setup MCP au niveau module
MCP_AVAILABLE = setup_mcp_path()

if MCP_AVAILABLE:
    try:
        #  IMPORT CORRIGÉ DES FONCTIONS MCP DIRECTES
        from mcp_client_utils import (
            mcp_send_progress, mcp_send_final, mcp_send_error, mcp_send_log,
            MCPCommunicator
        )

        print(f"[MCP] Communication MCP disponible", file=sys.stderr)
    except ImportError as e:
        print(f"[MCP] Erreur import MCP: {e}", file=sys.stderr)
        MCP_AVAILABLE = False
        mcp_send_progress = mcp_send_final = mcp_send_error = mcp_send_log = None
        MCPCommunicator = None
else:
    mcp_send_progress = mcp_send_final = mcp_send_error = mcp_send_log = None
    MCPCommunicator = None


# ========================================
# COMMUNICATION CORRIGÉE AVEC DEBUG RENFORCÉ
# ========================================

async def send_progress(session_id: str, message: str) -> bool:
    """Envoie un message de progression via MCP - VERSION CORRIGÉE"""
    print(f"[WRAPPER] send_progress appelé: {session_id} - {message[:50]}...", file=sys.stderr)

    if not MCP_AVAILABLE or not mcp_send_progress:
        print(f"[WRAPPER] MCP non disponible, fallback HTTP", file=sys.stderr)
        return await send_via_http_fallback(session_id, 'progress', message)

    try:
        print(f"[WRAPPER] Tentative envoi MCP progress...", file=sys.stderr)
        result = await mcp_send_progress(session_id, message)
        print(f"[WRAPPER] Résultat MCP progress: {result}", file=sys.stderr)

        if result and result.get("ok", False):
            print(f"[WRAPPER]  send_progress via MCP réussi", file=sys.stderr)
            return True
        else:
            print(f"[WRAPPER]  send_progress MCP échoué: {result}", file=sys.stderr)
            return await send_via_http_fallback(session_id, 'progress', message)

    except Exception as e:
        print(f"[WRAPPER]  Erreur send_progress MCP: {e}", file=sys.stderr)
        print(f"[WRAPPER] Traceback: {traceback.format_exc()}", file=sys.stderr)
        return await send_via_http_fallback(session_id, 'progress', message)


async def send_final(session_id: str, message: str) -> bool:
    """Envoie la réponse finale via MCP - VERSION CORRIGÉE"""
    print(f"[WRAPPER] send_final appelé: {session_id} - {message[:50]}...", file=sys.stderr)

    if not MCP_AVAILABLE or not mcp_send_final:
        print(f"[WRAPPER] MCP non disponible, fallback HTTP", file=sys.stderr)
        return await send_via_http_fallback(session_id, 'final', message)

    try:
        print(f"[WRAPPER] Tentative envoi MCP final...", file=sys.stderr)
        result = await mcp_send_final(session_id, message)
        print(f"[WRAPPER] Résultat MCP final: {result}", file=sys.stderr)

        if result and result.get("ok", False):
            print(f"[WRAPPER]  send_final via MCP réussi", file=sys.stderr)
            return True
        else:
            print(f"[WRAPPER]  send_final MCP échoué: {result}", file=sys.stderr)
            return await send_via_http_fallback(session_id, 'final', message)

    except Exception as e:
        print(f"[WRAPPER]  Erreur send_final MCP: {e}", file=sys.stderr)
        print(f"[WRAPPER] Traceback: {traceback.format_exc()}", file=sys.stderr)
        return await send_via_http_fallback(session_id, 'final', message)


async def send_error(session_id: str, error: str) -> bool:
    """Envoie un message d'erreur via MCP - VERSION CORRIGÉE"""
    print(f"[WRAPPER] send_error appelé: {session_id} - {error[:50]}...", file=sys.stderr)

    if not MCP_AVAILABLE or not mcp_send_error:
        print(f"[WRAPPER] MCP non disponible, fallback HTTP", file=sys.stderr)
        return await send_via_http_fallback(session_id, 'error', error)

    try:
        result = await mcp_send_error(session_id, error)
        print(f"[WRAPPER] Résultat MCP error: {result}", file=sys.stderr)

        if result and result.get("ok", False):
            print(f"[WRAPPER]  send_error via MCP réussi", file=sys.stderr)
            return True
        else:
            print(f"[WRAPPER]  send_error MCP échoué: {result}", file=sys.stderr)
            return await send_via_http_fallback(session_id, 'error', error)

    except Exception as e:
        print(f"[WRAPPER]  Erreur send_error MCP: {e}", file=sys.stderr)
        return await send_via_http_fallback(session_id, 'error', error)


async def send_log(session_id: str, log_message: str, log_level: str = "INFO") -> bool:
    """Envoie un log détaillé via MCP - VERSION CORRIGÉE"""
    if not MCP_AVAILABLE or not mcp_send_log:
        print(f"[{log_level}] {log_message}", file=sys.stderr)
        return True

    try:
        result = await mcp_send_log(session_id, log_message, log_level)
        return result and result.get("ok", False)
    except Exception as e:
        print(f"[{log_level}] {log_message} (MCP failed: {e})", file=sys.stderr)
        return False


async def send_via_http_fallback(session_id: str, message_type: str, content: str) -> bool:
    """
    Fallback HTTP en cas d'échec MCP - VERSION AMÉLIORÉE
    """
    import requests

    try:
        payload = {
            'sessionId': session_id,
            'type': message_type,
            'content': content,
            'metadata': {
                'timestamp': time.time(),
                'source': 'backend_fallback_http'
            }
        }

        print(f"[WRAPPER] Fallback HTTP: {message_type} vers {FALLBACK_FASTAPI_URL}", file=sys.stderr)

        response = requests.post(
            FALLBACK_FASTAPI_URL,
            json=payload,
            timeout=10,
            headers={'Content-Type': 'application/json'}
        )

        if response.status_code == 200:
            print(f"[WRAPPER]  {message_type} envoyé via HTTP fallback", file=sys.stderr)
            return True
        else:
            print(f"[WRAPPER]  Erreur fallback {response.status_code}: {response.text}", file=sys.stderr)
            return False

    except Exception as e:
        print(f"[WRAPPER]  Erreur fallback: {e}", file=sys.stderr)
        return False


# ========================================
# INTÉGRATION AVEC LES AGENTS ET JWT (IDENTIQUE)
# ========================================

async def initialize_chatbot_with_permissions(session_id: str, user_permissions: Optional[List[str]], user_role: str):
    """
    Initialise le chatbot avec prise en compte des permissions JWT - VERSION SÉCURISÉE
    """
    try:
        #  VALIDATION DES PERMISSIONS
        if user_permissions is None:
            user_permissions = ["read_public_docs"]  # Sécurité par défaut
            await send_log(session_id, f"Permissions None détectées, défaut à : {user_permissions}", "WARNING")

        if not isinstance(user_permissions, list):
            user_permissions = ["read_public_docs"]  # Sécurité par défaut
            await send_log(session_id, f"Permissions non-liste détectées, défaut à : {user_permissions}", "WARNING")

        # Validation du rôle
        if not user_role or user_role not in ['public', 'employee', 'admin']:
            user_role = 'public'
            await send_log(session_id, f"Rôle invalide, défaut à : {user_role}", "WARNING")

        await send_progress(session_id, f"Chargement base vectorielle (niveau: {user_role})...")

        #  IMPORT SÉCURISÉ DES MODULES
        try:
            from src.core.chatbot import ChatbotMarocSessionId
            from src.rag.indexer import RAGTableIndex
            await send_log(session_id, "Modules IA importés avec succès", "INFO")
        except ImportError as e:
            await send_error(session_id, f"Modules IA non trouvés: {e}")
            await send_error(session_id, "Vérifiez que vous êtes dans le bon répertoire et que les modules existent")
            raise

        # Configuration RAG avec permissions
        chroma_db_path = "./chroma_db"
        if not os.path.exists(chroma_db_path):
            chroma_db_path = "../chroma_db"

        if not os.path.exists(chroma_db_path):
            await send_error(session_id, f"Base vectorielle non trouvée: {chroma_db_path}")
            raise FileNotFoundError(f"Chroma DB non trouvé: {chroma_db_path}")

        # Passer les permissions au RAG
        rag_index = RAGTableIndex(
            db_path=str(chroma_db_path)
        )

        await send_progress(session_id, f"Agents IA configurés pour rôle: {user_role}")

        #  CRÉATION CHATBOT AVEC VALIDATION
        try:
            chatbot = ChatbotMarocSessionId(
                rag_index,
                user_permissions=user_permissions,
                user_role=user_role
            )
            await send_log(session_id, f"Chatbot créé avec {len(user_permissions)} permissions", "INFO")
        except Exception as e:
            await send_error(session_id, f"Erreur création chatbot: {e}")
            raise

        await send_progress(session_id, f"Chatbot prêt - Accès niveau {user_role}")
        return chatbot

    except ImportError as e:
        await send_error(session_id, f"Module non trouvé: {e}")
        raise
    except Exception as e:
        await send_error(session_id, f"Erreur initialisation avec permissions: {e}")
        raise


async def process_question_with_permissions(chatbot, question: str, session_id: str,
                                            user_permissions: Optional[List[str]]):
    """
    Traite la question avec les agents en utilisant les permissions JWT - VERSION SÉCURISÉE
    """
    try:
        #  VALIDATION DES PARAMÈTRES
        if not question or not question.strip():
            await send_error(session_id, "Question vide reçue")
            raise ValueError("Question vide")

        if user_permissions is None:
            user_permissions = ["read_public_docs"]
            await send_log(session_id, "Permissions None lors du traitement, défaut appliqué", "WARNING")

        if not isinstance(user_permissions, list):
            user_permissions = ["read_public_docs"]
            await send_log(session_id, "Permissions non-liste lors du traitement, défaut appliqué", "WARNING")

        await send_progress(session_id, f"Traitement avec niveau d'accès pour: '{question[:50]}...'")

        #  VÉRIFICATION DE LA MÉTHODE DU CHATBOT
        if not hasattr(chatbot, 'poser_question_with_permissions'):
            await send_error(session_id, "Méthode 'poser_question_with_permissions' non trouvée dans le chatbot")
            raise AttributeError("Méthode chatbot manquante")

        # Capturer les sorties des agents
        captured_output = io.StringIO()

        with redirect_stdout(captured_output):
            try:
                response = chatbot.poser_question_with_permissions(
                    question,
                    session_id=session_id,
                    user_permissions=user_permissions
                )
            except TypeError as e:
                await send_error(session_id, f"Erreur paramètres chatbot: {e}")
                # Tentative avec paramètres simplifiés
                response = chatbot.poser_question_with_permissions(question, user_permissions)

        # Récupérer les logs capturés
        captured_text = captured_output.getvalue()
        if captured_text.strip():
            # Envoyer les logs capturés ligne par ligne via MCP
            for line in captured_text.strip().split('\n'):
                if line.strip():
                    await send_log(session_id, line.strip(), "INFO")

        await send_progress(session_id, "Génération de la réponse finale terminée")

        #  VALIDATION DE LA RÉPONSE
        if not response:
            await send_error(session_id, "Réponse vide générée par le chatbot")
            response = "Désolé, je n'ai pas pu générer une réponse appropriée."

        if not isinstance(response, str):
            response = str(response)

        return response

    except Exception as e:
        error_msg = f"Erreur traitement avec permissions: {str(e)}"
        await send_error(session_id, error_msg)
        await send_log(session_id, f"Traceback: {traceback.format_exc()}", "ERROR")
        raise


# ========================================
# VALIDATION DES ARGUMENTS JWT (IDENTIQUE)
# ========================================

def valider_arguments_jwt(args):
    """
    Valide les arguments JWT de manière robuste - VERSION SÉCURISÉE
    """
    if len(args) < 5:
        return {
            'error': True,
            'message': "Usage: python chatbot_wrapper.py <question> <session_id> <permissions> <role>"
        }

    try:
        user_message = args[1].strip() if args[1] else ""
        session_id = args[2].strip() if args[2] else ""
        user_permissions_str = args[3].strip() if args[3] else ""
        user_role = args[4].strip() if args[4] else ""

        # Validation de la question
        if not user_message or len(user_message) > 2000:
            return {'error': True, 'message': "Question invalide: vide ou trop longue"}

        # Validation du session_id
        if not session_id:
            return {'error': True, 'message': "Session ID invalide"}

        #  PARSING ROBUSTE DES PERMISSIONS JWT
        if user_permissions_str and user_permissions_str.lower() not in ['none', 'null', '']:
            try:
                user_permissions = [p.strip() for p in user_permissions_str.split(",") if p.strip()]
                if not user_permissions:  # Liste vide après nettoyage
                    user_permissions = ["read_public_docs"]
            except Exception:
                user_permissions = ["read_public_docs"]
        else:
            user_permissions = ["read_public_docs"]  # Défaut sécurisé

        #  VALIDATION ROBUSTE DU RÔLE JWT
        roles_valides = ['public', 'employee', 'admin']
        if not user_role or user_role.lower() not in roles_valides:
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
# FONCTION PRINCIPALE AVEC MCP CORRIGÉE
# ========================================

async def main_async():
    """Point d'entrée principal asynchrone du backend avec MCP - VERSION COMMUNICATION CORRIGÉE"""

    # Validation robuste des arguments JWT
    validation_result = valider_arguments_jwt(sys.argv)

    if validation_result['error']:
        error_response = {
            "success": False,
            "error": validation_result['message'],
            "backend": "enterprise_with_mcp_communication_fixed"
        }
        print(json.dumps(error_response, ensure_ascii=False))
        return False

    # Extraction des arguments validés
    user_message = validation_result['user_message']
    session_id = validation_result['session_id']
    user_permissions = validation_result['user_permissions']
    user_role = validation_result['user_role']

    original_dir = None

    print(f"[BACKEND] Démarré pour {user_role} - Session: {session_id}", file=sys.stderr)
    print(f"[BACKEND] Permissions: {user_permissions}", file=sys.stderr)
    print(f"[BACKEND] Communication: {'MCP' if MCP_AVAILABLE else 'HTTP Fallback'}", file=sys.stderr)

    try:
        # 1. Setup de l'environnement
        original_dir = setup_environment()

        #  TEST INITIAL DE COMMUNICATION MCP
        print(f"[BACKEND] Test initial communication MCP...", file=sys.stderr)
        test_success = await send_progress(session_id, f"Backend MCP initialisé pour {user_role}")
        if not test_success:
            print(f"[BACKEND]  Communication MCP échouée, utilisation fallback HTTP", file=sys.stderr)

        # 2. Initialisation du chatbot AVEC permissions JWT
        chatbot = await initialize_chatbot_with_permissions(session_id, user_permissions, user_role)

        # 3. Traitement de la question avec permissions JWT
        await send_progress(session_id, f"Traitement MCP avec niveau d'accès: {user_role}")
        response = await process_question_with_permissions(chatbot, user_message, session_id, user_permissions)

        # 4. Envoi de la réponse finale via MCP
        print(f"[BACKEND] Envoi réponse finale...", file=sys.stderr)
        final_success = await send_final(session_id, response)

        if final_success:
            print(f"[BACKEND]  Réponse finale envoyée avec succès", file=sys.stderr)
        else:
            print(f"[BACKEND]  Problème envoi réponse finale", file=sys.stderr)

        # 5. Succès
        result = {
            "success": True,
            "response": response,
            "session_id": session_id,
            "user_role": user_role,
            "permissions_used": user_permissions,
            "backend": "enterprise_with_mcp_communication_fixed",
            "communication": "MCP" if MCP_AVAILABLE else "HTTP_FALLBACK"
        }
        print(json.dumps(result, ensure_ascii=False))

        print(f"[BACKEND]  Traitement MCP terminé pour {user_role} - Session: {session_id}", file=sys.stderr)
        return True

    except Exception as e:
        # Gestion d'erreur globale
        error_msg = f"Erreur backend MCP: {str(e)}"
        await send_error(session_id, error_msg)

        # Log détaillé pour debugging
        print(f"[BACKEND]  Erreur complète: {traceback.format_exc()}", file=sys.stderr)

        error_result = {
            "success": False,
            "error": error_msg,
            "session_id": session_id,
            "user_role": user_role,
            "backend": "enterprise_with_mcp_communication_fixed"
        }
        print(json.dumps(error_result, ensure_ascii=False))

        return False

    finally:
        # Nettoyage
        if original_dir:
            try:
                os.chdir(original_dir)
            except Exception:
                pass


def main():
    """Point d'entrée synchrone qui lance la version asynchrone"""
    try:
        # Lancer la version asynchrone
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success = loop.run_until_complete(main_async())
        loop.close()

        if not success:
            sys.exit(1)

    except Exception as e:
        print(f"[BACKEND] Erreur critique: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
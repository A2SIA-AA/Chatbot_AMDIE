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
def __init__():
    pass

def setup_environment():
    """
    Configure l'environnement pour l'exécution du projet.

    Cette fonction charge les variables d'environnement à partir d'un fichier
    .env s'il est disponible. Elle ajuste le répertoire courant si le
    répertoire du projet est défini dans les variables d'environnement,
    et configure le système de logging pour des journaux d'informations 
    plus détaillés. Si une erreur se produit lors de la configuration, 
    un message d'erreur est affiché, et la valeur de retour sera ``None``.

    :return: Le chemin d'origine du répertoire courant avant tout changement 
             effectué par la fonction, ou ``None`` en cas d'erreur.
    :rtype: Optional[str]
    """
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
# COMMUNICATION MCP
# ========================================

# Variables globales pour MCP
MCP_BACKEND_URL = os.getenv("MCP_BACKEND_URL", "http://localhost:8090/mcp")
FALLBACK_FASTAPI_URL = os.getenv("FASTAPI_URL", "http://localhost:8000/api/v1/messages")


def setup_mcp_path():
    """
    Configure le chemin pour le module `mcp_client_utils`.

    Cette fonction cherche le fichier `mcp_client_utils.py` dans différents répertoires
    parents du répertoire actuel et, si trouvé, ajoute automatiquement son chemin
    au `sys.path` pour permettre son importation. Cela facilite le chargement d'un module
    qui peut ne pas être dans le chemin courant ou sur le chemin par défaut de Python.

    :raises FileNotFoundError: Si le fichier `mcp_client_utils.py` n'est pas trouvé
      dans les répertoires spécifiés ou dans l'emplacement défini en dur.

    :return: Un booléen indiquant si le fichier `mcp_client_utils.py` a été trouvé
       et le chemin correctement ajouté au `sys.path`.
    :rtype: bool
    """
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




async def send_progress(session_id: str, message: str) -> bool:
    """
    Cette fonction envoie un message de progression associé à une session donnée en utilisant
    le protocole MCP si disponible. Si MCP est indisponible ou que l'envoi échoue, un fallback
    via HTTP est utilisé.

    :param session_id: L'identifiant de la session associée au message.
    :type session_id: str
    :param message: Le message de progression à envoyer, limité à 50 caractères pour l'affichage.
    :type message: str
    :return: True si l'envoi a été un succès via MCP ou fallback HTTP, False sinon.
    :rtype: bool
    :raises Exception: Si une erreur inattendue survient durant l'envoi via MCP, qui mène
        ensuite au fallback HTTP.
    """
    # PROTECTION CONTRE None
    if message is None:
        message = "Progression: message None reçu"

    # PROTECTION POUR L'AFFICHAGE
    display_message = str(message)[:50] if message else "None"
    print(f"[WRAPPER] send_progress appelé: {session_id} - {display_message}...", file=sys.stderr)

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
    """
    Envoie un message final à une session donnée en utilisant MCP si disponible, sinon
    utilise un système de repli basé sur HTTP. Cette fonction gère les erreurs et
    les exceptions pour assurer une méthode d'envoi fiable.

    :param session_id: Identifiant unique de la session.
    :type session_id: str
    :param message: Message à envoyer, limité à 50 caractères pour l'affichage.
    :type message: str
    :return: Retourne True si l'envoi a réussi, False sinon.
    :rtype: bool
    :raises Exception: Si une erreur est rencontrée lors de la tentative d'envoi via MCP.
    """
    # PROTECTION CONTRE None
    if message is None:
        message = "Erreur: Réponse générée est None"

    # PROTECTION POUR L'AFFICHAGE
    display_message = str(message)[:50] if message else "None"
    print(f"[WRAPPER] send_final appelé: {session_id} - {display_message}...", file=sys.stderr)

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
    """
    Envoie un message d'erreur pour une session donnée. Cette fonction utilise le service MCP, et en cas 
    d'indisponibilité ou d'échec de MCP, elle effectue un fallback HTTP pour transmettre l'erreur.

    :param session_id: L'identifiant de session pour laquelle envoyer le message d'erreur.
    :type session_id: str
    :param error: Le message d'erreur à transmettre.
    :type error: str
    :return: Renvoie True si l'envoi réussit (via MCP ou fallback HTTP), sinon False.
    :rtype: bool
    :raises Exception: Exception levée si une erreur survient durant le processus MCP.
    """
    # PROTECTION CONTRE None
    if error is None:
        error = "Erreur: message d'erreur None"

    # PROTECTION POUR L'AFFICHAGE
    display_error = str(error)[:50] if error else "None"
    print(f"[WRAPPER] send_error appelé: {session_id} - {display_error}...", file=sys.stderr)

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
    """
    Envoie un message de log à un service MCP ou à stderr si MCP n'est pas
    disponible. Cette fonction permet de journaliser les messages d'une session
    avec un certain niveau de gravité.

    :param session_id: Identifiant unique de la session.
    :type session_id: str
    :param log_message: Message à enregistrer dans les logs.
    :type log_message: str
    :param log_level: Niveau de gravité du log (par défaut : "INFO").
    :type log_level: str
    :return: True si le message a été enregistré avec succès, False en cas 
             d’échec.
    :rtype: bool
    """
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
    Envoie un message via une méthode de repli HTTP (fallback) à une URL spécifiée. 

    Cette fonction utilise une requête HTTP POST pour transmettre un message 
    spécifié avec un type et un contenu donnés, ainsi qu'un identifiant de session. 
    Elle permet de gérer des alternatives de communication via une configuration 
    de secours HTTP. Les données incluent également des métadonnées ajoutées pour le 
    suivi et l'identification de la source.

    :param session_id: Identifiant unique de la session.
    :type session_id: str
    :param message_type: Type du message qui est transmis (par exemple "texte" ou "notification").
    :type message_type: str
    :param content: Contenu du message qui doit être envoyé.
    :type content: str

    :return: Un booléen qui indique si l'envoi via HTTP fallback a réussi.
    :rtype: bool
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
# INTÉGRATION AVEC LES AGENTS ET JWT 
# ========================================

async def initialize_chatbot_with_permissions(session_id: str, user_permissions: Optional[List[str]], user_role: str):
    """
    Initialise un chatbot avec les permissions utilisateur, en validant les entrées et configurant 
    les modules nécessaires pour permettre une interaction basée sur le rôle et les autorisations.

    :param session_id: Identifiant unique de session.
    :type session_id: str
    :param user_permissions: Liste des permissions utilisateur associées à la session. Si aucune 
        valeur n'est fournie ou si elle est invalide, une valeur par défaut sera utilisée.
    :type user_permissions: List[str], optional
    :param user_role: Rôle utilisateur spécifié, parmi les options suivantes: 'public', 'employee', 
        ou 'admin'. Si le rôle fourni est invalide ou manquant, une valeur par défaut sera attribuée.
    :type user_role: str
    :return: Une instance de Chatbot configurée selon les permissions et rôle utilisateur.
    :rtype: ChatbotMarocV2Simplified
    :raises FileNotFoundError: Si la base vectorielle (Chroma DB) ne peut pas être localisée.
    :raises ImportError: Si les modules requis pour l'IA ne sont pas trouvés dans le projet.
    :raises Exception: Pour toute erreur non spécifiée qui survient durant l'initialisation du 
        chatbot.
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

        #  IMPORT DES MODULES
        try:
            from src.core.chatbot_v2_simplified import ChatbotMarocV2Simplified as ChatbotMarocSessionId
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
                                            user_permissions: Optional[List[str]],
                                            username: str = None, email: str = None):
    """
    Traite une question en utilisant les permissions utilisateur et un historique 
    associé. Cette fonction permet une gestion adaptative des entrées manquantes 
    et fait appel à la méthode `poser_question_with_permissions` du chatbot 
    fourni.

    :param chatbot: Instance de chatbot, contenant la méthode 
        `poser_question_with_permissions`.
    :type chatbot: objet
    :param question: Question textuelle à traiter.
    :type question: str
    :param session_id: Identifiant unique de session utilisé pour le suivi et les 
        logs.
    :type session_id: str
    :param user_permissions: Liste optionnelle des permissions utilisateur qui 
        déterminent les autorisations disponibles. Si elle est `None`, une valeur 
        par défaut de `["read_public_docs"]` sera appliquée.
    :type user_permissions: Optional[List[str]]
    :param username: Nom d'utilisateur facultatif associé à la requête. Si absent, 
        un nom par défaut sera généré basé sur l'identifiant de session.
    :type username: str, optional
    :param email: Adresse email facultative de l'utilisateur. Si absente, une valeur 
        par défaut sera construite à partir du nom d'utilisateur.
    :type email: str, optional
    :return: Réponse textuelle générée par le chatbot en fonction des données et 
        permissions fournies.
    :rtype: str

    :raises ValueError: Si la question est vide ou invalide.
    :raises AttributeError: Si le chatbot ne contient pas la méthode 
        `poser_question_with_permissions`.
    :raises Exception: Pour toute autre erreur non prévue durant le traitement de 
        la question ou l'exécution de la méthode du chatbot.
    """
    try:
        # VALIDATION DES PARAMÈTRES
        if not question or not question.strip():
            await send_error(session_id, "Question vide reçue")
            raise ValueError("Question vide")

        if user_permissions is None:
            user_permissions = ["read_public_docs"]
            await send_log(session_id, "Permissions None lors du traitement, défaut appliqué", "WARNING")

        if not isinstance(user_permissions, list):
            user_permissions = ["read_public_docs"]
            await send_log(session_id, "Permissions non-liste lors du traitement, défaut appliqué", "WARNING")

        # VALIDATION HISTORIQUE UTILISATEUR
        if not username:
            username = f"user_{session_id[:8]}"
            await send_log(session_id, f"Username manquant, défaut: {username}", "WARNING")

        if not email:
            email = f"{username}@amdie.ma"
            await send_log(session_id, f"Email manquant, défaut: {email}", "WARNING")

        await send_progress(session_id, f"Traitement avec historique pour {username} (niveau: {user_permissions})")

        # VÉRIFICATION DE LA MÉTHODE DU CHATBOT
        if not hasattr(chatbot, 'poser_question_with_permissions'):
            await send_error(session_id, "Méthode 'poser_question_with_permissions' non trouvée dans le chatbot")
            raise AttributeError("Méthode chatbot manquante")

        # Capturer les sorties des agents
        captured_output = io.StringIO()

        with redirect_stdout(captured_output):
            try:
                # APPEL AVEC HISTORIQUE UTILISATEUR

                print(f"[ERROR TRACE] question type: {type(question)}", file=sys.stderr)
                print(f"[ERROR TRACE] user_permissions type: {type(user_permissions)}, value: {user_permissions}",file=sys.stderr)

                print(f"[ERROR TRACE] Avant appel chatbot", file=sys.stderr)

                response = chatbot.poser_question_with_permissions(
                    question,
                    session_id=session_id,
                    user_permissions=user_permissions,
                    username=username,  # NOUVEAU
                    email=email  # NOUVEAU
                )

                print(f"[ERROR TRACE] Après appel chatbot, response type: {type(response)}", file=sys.stderr)


            except TypeError as e:
                await send_error(session_id, f"Erreur paramètres chatbot: {e}")
                # Tentative avec paramètres simplifiés (sans historique)
                response = chatbot.poser_question_with_permissions(question, session_id, user_permissions)

        # Récupérer les logs capturés 
        captured_text = captured_output.getvalue()
        if captured_text.strip():
            for line in captured_text.strip().split('\n'):
                if line.strip():
                    await send_log(session_id, line.strip(), "INFO")

        await send_progress(session_id, f"Réponse générée avec historique pour {username}")

        # VALIDATION DE LA RÉPONSE
        if not response:
            await send_error(session_id, "Réponse vide générée par le chatbot")
            response = "Désolé, je n'ai pas pu générer une réponse appropriée."

        if not isinstance(response, str):
            response = str(response)

        return response

    except Exception as e:
        error_msg = f"Erreur traitement avec permissions + historique: {str(e)}"
        await send_error(session_id, error_msg)
        await send_log(session_id, f"Traceback: {traceback.format_exc()}", "ERROR")
        raise


# ========================================
# VALIDATION DES ARGUMENTS JWT (IDENTIQUE)
# ========================================

def valider_arguments_jwt(args):
    """
    Valide les arguments fournis pour JWT et structure les données en fonction des paramètres
    saisis. Cette fonction assure la robustesse de la validation et structure également les 
    permissions, rôles et données associés à l'utilisateur, tels que le nom d'utilisateur et
    l'email.

    La méthode accepte les paramètres transmis dans une liste d'arguments et renvoie un 
    dictionnaire contenant des informations validées ainsi qu'un indicateur d'erreur en
    cas d'échec.

    Sections du traitement:
    - Validation et extraction de la question utilisateur.
    - Validation de l'identifiant de session (`session_id`).
    - Parsing et validation des permissions associées à l'utilisateur.
    - Validation et résolution du rôle utilisateur.
    - Gestion des cas où le nom d'utilisateur ou l'email ne sont pas valides ou manquent.

    :param args: Liste des arguments. Elle doit inclure au minimum les informations suivantes
        (dans cet ordre): la question utilisateur (`<question>`), l'identifiant de session
        (`<session_id>`), les permissions utilisateur (`<permissions>`), le rôle utilisateur
        (`<role>`), le nom de l'utilisateur (`<username>`) et l'email (`<email>`).
    :type args: list

    :return: Dictionnaire contenant les informations validées ou un message d'erreur.
    :rtype: dict
    """
    if len(args) < 7: 
        return {
            'error': True,
            'message': "Usage: python chatbot_wrapper.py <question> <session_id> <permissions> <role> <username> <email>"
        }

    try:
        user_message = args[1].strip() if args[1] else ""
        session_id = args[2].strip() if args[2] else ""
        user_permissions_str = args[3].strip() if args[3] else ""
        user_role = args[4].strip() if args[4] else ""
        username = args[5].strip() if len(args) > 5 and args[5] else "unknown_user"  # NOUVEAU
        email = args[6].strip() if len(args) > 6 and args[6] else "unknown@amdie.ma"  # NOUVEAU

        # Validation de la question
        if not user_message or len(user_message) > 2000:
            return {'error': True, 'message': "Question invalide: vide ou trop longue"}

        # Validation du session_id
        if not session_id:
            return {'error': True, 'message': "Session ID invalide"}

        # PARSING ROBUSTE DES PERMISSIONS JWT
        if user_permissions_str and user_permissions_str.lower() not in ['none', 'null', '']:
            try:
                user_permissions = [p.strip() for p in user_permissions_str.split(",") if p.strip()]
                if not user_permissions:
                    user_permissions = ["read_public_docs"]
            except Exception:
                user_permissions = ["read_public_docs"]
        else:
            user_permissions = ["read_public_docs"]

        # VALIDATION ROBUSTE DU RÔLE JWT
        roles_valides = ['public', 'employee', 'admin']
        if not user_role or user_role.lower() not in roles_valides:
            print(f"Rôle '{user_role}' non reconnu, défaut à 'public'", file=sys.stderr)
            user_role = 'public'

        # VALIDATION USERNAME/EMAIL POUR HISTORIQUE
        if not username or username.lower() in ['none', 'null', '']:
            username = f"user_{session_id[:8]}"  # Fallback basé sur session

        if not email or email.lower() in ['none', 'null', ''] or '@' not in email:
            email = f"{username}@amdie.ma"  # Fallback email

        return {
            'error': False,
            'user_message': user_message,
            'session_id': session_id,
            'user_permissions': user_permissions,
            'user_role': user_role.lower(),
            'username': username,  # NOUVEAU
            'email': email  # NOUVEAU
        }

    except Exception as e:
        return {'error': True, 'message': f"Erreur validation arguments: {e}"}


# ========================================
# FONCTION PRINCIPALE AVEC MCP
# ========================================


async def main_async():
    """
    Fonction asynchrone principale qui orchestre le traitement backend avec gestion des permissions, 
    historique utilisateur, et communication via MCP ou fallback HTTP. Valide les arguments JWT, 
    initialise les composants nécessaires comme le chatbot avec permissions, traite les messages 
    en tenant compte de l'historique, et gère la communication des réponses progressives et finales.

    La fonction inclut également une gestion robuste des erreurs et un nettoyage de l'environnement 
    systématique en cas d'exception.

    :return: Un booléen indiquant le succès ou l'échec du traitement global
    :rtype: bool

    :raises Exception: En cas d'erreur inattendue pendant l'exécution
    """

    # Validation robuste des arguments JWT + historique
    validation_result = valider_arguments_jwt(sys.argv)

    if validation_result['error']:
        error_response = {
            "success": False,
            "error": validation_result['message'],
            "backend": "backend_with_mcp_and_history"
        }
        print(json.dumps(error_response, ensure_ascii=False))
        return False

    # Extraction des arguments validés
    user_message = validation_result['user_message']
    session_id = validation_result['session_id']
    user_permissions = validation_result['user_permissions']
    user_role = validation_result['user_role']
    username = validation_result['username']
    email = validation_result['email'] 

    original_dir = None

    print(f"[BACKEND] Démarré pour {user_role} - User: {username} - Session: {session_id}", file=sys.stderr)
    print(f"[BACKEND] Permissions: {user_permissions}", file=sys.stderr)
    print(f"[BACKEND] Historique: {username} ({email})", file=sys.stderr)
    print(f"[BACKEND] Communication: {'MCP' if MCP_AVAILABLE else 'HTTP Fallback'}", file=sys.stderr)

    try:
        # 1. Setup de l'environnement
        original_dir = setup_environment()

        # TEST INITIAL DE COMMUNICATION MCP
        print(f"[BACKEND] Test initial communication MCP...", file=sys.stderr)
        test_success = await send_progress(session_id, f"Backend MCP initialisé pour {username} ({user_role})")
        if not test_success:
            print(f"[BACKEND] Communication MCP échouée, utilisation fallback HTTP", file=sys.stderr)

        # 2. Initialisation du chatbot AVEC permissions JWT
        chatbot = await initialize_chatbot_with_permissions(session_id, user_permissions, user_role)

        # 3. Traitement de la question avec permissions JWT + HISTORIQUE
        await send_progress(session_id, f"Traitement avec historique pour {username}")
        response = await process_question_with_permissions(
            chatbot,
            user_message,
            session_id,
            user_permissions,
            username, 
            email 
        )

        # 4. Envoi de la réponse finale via MCP
        print(f"[BACKEND] Envoi réponse finale...", file=sys.stderr)
        final_success = await send_final(session_id, response)

        if final_success:
            print(f"[BACKEND] Réponse finale envoyée avec succès", file=sys.stderr)
        else:
            print(f"[BACKEND] Problème envoi réponse finale", file=sys.stderr)

        # 5. Succès avec infos utilisateur
        result = {
            "success": True,
            "response": response,
            "session_id": session_id,
            "user_role": user_role,
            "username": username, 
            "email": email,  
            "permissions_used": user_permissions,
            "backend": "backend_with_mcp_and_history",
            "communication": "MCP" if MCP_AVAILABLE else "HTTP_FALLBACK"
        }
        print(json.dumps(result, ensure_ascii=False))

        print(f"[BACKEND] Traitement MCP terminé pour {username} ({user_role}) - Session: {session_id}", file=sys.stderr)
        return True

    except Exception as e:
        # Gestion d'erreur globale
        error_msg = f"Erreur backend MCP + historique: {str(e)}"
        await send_error(session_id, error_msg)

        # Log détaillé pour debugging
        print(f"[BACKEND] Erreur complète: {traceback.format_exc()}", file=sys.stderr)

        error_result = {
            "success": False,
            "error": error_msg,
            "session_id": session_id,
            "user_role": user_role,
            "username": username,  
            "email": email,  
            "backend": "backend_with_mcp_and_history"
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
    """
    Lance le programme principal. Cette fonction initialise une boucle événementielle
    asynchrone, exécute la fonction principale asynchrone et gère les exceptions
    critiques, le cas échéant.

    :raises Exception: Si une erreur critique survient lors de l'exécution du code
        asynchrone ou de la configuration de la boucle.
    :return: Aucun
    """
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
# mcp_backend_server.py
import os, sys, asyncio, signal
import time
from typing import Dict, Any

from fastmcp import FastMCP

mcp = FastMCP("AMDIE-Backend-MCP")

# --------- CONFIG ----------
PROJECT_DIR = os.getenv("PROJECT_DIR", "/home/aissa/Bureau/Projet_Chatbot/Chatbot_AMDIE/chatbot_maroc/backend_python")
WRAPPER_PATH = os.getenv("WRAPPER_PATH", "chatbot_wrapper.py")
FASTAPI_URL = os.getenv("FASTAPI_URL", "http://localhost:8000")

if not PROJECT_DIR or not os.path.isabs(PROJECT_DIR):
    raise RuntimeError("PROJECT_DIR doit être défini et ABSOLU (export PROJECT_DIR=/chemin/absolu)")

# --------- STATE ----------
PROCS: Dict[str, asyncio.subprocess.Process] = {}

# --------- IMPORT MESSAGE STORE AVEC DEBUG APPROFONDI ----------
print(f"[MCP] Tentative d'import message_store...")
print(f"[MCP] Répertoire actuel: {os.getcwd()}")


# Trouver automatiquement le chemin vers message_fastapi
def find_message_fastapi_path():
    """
    Recherche le chemin du dossier contenant le module `message_fastapi`. Cette fonction vérifie
    plusieurs chemins possibles relatifs au répertoire actuel, ainsi qu'un chemin absolu de secours.
    Elle teste l'existence d'un fichier nommé `message_store.py` à l'intérieur du répertoire trouvé
    pour valider le bon emplacement.

    :rtype: Optional[str]
    :return: Le chemin absolu du dossier contenant `message_store.py` si trouvé, sinon None.
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))

    # Chemins possibles relatifs au fichier actuel
    possible_paths = [
        os.path.join(current_dir, '..', 'message_fastapi'),  # ../message_fastapi
        os.path.join(current_dir, '..', '..', 'message_fastapi'),  # ../../message_fastapi
        os.path.join(current_dir, 'message_fastapi'),  # ./message_fastapi
        '/home/aissa/Bureau/Projet_Chatbot/Chatbot_AMDIE/chatbot_maroc/message_fastapi',  # Chemin absolu de secours
    ]

    for path in possible_paths:
        abs_path = os.path.abspath(path)
        message_store_file = os.path.join(abs_path, 'message_store.py')

        print(f"[MCP] Test chemin: {abs_path}")
        print(f"[MCP]   - Existe: {os.path.exists(abs_path)}")
        print(f"[MCP]   - message_store.py: {os.path.exists(message_store_file)}")

        if os.path.exists(message_store_file):
            print(f"[MCP]  Chemin trouvé: {abs_path}")
            return abs_path

    return None


# Chercher le chemin
message_fastapi_path = find_message_fastapi_path()

if message_fastapi_path:
    if message_fastapi_path not in sys.path:
        sys.path.insert(0, message_fastapi_path)
    print(f"[MCP] sys.path étendu avec: {message_fastapi_path}")

    try:
        #  IMPORT AVEC DEBUG DÉTAILLÉ
        print(f"[MCP] Import du module message_store...")
        import message_store as ms_module

        print(f"[MCP] Module importé: {ms_module}")
        print(f"[MCP] Fichier module: {ms_module.__file__}")

        # Lister les attributs pour debug
        print(f"[MCP] Attributs du module: {[attr for attr in dir(ms_module) if not attr.startswith('_')]}")

        #  IMPORT DE L'INSTANCE
        print(f"[MCP] Import de l'instance message_store...")
        from message_store import message_store

        print(f"[MCP] Instance importée: {message_store}")
        print(f"[MCP] Type de l'instance: {type(message_store)}")

        # Vérifier les méthodes essentielles
        essential_methods = ['add_message', 'get_messages', 'get_all_sessions', 'clear_session']
        missing_methods = []

        for method in essential_methods:
            if hasattr(message_store, method):
                print(f"[MCP]  Méthode {method} disponible")
            else:
                missing_methods.append(method)
                print(f"[MCP]  Méthode {method} manquante")

        if missing_methods:
            raise RuntimeError(f"Méthodes manquantes: {missing_methods}")

        FASTAPI_MESSAGE_STORE_AVAILABLE = True
        print(f"[MCP]  Message store FastAPI importé avec succès")

    except ImportError as e:
        print(f"[MCP]  Erreur import: {e}")
        FASTAPI_MESSAGE_STORE_AVAILABLE = False
        message_store = None
        import traceback

        traceback.print_exc()

else:
    print(f"[MCP]  Aucun chemin valide trouvé pour message_fastapi")
    FASTAPI_MESSAGE_STORE_AVAILABLE = False
    message_store = None


# --------- HELPER FUNCTIONS (LOGIQUE MÉTIER) ----------
async def _spawn_wrapper(question: str, session_id: str, permissions_csv: str, role: str, username: str, email: str) -> Dict[str, Any]:
    """
    Exécute un processus asynchrone permettant de gérer une session avec un wrapper Python.

    Cette fonction vérifie d'abord si un processus est déjà en cours d'exécution pour l'identifiant
    de session donné. Si tel est le cas, une erreur est retournée. Sinon, un nouveau processus est
    lancé en utilisant les paramètres fournis. La gestion des flux stdout et stderr se fait de façon
    asynchrone pour permettre le suivi des journaux en temps réel.

    :param question: Question ou requête à exécuter via le wrapper.
    :type question: str
    :param session_id: Identifiant unique pour la session.
    :type session_id: str
    :param permissions_csv: Liste des permissions au format CSV.
    :type permissions_csv: str
    :param role: Rôle de l'utilisateur dans le contexte de la session.
    :type role: str
    :param username: Nom d'utilisateur associé au processus.
    :type username: str
    :param email: Adresse e-mail de l'utilisateur.
    :type email: str
    :return: Dictionnaire contenant l'état de l'opération (`ok` pour indiquer un succès ou `error` pour signaler une erreur).
    :rtype: Dict[str, Any]
    """
    if session_id in PROCS and PROCS[session_id].returncode is None:
        return {"ok": False, "error": f"Session déjà en cours: {session_id}"}

    py = sys.executable
    cmd = [
        py,
        os.path.join(PROJECT_DIR, WRAPPER_PATH),
        question,
        session_id,
        permissions_csv,
        role,
        username,
        email
    ]
    env = os.environ.copy()
    env["MCP_BACKEND_URL"] = "http://localhost:8090/mcp"
    env["FASTAPI_URL"] = f"{FASTAPI_URL.rstrip('/')}/api/v1/messages"

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=PROJECT_DIR,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    PROCS[session_id] = proc

    # lecture asynchrone pour logs
    async def _drain(name, stream):
        """
        Lit de manière asynchrone une ligne d'un flux donné en boucle, jusqu'à ce que le flux soit terminé.
        Chaque ligne est décodée et affichée dans un format spécifique. Les exceptions éventuelles
        sont silencieusement ignorées.

        :param name: Nom associé au flux courant.
        :type name: str
        :param stream: Flux asynchrone dont les lignes seront lues.
        :type stream: asyncio.StreamReader
        """
        try:
            while True:
                line = await stream.readline()
                if not line:
                    break
                print(f"[{session_id}][{name}] {line.decode(errors='ignore').rstrip()}")
        except Exception:
            pass

    asyncio.create_task(_drain("STDERR", proc.stderr))
    asyncio.create_task(_drain("STDOUT", proc.stdout))

    return {"ok": True, "pid": proc.pid}


async def _cancel_session(session_id: str) -> Dict[str, Any]:
    """
    Annule une session en cours en envoyant un signal au processus associé. Si le
    processus ne termine pas dans un délai spécifié, il sera forcé à se terminer.

    :param session_id: L’identifiant de la session à annuler.
    :type session_id: str
    :return: Un dictionnaire indiquant le résultat de l'annulation avec une clé
             `ok` pour le succès de l'opération, et une clé `error` le cas
             échéant.
    :rtype: Dict[str, Any]
    """
    proc = PROCS.get(session_id)
    if not proc or proc.returncode is not None:
        return {"ok": False, "error": "Aucun process actif pour cette session"}

    try:
        proc.send_signal(signal.SIGTERM)
        try:
            await asyncio.wait_for(proc.wait(), timeout=5)
        except asyncio.TimeoutError:
            proc.kill()
        return {"ok": True}
    finally:
        PROCS.pop(session_id, None)


#  FONCTION HELPER AVEC DEBUG MAXIMUM
async def _send_message_helper(session_id: str, message_type: str, content: str, metadata: Dict[str, Any] = None) -> \
Dict[str, Any]:
    """
    Cette fonction auxiliaire asynchrone envoie un message au système MessageStore si celui-ci est activé
    et disponible. Elle construit un message avec les données fournies, l'envoie via le
    message_store, et retourne le résultat de l'opération. La fonction assure également
    une gestion d'erreur minimale et consigne des informations essentielles dans la console.

    :param session_id: Identifiant de session pour lequel le message doit être envoyé
    :type session_id: str
    :param message_type: Type ou catégorie du message à envoyer
    :type message_type: str
    :param content: Contenu principal du message
    :type content: str
    :param metadata: Métadonnées associées au message; par défaut, inclut un horodatage et
        une indication de source
    :type metadata: dict
    :return: Un dictionnaire contenant les résultats de l'envoi du message. La clé "ok" indique si
        l'opération a réussi ou échoué, et des détails sont inclus en cas d'erreur ou de succès.
    :rtype: dict
    """

    try:
        # Juste log essentiel en cas d'erreur
        if not FASTAPI_MESSAGE_STORE_AVAILABLE or not message_store:
            print(f"[MCP] MessageStore non disponible", file=sys.stderr)
            return {"ok": False, "error": "MessageStore non disponible"}

        # Construction du message
        message_data = {
            'type': message_type,
            'content': content,
            'metadata': metadata or {'timestamp': time.time(), 'source': 'backend_via_mcp'}
        }

        # Ajout du message SANS tous les logs de debug
        result = await message_store.add_message(session_id, message_data)

        # Log minimal de succès
        print(f"[MCP] {message_type} envoyé pour {session_id}", file=sys.stderr)

        return {"ok": True, "message": f"Message {message_type} envoyé avec succès", "session_id": session_id}

    except Exception as e:
        print(f"[MCP ERROR] {session_id}: {e}", file=sys.stderr)
        return {"ok": False, "error": str(e)}


# --------- TOOLS ORIGINAUX ----------
@mcp.tool
async def start_backend(question: str, session_id: str, permissions_csv: str, role: str, username: str, email: str) -> Dict[str, Any]:
    """
    Appelle une fonction asynchrone pour initialiser le backend tout en transmettant plusieurs
    paramètres pour configurer la session.

    Ce processus inclut la génération d'une session basée sur l'identifiant fourni et le contrôle
    de certains paramètres comme les permissions, le rôle de l'utilisateur, ainsi que des informations
    importantes telles que l'email et l'identifiant utilisateur.

    :param question: Question ou requête liée à la session à traiter.
    :type question: str
    :param session_id: Identifiant unique de la session pour le backend.
    :type session_id: str
    :param permissions_csv: Chaîne de permissions formatée en CSV pour définir les droits.
    :type permissions_csv: str
    :param role: Rôle attribué à l'utilisateur actuel durant la session.
    :type role: str
    :param username: Nom d'utilisateur associé à la session.
    :type username: str
    :param email: Adresse email associée à l'utilisateur participant à la session.
    :type email: str
    :return: Un dictionnaire contenant les détails et le statut de la session ou des données pertinentes.
    :rtype: Dict[str, Any]
    """
    print(f"[MCP] start_backend session={session_id} role={role}")
    return await _spawn_wrapper(question, session_id, permissions_csv, role, username, email)


@mcp.tool
async def cancel_session(session_id: str) -> Dict[str, Any]:
    """
    Arrête proprement le process backend associé à la session.
    """
    print(f"[MCP] cancel_session session={session_id}")
    return await _cancel_session(session_id)


@mcp.tool
async def health() -> Dict[str, Any]:
    """
    Effectue une vérification de santé de l'application en rassemblant des informations
    pertinentes sur l'état actuel du système et du magasin de messages.

    Récupère différents détails tels que le statut du système, les chemins de répertoires
    et fichiers importants, les sessions actives et des informations sur le magasin de
    messages (s'il est disponible). Si le magasin de messages est opérationnel, il exécute
    également un test rapide pour évaluer son bon fonctionnement et inclut les résultats
    dans les informations retournées.

    :return: Un dictionnaire contenant des informations détaillées sur l'état de santé
             de l'application.
    :rtype: Dict[str, Any]
    """
    # Ajouter info détaillée sur le message store
    health_info = {
        "status": "ok",
        "project_dir": PROJECT_DIR,
        "wrapper": WRAPPER_PATH,
        "fastapi_url": FASTAPI_URL,
        "active_sessions": [sid for sid, p in PROCS.items() if p.returncode is None],
        "message_store_available": FASTAPI_MESSAGE_STORE_AVAILABLE,
        "message_store_type": type(message_store).__name__ if message_store else "None",
        "message_store_path": message_fastapi_path,
    }

    # Test rapide du message store si disponible
    if FASTAPI_MESSAGE_STORE_AVAILABLE and message_store:
        try:
            test_sessions = await message_store.get_all_sessions()
            health_info["fastapi_sessions_count"] = len(test_sessions)
            health_info["fastapi_sessions"] = test_sessions
        except Exception as e:
            health_info["message_store_error"] = str(e)

    return health_info


# --------- TOOLS DE COMMUNICATION (UTILISENT LES HELPERS) ----------
@mcp.tool
async def send_message(session_id: str, message_type: str, content: str, metadata: Dict[str, Any] = None) -> Dict[
    str, Any]:
    """
    Envoie un message via une session donnée en spécifiant le type de message, le contenu
    et des métadonnées optionnelles.

    :param session_id: Identifiant unique de la session dans laquelle le message doit
        être envoyé.
    :type session_id: str
    :param message_type: Type de message à envoyer (ex.: "texte", "image").
    :type message_type: str
    :param content: Contenu du message à envoyer. Il peut s'agir de texte ou d'autres
        types de contenu en fonction du type de message.
    :type content: str
    :param metadata: Métadonnées optionnelles accompagnant le message, sous forme
        d'un dictionnaire.
    :type metadata: Dict[str, Any], optionnel
    :return: Un dictionnaire contenant les informations ou résultats relatifs à l'action de l'envoi du message.
    :rtype: Dict[str, Any]
    """
    return await _send_message_helper(session_id, message_type, content, metadata)


@mcp.tool
async def send_progress(session_id: str, message: str) -> Dict[str, Any]:
    """
    Envoie un message de progression asynchrone à l'aide d'un outil interne.

    Cette fonction utilise `_send_message_helper` pour formater et envoyer un
    message de progression spécifique à une session donnée. Elle est conçue pour
    être utilisée dans des environnements de programmation asynchrone.

    :param session_id: Identifiant unique de la session. Utilisé pour lier
        le message de progression à une session spécifique.
    :type session_id: str
    :param message: Texte du message contenant les détails de la progression
        à transmettre.
    :type message: str
    :return: Un dictionnaire contenant la réponse du message envoyé.
    :rtype: Dict[str, Any]
    """
    return await _send_message_helper(session_id, 'progress', message)


@mcp.tool
async def send_final(session_id: str, response: str) -> Dict[str, Any]:
    """
    Envoie le message final à une session spécifique.

    Cette fonction envoie une réponse finale à une session donnée, identifiée à l'aide
    de son identifiant de session (`session_id`). Elle s'appuie sur un assistant pour
    l'envoi du message. Elle est asynchrone et retourne un dictionnaire contenant des
    informations sur l'état de l'envoi.

    :param session_id: Identifiant unique de la session à laquelle le message final
                       doit être envoyé.
    :type session_id: str
    :param response: Message final à envoyer à la session. Ce message représente la
                     réponse à transmettre.
    :type response: str
    :return: Un dictionnaire contenant des informations sur l'état de l'envoi du
             message.
    :rtype: Dict[str, Any]
    """
    return await _send_message_helper(session_id, 'final', response)


@mcp.tool
async def send_error(session_id: str, error: str) -> Dict[str, Any]:
    """
    Envoie un message d'erreur avec le contenu spécifié pour une session donnée.

    Un assistant asynchrone permettant d'envoyer une notification d'erreur
    dans une session particulière en utilisant une structure pré-définie.

    :param session_id: L'identifiant unique de la session où le message d'erreur
        doit être envoyé.
    :param error: Le message d'erreur à envoyer, sous forme de chaîne de caractères.
    :return: Un dictionnaire contenant la réponse asynchrone liée à
        l'envoi du message d'erreur. La structure du contenu inclut tous
        les détails confirmant ou contextualisant l'envoi.
    """
    return await _send_message_helper(session_id, 'error', f"ERREUR: {error}")


@mcp.tool
async def send_log(session_id: str, log_message: str, log_level: str = "INFO") -> Dict[str, Any]:
    """
    Envoie un message de journalisation avec le niveau spécifié via MCP.

    Résumé détaillé :
    Cette fonction permet d'envoyer un message de journalisation (log) associé à une session donnée.
    Elle inclut un niveau de journalisation (par exemple, INFO, WARNING, ERROR) et un message
    défini par l'utilisateur. La fonction construit également des métadonnées contenant le
    niveau de journalisation, un horodatage généré à l'exécution et une source par défaut pour
    indiquée comme « backend_log_via_mcp ». Le message est envoyé de manière asynchrone avec l'aide
    d'un assistant interne.

    :param session_id: Identifiant unique de la session liée à l'envoi du log.
    :type session_id: str
    :param log_message: Message de journalisation à envoyer.
    :type log_message: str
    :param log_level: Niveau de journalisation à appliquer au message (par défaut « INFO »).
    :type log_level: str, optionnel
    :return: Le résultat de l'appel asynchrone à l’assistant d'envoi du message.
    :rtype: Dict[str, Any]
    """
    metadata = {
        'log_level': log_level,
        'timestamp': asyncio.get_event_loop().time(),
        'source': 'backend_log_via_mcp'
    }

    return await _send_message_helper(session_id, 'progress', log_message, metadata)


# --------- TOOLS DE DEBUG ----------
@mcp.tool
async def list_active_sessions() -> Dict[str, Any]:
    """
    Retourne une liste des sessions actives ainsi que des détails sur leur état.

    Cette fonction collecte les informations concernant les sessions actives
    gérées par le processus MCP ainsi que, si disponible, les sessions actives
    de FastAPI. Chaque session est accompagnée de son identifiant unique (session_id),
    de son PID, de son état actuel ("running" ou "finished") et éventuellement d'autres
    détails comme le code de retour pour les processus terminés. Si l'intégration
    FastAPI est fonctionnelle, les sessions de FastAPI et les éventuelles erreurs
    seront également incluses dans le résultat.

    :return: Dictionnaire contenant les détails des sessions actives ainsi que les
        statistiques associées, comme le nombre total de sessions MCP et/ou FastAPI.
    :rtype: Dict[str, Any]
    """
    active_sessions = []
    for session_id, proc in PROCS.items():
        if proc.returncode is None:
            active_sessions.append({
                "session_id": session_id,
                "pid": proc.pid,
                "status": "running"
            })
        else:
            active_sessions.append({
                "session_id": session_id,
                "pid": proc.pid,
                "status": "finished",
                "return_code": proc.returncode
            })

    # Ajouter info FastAPI si disponible
    result = {
        "ok": True,
        "mcp_active_sessions": active_sessions,
        "mcp_total_count": len(active_sessions)
    }

    if FASTAPI_MESSAGE_STORE_AVAILABLE and message_store:
        try:
            fastapi_sessions = await message_store.get_all_sessions()
            result["fastapi_sessions"] = fastapi_sessions
            result["fastapi_total_count"] = len(fastapi_sessions)
        except Exception as e:
            result["fastapi_error"] = str(e)

    return result


@mcp.tool
async def get_session_info(session_id: str) -> Dict[str, Any]:
    """
    Récupère les informations sur une session donnée en utilisant les données de
    MCP et FastAPI. Cette fonction rassemble les données relatives au traitement
    d'une session, si elle existe, et renvoie les informations pertinentes sous
    forme d'un dictionnaire.

    :param session_id: Identifiant de la session à récupérer.
    :type session_id: str
    :return: Un dictionnaire contenant des informations sur la session, y compris
             son état dans le traitement MCP et FastAPI.
    :rtype: Dict[str, Any]
    """
    result = {"session_id": session_id}

    # Info MCP
    if session_id in PROCS:
        proc = PROCS[session_id]
        result.update({
            "mcp_found": True,
            "pid": proc.pid,
            "is_running": proc.returncode is None,
            "return_code": proc.returncode
        })
    else:
        result["mcp_found"] = False

    # Info FastAPI
    if FASTAPI_MESSAGE_STORE_AVAILABLE and message_store:
        try:
            session_info = await message_store.get_session_info(session_id)
            if session_info:
                result["fastapi_info"] = session_info
            else:
                result["fastapi_found"] = False
        except Exception as e:
            result["fastapi_error"] = str(e)

    result["ok"] = True
    return result


# --------- RUN ----------
if __name__ == "__main__":
    port = int(os.getenv("MCP_BACKEND_PORT", "8090"))

    print(f"[MCP] Démarrage serveur MCP sur port {port}")
    print(f"[MCP] PROJECT_DIR: {PROJECT_DIR}")
    print(f"[MCP] FASTAPI_URL: {FASTAPI_URL}")
    print(f"[MCP] Message store disponible: {FASTAPI_MESSAGE_STORE_AVAILABLE}")
    print(f"[MCP] Message store path: {message_fastapi_path}")
    if FASTAPI_MESSAGE_STORE_AVAILABLE:
        print(f"[MCP] Message store type: {type(message_store).__name__}")

    # serveur MCP
    mcp.run(transport="http", host="0.0.0.0", port=port, path="/mcp/")
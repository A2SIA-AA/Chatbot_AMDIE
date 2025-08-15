# mcp_backend_server.py
import os, sys, asyncio, signal
from typing import Dict, Any

from fastmcp import FastMCP

mcp = FastMCP("AMDIE-Backend-MCP")

# --------- CONFIG ----------
PROJECT_DIR = os.getenv("PROJECT_DIR")
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
    """Trouve automatiquement le chemin vers message_fastapi"""
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
    """Lance le wrapper backend"""
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
    """Annule une session backend"""
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
    Helper function pour envoyer des messages
    """
    print(f"[MCP DEBUG] ==========================================")
    print(f"[MCP DEBUG] _send_message_helper DÉMARRAGE")
    print(f"[MCP DEBUG] session_id: '{session_id}'")
    print(f"[MCP DEBUG] message_type: '{message_type}'")
    print(f"[MCP DEBUG] content: '{content[:100]}...'")
    print(f"[MCP DEBUG] metadata: {metadata}")
    print(f"[MCP DEBUG] FASTAPI_MESSAGE_STORE_AVAILABLE: {FASTAPI_MESSAGE_STORE_AVAILABLE}")
    print(f"[MCP DEBUG] message_store objet: {message_store}")
    print(f"[MCP DEBUG] type(message_store): {type(message_store)}")

    #  VALIDATION ÉTAPE PAR ÉTAPE
    if not FASTAPI_MESSAGE_STORE_AVAILABLE:
        print(f"[MCP DEBUG]  ÉCHEC: Message store non disponible")
        return {"ok": False, "error": "Message store non disponible"}

    if message_store is None:
        print(f"[MCP DEBUG]  ÉCHEC: message_store est None")
        return {"ok": False, "error": "message_store est None"}

    if not session_id or not session_id.strip():
        print(f"[MCP DEBUG]  ÉCHEC: Session ID invalide: '{session_id}'")
        return {"ok": False, "error": "Session ID requis"}

    if not content or not content.strip():
        print(f"[MCP DEBUG]  ÉCHEC: Contenu invalide: '{content}'")
        return {"ok": False, "error": "Contenu requis"}

    print(f"[MCP DEBUG]  Toutes les validations passées")

    try:
        # Construire le message
        message_data = {
            'type': message_type,
            'content': content,
            'metadata': metadata or {
                'timestamp': asyncio.get_event_loop().time(),
                'source': 'backend_via_mcp'
            }
        }

        print(f"[MCP DEBUG] Message data construit:")
        print(f"[MCP DEBUG]   type: {message_data['type']}")
        print(f"[MCP DEBUG]   content: {message_data['content'][:50]}...")
        print(f"[MCP DEBUG]   metadata: {message_data['metadata']}")

        #  ÉTAPE CRITIQUE: VÉRIFIER LES MÉTHODES DISPONIBLES
        print(f"[MCP DEBUG] Vérification méthodes message_store...")
        available_methods = [method for method in dir(message_store) if not method.startswith('_')]
        print(f"[MCP DEBUG] Méthodes disponibles: {available_methods}")

        if not hasattr(message_store, 'add_message'):
            print(f"[MCP DEBUG]  CRITIQUE: add_message non trouvée!")
            return {"ok": False, "error": "add_message method not found"}

        print(f"[MCP DEBUG] add_message method: {getattr(message_store, 'add_message')}")

        #  ÉTAPE CRITIQUE: TENTATIVE D'AJOUT MESSAGE
        print(f"[MCP DEBUG] TENTATIVE add_message...")
        print(f"[MCP DEBUG] Appel: message_store.add_message('{session_id}', {message_data})")

        # AJOUT AVEC MAXIMUM DE DEBUG
        result = await message_store.add_message(session_id, message_data)
        print(f"[MCP DEBUG] add_message retourné: {result}")

        print(f"[MCP DEBUG]  add_message réussi! Vérification...")

        #  VÉRIFICATION IMMÉDIATE: RÉCUPÉRER LES MESSAGES
        try:
            print(f"[MCP DEBUG] Vérification 1: get_all_sessions...")
            all_sessions = await message_store.get_all_sessions()
            print(f"[MCP DEBUG] Sessions après ajout: {all_sessions}")

            if session_id in all_sessions:
                print(f"[MCP DEBUG]  Session {session_id} trouvée dans all_sessions")
            else:
                print(f"[MCP DEBUG] ⚠️ Session {session_id} PAS trouvée dans all_sessions")

            print(f"[MCP DEBUG] Vérification 2: get_messages...")
            session_messages = await message_store.get_messages(session_id)
            print(f"[MCP DEBUG] Messages dans la session: {len(session_messages)}")

            if len(session_messages) > 0:
                print(f"[MCP DEBUG]  {len(session_messages)} messages trouvés")
                for i, msg in enumerate(session_messages):
                    print(f"[MCP DEBUG]   Message {i + 1}: {msg}...")
            else:
                print(f"[MCP DEBUG] AUCUN message trouvé dans la session!")

            print(f"[MCP DEBUG] Vérification 3: get_session_info...")
            session_info = await message_store.get_session_info(session_id)
            print(f"[MCP DEBUG] Session info: {session_info}")

        except Exception as verify_error:
            print(f"[MCP DEBUG]  ERREUR VÉRIFICATION: {verify_error}")
            import traceback
            print(f"[MCP DEBUG] Traceback vérification:")
            traceback.print_exc()

        print(f"[MCP DEBUG]  SUCCÈS COMPLET")
        return {
            "ok": True,
            "message": f"Message {message_type} envoyé avec succès",
            "session_id": session_id
        }

    except Exception as e:
        print(f"[MCP DEBUG]  EXCEPTION DANS add_message: {e}")
        print(f"[MCP DEBUG] Type exception: {type(e)}")
        import traceback
        print(f"[MCP DEBUG] Traceback complet:")
        traceback.print_exc()
        return {"ok": False, "error": f"Exception: {str(e)}"}

    finally:
        print(f"[MCP DEBUG] ==========================================")


# --------- TOOLS ORIGINAUX ----------
@mcp.tool
async def start_backend(question: str, session_id: str, permissions_csv: str, role: str, username: str, email: str) -> Dict[str, Any]:
    """
    Lance le backend (wrapper) pour une session donnée.
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
    Santé du serveur MCP backend.
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
    Tool pour que le backend envoie des messages via MCP vers FastAPI
    """
    return await _send_message_helper(session_id, message_type, content, metadata)


@mcp.tool
async def send_progress(session_id: str, message: str) -> Dict[str, Any]:
    """
    Envoie un message de progression via MCP
    """
    return await _send_message_helper(session_id, 'progress', message)


@mcp.tool
async def send_final(session_id: str, response: str) -> Dict[str, Any]:
    """
    Envoie la réponse finale via MCP
    """
    return await _send_message_helper(session_id, 'final', response)


@mcp.tool
async def send_error(session_id: str, error: str) -> Dict[str, Any]:
    """
    Envoie un message d'erreur via MCP
    """
    return await _send_message_helper(session_id, 'error', f"ERREUR: {error}")


@mcp.tool
async def send_log(session_id: str, log_message: str, log_level: str = "INFO") -> Dict[str, Any]:
    """
    Envoie un log détaillé via MCP
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
    Liste toutes les sessions actives
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
    Récupère les informations d'une session spécifique
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
    mcp.run(transport="http", host="0.0.0.0", port=port, path="/mcp")
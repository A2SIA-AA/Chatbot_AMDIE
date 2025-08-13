# mcp_client_utils.py
import os, json
from typing import Any, Dict

from mcp.client.streamable_http import streamablehttp_client
from mcp.client.session import ClientSession

MCP_BACKEND_URL = os.getenv("MCP_BACKEND_URL", "http://localhost:8090/mcp").rstrip("/")
MCP_SSE_URL = f"{MCP_BACKEND_URL}"

print(f"[MCP Client] URL configurée: {MCP_SSE_URL}")


async def _with_session(fn):
    """Session MCP"""
    async with streamablehttp_client(MCP_SSE_URL) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            try:
                await session.initialize()
            except Exception:
                pass  # L'initialisation peut échouer selon les versions
            return await fn(session)


def _extract_json(result: Any) -> Dict[str, Any]:
    """Extraction JSON simple"""
    # 1) Direct result
    try:
        if isinstance(getattr(result, "result", None), dict):
            return result.result
    except Exception:
        pass

    # 2) Via content[]
    try:
        for c in getattr(result, "content", []) or []:
            t = getattr(c, "type", None)
            if t == "json":
                data = getattr(c, "data", None)
                if isinstance(data, dict):
                    return data
            if t == "text":
                txt = getattr(c, "text", None)
                if isinstance(txt, str) and txt.strip():
                    try:
                        return json.loads(txt)
                    except Exception:
                        return {"text": txt}
    except Exception:
        pass

    return {}


async def _call_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Appel d'outil MCP"""

    async def runner(session: ClientSession):
        tools_result = await session.list_tools()
        tools = [t.name for t in getattr(tools_result, "tools", [])]
        if tool_name not in tools:
            raise RuntimeError(f"Tool MCP introuvable: {tool_name}. Tools disponibles: {tools}")
        result = await session.call_tool(tool_name, arguments=arguments)
        return _extract_json(result)

    return await _with_session(runner)


# --------- TOOLS ORIGINAUX ----------
async def mcp_start_backend(question: str, session_id: str, permissions_csv: str, role: str) -> Dict[str, Any]:
    """Démarrage backend via MCP"""
    return await _call_tool("start_backend", {
        "question": question,
        "session_id": session_id,
        "permissions_csv": permissions_csv,
        "role": role,
    })


async def mcp_cancel_session(session_id: str) -> Dict[str, Any]:
    """Annulation session via MCP"""
    return await _call_tool("cancel_session", {"session_id": session_id})


async def mcp_health() -> Dict[str, Any]:
    """Santé du serveur via MCP"""
    return await _call_tool("health", {})


# --------- TOOLS POUR COMMUNICATION ----------
async def mcp_send_message(session_id: str, message_type: str, content: str, metadata: Dict[str, Any] = None) -> Dict[
    str, Any]:
    """
    Envoie un message générique via MCP

    Args:
        session_id: ID de la session
        message_type: Type de message ('progress', 'final', 'error')
        content: Contenu du message
        metadata: Métadonnées optionnelles
    """
    return await _call_tool("send_message", {
        "session_id": session_id,
        "message_type": message_type,
        "content": content,
        "metadata": metadata or {}
    })


async def mcp_send_progress(session_id: str, message: str) -> Dict[str, Any]:
    """
    Envoie un message de progression via MCP
    """
    return await _call_tool("send_progress", {
        "session_id": session_id,
        "message": message
    })


async def mcp_send_final(session_id: str, response: str) -> Dict[str, Any]:
    """
    Envoie la réponse finale via MCP
    """
    return await _call_tool("send_final", {
        "session_id": session_id,
        "response": response
    })


async def mcp_send_error(session_id: str, error: str) -> Dict[str, Any]:
    """
    Envoie un message d'erreur via MCP
    """
    return await _call_tool("send_error", {
        "session_id": session_id,
        "error": error
    })


async def mcp_send_log(session_id: str, log_message: str, log_level: str = "INFO") -> Dict[str, Any]:
    """
    Envoie un log détaillé via MCP
    """
    return await _call_tool("send_log", {
        "session_id": session_id,
        "log_message": log_message,
        "log_level": log_level
    })


# --------- TOOLS DE DEBUG ----------
async def mcp_list_active_sessions() -> Dict[str, Any]:
    """Liste toutes les sessions actives via MCP"""
    return await _call_tool("list_active_sessions", {})


async def mcp_get_session_info(session_id: str) -> Dict[str, Any]:
    """Récupère les informations d'une session via MCP"""
    return await _call_tool("get_session_info", {"session_id": session_id})


# --------- CLASSE HELPER POUR COMMUNICATION MCP ----------
class MCPCommunicator:
    """
    Classe helper pour simplifier la communication MCP dans le backend
    """

    def __init__(self, session_id: str):
        self.session_id = session_id

    async def send_progress(self, message: str) -> bool:
        """Envoie un message de progression"""
        try:
            result = await mcp_send_progress(self.session_id, message)
            return result.get("ok", False)
        except Exception as e:
            print(f"[MCP] Erreur send_progress: {e}")
            return False

    async def send_final(self, response: str) -> bool:
        """Envoie la réponse finale"""
        try:
            result = await mcp_send_final(self.session_id, response)
            return result.get("ok", False)
        except Exception as e:
            print(f"[MCP] Erreur send_final: {e}")
            return False

    async def send_error(self, error: str) -> bool:
        """Envoie un message d'erreur"""
        try:
            result = await mcp_send_error(self.session_id, error)
            return result.get("ok", False)
        except Exception as e:
            print(f"[MCP] Erreur send_error: {e}")
            return False

    async def send_log(self, log_message: str, log_level: str = "INFO") -> bool:
        """Envoie un log détaillé"""
        try:
            result = await mcp_send_log(self.session_id, log_message, log_level)
            return result.get("ok", False)
        except Exception as e:
            print(f"[MCP] Erreur send_log: {e}")
            return False


# --------- TEST STANDALONE ----------
if __name__ == "__main__":
    import asyncio


    async def test_mcp_communication():
        """Test des fonctions de communication MCP"""
        print("=== TEST COMMUNICATION MCP ===")

        # Test health
        try:
            health = await mcp_health()
            print(f" Health: {health}")
        except Exception as e:
            print(f" Health error: {e}")
            return

        # Test communication
        test_session_id = "test_comm_123"

        try:
            # Test progress
            result = await mcp_send_progress(test_session_id, "Test message de progression")
            print(f" Send progress: {result}")

            # Test log
            result = await mcp_send_log(test_session_id, "Test log message", "INFO")
            print(f" Send log: {result}")

            # Test error
            result = await mcp_send_error(test_session_id, "Test error message")
            print(f" Send error: {result}")

            # Test final
            result = await mcp_send_final(test_session_id, "Test réponse finale")
            print(f" Send final: {result}")

        except Exception as e:
            print(f" Communication error: {e}")


    asyncio.run(test_mcp_communication())
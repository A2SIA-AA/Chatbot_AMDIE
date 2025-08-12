# mcp_client_utils.py
import os, json
from typing import Any, Dict

# Le SDK a deux noms possibles selon versions.
try:
    # Nom "officiel" récent
    from mcp.client.sse import sse_client
    from mcp.client.session import ClientSession
except Exception:
    # Alias community/ancien nom
    from modelcontextprotocol.client.sse import sse_client  # type: ignore
    from modelcontextprotocol.client.session import ClientSession  # type: ignore


# MCP_BACKEND_URL doit ressembler à: http://localhost:8090/mcp
MCP_BACKEND_URL = os.getenv("MCP_BACKEND_URL", "http://localhost:8090/mcp").rstrip("/")
MCP_SSE_URL = f"{MCP_BACKEND_URL}/sse"


async def _with_session(fn):
    """
    Ouvre une session MCP (SSE) => initialize => exécute fn(session).
    """
    async with sse_client(MCP_SSE_URL) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            # Certaines versions nécessitent initialize(), d'autres le font implicitement.
            try:
                await session.initialize()
            except Exception:
                pass
            return await fn(session)


def _extract_json(result: Any) -> Dict[str, Any]:
    """
    Normalise la réponse d'un call_tool en dict.
    Gère les variantes selon SDK (result.result, result.content[...].data/text).
    """
    # 1) Tentative d'accès direct
    try:
        if isinstance(getattr(result, "result", None), dict):
            return result.result  # type: ignore[attr-defined]
    except Exception:
        pass

    # 2) Parcours du contenu structuré
    try:
        for c in getattr(result, "content", []) or []:
            ctype = getattr(c, "type", None)
            if ctype == "json":
                data = getattr(c, "data", None)
                if isinstance(data, dict):
                    return data
            if ctype == "text":
                text = getattr(c, "text", None)
                if isinstance(text, str) and text.strip():
                    try:
                        return json.loads(text)
                    except Exception:
                        return {"text": text}
    except Exception:
        pass

    return {}


async def _call_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    list_tools -> call_tool(tool_name, arguments) -> extrait JSON.
    """
    async def runner(session: ClientSession):
        # Optionnel: vérifier la présence du tool
        tools_result = await session.list_tools()
        tools = [t.name for t in getattr(tools_result, "tools", [])]
        if tool_name not in tools:
            raise RuntimeError(f"Tool MCP introuvable: {tool_name}. Tools disponibles: {tools}")

        result = await session.call_tool(tool_name, arguments=arguments)
        return _extract_json(result)

    return await _with_session(runner)


# -------- Helpers spécifiques à ton serveur MCP --------

async def mcp_start_backend(question: str, session_id: str, permissions_csv: str, role: str) -> Dict[str, Any]:
    """
    Appelle le tool MCP 'start_backend' exposé par ton serveur MCP backend.
    """
    args = {
        "question": question,
        "session_id": session_id,
        "permissions_csv": permissions_csv,
        "role": role,
    }
    return await _call_tool("start_backend", args)


async def mcp_cancel_session(session_id: str) -> Dict[str, Any]:
    """
    Appelle le tool MCP 'cancel_session' pour arrêter proprement le process backend.
    """
    return await _call_tool("cancel_session", {"session_id": session_id})


async def mcp_health() -> Dict[str, Any]:
    """
    Vérifie la santé du serveur MCP backend.
    """
    return await _call_tool("health", {})

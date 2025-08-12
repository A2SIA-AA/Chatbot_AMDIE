# mcp_client_utils.py - VERSION FINALE CORRIGÉE
import os, json
from typing import Any, Dict

from mcp.client.streamable_http import streamablehttp_client
from mcp.client.session import ClientSession

MCP_BACKEND_URL = os.getenv("MCP_BACKEND_URL", "http://localhost:8090/mcp").rstrip("/")
MCP_SSE_URL = f"{MCP_BACKEND_URL}"


async def _with_session(fn):
    """Session MCP avec la syntaxe officielle correcte"""
    # ✅ CORRECTION: streamablehttp_client retourne 3 valeurs selon la doc officielle
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
    """Appel d'outil MCP selon la doc officielle"""

    async def runner(session: ClientSession):
        tools_result = await session.list_tools()
        tools = [t.name for t in getattr(tools_result, "tools", [])]
        if tool_name not in tools:
            raise RuntimeError(f"Tool MCP introuvable: {tool_name}. Tools disponibles: {tools}")
        result = await session.call_tool(tool_name, arguments=arguments)
        return _extract_json(result)

    return await _with_session(runner)


# ---- Helpers spécifiques ----
async def mcp_start_backend(question: str, session_id: str, permissions_csv: str, role: str) -> Dict[str, Any]:
    return await _call_tool("start_backend", {
        "question": question,
        "session_id": session_id,
        "permissions_csv": permissions_csv,
        "role": role,
    })


async def mcp_cancel_session(session_id: str) -> Dict[str, Any]:
    return await _call_tool("cancel_session", {"session_id": session_id})


async def mcp_health() -> Dict[str, Any]:
    return await _call_tool("health", {})
# mcp_bridge.py
import os
import httpx
from typing import Optional, Any, Dict, List
from fastmcp import FastMCP

# Nom du serveur MCP (tel qu’il apparaît côté client)
mcp = FastMCP("AMDIE-MCP-Bridge")

BACKEND = os.getenv("BACKEND_BASE_URL", "http://localhost:8000")

# --- Helper HTTP -------------------------------------------------------------
async def _call(
    method: str,
    path: str,
    token: Optional[str] = None,
    params: Dict[str, Any] | None = None,
    json: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    headers: Dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    url = f"{BACKEND}{path}"
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.request(method, url, params=params, json=json, headers=headers)
        resp.raise_for_status()
        return resp.json()

# --- Tools MCP ---------------------------------------------------------------
@mcp.tool
async def run_chat_keycloak(question: str, token: str) -> Dict[str, Any]:
    """
    Démarre le traitement côté backend (Keycloak).
    - Appelle POST /api/v1/start-processing-keycloak
    - Retourne au minimum: { sessionId, status, message, user }
    """
    payload = {"question": question}
    return await _call("POST", "/api/v1/start-processing-keycloak", token=token, json=payload)

@mcp.tool
async def poll_messages(session_id: str, since: float = 0.0) -> Dict[str, Any]:
    """
    Récupère les messages d'une session.
    - Appelle GET /api/v1/messages/{session_id}?since=...
    - Retourne { messages: [...] }
    """
    return await _call("GET", f"/api/v1/messages/{session_id}", params={"since": since})

@mcp.tool
async def clear_session(session_id: str) -> Dict[str, Any]:
    """
    Supprime la session côté API.
    - Appelle DELETE /api/v1/messages/{session_id}
    - Retourne { success: bool, message: str }
    """
    return await _call("DELETE", f"/api/v1/messages/{session_id}")

@mcp.tool
async def health() -> Dict[str, Any]:
    """
    Santé de l'API orchestratrice.
    - Appelle GET /health
    """
    return await _call("GET", "/health")

# --- Lancement du serveur MCP -----------------------------------------------
if __name__ == "__main__":
    # Transport "http" = accessible par des clients distants (Claude Desktop, Agents, etc.)
    # Le serveur expose MCP sur http://0.0.0.0:8082/mcp
    mcp.run(transport="http", host="0.0.0.0", port=8082, path="/mcp")

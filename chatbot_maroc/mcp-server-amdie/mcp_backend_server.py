# mcp_backend_server.py
import os, sys, asyncio, signal
from typing import Dict, Any

from fastmcp import FastMCP

mcp = FastMCP("AMDIE-Backend-MCP")

# --------- CONFIG ----------
PROJECT_DIR  = os.getenv("PROJECT_DIR")  # DOIT être ABSOLU
WRAPPER_PATH = os.getenv("WRAPPER_PATH", "chatbot_wrapper.py")
FASTAPI_URL  = os.getenv("FASTAPI_URL", "http://localhost:8000")

if not PROJECT_DIR or not os.path.isabs(PROJECT_DIR):
    raise RuntimeError("PROJECT_DIR doit être défini et ABSOLU (export PROJECT_DIR=/chemin/absolu)")

# --------- STATE ----------
# on garde la liste des sous-process backends par session pour pouvoir les stopper
PROCS: Dict[str, asyncio.subprocess.Process] = {}

async def _spawn_wrapper(question: str, session_id: str, permissions_csv: str, role: str) -> Dict[str, Any]:
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
    ]
    env = os.environ.copy()
    env["FASTAPI_URL"] = f"{FASTAPI_URL.rstrip('/')}/api/v1/messages"  # pour le wrapper

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=PROJECT_DIR,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    PROCS[session_id] = proc

    # lecture asynchrone minimaliste pour log (non bloquant)
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

# --------- TOOLS ----------
@mcp.tool
async def start_backend(question: str, session_id: str, permissions_csv: str, role: str) -> Dict[str, Any]:
    """
    Lance le backend (wrapper) pour une session donnée.
    """
    print(f"[MCP] start_backend session={session_id} role={role}")
    return await _spawn_wrapper(question, session_id, permissions_csv, role)

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
    return {
        "status": "ok",
        "project_dir": PROJECT_DIR,
        "wrapper": WRAPPER_PATH,
        "fastapi_url": FASTAPI_URL,
        "active_sessions": [sid for sid,p in PROCS.items() if p.returncode is None],
    }

# --------- RUN ----------
if __name__ == "__main__":
    port = int(os.getenv("MCP_BACKEND_PORT", "8090"))
    # serveur MCP (HTTP+SSE)
    mcp.run(transport="http", host="0.0.0.0", port=port, path="/mcp")

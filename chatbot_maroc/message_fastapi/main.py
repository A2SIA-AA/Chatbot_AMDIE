from datetime import timedelta

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import time
import logging
import subprocess
import os
from typing import Optional
import asyncio
from auth import (
    authenticate_user, create_access_token, get_current_user,
    require_permission, check_permission, USERS_DATABASE
)
from models import LoginRequest, LoginResponse, User

# Import de nos modèles et stockage
from models import MessageRequest, MessagesResponse, SuccessResponse, MessageResponse
from message_store import message_store

ACCESS_TOKEN_EXPIRE_MINUTES = 30

# ========================================
# CONFIGURATION LOGGING
# ========================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========================================
# CRÉATION DE L'APP FASTAPI
# ========================================
app = FastAPI(
    title="Message API - Architecture Séparée",
    description="API REST pour orchestrer chatbot IA avec backend séparé",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# ========================================
# CONFIGURATION CORS (configure les origines pouvant communiquer avec notre API)
# ========================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# ========================================
# MIDDLEWARE DE LOGGING
# ========================================
@app.middleware("http")
async def log_requests(request, call_next):
    """Log automatique de toutes les requêtes"""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time

    logger.info(
        f"{request.method} {request.url} - "
        f"Status: {response.status_code} - "
        f"Time: {process_time:.4f}s"
    )

    response.headers["X-Process-Time"] = str(process_time)
    return response


# ========================================
# ROUTES HEALTH
# ========================================

@app.get("/", tags=["Health"])
async def root():
    """Page d'accueil de l'API"""
    return {
        "message": "Message API v2.0 - Architecture Séparée ",
        "version": "2.0.0",
        "documentation": "/docs",
        "health_check": "/health",
        "services": {
            "frontend": "http://localhost:3000",
            "api": "http://localhost:8000",
            "backend": "Orchestré par cette API"
        }
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Vérification de santé complète"""
    backend_path = "../backend_python"
    backend_accessible = os.path.exists(backend_path)

    return {
        "status": "healthy",
        "timestamp": time.time(),
        "version": "2.0.0",
        "architecture": "separated",
        "services": {
            "api": "running",
            "backend_path": backend_path,
            "backend_accessible": backend_accessible
        },
        "active_sessions": len(await message_store.get_all_sessions())
    }
# ========================================
# ROUTES DE MESSAGES
# ========================================

@app.post("/api/v1/messages", response_model=SuccessResponse, tags=["Messages"])
async def create_message(message: MessageRequest):
    """
    Créer un nouveau message (utilisé par le Backend Python)
    """
    try:
        await message_store.add_message(message.sessionId, {
            'type': message.type,
            'content': message.content,
            'metadata': message.metadata
        })

        logger.info(f" Message reçu du backend pour {message.sessionId}: {message.type}")

        return SuccessResponse(
            success=True,
            message=f"Message {message.type} ajouté avec succès"
        )

    except Exception as e:
        logger.error(f"Erreur lors de l'ajout du message: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/messages/{session_id}", response_model=MessagesResponse, tags=["Messages"])
async def get_messages(
        session_id: str,
        since: Optional[float] = Query(0, description="Timestamp depuis lequel récupérer les messages")
):
    """
    Récupérer les messages d'une session (utilisé par le Frontend)
    """
    try:
        if since > 0:
            messages = await message_store.get_new_messages(session_id, since)
        else:
            messages = await message_store.get_messages(session_id)

        return MessagesResponse(
            sessionId=session_id,
            messages=messages,
            timestamp=time.time(),
            messageCount=len(messages)
        )

    except Exception as e:
        logger.error(f"Erreur lors de la récupération des messages: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/v1/messages/{session_id}", response_model=SuccessResponse, tags=["Messages"])
async def delete_session(session_id: str):
    """
    Supprimer une session et ses messages
    """
    try:
        success = await message_store.clear_session(session_id)

        if success:
            logger.info(f" Session {session_id} supprimée")
            return SuccessResponse(
                success=True,
                message=f"Session {session_id} supprimée avec succès"
            )
        else:
            return SuccessResponse(
                success=True,
                message=f"Session {session_id} était déjà supprimée"
            )

    except Exception as e:
        logger.error(f"Erreur lors de la suppression: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========================================
# ROUTES DE DEBUG ET MONITORING
# ========================================

@app.get("/api/v1/sessions", tags=["Debug"])
async def list_sessions():
    """Liste toutes les sessions actives"""
    try:
        sessions = await message_store.get_all_sessions()
        return {
            "sessions": sessions,
            "count": len(sessions),
            "timestamp": time.time()
        }
    except Exception as e:
        logger.error(f"Erreur lors de la liste des sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/sessions/{session_id}/info", tags=["Debug"])
async def get_session_info(session_id: str):
    """Récupérer les informations détaillées d'une session"""
    try:
        info = await message_store.get_session_info(session_id)
        if info:
            return info
        else:
            raise HTTPException(status_code=404, detail="Session non trouvée")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des infos: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/backend/status", tags=["Debug"])
async def backend_status():
    """Vérifier le statut du backend"""
    backend_path = "../backend_python"
    script_path = os.path.join(backend_path, "chatbot_wrapper.py")

    return {
        "backend_path": os.path.abspath(backend_path),
        "script_exists": os.path.exists(script_path),
        "script_path": os.path.abspath(script_path),
        "backend_accessible": os.path.exists(backend_path),
        "python_version": subprocess.run(["python3", "--version"], capture_output=True, text=True).stdout.strip()
    }


# Route de connexion
@app.post("/api/v1/auth/login", response_model=LoginResponse, tags=["Authentication"])
async def login(login_data: LoginRequest):
    """Connexion utilisateur avec JWT"""
    user = authenticate_user(login_data.email, login_data.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Email ou mot de passe incorrect"
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["email"]}, expires_delta=access_token_expires
    )

    user_response = User(
        username=user["username"],
        email=user["email"],
        role=user["role"],
        permissions=user["permissions"],
        full_name=user["full_name"],
        department=user["department"]
    )

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user=user_response,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60  # en secondes
    )

from fastapi import Depends

# Route de déconnexion
@app.post("/api/v1/auth/logout", tags=["Authentication"])
async def logout(current_user: dict = Depends(get_current_user)):
    """Déconnexion (côté client)"""
    return {"message": f"Utilisateur {current_user['username']} déconnecté avec succès"}


# Route profil utilisateur
@app.get("/api/v1/auth/me", response_model=User, tags=["Authentication"])
async def get_me(current_user: dict = Depends(get_current_user)):
    """Récupérer le profil de l'utilisateur connecté"""
    return User(
        username=current_user["username"],
        email=current_user["email"],
        role=current_user["role"],
        permissions=current_user["permissions"],
        full_name=current_user["full_name"],
        department=current_user["department"]
    )


# route start-processing pour inclure l'auth
@app.post("/api/v1/start-processing", tags=["Processing"])
async def start_processing(
        request: dict,
        current_user: dict = Depends(get_current_user)
):
    """
    Démarrer le traitement
    """
    try:
        # Vérifier permission de chat
        if not check_permission(current_user, "chat_basic"):
            raise HTTPException(
                status_code=403,
                detail="Permission de chat requise"
            )

        question = request.get("question", "")
        if not question.strip():
            raise HTTPException(status_code=400, detail="Question requise")

        # Générer session ID avec info utilisateur
        session_id = f"session_{current_user['role']}_{int(time.time())}_{os.urandom(4).hex()}"

        # Message de démarrage avec info utilisateur
        await message_store.add_message(session_id, {
            'type': 'progress',
            'content': f'Connexion réussie - Utilisateur: {current_user["full_name"]} ({current_user["role"]})',
            'metadata': {
                'source': 'api_orchestrator',
                'user_role': current_user['role'],
                'user_permissions': current_user['permissions']
            }
        })

        # Chemin vers le backend
        backend_path = "../backend_python"
        script_path = os.path.join(backend_path, "chatbot_wrapper.py")

        if not os.path.exists(script_path):
            raise HTTPException(status_code=500, detail=f"Backend non trouvé: {script_path}")

        # LANCER LE BACKEND avec les permissions utilisateur
        try:
            # Passer les permissions comme argument supplémentaire
            user_permissions_str = ",".join(current_user['permissions'])

            process = await asyncio.create_subprocess_exec(
                "python3", script_path,
                question,
                session_id,
                user_permissions_str,
                current_user['role'],
                cwd=backend_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            logger.info(f"Backend IA démarré pour {current_user['username']} (session {session_id})")

            await message_store.add_message(session_id, {
                'type': 'progress',
                'content': f'Backend IA initialisé avec permissions {current_user["role"]}',
                'metadata': {
                    'source': 'api_orchestrator',
                    'process_id': process.pid,
                    'user_role': current_user['role']
                }
            })

        except Exception as e:
            logger.error(f"Erreur lancement backend: {e}")
            await message_store.add_message(session_id, {
                'type': 'error',
                'content': f'❌ Erreur lancement backend: {str(e)}',
                'metadata': {'source': 'api_orchestrator'}
            })
            raise HTTPException(status_code=500, detail=f"Erreur lancement backend: {str(e)}")

        return {
            "sessionId": session_id,
            "status": "processing_started",
            "message": "Traitement IA démarré avec succès",
            "user": {
                "role": current_user['role'],
                "permissions": current_user['permissions'],
                "name": current_user['full_name']
            },
            "process_id": process.pid
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur démarrage traitement: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Route pour tester les permissions
@app.get("/api/v1/permissions/test", tags=["Debug"])
async def test_permissions(current_user: dict = Depends(get_current_user)):
    """Test des permissions utilisateur"""
    return {
        "user": current_user['username'],
        "role": current_user['role'],
        "permissions": current_user['permissions'],
        "can_read_public": check_permission(current_user, "read_public_docs"),
        "can_read_internal": check_permission(current_user, "read_internal_docs"),
        "can_manage_users": check_permission(current_user, "manage_users")
    }


# Route admin seulement
@app.get("/api/v1/admin/users", tags=["Admin"])
async def list_users(current_user: dict = Depends(require_permission("manage_users"))):
    """Liste des utilisateurs (admin seulement)"""
    users = []
    for email, user_data in USERS_DATABASE.items():
        users.append({
            "email": email,
            "username": user_data["username"],
            "role": user_data["role"],
            "full_name": user_data["full_name"],
            "department": user_data["department"]
        })
    return {"users": users, "total": len(users)}


# ========================================
# LANCEMENT DU SERVEUR
# ========================================
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
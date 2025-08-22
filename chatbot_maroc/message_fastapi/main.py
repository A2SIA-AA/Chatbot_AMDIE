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

from mcp_client_utils import mcp_start_backend


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
    docs_url="/docs", #Avec docs automatique
    redoc_url="/redoc"
)

# ========================================
# CONFIGURATION CORS (configure les origines pouvant communiquer avec notre API)
# Authorise les requêtes venant du frontend
# ========================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ========================================
# MIDDLEWARE DE LOGGING
# Permet l'envoie des messages (INFO: ...)
# ========================================
@app.middleware("http")
async def log_requests(request, call_next):
    """Log automatique de toutes les requêtes"""
    #mesure du temp d'exécution
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time

    #enregistrement des infos utiles
    logger.info(
        f"{request.method} {request.url} - "
        f"Status: {response.status_code} - "
        f"Time: {process_time:.4f}s"
    )

    #ajout des infos dans l'en-tête de la requête
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
    Créer un nouveau message (utilisé par le Backend Python chatbot_wrapper.py)
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
    Récupérer les messages d'une session (utilisé par le Frontend React)
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


# ROUTE DE CONNEXION
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

# ROUTE DE DECONNEXION
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
            # permissions_csv
            permissions_csv = ",".join(current_user['permissions']) if isinstance(current_user['permissions'], list) else str(current_user['permissions'])

            # Appel du serveur MCP (tool "start_backend")
            try:
                mcp_res = await mcp_start_backend(
                    question=question,
                    session_id=session_id,
                    permissions_csv=permissions_csv,
                    role=current_user['role'],
                    username=current_user["username"],
                    email=current_user["email"]
                )
                # Log optionnel
                print("[API] MCP start_backend ->", mcp_res)
            except Exception as e:
                # Si le serveur MCP n'est pas joignable, renvoyer une 502
                raise HTTPException(status_code=502, detail=f"MCP backend indisponible: {e}")

            await message_store.add_message(session_id, {
                'type': 'progress',
                'content': f'Backend IA initialisé avec permissions {current_user["role"]}',
                'metadata': {
                    'source': 'api_orchestrator',
                    'user_role': current_user['role']
                }
            })

        except Exception as e:
            logger.error(f"Erreur lancement backend: {e}")
            await message_store.add_message(session_id, {
                'type': 'error',
                'content': f' Erreur lancement backend: {str(e)}',
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
            }
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
# ROUTES KEYCLOAK
# ========================================

from pydantic import BaseModel


from auth_keycloack import (
    get_current_user_keycloak,
    check_permission_keycloak,
    get_keycloak_login_url,
    exchange_code_for_token
)


# Nouveaux modèles pour Keycloak
class KeycloakAuthUrl(BaseModel):
    auth_url: str


class TokenExchangeRequest(BaseModel):
    code: str
    redirect_uri: str


@app.get("/api/v1/auth/keycloak/login-url", response_model=KeycloakAuthUrl, tags=["Keycloak"])
async def get_keycloak_auth_url(redirect_uri: str | None = Query(None)):
    # si le front fournit ?redirect_uri=..., on le respecte
    auth_url = get_keycloak_login_url(redirect_uri=redirect_uri)
    return {"auth_url": auth_url}


from fastapi import Request


# Route pour échanger le code OAuth2 contre un token (POST)
@app.post("/api/v1/auth/keycloak/callback", tags=["Keycloak"])
async def keycloak_callback_post(request: TokenExchangeRequest):
    """Callback POST après connexion Keycloak"""
    return await process_keycloak_callback(request.code, request.redirect_uri)


# Route pour gérer les GET sur callback (redirection navigateur)
@app.get("/api/v1/auth/keycloak/callback", tags=["Keycloak"])
async def keycloak_callback_get(request: Request):
    """Callback GET - redirection depuis navigateur"""
    code = request.query_params.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="Code manquant")

    # IMPORTANT: le redirect_uri doit être le même que celui utilisé au login
    redirect_uri = "http://localhost:8000/api/v1/auth/keycloak/callback"

    return await process_keycloak_callback(code, redirect_uri)


# Fonction commune pour traiter le callback
async def process_keycloak_callback(code: str, redirect_uri: str):
    """Traitement commun du callback Keycloak"""
    try:
        # Échanger le code contre un token
        token_response = exchange_code_for_token(code, redirect_uri)

        # Décoder le token pour avoir les infos utilisateur
        from jose import jwt
        from auth_keycloack import keycloak_openid

        public_key = keycloak_openid.public_key()
        keycloak_public_key = f"-----BEGIN PUBLIC KEY-----\n{public_key}\n-----END PUBLIC KEY-----"

        token_info = jwt.decode(
            token_response["access_token"],
            keycloak_public_key,
            algorithms=["RS256"],
            audience="account"
        )

        # DEBUG - Afficher les rôles détectés
        keycloak_roles = token_info.get('realm_access', {}).get('roles', [])
        logger.info(f"DEBUG - Rôles Keycloak détectés: {keycloak_roles}")

        # Convertir vers le format de ton User model existant
        from auth_keycloack import keycloak_role_to_amdie_role, get_permissions_from_role

        amdie_role = keycloak_role_to_amdie_role(keycloak_roles)
        logger.info(f" DEBUG - Rôle AMDIE mappé: {amdie_role}")

        user_response = User(
            username=token_info.get('preferred_username', 'unknown'),
            email=token_info.get('email', ''),
            role=amdie_role,
            permissions=get_permissions_from_role(amdie_role),
            full_name=f"{token_info.get('given_name', '')} {token_info.get('family_name', '')}".strip(),
            department="External" if amdie_role == "public" else "Internal" if amdie_role == "employee" else "Management"
        )

        logger.info(f" Connexion Keycloak réussie: {user_response.full_name} ({user_response.role})")

        return LoginResponse(
            access_token=token_response["access_token"],
            token_type="bearer",
            user=user_response,
            expires_in=token_response.get("expires_in", 3600)
        )

    except Exception as e:
        logger.error(f"Erreur callback Keycloak: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# Route pour tester Keycloak (identique à ton /api/v1/auth/me mais avec Keycloak)
@app.get("/api/v1/auth/keycloak/me", response_model=User, tags=["Keycloak"])
async def get_me_keycloak(current_user: dict = Depends(get_current_user_keycloak)):
    """Profil utilisateur Keycloak (même format que l'existant)"""
    return User(
        username=current_user["username"],
        email=current_user["email"],
        role=current_user["role"],
        permissions=current_user["permissions"],
        full_name=current_user["full_name"],
        department=current_user["department"]
    )


# Route de traitement avec Keycloak
@app.post("/api/v1/start-processing-keycloak", tags=["Keycloak"])
async def start_processing_keycloak(
        request: dict,
        current_user: dict = Depends(get_current_user_keycloak)
):
    """Version Keycloak de start-processing"""
    try:
        if not check_permission_keycloak(current_user, "chat_basic"):
            raise HTTPException(
                status_code=403,
                detail="Permission de chat requise"
            )

        question = request.get("question", "")
        if not question.strip():
            raise HTTPException(status_code=400, detail="Question requise")

        session_id = f"session_keycloak_{current_user['role']}_{int(time.time())}_{os.urandom(4).hex()}"

        await message_store.add_message(session_id, {
            'type': 'progress',
            'content': f'Connexion Keycloak réussie - Utilisateur: {current_user["full_name"]} ({current_user["role"]})',
            'metadata': {
                'source': 'api_orchestrator',
                'user_role': current_user['role'],
                'user_permissions': current_user['permissions'],
                'auth_type': 'keycloak'
            }
        })

        permissions_csv = ",".join(current_user['permissions']) if isinstance(current_user['permissions'],
                                                                              list) else str(
            current_user['permissions'])

        try:
            mcp_res = await mcp_start_backend(
                question=question,
                session_id=session_id,
                permissions_csv=permissions_csv,
                role=current_user['role'],
                username=current_user['username'],
                email=current_user['email']
            )
            logger.info(f"[API] MCP start_backend -> {mcp_res}")
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"MCP backend indisponible: {e}")

        logger.info(f"Backend IA Keycloak démarré pour {current_user['username']} (session {session_id})")

        return {
            "sessionId": session_id,
            "status": "processing_started",
            "message": "Traitement IA Keycloak démarré avec succès",
            "user": {
                "role": current_user['role'],
                "permissions": current_user['permissions'],
                "name": current_user['full_name'],
                "auth_type": "keycloak"
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur démarrage traitement Keycloak: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========================================
# LANCEMENT DU SERVEUR
# ========================================
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="localhost",
        port=8000,
        reload=True,
        log_level="info"
    )
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
    """
    Mesure et journalisation du temps d'exécution des requêtes HTTP. Ce middleware
    enregistre les informations concernant la requête HTTP, telles que la méthode,
    l'URL, le statut HTTP de la réponse, et le temps de traitement de la requête.
    De plus, le temps de traitement est inclus dans les en-têtes de la réponse.

    :param request: Objet représentant la requête HTTP entrante.
    :type request: starlette.requests.Request
    :param call_next: Fonction utilisée pour exécuter la prochaine étape du flux de traitement
        de la requête, qui retourne une réponse HTTP.
    :type call_next: typing.Callable
    :return: Réponse HTTP modifiée avec des informations supplémentaires dans l'en-tête.
    :rtype: starlette.responses.Response
    """
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
    """
    Point d'entrée principal de l'API pour vérifier l'état du système et fournir des informations
    de base sur les services configurés.

    :return: Un dictionnaire contenant un message d'accueil, la version de l'API, des liens vers
        la documentation et les contrôles de santé, ainsi qu'une description des services
        interconnectés.
    :rtype: dict
    """
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
    """
    Vérifie l'état de santé de l'application.

    Cette fonction asynchrone retourne un état de santé détaillé de l'application,
    y compris le statut de l'API, la disponibilité d'un chemin backend, le nombre
    de sessions actives et plusieurs méta-informations importantes.

    :param backend_path: Chemin vers le répertoire du backend Python.
    :param backend_accessible: Indique si le chemin backend est accessible ou non.
    :param active_sessions: Nombre total de sessions actives retournées par le
        magasin de messages.

    :return: Un dictionnaire contenant les informations du statut de santé de
        l'application.
    :rtype: dict
    """
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
    Crée un message basé sur les données fournies dans la requête. Cette méthode est
    généralement utilisée pour ajouter des messages à partir d'une session active
    dans le backend. Elle enregistre les messages associés à une session donnée et
    renvoie une réponse indiquant le succès ou l'échec de l'opération.

    :param message: Les détails du message à ajouter, incluant le type, le
        contenu et les métadonnées associés à une session spécifique.
    :type message: MessageRequest
    :return: Une réponse confirmant le succès ou l'échec de l'opération d'ajout
        du message.
    :rtype: SuccessResponse
    :raises HTTPException: Exception HTTP levée en cas d'erreur serveur lors
        de l'ajout du message dans le stockage.
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
    Récupère les messages correspondant à une session donnée. Cette fonction permet de
    récupérer soit tous les messages de la session ou, si un timestamp `since` est fourni,
    uniquement les messages postérieurs à ce moment-là.

    :param session_id: L'identifiant unique de la session pour laquelle les messages
        doivent être récupérés.
    :type session_id: str
    :param since: Timestamp Unix optionnel (en secondes) représentant le moment depuis
        lequel les messages seront récupérés. Si omis ou égal à 0, tous les messages
        de la session seront retournés. La valeur par défaut est 0.
    :type since: Optional[float]
    :return: Une instance de `MessagesResponse` contenant les messages récents de la session,
        le timestamp actuel, et le nombre total des messages inclus dans la réponse.
    :rtype: MessagesResponse
    :raises HTTPException: Si une erreur se produit lors de la récupération des messages,
        une exception avec le code 500 et le détail de l'erreur est levée.
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
    Supprime une session donnée identifiée par un `session_id` et retourne une réponse
    indiquant le succès ou non de l'opération. Si la session n'existe plus, un message
    approprié est également retourné. En cas d'erreur imprévue, une exception HTTP
    avec le code 500 est levée.

    :param session_id: L'identifiant unique de la session à supprimer.
    :type session_id: str
    :return: Une instance de `SuccessResponse` indiquant le succès de l'opération.
    :rtype: SuccessResponse
    :raises HTTPException: Exception levée avec un code d'état 500 en cas d'erreur interne.
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
    """
    Récupère une liste de toutes les sessions disponibles.

    Cette fonction interroge le magasin de messages pour obtenir toutes les
    sessions actuellement disponibles et renvoie leur liste, accompagnée
    du nombre total de sessions et d'un timestamp indiquant quand l'action
    a été exécutée.

    :param message_store: L'objet responsable de la gestion et du stockage
        des messages. Il doit fournir une méthode pour récupérer toutes
        les sessions.
    :return: Un dictionnaire contenant la liste des sessions, le nombre
        total de sessions et un timestamp en temps réel.
    :rtype: dict
    :raises HTTPException: Si une erreur se produit pendant la récupération
        des sessions, une exception `HTTPException` avec un code d'état
        HTTP 500 est levée.
    """
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
    """
    Récupère les informations d'une session spécifique.

    Cette fonction permet d'obtenir les détails associés à une session identifiée
    par son identifiant unique. Si la session est introuvable, une exception HTTP
    avec un statut 404 est levée. En cas d'erreur inattendue, une exception avec un
    statut 500 est levée.

    :param session_id: Identifiant unique de la session
    :type session_id: str
    :return: Les informations de la session sous forme de dictionnaire ou autre
             format correspondant
    :rtype: dict
    :raises HTTPException: Si la session est introuvable (404) ou en cas d'erreur
                           interne du serveur (500)
    """
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
    """
    Vérifie l'état du backend et retourne des informations sur son accessibilité,
    l'existence du script associé et la version de Python utilisée.

    :return: Un dictionnaire contenant les informations sur le chemin du backend,
        l'existence du script, le chemin du script, l'accessibilité du backend
        et la version actuelle de Python.
    :rtype: dict
    """
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
    """
    Gère l'authentification de l'utilisateur en validant les informations
    d'identification fournies (email et mot de passe). Si les informations
    d'identification sont correctes, un jeton d'accès (access_token) est généré
    et des informations détaillées sur l'utilisateur sont renvoyées. Le jeton a
    une durée d'expiration définie.

    :param login_data: Les données de connexion contenant l'email et le mot de passe de l'utilisateur.
    :type login_data: LoginRequest
    :return: Une réponse contenant le jeton d'accès généré, son type, les informations
             de l'utilisateur validées et le temps d'expiration du jeton en secondes.
    :rtype: LoginResponse
    :raises HTTPException: Retourne une exception HTTP avec un code d'erreur 401 si
                             les informations d'identification sont incorrectes.
    """
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
    """
    Déconnecte l'utilisateur actuellement authentifié.

    Cette fonction met fin à la session de l'utilisateur en cours
    et retourne un message confirmant la déconnexion réussie.

    :param current_user: Les informations de l'utilisateur authentifié.
    :type current_user: dict
    :return: Un message confirmant la déconnexion réussie.
    :rtype: dict
    """
    return {"message": f"Utilisateur {current_user['username']} déconnecté avec succès"}


# Route profil utilisateur
@app.get("/api/v1/auth/me", response_model=User, tags=["Authentication"])
async def get_me(current_user: dict = Depends(get_current_user)):
    """
    Récupère les informations de l'utilisateur actuellement authentifié.

    Cette fonction utilise une dépendance pour récupérer les informations de
    l'utilisateur courant et retourne un objet utilisateur structuré. Elle est
    conçue pour les API REST et est annotée en tant que point de terminaison
    GET avec une réponse modélisée.

    :param current_user: Dictionnaire contenant les informations de l'utilisateur
        récupérées via la fonction de dépendance ``get_current_user``.
    :return: Une instance de l’objet ``User`` contenant les détails de
        l'utilisateur actuellement authentifié.
    """
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
    Débute le traitement d'un chatbot en validant les permissions de l'utilisateur, en
    vérifiant les prérequis et en appelant les scripts backend nécessaires.

    Cette fonction vérifie d'abord si l'utilisateur actuel dispose des permissions
    requises pour exécuter cette opération. Si toutes les validations sont réussies,
    elle initialise un identifiant de session, envoie un message de progression via
    un message_store et déclenche le backend via une interaction avec un serveur MCP.
    Elle retourne une confirmation de démarrage du traitement, accompagnée des données
    d'utilisateur et de session.

    :param request: Paramètre JSON contenant les données de requête, notamment une clé
        "question" en tant que message utilisateur initialement fourni.
    :type request: dict
    :param current_user: Dictionnaire contenant les détails de l'utilisateur actuellement connecté.
        Doit inclure des informations comme le rôle, le nom, les permissions, etc.
    :type current_user: dict
    :return: Détails sur l'état de démarrage du traitement, identifiant de session et informations
        sur l'utilisateur validé.
    :rtype: dict
    :raises HTTPException: Cette fonction peut renvoyer des exceptions HTTPException dans
        plusieurs situations, comme l'absence de permission (403), absence de question requise (400),
        backend inaccessible ou non trouvé (500), ou échec de connexion au serveur MCP (502).
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
    """
    Teste les permissions de l'utilisateur actuel et retourne ses informations, son rôle,
    ses permissions et ses capacités spécifiques en fonction de ses autorisations.

    :param current_user: Utilisateur actuel, obtenu via le middleware d'authentification.
    :type current_user: dict
    :return: Dictionnaire contenant les informations sur l'utilisateur, son rôle, ses permissions
        et des indicateurs sur ses capacités à lire les documents publics, lire les documents internes,
        et gérer les utilisateurs.
    :rtype: dict
    """
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
    """
    Récupère une liste d'utilisateurs avec leurs informations associées ainsi que le
    nombre total d'utilisateurs. Cette fonction est uniquement accessible aux administrateurs
    ayant la permission "manage_users".

    :param current_user: Un dictionnaire fournissant les informations de l'utilisateur
        actuel après vérification des permissions.
    :type current_user: dict
    :return: Un dictionnaire contenant une liste d'utilisateurs avec leurs informations
        (email, username, role, nom complet, département) ainsi que le nombre total
        d'utilisateurs.
    :rtype: dict
    """
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
    """
    Retourne l'URL d'authentification pour Keycloak.

    Cette fonction génère et retourne l'URL d'authentification à utiliser pour
    se connecter à Keycloak. Le paramètre optionnel `redirect_uri` peut être fourni
    pour indiquer une URL spécifique vers laquelle l'utilisateur doit être redirigé
    après l'authentification.

    :param redirect_uri: URI vers laquelle l'utilisateur sera redirigé après
                         l'authentification (optionnel).
                         Si non spécifié, une URI par défaut sera utilisée.
    :type redirect_uri: str | None
    :return: Un dictionnaire contenant l'URL d'authentification générée pour
             Keycloak.
    :rtype: dict
    """
    # si le front fournit ?redirect_uri=..., on le respecte
    auth_url = get_keycloak_login_url(redirect_uri=redirect_uri)
    return {"auth_url": auth_url}


from fastapi import Request


# Route pour échanger le code OAuth2 contre un token (POST)
@app.post("/api/v1/auth/keycloak/callback", tags=["Keycloak"])
async def keycloak_callback_post(request: TokenExchangeRequest):
    """
    Gère le point d'entrée de rappel Keycloak pour l'échange de jetons.

    Cette méthode est utilisée pour traiter les rappels de Keycloak
    lorsque l'utilisateur a été redirigé après une authentification
    réussie. Elle extrait et transmet les informations nécessaires
    pour compléter la procédure d'échange de jetons.

    :param request: La requête contenant le code d'autorisation et l'URI de
        redirection fournis par Keycloak dans le cadre du rappel.
    :type request: TokenExchangeRequest

    :return: Le résultat du traitement du rappel, généralement un objet ou une
             réponse indiquant si l'opération a réussi.
    :rtype: Depends du résultat de `process_keycloak_callback`
    """
    return await process_keycloak_callback(request.code, request.redirect_uri)


# Route pour gérer les GET sur callback (redirection navigateur)
@app.get("/api/v1/auth/keycloak/callback", tags=["Keycloak"])
async def keycloak_callback_get(request: Request):
    """
    Gère le callback de Keycloak lors de l'authentification.

    Ce point de terminaison est appelé après que l'utilisateur a été redirigé depuis
    Keycloak avec un code d'autorisation. Il vérifie si le code est présent dans les
    paramètres de la requête et appelle la fonction de traitement pour effectuer les
    étapes nécessaires d'échange de code ou validation.

    :param request: Requête HTTP asynchrone contenant les données transmises par
        Keycloak après la redirection utilisateur.
    :type request: Request
    :return: Résultat du traitement du callback Keycloak.
    :rtype: dict
    :raises HTTPException: Si le code requis n'est pas fourni dans la requête,
        renvoie une erreur HTTP avec un code de statut 400 ("Code manquant").
    """
    code = request.query_params.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="Code manquant")

    redirect_uri = "http://localhost:8000/api/v1/auth/keycloak/callback"

    return await process_keycloak_callback(code, redirect_uri)


# Fonction commune pour traiter le callback
async def process_keycloak_callback(code: str, redirect_uri: str):
    """
    Traite le rappel de Keycloak après l'approbation de l'utilisateur et le redirige
    en fonction des informations incluses dans le token généré par Keycloak.

    Ce processus comprend l'échange du code d'autorisation contre un token, le décodage
    de ce dernier pour extraire les informations utilisateur, la conversion des rôles
    Keycloak au format utilisé dans l'application, et la création d'une réponse utilisateur.

    :param code: Le code d'autorisation reçu via le rappel Keycloak
    :type code: str
    :param redirect_uri: L'URI de redirection configurée pour le client dans Keycloak
    :type redirect_uri: str
    :return: Un objet LoginResponse contenant le token d'accès, son type, des informations
    utilisateur associées, ainsi que la durée de validité du token en secondes.
    :rtype: LoginResponse
    :raises HTTPException: Lorsque le processus de rappel échoue, une exception est levée avec
    un message d'erreur approprié et un statut HTTP 400.
    """
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
    """
    Récupère les détails de l'utilisateur actuellement authentifié via Keycloak.

    Cette fonction interagit avec le système Keycloak pour obtenir les informations
    associées à l'utilisateur actuellement connecté. Les informations incluent le
    nom d'utilisateur, l'adresse email, le rôle, les permissions, le nom complet et
    le département. Ces données sont ensuite utilisées pour retourner un objet de
    type `User`.

    :param current_user: Le dictionnaire contenant les informations de l'utilisateur
        authentifié, fourni par la dépendance Keycloak.
    :return: Un objet `User` représentant l'utilisateur actuellement connecté.
    """
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
    """
    Démarre le traitement IA Keycloak pour l'utilisateur authentifié. Cette
    fonction effectue une vérification des permissions, génère un identifiant
    de session unique et initialise la communication avec le backend MCP.
    Elle enregistre également un message de progression initial.

    :param request: Dictionnaire contenant les données de la requête. Doit
        inclure une clé "question" de type chaîne de caractères.
    :type request: dict
    :param current_user: Dictionnaire contenant les informations de
        l'utilisateur connecté. Passé automatiquement via la dépendance
        `get_current_user_keycloak`.
    :type current_user: dict
    :return: Un dictionnaire contenant l'identifiant de session unique,
        l'état du démarrage, un message de confirmation et des informations
        sur l'utilisateur.
    :rtype: dict
    :raises HTTPException: Si l'utilisateur n'a pas les permissions
        nécessaires, si la clé "question" est manquante ou vide, ou en cas
        d'erreur de communication avec le backend MCP.
    """
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
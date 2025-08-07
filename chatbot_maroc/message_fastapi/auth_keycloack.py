from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from keycloak import KeycloakOpenID
from jose import jwt, JWTError
from typing import Dict, List
import logging

# Configuration Keycloak
KEYCLOAK_SERVER_URL = "http://localhost:8080"
KEYCLOAK_REALM = "AMDIE_CHATBOT"
KEYCLOAK_CLIENT_ID = "chatbot-amdie"

# Initialisation Keycloak
keycloak_openid = KeycloakOpenID(
    server_url=KEYCLOAK_SERVER_URL,
    client_id=KEYCLOAK_CLIENT_ID,
    realm_name=KEYCLOAK_REALM
)

security = HTTPBearer()
logger = logging.getLogger(__name__)


def keycloak_role_to_amdie_role(keycloak_roles: List[str]) -> str:
    """Convertit les rôles Keycloak vers tes rôles existants"""

    # DEBUG DÉTAILLÉ
    print(f" TOUS les rôles reçus: {keycloak_roles}")

    if 'admin' in keycloak_roles:
        print(" Rôle admin détecté -> admin")
        return 'admin'
    elif 'employee' in keycloak_roles:
        print(" Rôle employee détecté -> employee")
        return 'employee'
    elif 'public' in keycloak_roles:
        print(" Rôle public détecté -> public")
        return 'public'
    else:
        print(" AUCUN rôle reconnu -> public par défaut")
        print(f"   Rôles attendus: ['admin', 'employee', 'public']")
        print(f"   Rôles reçus: {keycloak_roles}")
        return 'public'  # Par défaut


def get_permissions_from_role(role: str) -> List[str]:
    """Reprend exactement le même système de permissions que ton auth.py"""
    permissions_map = {
        'public': [
            "read_public_docs",
            "chat_basic",
            "view_statistics"
        ],
        'employee': [
            "read_public_docs",
            "read_internal_docs",
            "chat_basic",
            "chat_advanced",
            "view_statistics",
            "view_internal_stats",
            "download_reports"
        ],
        'admin': [
            "read_public_docs",
            "read_internal_docs",
            "read_confidential_docs",
            "chat_basic",
            "chat_advanced",
            "chat_admin",
            "view_statistics",
            "view_internal_stats",
            "view_admin_stats",
            "download_reports",
            "manage_users",
            "upload_documents",
            "delete_documents"
        ]
    }
    return permissions_map.get(role, permissions_map['public'])


async def get_current_user_keycloak(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict:
    """Version Keycloak de get_current_user - même format de sortie que ton auth.py"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token invalide ou expiré",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # Récupérer la clé publique Keycloak
        public_key = keycloak_openid.public_key()
        keycloak_public_key = f"-----BEGIN PUBLIC KEY-----\n{public_key}\n-----END PUBLIC KEY-----"

        # Décoder le token JWT
        token_info = jwt.decode(
            credentials.credentials,
            keycloak_public_key,
            algorithms=["RS256"],
            audience="account"
        )

        # Extraire les infos utilisateur
        username = token_info.get('preferred_username', 'unknown')
        email = token_info.get('email', '')
        first_name = token_info.get('given_name', '')
        last_name = token_info.get('family_name', '')
        full_name = f"{first_name} {last_name}".strip() or username

        # Extraire les rôles Keycloak
        realm_access = token_info.get('realm_access', {})
        keycloak_roles = realm_access.get('roles', [])

        # Convertir vers ton format existant
        amdie_role = keycloak_role_to_amdie_role(keycloak_roles)
        permissions = get_permissions_from_role(amdie_role)

        department_map = {
            'public': 'External',
            'employee': 'Internal',
            'admin': 'Management'
        }

        # Retourner au même format que ton auth.py actuel
        return {
            'username': username,
            'email': email,
            'role': amdie_role,
            'permissions': permissions,
            'full_name': full_name,
            'department': department_map[amdie_role]
        }

    except JWTError as e:
        logger.error(f"Erreur JWT Keycloak: {e}")
        raise credentials_exception
    except Exception as e:
        logger.error(f"Erreur authentification Keycloak: {e}")
        raise credentials_exception


def check_permission_keycloak(user: Dict, required_permission: str) -> bool:
    """Même fonction que ton auth.py"""
    return required_permission in user.get("permissions", [])


def require_permission_keycloak(permission: str):
    """Même décorateur que ton auth.py mais avec Keycloak"""

    def permission_checker(current_user: Dict = Depends(get_current_user_keycloak)):
        if not check_permission_keycloak(current_user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission requise: {permission}"
            )
        return current_user

    return permission_checker


def get_keycloak_login_url() -> str:
    """URL pour rediriger vers Keycloak"""
    return keycloak_openid.auth_url(
        redirect_uri="http://localhost:3000/"
    )


def exchange_code_for_token(code: str, redirect_uri: str) -> dict:
    """Échanger le code OAuth contre un token"""
    try:
        return keycloak_openid.token(
            grant_type='authorization_code',
            code=code,
            redirect_uri=redirect_uri
        )
    except Exception as e:
        logger.error(f"Erreur échange token: {e}")
        raise HTTPException(status_code=400, detail="Code invalide")
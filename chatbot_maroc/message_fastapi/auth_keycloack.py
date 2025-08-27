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
    """
    Convertit un rôle de Keycloak en rôle AMDiE.

    Cette fonction prend en entrée une liste de rôles Keycloak et renvoie un
    rôle correspondant dans le système AMDiE. Les rôles possibles dans Keycloak
    sont vérifiés séquentiellement selon une priorité définie et convertis en
    « admin », « employee » ou « public ». Si aucun des rôles connus n'est
    trouvé, la fonction renvoie « public » par défaut.

    :param keycloak_roles: Liste des rôles en provenance de Keycloak.
    :type keycloak_roles: List[str]
    :return: Le rôle AMDiE correspondant au rôle Keycloak détecté.
    :rtype: str
    """

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
    """
    Récupère la liste des permissions associées à un rôle spécifique.

    Cette fonction permet de retourner les permissions correspondant à un rôle donné.
    Si le rôle spécifié n'est pas trouvé dans le dictionnaire des permissions,
    les permissions par défaut pour le rôle 'public' sont retournées.

    :param role: Le rôle pour lequel récupérer les permissions. Les valeurs possibles
        incluent 'public', 'employee' et 'admin'.
    :type role: str
    :return: Une liste de chaînes de caractères représentant les permissions associées
        au rôle spécifié. Si le rôle n'est pas trouvé, retourne les permissions par
        défaut pour le rôle 'public'.
    :rtype: List[str]
    """

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
    """
    Récupère les informations de l'utilisateur actuel via Keycloak.

    Cette fonction utilise les informations contenues dans le token JWT fourni par Keycloak pour
    extraire les données de l'utilisateur, telles que le nom, l'adresse e-mail, les rôles,
    et autres détails, et les formate en un dictionnaire compatible avec les exigences actuelles
    du système de gestion des rôles et permissions.

    :param credentials: Credentials JWT utilisés pour l'authentification, extraits automatiquement
                        via `Depends(security)`.
    :type credentials: HTTPAuthorizationCredentials
    :return: Dictionnaire contenant les informations de l'utilisateur, incluant son nom,
             adresse e-mail, rôle attribué, permissions associées, nom complet et département.
    :rtype: Dict
    :raises HTTPException: Si le token est invalide, expiré, ou incorrect.
    """
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

        amdie_role = keycloak_role_to_amdie_role(keycloak_roles)
        permissions = get_permissions_from_role(amdie_role)

        department_map = {
            'public': 'External',
            'employee': 'Internal',
            'admin': 'Management'
        }

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
    """
    Vérifie si un utilisateur dispose d'une permission requise dans une liste de
    permissions issues de Keycloak.

    Cela permet de s'assurer qu'un utilisateur possède les permissions nécessaires,
    telles que spécifiées dans `required_permission`, en vérifiant s'il est listé dans
    les permissions de l'utilisateur.

    :param user: Un dictionnaire représentant l'utilisateur, contenant potentiellement
                 une clé "permissions" listant les permissions dont l'utilisateur dispose.
    :param required_permission: Une chaîne de caractères représentant la permission
                                exigée à vérifier.
    :return: Retourne un booléen indiquant si la permission requise est présente parmi
             les permissions associées à l'utilisateur.
    """
    return required_permission in user.get("permissions", [])


def require_permission_keycloak(permission: str):
    """
    Vérifie si l'utilisateur authentifié dispose d'une permission spécifique dans Keycloak.

    Cette fonction génère un "dépend" (Depends) qui peut être utilisé dans les routes FastAPI
    pour restreindre l'accès aux utilisateurs ayant une permission donnée. Si la vérification
    échoue, une exception HTTP 403 est levée.

    :param permission: La permission spécifique requise pour accéder à une ressource.
    :type permission: str
    :return: Une fonction dépendante (checker) implémentant la vérification de permission.
    :rtype: Callable
    :raises HTTPException: Si l'utilisateur ne dispose pas de la permission requise.
    """

    def permission_checker(current_user: Dict = Depends(get_current_user_keycloak)):
        """
        Vérifie si l'utilisateur actuel possède les permissions nécessaires et
        lève une exception HTTP 403 si elles ne sont pas accordées.

        Cette fonction utilise un dictionnaire de l'utilisateur actuel obtenu à partir
        de l'authentification Keycloak et vérifie les permissions en appelant la
        fonction appropriée. Si l'utilisateur ne dispose pas des permissions requises,
        une exception HTTP sera déclenchée avec un message détaillant la permission
        demandée.

        :param current_user: Dictionnaire contenant les informations
            de l'utilisateur actuel, fourni par la dépendance Keycloak.
        :return: L'utilisateur actuel sous forme de dictionnaire si les permissions
            sont valides.
        :raises HTTPException: Si l'utilisateur ne dispose pas des permissions
            nécessaires, une exception HTTP avec un code 403 est levée.
        """
        if not check_permission_keycloak(current_user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission requise: {permission}"
            )
        return current_user

    return permission_checker


def get_keycloak_login_url(redirect_uri: str | None = None) -> str:
    """
    Génère une URL de connexion pour Keycloak avec l'URI de redirection spécifié.

    Si aucun `redirect_uri` n'est fourni, une valeur par défaut sera utilisée
    pour permettre un flux standard côté API. Cette méthode retourne une URL
    de point d'entrée pour démarrer un processus d'authentification OpenID
    avec Keycloak.

    :param redirect_uri: URI de redirection à utiliser après l'authentification.
        Si aucun URI n'est fourni, une valeur par défaut sera utilisée.
    :type redirect_uri: str | None
    :return: URL de connexion Keycloak générée avec l'URI de redirection.
    :rtype: str
    """
    if not redirect_uri:
        # valeur par défaut
        redirect_uri = "http://localhost:8000/api/v1/auth/keycloak/callback"

    return keycloak_openid.auth_url(
        redirect_uri=redirect_uri,
        scope="openid"
    )


def exchange_code_for_token(code: str, redirect_uri: str) -> dict:
    """
    Échange un code d'autorisation pour obtenir un jeton d'accès.

    Cette fonction permet d'obtenir un jeton d'accès en utilisant un code
    d'autorisation et une URI de redirection dans le cadre du flux
    d'autorisation OAuth 2.0.

    :param code: Le code d'autorisation obtenu depuis le fournisseur d'identité.
    :type code: str
    :param redirect_uri: L'URI de redirection utilisée pour obtenir le code
        d'autorisation.
    :type redirect_uri: str
    :return: Un dictionnaire contenant le jeton d'accès et les informations
        associées.
    :rtype: dict
    :raises HTTPException: Si une erreur se produit pendant le processus
        d'échange, une exception est levée avec un statut HTTP 400 et un message
        détaillant la cause de l'échec.
    """
    try:
        return keycloak_openid.token(
            grant_type='authorization_code',
            code=code,
            redirect_uri=redirect_uri
        )
    except Exception as e:
        logger.error(f"Erreur échange token: {e}")
        raise HTTPException(status_code=400, detail="Code invalide")
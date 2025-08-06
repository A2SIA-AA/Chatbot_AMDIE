from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import bcrypt
from models import User, UserRole, LoginRequest, LoginResponse

# Configuration JWT
SECRET_KEY = "amdie-chatbot-secret-key-2025"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480  # 8 heures

#pour une authentification réussie
security = HTTPBearer()

# Base de données utilisateurs (à modif pour une vraie DB)
USERS_DATABASE = {
    "public@demo.ma": {
        "username": "public_user",
        "email": "public@demo.ma",
        "hashed_password": bcrypt.hashpw("public123".encode(), bcrypt.gensalt()).decode(),
        "role": "public",
        "permissions": [
            "read_public_docs",
            "chat_basic",
            "view_statistics"
        ],
        "full_name": "Utilisateur Public",
        "department": "External"
    },
    "salarie@amdie.ma": {
        "username": "employee_user",
        "email": "salarie@amdie.ma",
        "hashed_password": bcrypt.hashpw("salarie123".encode(), bcrypt.gensalt()).decode(),
        "role": "employee",
        "permissions": [
            "read_public_docs",  # Hérite du public
            "read_internal_docs",  # Données internes
            "chat_basic",
            "chat_advanced",
            "view_statistics",
            "view_internal_stats",
            "download_reports"
        ],
        "full_name": "Employé AMDIE",
        "department": "Internal"
    },
    "admin@amdie.ma": {
        "username": "admin_user",
        "email": "admin@amdie.ma",
        "hashed_password": bcrypt.hashpw("admin123".encode(), bcrypt.gensalt()).decode(),
        "role": "admin",
        "permissions": [
            "read_public_docs",
            "read_internal_docs",
            "read_confidential_docs",  # Données confidentielles
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
        ],
        "full_name": "Administrateur AMDIE",
        "department": "Management"
    }
}


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Créer un token JWT"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Vérifier le mot de passe"""
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())


def authenticate_user(email: str, password: str) -> Optional[Dict]:
    """Authentifier un utilisateur"""
    user = USERS_DATABASE.get(email)
    if not user:
        return None
    if not verify_password(password, user["hashed_password"]):
        return None
    return user


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict:
    """Récupérer l'utilisateur courant depuis le token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token invalide ou expiré",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = USERS_DATABASE.get(email)
    if user is None:
        raise credentials_exception

    return user


def check_permission(user: Dict, required_permission: str) -> bool:
    """Vérifier si l'utilisateur a une permission"""
    return required_permission in user.get("permissions", [])


def require_permission(permission: str):
    """Décorateur pour exiger une permission"""

    def permission_checker(current_user: Dict = Depends(get_current_user)):
        #exécute d'abord get_current_user puis l'injecte dans la fonction
        if not check_permission(current_user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission requise: {permission}"
            )
        return current_user

    return permission_checker

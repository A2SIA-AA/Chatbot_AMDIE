from pydantic import BaseModel
from typing import Dict, Any, Optional
from enum import Enum

# ========================================
# TYPES DE MESSAGES POSSIBLES
# ========================================
class MessageType(str, Enum):
    """Types de messages que peuvent envoyer vos agents"""
    PROGRESS = "progress"      # Messages de progression : "RAG Agent: Recherche..."
    FINAL = "final"           # Réponse finale du chatbot
    ERROR = "error"           # Messages d'erreur
    AGENT_RESULT = "agent_result"  # Résultats d'agents avec confidence

# ========================================
# FORMAT DES DONNÉES REÇUES (Backend -> API)
# ========================================
class MessageRequest(BaseModel):
    """Ce que le backend Python envoie à l'API"""
    sessionId: str                           # ID de la session (ex: "session_123_abc")
    type: MessageType                        # Type du message (progress, final, error)
    content: str                            # Le message lui-même
    metadata: Optional[Dict[str, Any]] = {}  # Infos supplémentaires (agent_name, confidence, etc.)

# ========================================
# FORMAT DES DONNÉES ENVOYÉES (API -> Frontend)
# ========================================
class MessageResponse(BaseModel):
    """Ce que l'API renvoie au frontend"""
    type: str                    # Type du message
    content: str                # Le message
    timestamp: float            # Quand le message a été créé
    metadata: Dict[str, Any] = {} # Métadonnées additionnelles

# ========================================
# RÉPONSE POUR LISTE DE MESSAGES (API -> Frontend)
# ========================================
class MessagesResponse(BaseModel):
    """Quand le frontend demande les messages d'une session"""
    sessionId: str                    # Session demandée
    messages: list[MessageResponse]   # Liste des messages
    timestamp: float                  # Timestamp de la réponse
    messageCount: int                 # Nombre de messages retournés

# ========================================
# RÉPONSE DE SUCCÈS GÉNÉRIQUE
# ========================================
class SuccessResponse(BaseModel):
    """Réponse standard pour les opérations réussies"""
    success: bool                           # True/False
    message: Optional[str] = None           # Message explicatif optionnel

# ========================================
# FORMAT DE DONNÉES POUR L'AUTHENTIFICATION
# ========================================
class UserRole(str, Enum):
    PUBLIC = "public"
    EMPLOYEE = "employee"
    ADMIN = "admin"

from pydantic import BaseModel
from typing import List, Optional

class User(BaseModel):
    username: str
    email: str
    role: str
    permissions: List[str]
    full_name: str
    department: str


class KeycloakAuthUrl(BaseModel):
    auth_url: str
    state: Optional[str] = None

class TokenExchangeRequest(BaseModel):
    code: str
    redirect_uri: str

class LoginRequest(BaseModel):
    email: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user: User
    expires_in: int

class PermissionRequest(BaseModel):
    sessionId: str
    type: MessageType
    content: str
    metadata: Optional[Dict[str, Any]] = {}
    user_permissions: list[str] = []
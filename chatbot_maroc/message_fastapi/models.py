from pydantic import BaseModel
from typing import Dict, Any, Optional
from enum import Enum

# ========================================
# TYPES DE MESSAGES POSSIBLES
# ========================================
class MessageType(str, Enum):
    """
    Représente les types de messages dans une application ou un chatbot.

    Ce type énumératif est utilisé pour identifier différentes catégories de messages générés
    ou échangés dans le système. Il inclut des types tels que les messages de progression,
    les messages finaux, les erreurs, et les résultats d'agents. Ces types permettent une
    gestion organisée et structurée des messages.

    :ivar PROGRESS: Messages de progression, par exemple "RAG Agent: Recherche...".
    :type PROGRESS: str
    :ivar FINAL: Réponse finale du chatbot.
    :type FINAL: str
    :ivar ERROR: Messages indiquant des erreurs.
    :type ERROR: str
    :ivar AGENT_RESULT: Résultats d'agents incluant des informations de confiance.
    :type AGENT_RESULT: str
    """
    PROGRESS = "progress"      # Messages de progression : "RAG Agent: Recherche..."
    FINAL = "final"           # Réponse finale du chatbot
    ERROR = "error"           # Messages d'erreur
    AGENT_RESULT = "agent_result"  # Résultats d'agents avec confidence

# ========================================
# FORMAT DES DONNÉES REÇUES
# ========================================
class MessageRequest(BaseModel):
    """
    Représente une requête de message dans un contexte de communication.

    Cette classe est utilisée pour encapsuler les informations d'un message,
    incluant son contenu, son type et ses métadonnées. Elle permet de transmettre
    ces informations aux fichiers ou systèmes utilisant ce format.

    :ivar sessionId: ID unique de la session.
    :type sessionId: str
    :ivar type: Type de message, indiquant son statut ou sa catégorie
        (ex : progress, final, error).
    :type type: MessageType
    :ivar content: Contenu textuel du message.
    :type content: str
    :ivar metadata: Métadonnées optionnelles associées au message, pouvant contenir
        des informations supplémentaires comme le nom de l'agent ou un indice
        de confiance.
    :type metadata: Optional[Dict[str, Any]]
    """
    sessionId: str                           # ID de la session (ex: "session_123_abc")
    type: MessageType                        # Type du message (progress, final, error)
    content: str                            # Le message lui-même
    metadata: Optional[Dict[str, Any]] = {}  # Infos supplémentaires (agent_name, confidence, etc.)

# ========================================
# FORMAT DES DONNÉES ENVOYÉES (API -> Frontend)
# ========================================
class MessageResponse(BaseModel):
    """
    Représentation d'une réponse de message.

    Cette classe est utilisée pour encapsuler les informations
    relatives à un message, telles que son type, son contenu, et
    son horodatage, ainsi que des métadonnées additionnelles.

    :ivar type: Type du message.
    :type type: str
    :ivar content: Contenu textuel du message.
    :type content: str
    :ivar timestamp: Horodatage indiquant quand le message a été créé.
    :type timestamp: float
    :ivar metadata: Métadonnées additionnelles associées au message.
    :type metadata: Dict[str, Any]
    """
    type: str                    # Type du message
    content: str                # Le message
    timestamp: float            # Quand le message a été créé
    metadata: Dict[str, Any] = {} # Métadonnées additionnelles

# ========================================
# RÉPONSE POUR LISTE DE MESSAGES (API -> Frontend)
# ========================================
class MessagesResponse(BaseModel):
    """
    Résumé de ce que fait la classe.

    Description détaillée de la classe, son objectif et son utilisation.

    :ivar sessionId: Identifiant de la session demandée.
    :type sessionId: str
    :ivar messages: Liste des messages retournés dans la réponse.
    :type messages: list[MessageResponse]
    :ivar timestamp: Timestamp de la réponse en format float.
    :type timestamp: float
    :ivar messageCount: Nombre total de messages retournés.
    :type messageCount: int
    """
    sessionId: str                    # Session demandée
    messages: list[MessageResponse]   # Liste des messages
    timestamp: float                  # Timestamp de la réponse
    messageCount: int                 # Nombre de messages retournés

# ========================================
# RÉPONSE DE SUCCÈS GÉNÉRIQUE
# ========================================
class SuccessResponse(BaseModel):
    """
    Représentation d'une réponse indiquant le succès d'une opération.

    Cette classe est utilisée pour fournir une réponse standardisée contenant des informations
    sur le succès d'une opération et un message explicatif optionnel.

    :ivar success: Indique si l'opération est réussie ou non.
    :type success: bool
    :ivar message: Un message explicatif optionnel pour fournir plus de contexte ou des détails.
    :type message: Optional[str]
    """
    success: bool                           # True/False
    message: Optional[str] = None           # Message explicatif optionnel

# ========================================
# FORMAT DE DONNÉES POUR L'AUTHENTIFICATION
# ========================================
class UserRole(str, Enum):
    """
    Représente les rôles d'un utilisateur dans le système.

    Cette classe énumère les différents rôles possibles pour un utilisateur,
    tels que PUBLIC, EMPLOYEE ou ADMIN, et offre une structure standardisée
    pour leur utilisation.

    :ivar PUBLIC: Rôle indiquant un utilisateur public, avec un accès limité aux
        fonctionnalités du système.
    :ivar EMPLOYEE: Rôle indiquant un utilisateur employé, avec un accès étendu
        aux fonctionnalités professionnelles du système.
    :ivar ADMIN: Rôle indiquant un utilisateur administrateur, avec des
        privilèges complets pour gérer le système.
    """
    PUBLIC = "public"
    EMPLOYEE = "employee"
    ADMIN = "admin"

from pydantic import BaseModel
from typing import List, Optional

class User(BaseModel):
    """
    Représentation d'un utilisateur dans le système.

    Cette classe fournit une structure pour stocker et manipuler les informations
    relatives à un utilisateur. Elle inclut des détails tels que le nom d'utilisateur,
    l'adresse électronique, le rôle, les permissions associées, le nom complet
    et le département auquel l'utilisateur appartient.

    :ivar username: Nom d'utilisateur unique utilisé pour l'identification.
    :type username: str
    :ivar email: Adresse électronique de l'utilisateur.
    :type email: str
    :ivar role: Rôle attribué à l'utilisateur, indiquant son niveau d'accès.
    :type role: str
    :ivar permissions: Liste des permissions associées à l'utilisateur.
    :type permissions: List[str]
    :ivar full_name: Nom complet de l'utilisateur.
    :type full_name: str
    :ivar department: Département auquel l'utilisateur appartient.
    :type department: str
    """
    username: str
    email: str
    role: str
    permissions: List[str]
    full_name: str
    department: str


class KeycloakAuthUrl(BaseModel):
    """
    Fournit un modèle pour l'URL d'authentification Keycloak.

    Ce modèle est utilisé pour gérer les informations nécessaires
    pour construire ou traiter une URL d'authentification Keycloak,
    incluant l'URL principale d'authentification et un état optionnel.

    :ivar auth_url: URL de base utilisée pour l'authentification Keycloak.
    :type auth_url: str
    :ivar state: État optionnel utilisé pour suivre des informations
        entre l'utilisateur et le serveur lors de l'authentification.
    :type state: Optional[str]
    """
    auth_url: str
    state: Optional[str] = None

class TokenExchangeRequest(BaseModel):
    """
    Représentation d'une requête d'échange de jeton.

    Cette classe modélise une requête envoyée pour échanger un code d'autorisation
    contre un jeton. Les paramètres incluent le code d'autorisation obtenu
    lors du processus d'authentification et l'URI de redirection utilisée
    pour générer ce code.

    :ivar code: Code d'autorisation utilisé pour l'échange de jeton.
    :type code: str
    :ivar redirect_uri: URI de redirection associée au code d'autorisation.
    :type redirect_uri: str
    """
    code: str
    redirect_uri: str

class LoginRequest(BaseModel):
    """
    Représentation d'une demande de connexion.

    Classe utilisée pour encapsuler les informations nécessaires pour une
    tentative de connexion, telles que l'adresse email et le mot de passe.

    :ivar email: Adresse email liée au compte utilisateur.
    :type email: str
    :ivar password: Mot de passe associé à l'utilisateur.
    :type password: str
    """
    email: str
    password: str

class LoginResponse(BaseModel):
    """
    Contient la réponse de connexion.

    Cette classe représente la structure d'une réponse de connexion, contenant des informations
    sur le jeton d'accès, le type de jeton, les détails de l'utilisateur, et la durée d'expiration du jeton.

    :ivar access_token: Le jeton d'accès qui permet de confirmer l'authentification de l'utilisateur.
    :type access_token: str
    :ivar token_type: Le type de jeton utilisé (par exemple, Bearer).
    :type token_type: str
    :ivar user: Les informations de l'utilisateur authentifié.
    :type user: User
    :ivar expires_in: La durée de validité du jeton (en secondes).
    :type expires_in: int
    """
    access_token: str
    token_type: str
    user: User
    expires_in: int

class PermissionRequest(BaseModel):
    """
    Représentation d'une demande de permission.

    Modélise une demande de permission comprenant les informations relatives à une
    session utilisateur, le type de message associé, le contenu, des métadonnées
    facultatives ainsi qu'une liste des permissions de l'utilisateur.

    :ivar sessionId: Identifiant unique de la session utilisateur.
    :type sessionId: str
    :ivar type: Type de message représenté par une instance de MessageType.
    :type type: MessageType
    :ivar content: Contenu textuel associé à la demande de permission.
    :type content: str
    :ivar metadata: Dictionnaire facultatif contenant des métadonnées supplémentaires.
    :type metadata: dict[str, Any], optionnel
    :ivar user_permissions: Liste des permissions actuelles de l'utilisateur.
    :type user_permissions: list[str]
    """
    sessionId: str
    type: MessageType
    content: str
    metadata: Optional[Dict[str, Any]] = {}
    user_permissions: list[str] = []
import pandas as pd
from typing import Dict, List, Optional, TypedDict, Any


# =============================================================================
# ÉTAT PARTAGÉ ENTRE TOUS LES AGENTS - AVEC SUPPORT JWT
# =============================================================================

class ChatbotState(TypedDict):
    """
    État partagé entre tous les agents du chatbot avec gestion JWT

    AJOUTS pour votre système d'authentification:
    - user_role: Rôle JWT (public, employee, admin)
    - user_permissions: Permissions spécifiques JWT

    Structure conservée de votre code original
    """

    # ========================================
    # CHAMPS ORIGINAUX CONSERVÉS
    # ========================================
    question_utilisateur: str  # Question originale de l'utilisateur
    tableaux_pertinents: List[Dict]  # 10 tableaux trouvés par RAG
    tableaux_charges: List[Dict]  # Données complètes des tableaux
    tableaux_pour_upload: List[Dict]  # Tableaux sélectionnés pour upload (3-5)
    tableaux_reference: List[Dict]  # Tous les tableaux pour référence
    explication_selection: Optional[str]  # Justification de la sélection Gemini
    reponse_analyseur_brute: Optional[str]  # Réponse brute de l'analyseur
    reponse_analyseur_texte_brut: Optional[str]
    besoin_calculs: bool  # Est-ce qu'on a besoin de pandas ?
    instruction_calcul: Optional[str]  # Que doit calculer pandas ?
    code_pandas: Optional[str]  # Code généré par l'agent pandas
    algo_genere: Optional[str]  # Algo généré par l'agent analyse
    dataframes: List[pd.DataFrame]  # liste des dataframes
    resultat_pandas: Optional[Any]  # Résultat du code pandas
    erreur_pandas: Optional[str]  # Erreur si pandas échoue
    reponse_finale: str  # Réponse finale à l'utilisateur
    historique: List[str]  # Log des étapes pour debug
    fichiers_gemini: List[Any]  # Fichiers à upload à Gemini
    fichiers_csvs_local: List[Any]  # Fichiers utile pour pouvoir uploader à Gemini
    documents_trouves: List[Dict]  # TOUS les documents trouvés
    documents_selectionnes: List[Dict]  # Docs selectionnés (tout type)
    tableau_pour_calcul: Optional[Dict]  # Quel tableau utiliser pour pandas ?
    pdfs_pour_contexte: List[Dict]  # pdfs selectionnes
    session_id: str
    user_role: Optional[str]  # Rôle JWT: 'public', 'employee', 'admin'
    user_permissions: Optional[List[str]]  # Permissions spécifiques JWT
    username: Optional[str]  # Nom d'utilisateur Keycloak pour historique
    email: Optional[str]  # Email utilisateur pour historique
import pandas as pd
from typing import Dict, List, Optional, TypedDict, Any


# =============================================================================
# ÉTAT PARTAGÉ ENTRE TOUS LES AGENTS - AVEC SUPPORT JWT
# =============================================================================

class ChatbotState(TypedDict):
    """
    Représente l'état d'un chatbot avec les données pertinentes pour les interactions
    et calculs associés.

    Cette classe modélise les informations nécessaires pour l'interaction d'un chatbot
    avec l'utilisateur, y compris les questions posées, les documents pertinents
    trouvés, les calculs optionnels à réaliser, les réponses produites, ainsi que
    les données liées à l'historique et aux permissions utilisateur.

    :ivar question_utilisateur: Question originale posée par l'utilisateur.
    :type question_utilisateur: str
    :ivar tableaux_pertinents: Liste des 10 tableaux identifiés comme pertinents
        dans une recherche RAG.
    :type tableaux_pertinents: List[Dict]
    :ivar pdfs_pertinents: Liste des PDF identifiés comme pertinents pour la réponse.
    :type pdfs_pertinents: List[Dict]
    :ivar tableaux_charges: Données complètes des tableaux chargés pour utilisation.
    :type tableaux_charges: List[Dict]
    :ivar pdfs_charges: Données complètes des PDF chargés pour utilisation.
    :type pdfs_charges: List[Dict]
    :ivar tableaux_pour_upload: Tableaux sélectionnés pour être uploadés (entre 3 et 5).
    :type tableaux_pour_upload: List[Dict]
    :ivar pdfs_pour_upload: PDF sélectionnés pour être uploadés.
    :type pdfs_pour_upload: List[Dict]
    :ivar tableaux_reference: Liste complète de tous les tableaux trouvés qui peuvent
        être utilisés comme référence.
    :type tableaux_reference: List[Dict]
    :ivar explication_selection: Justification de la sélection des ressources par
        le mécanisme Gemini.
    :type explication_selection: Optional[str]
    :ivar reponse_analyseur_brute: Réponse brute produite par l'analyseur.
    :type reponse_analyseur_brute: Optional[str]
    :ivar reponse_analyseur_texte_brut: Version texte brut de la réponse de l'analyseur.
    :type reponse_analyseur_texte_brut: Optional[str]
    :ivar besoin_calculs: Indique si des calculs pandas sont nécessaires ou non.
    :type besoin_calculs: bool
    :ivar instruction_calcul: Instructions spécifiques pour effectuer les calculs pandas.
    :type instruction_calcul: Optional[str]
    :ivar code_pandas: Code pandas généré automatiquement par l'agent pour
        effectuer les calculs requis.
    :type code_pandas: Optional[str]
    :ivar algo_genere: Algorithme généré par l'agent d'analyse.
    :type algo_genere: Optional[str]
    :ivar dataframes: Liste des DataFrames pandas utilisés pour le traitement.
    :type dataframes: List[pd.DataFrame]
    :ivar resultat_pandas: Résultat de l'exécution du code pandas.
    :type resultat_pandas: Optional[Any]
    :ivar erreur_pandas: Message d'erreur produit si une exécution pandas échoue.
    :type erreur_pandas: Optional[str]
    :ivar reponse_finale: Réponse finale générée par le chatbot pour l'utilisateur.
    :type reponse_finale: str
    :ivar historique: Liste des étapes et logs pour une analyse de débogage.
    :type historique: List[str]
    :ivar fichiers_gemini: Liste des fichiers destinés à être uploadés au service Gemini.
    :type fichiers_gemini: List[Any]
    :ivar fichiers_csvs_local: Fichiers locaux utilisés pour faciliter le téléchargement
        vers Gemini.
    :type fichiers_csvs_local: List[Any]
    :ivar documents_trouves: Liste de tous les documents trouvés qui pourraient
        être pertinents.
    :type documents_trouves: List[Dict]
    :ivar documents_selectionnes: Liste des documents sélectionnés pour traitement,
        quel que soit leur type.
    :type documents_selectionnes: List[Dict]
    :ivar tableau_pour_calcul: Tableau spécifique sélectionné pour exécuter des calculs
        pandas.
    :type tableau_pour_calcul: Optional[Dict]
    :ivar pdfs_pour_contexte: Liste des PDF spécifiques sélectionnés pour fournir
        du contexte.
    :type pdfs_pour_contexte: List[Dict]
    :ivar session_id: Identifiant unique de la session en cours pour tracer les interactions.
    :type session_id: str
    :ivar user_role: Rôle de l'utilisateur basé sur la sécurité JWT, tels que 'public',
        'employee' ou 'admin'.
    :type user_role: Optional[str]
    :ivar user_permissions: Liste des permissions utilisateur spécifiques dérivées
        du JWT.
    :type user_permissions: Optional[List[str]]
    :ivar username: Nom d'utilisateur attribué dans Keycloak, utilisé pour l'historique.
    :type username: Optional[str]
    :ivar email: Adresse e-mail de l'utilisateur utilisée pour tracer l'historique
        des interactions.
    :type email: Optional[str]
    :ivar documents_pdf: Liste des documents PDF trouvés lors des recherches.
    :type documents_pdf: List[Dict]
    :ivar documents_excel: Liste des documents Excel trouvés lors des recherches.
    :type documents_excel: List[Dict]
    :ivar processing_mode: Mode de traitement des documents, tel que 'excel_only',
        'pdf_only', 'both', ou 'no_documents'.
    :type processing_mode: str
    :ivar reponse_finale_pdf: Réponse finale spécifique générée à l'aide des documents PDF.
    :type reponse_finale_pdf: str
    :ivar sources_pdf: Liste des sources PDF référencées.
    :type sources_pdf: List[str]
    :ivar excel_empty: Indique l'absence éventuelle de données dans un document Excel.
    :type excel_empty: str
    """

    # ========================================
    # CHAMPS ORIGINAUX CONSERVÉS
    # ========================================
    question_utilisateur: str  # Question originale de l'utilisateur
    tableaux_pertinents: List[Dict]  # 10 tableaux trouvés par RAG
    pdfs_pertinents: List[Dict]
    tableaux_charges: List[Dict]  # Données complètes des tableaux
    pdfs_charges: List[Dict]
    tableaux_pour_upload: List[Dict]  # Tableaux sélectionnés pour upload (3-5)
    pdfs_pour_upload: List[Dict]
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

    documents_pdf: List[Dict]  # Documents PDF trouvés
    documents_excel: List[Dict]  # Documents Excel trouvés
    processing_mode: str  # Mode: 'excel_only', 'pdf_only', 'both', 'no_documents'
    reponse_finale_pdf: str  # Réponse spécifique aux PDF
    sources_pdf: List[str]
    excel_empty: str
import time
from langgraph.graph import StateGraph, END
import google.generativeai as genai
import sys
from typing import List

from .state import ChatbotState
from ..agents.pandas_agent import SimplePandasAgent
from ..agents.code_agent import CodeAgent
from ..agents.synthesis_agent import SynthesisAgent

# AGENTS UNIFIÉS
from ..agents.rag_agent_unified import RAGAgentUnified
from ..agents.selector_agent_unified import SelectorAgentUnified
from ..agents.analyzer_agent_unified import AnalyzerAgentUnified

from ..core.memory_store import conversation_memory

sys.path[:0] = ['../../']
from config.logging import setup_logging, PerformanceLogger
from config.setting import get_settings


class ChatbotMarocV2Simplified:
    """
    Chatbot pour analyser les données du Maroc avec support Excel + PDF
    """

    def __init__(self, rag_index, user_permissions: List[str] = None, user_role: str = "guest", settings=None):
        """
        Initialisation du chatbot avec support unifié Excel + PDF

        Args:
            rag_index: Index RAG existant
            user_permissions: Liste des permissions de l'utilisateur connecté
            user_role: Rôle de l'utilisateur (public, employee, admin)
            settings: Configuration existante
        """

        # Configuration existante
        self.settings = get_settings() if settings is None else settings
        self.rag = rag_index

        # Setup logging existant
        self.logger = setup_logging(self.settings)
        self.perf_logger = PerformanceLogger(self.settings)

        # Configuration Gemini existante
        genai.configure(api_key=self.settings.gemini_api_key)
        self.gemini_model = genai.GenerativeModel('gemini-2.5-flash')

        # Support des permissions utilisateur
        self.user_permissions = user_permissions or ["read_public_docs"]
        self.user_role = user_role

        # Agent pandas existant
        self.pandas_agent = SimplePandasAgent(self.gemini_model)

        # AGENTS UNIFIÉS (SIMPLES ET ROBUSTES)
        self.rag_agent = RAGAgentUnified(self.rag, self)
        self.selector_agent = SelectorAgentUnified(self.gemini_model, self)
        self.analyzer_agent = AnalyzerAgentUnified(self.gemini_model, self)
        self.code_agent = CodeAgent(self.gemini_model, self)
        self.synthesis_agent = SynthesisAgent(self.gemini_model, self)

        # Créer le graphe LangGraph ULTRA-SIMPLIFIÉ
        self.graph = self._creer_graphe_simplifie()

        print(f"Chatbot V2 Simplifié initialisé pour utilisateur {user_role} avec permissions: {user_permissions}")

    def _log(self, message: str, state: ChatbotState):
        """Ajoute un message au log ET l'affiche pour le frontend"""
        self.logger.info(message)

        # Vérifier si 'historique' existe avant d'y accéder
        if 'historique' not in state:
            state['historique'] = []

        state['historique'].append(message)

        # Ligne pour le frontend
        print(f"PROGRESS:{message}", file=sys.stderr)

    def _log_with_permissions(self, message: str, state: ChatbotState):
        """Version enrichie du log qui inclut le niveau d'accès"""
        enriched_message = f"[{self.user_role.upper()}] {message}"
        self.logger.info(enriched_message)

        # Vérifier si 'historique' existe avant d'y accéder
        if 'historique' not in state:
            state['historique'] = []

        state['historique'].append(enriched_message)

        # Pour le frontend avec indicateur de permission
        role_indicator = {'public': '[PUBLIC]', 'employee': '[EMPLOYE]', 'admin': '[ADMIN]'}.get(self.user_role,
                                                                                                 '[USER]')
        print(f"PROGRESS:{role_indicator} {message}", file=sys.stderr)

    def _log_error(self, error: str, state: ChatbotState):
        """Log spécialisé pour les erreurs"""
        error_msg = f"ERREUR: {error}"
        self.logger.error(error_msg)

        # Vérifier si 'historique' existe avant d'y accéder
        if 'historique' not in state:
            state['historique'] = []

        state['historique'].append(error_msg)

    def _creer_graphe_simplifie(self) -> StateGraph:
        """
        Crée le graphe LangGraph ULTRA-SIMPLIFIÉ

        FLUX LINÉAIRE :
        RAG → Selector → Analyzer → [Code si calculs] → Synthesis

        UNE SEULE CONDITION : Calculs nécessaires ou pas
        """

        graph = StateGraph(ChatbotState)

        # NOEUDS PRINCIPAUX (SIMPLES)
        graph.add_node("rag_unified", self.rag_agent.execute)
        graph.add_node("selector_unified", self.selector_agent.execute)
        graph.add_node("analyzer_unified", self.analyzer_agent.execute)
        graph.add_node("generateur_code", self.code_agent.execute)
        graph.add_node("synthese", self.synthesis_agent.execute)

        # FLUX LINÉAIRE ULTRA-SIMPLE
        graph.set_entry_point("rag_unified")
        graph.add_edge("rag_unified", "selector_unified")

        # Vérification documents disponibles
        graph.add_conditional_edges(
            "selector_unified",
            self._has_documents,
            {
                "no_documents": "synthese",  # Aucun document → Synthèse directe
                "has_documents": "analyzer_unified"  # Documents disponibles → Analyse
            }
        )

        # UNE SEULE CONDITION : Calculs nécessaires ?
        graph.add_conditional_edges(
            "analyzer_unified",
            self._needs_calculations,
            {
                "calculations": "generateur_code",  # Calculs détectés → Code
                "direct": "synthese"  # Réponse directe → Synthèse
            }
        )

        # Après calculs → Synthèse
        graph.add_edge("generateur_code", "synthese")

        # Fin
        graph.add_edge("synthese", END)

        return graph.compile()

    def _has_documents(self, state: ChatbotState) -> str:
        """
        Vérification simple : Y a-t-il des documents à traiter ?
        """
        tableaux = state.get('tableaux_pour_upload', [])
        pdfs = state.get('pdfs_pour_upload', [])

        total_documents = len(tableaux) + len(pdfs)

        if total_documents > 0:
            self._log(f"Documents disponibles: {len(tableaux)} Excel + {len(pdfs)} PDFs", state)
            return "has_documents"
        else:
            self._log("Aucun document disponible pour traitement", state)
            return "no_documents"

    def _needs_calculations(self, state: ChatbotState) -> str:
        """
        CONDITION UNIQUE ET SIMPLE : Calculs nécessaires ?

        L'analyzer_unified a fait son travail et a décidé :
        - Si calculs nécessaires : state['besoin_calculs'] = True
        - Sinon : réponses directes dans state['reponse_finale'] et/ou state['reponse_finale_pdf']
        """

        besoin_calculs = state.get('besoin_calculs', False)

        if besoin_calculs:
            # Vérifier que les prérequis sont présents
            if state.get('algo_genere') and state.get('instruction_calcul') and state.get('dataframes'):
                self._log("CALCULS NÉCESSAIRES - Génération de code", state)
                return "calculations"
            else:
                # Problème avec les prérequis calculs
                self._log("ERREUR: Calculs demandés mais prérequis manquants - Synthèse directe", state)
                return "direct"
        else:
            # Réponse directe ou pas de calculs nécessaires
            self._log("PAS DE CALCULS - Synthèse directe", state)
            return "direct"

    def poser_question_id(self, question: str, session_id: str = None, username: str = None, email: str = None) -> str:
        """Interface principale avec gestion d'erreurs complète + historique"""
        return self.poser_question_with_permissions(question, session_id, self.user_permissions, username, email)

    def poser_question_with_permissions(self, question: str, session_id: str = None,
                                        user_permissions: List[str] = None, username: str = None,
                                        email: str = None) -> str:
        """
        Méthode principale simplifiée qui gère les permissions et le support PDF/Excel

        Args:
            question: Question de l'utilisateur
            session_id: ID de session
            user_permissions: Permissions spécifiques (override les permissions de l'instance)
        """

        start_time = time.time()
        active_permissions = user_permissions or self.user_permissions

        # Validation existante
        if not question.strip():
            return "Veuillez poser une question valide."

        print(f"Question reçue pour {self.user_role}: '{question[:50]}...'", file=sys.stderr)

        # État initial COMPLET avec tous les champs nécessaires
        etat_initial = ChatbotState(
            # Champs de base
            question_utilisateur=question.strip(),
            session_id=session_id,
            user_role=self.user_role,
            user_permissions=active_permissions,
            username=username,
            email=email,
            historique=[],

            # Champs RAG
            documents_trouves=[],
            tableaux_pertinents=[],
            pdfs_pertinents=[],

            # Champs chargement
            tableaux_charges=[],
            pdfs_charges=[],
            tableaux_reference=[],

            # Champs sélection
            tableaux_pour_upload=[],
            pdfs_pour_upload=[],
            explication_selection=None,

            # Champs analyse Excel
            dataframes=[],
            reponse_analyseur_brute=None,
            besoin_calculs=False,
            instruction_calcul=None,
            algo_genere=None,
            excel_empty="",

            # Champs calculs
            code_pandas=None,
            resultat_pandas=None,
            erreur_pandas=None,
            fichiers_gemini=[],
            fichiers_csvs_local=[],
            tableau_pour_calcul=None,

            # Champs analyse PDF
            reponse_analyseur_texte_brut=None,
            reponse_finale_pdf="",
            sources_pdf=[],

            # Champs compatibilité
            documents_selectionnes=[],
            pdfs_pour_contexte=[],
            documents_excel=[],
            documents_pdf=[],

            # Résultat final
            reponse_finale="",

            processing_mode=""
        )

        try:
            # Log initial avec permissions
            self._log_with_permissions(f"Démarrage analyse avec niveau d'accès {self.user_role}", etat_initial)

            # WORKFLOW SIMPLIFIÉ
            etat_final = self.graph.invoke(etat_initial)

            # Logs de succès
            duration = time.time() - start_time
            self.perf_logger.log_request_metrics(question, duration, True)

            # Enrichir la réponse finale avec info de permissions
            reponse_base = etat_final.get('reponse_finale', "Aucune réponse générée.")
            reponse_enrichie = self._enrichir_reponse_avec_permissions(reponse_base, etat_final)

            # SAUVEGARDE AUTOMATIQUE DANS L'HISTORIQUE
            if username and email:
                try:
                    success = conversation_memory.save_conversation(
                        username=username,
                        email=email,
                        question=question.strip(),
                        reponse=reponse_enrichie,
                        session_id=session_id
                    )
                    if success:
                        self._log(f"Conversation sauvegardée pour {username}", etat_final)
                        stats = conversation_memory.get_conversation_stats(username, email)
                        self._log(f"Stats: {stats['total_conversations']} total, {stats['conversations_24h']} récentes",
                                  etat_final)
                    else:
                        self._log("Erreur sauvegarde conversation", etat_final)
                except Exception as e:
                    self._log_error(f"Erreur sauvegarde historique: {e}", etat_final)
            else:
                self._log("Username/email manquants, pas de sauvegarde historique", etat_final)

            return reponse_enrichie

        except Exception as e:
            # Gestion d'erreur
            duration = time.time() - start_time
            error_msg = f"Erreur système: {str(e)}"
            self.perf_logger.log_request_metrics(question, duration, False, error_msg)

            self.logger.error(f"Erreur critique pour {self.user_role}: {error_msg}")
            return f"ERREUR: {error_msg}. Votre niveau d'accès: {self.user_role.upper()}. Veuillez réessayer."

    def _enrichir_reponse_avec_permissions(self, reponse_base: str, etat_final: ChatbotState) -> str:
        """Enrichit la réponse avec les informations de permissions"""

        # Indicateurs visuels par rôle
        role_indicators = {
            'public': '**Accès Public**',
            'employee': '**Accès Employé**',
            'admin': '**Accès Administrateur**'
        }

        indicator = role_indicators.get(self.user_role, '**Accès Limité**')

        # Compter les documents utilisés par niveau d'accès
        tableaux_utilises = etat_final.get('tableaux_charges', [])
        pdfs_utilises = etat_final.get('pdfs_charges', [])

        stats_acces = {'public': 0, 'internal': 0, 'confidential': 0}

        # Compter Excel
        for tableau in tableaux_utilises:
            if isinstance(tableau, dict):
                access_level = tableau.get('access_level', 'public')
                if access_level in stats_acces:
                    stats_acces[access_level] += 1

        # Compter PDFs
        for pdf in pdfs_utilises:
            if isinstance(pdf, dict):
                access_level = pdf.get('access_level', 'public')
                if access_level in stats_acces:
                    stats_acces[access_level] += 1

        # Construction de la réponse enrichie
        reponse_enrichie = f"{indicator}\n\n{reponse_base}"

        # Ajouter les stats d'accès si des documents ont été utilisés
        total_docs = sum(stats_acces.values())
        if total_docs > 0:
            reponse_enrichie += f"\n\n**Sources consultées :**\n"
            if stats_acces['public'] > 0:
                reponse_enrichie += f"- [PUBLIC] {stats_acces['public']} document(s) public(s)\n"
            if stats_acces['internal'] > 0:
                reponse_enrichie += f"- [INTERNE] {stats_acces['internal']} document(s) interne(s)\n"
            if stats_acces['confidential'] > 0:
                reponse_enrichie += f"- [CONFIDENTIEL] {stats_acces['confidential']} document(s) confidentiel(s)\n"

        # Info debug pour les admins
        if self.user_role == 'admin':
            permissions_safe = self.user_permissions or ["unknown_permissions"]
            if isinstance(permissions_safe, list):
                permissions_str = ', '.join(permissions_safe)
            else:
                permissions_str = str(permissions_safe)
            reponse_enrichie += f"\n**Debug Admin :** Permissions actives: {permissions_str}"

        return reponse_enrichie

    # MÉTHODES UTILITAIRES CONSERVÉES
    def get_user_conversation_history(self, username: str, email: str, limit: int = 10) -> dict:
        """Récupère l'historique des conversations d'un utilisateur"""
        try:
            history = conversation_memory.get_user_history_24h(username, email, limit)
            stats = conversation_memory.get_conversation_stats(username, email)
            context = conversation_memory.format_history_for_context(username, email, limit // 2)

            return {
                "username": username,
                "email": email,
                "conversations": history,
                "stats": stats,
                "context_for_ai": context,
                "total_returned": len(history)
            }
        except Exception as e:
            self.logger.error(f"Erreur récupération historique: {e}")
            return {
                "username": username,
                "email": email,
                "conversations": [],
                "stats": {"total_conversations": 0, "conversations_24h": 0},
                "context_for_ai": "",
                "total_returned": 0,
                "error": str(e)
            }

    def clear_user_conversation_history(self, username: str, email: str) -> dict:
        """Supprime l'historique d'un utilisateur"""
        try:
            deleted_count = conversation_memory.delete_user_conversations(username, email)

            return {
                "success": True,
                "deleted_conversations": deleted_count,
                "username": username,
                "email": email
            }
        except Exception as e:
            self.logger.error(f"Erreur suppression historique: {e}")
            return {
                "success": False,
                "error": str(e),
                "username": username,
                "email": email
            }

    def poser_question(self, question: str, username: str = None, email: str = None) -> str:
        """Interface simple pour compatibilité avec l'ancien code"""
        return self.poser_question_with_permissions(
            question=question,
            session_id=None,
            user_permissions=None,
            username=username,
            email=email
        )
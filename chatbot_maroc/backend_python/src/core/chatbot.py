import time
from langgraph.graph import StateGraph, END
import google.generativeai as genai
import sys
from typing import List

from .state import ChatbotState
from ..agents.pandas_agent import SimplePandasAgent
from ..agents.rag_agent import RAGAgent
from ..agents.selector_agent import SelectorAgent
from ..agents.analyzer_agent import AnalyzerAgent
from ..agents.code_agent import CodeAgent
from ..agents.synthesis_agent import SynthesisAgent
from ..core.memory_store import conversation_memory

sys.path[:0] = ['../../']
from config.logging import setup_logging, PerformanceLogger
from config.setting import get_settings


class ChatbotMarocSessionId:
    """Chatbot pour analyser les données du Maroc avec support des permissions"""

    def __init__(self, rag_index, user_permissions: List[str] = None, user_role: str = "guest", settings=None):
        """
        Initialisation du chatbot avec support des permissions utilisateur

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

        # Initialiser tous les agents (on passe self pour accès aux permissions)
        self.rag_agent = RAGAgent(self.rag, self)
        self.selector_agent = SelectorAgent(self.gemini_model, self)
        self.analyzer_agent = AnalyzerAgent(self.gemini_model, self)
        self.code_agent = CodeAgent(self.gemini_model, self)
        self.synthesis_agent = SynthesisAgent(self.gemini_model, self)

        # Créer le graphe LangGraph
        self.graph = self._creer_graphe()

        print(f"Chatbot initialisé pour utilisateur {user_role} avec permissions: {user_permissions}")

    def _log(self, message: str, state: ChatbotState):
        """Ajoute un message au log ET l'affiche pour le frontend"""
        self.logger.info(message)
        state['historique'].append(message)

        # Ligne pour le frontend
        print(f"PROGRESS:{message}", file=sys.stderr)

    def _log_with_permissions(self, message: str, state: ChatbotState):
        """Version enrichie du log qui inclut le niveau d'accès"""
        enriched_message = f"[{self.user_role.upper()}] {message}"
        self.logger.info(enriched_message)
        state['historique'].append(enriched_message)

        # Pour le frontend avec indicateur de permission
        role_indicator = {'public': '[PUBLIC]', 'employee': '[EMPLOYE]', 'admin': '[ADMIN]'}.get(self.user_role,
                                                                                                 '[USER]')
        print(f"PROGRESS:{role_indicator} {message}", file=sys.stderr)

    def _log_error(self, error: str, state: ChatbotState):
        """Log spécialisé pour les erreurs"""
        error_msg = f"ERREUR: {error}"
        self.logger.error(error_msg)
        state['historique'].append(error_msg)

    def _creer_graphe(self) -> StateGraph:
        """Crée le graphe LangGraph avec bifurcation"""

        graph = StateGraph(ChatbotState)

        # Ajouter les agents - on utilise les nouvelles instances
        graph.add_node("rag", self.rag_agent.execute)
        graph.add_node("selecteur_gemini", self.selector_agent.execute)
        graph.add_node("analyseur", self.analyzer_agent.execute)
        graph.add_node("generateur_code", self.code_agent.execute)
        graph.add_node("synthese", self.synthesis_agent.execute)

        # Flux linéaire jusqu'à l'analyseur
        graph.add_edge("rag", "selecteur_gemini")

        graph.add_conditional_edges(
            "selecteur_gemini",
            self._aucun_document,
            {
                "false": END,
                "true": "analyseur"
            }
        )

        #graph.add_edge("selecteur_gemini", "analyseur")

        # bifurcation
        graph.add_conditional_edges(
            "analyseur",
            self._doit_faire_calculs,
            {
                "direct": "synthese",
                "calculs": "generateur_code"
            }
        )

        graph.add_edge("generateur_code", "synthese")

        graph.set_entry_point("rag")
        graph.add_edge("synthese", END)

        return graph.compile()

    def _doit_faire_calculs(self, state: ChatbotState) -> str:
        """Fonction de décision avec fallbacks"""

        # Analyser l'intention de l'analyseur
        reponse_analyseur = state.get('reponse_analyseur_brute', '')

        if "CALCULS_NECESSAIRES" in reponse_analyseur:
            self._log("Analyseur demande des calculs", state)

            # Vérifier si extraction a réussi
            if state.get('algo_genere') and state.get('instruction_calcul'):
                self._log("Algorithme extrait -> Génération", state)
                return "calculs"
            else:
                # FALLBACK
                self._log("Extraction échouée -> Génération avec prompt minimal", state)

                # Créer des instructions minimales basées sur la question
                question = state['question_utilisateur']

                if 'ville' in question.lower() and 'pourcentage' in question.lower():
                    state[
                        'instruction_calcul'] = "Trouver la ville avec le pourcentage le plus élevé de femmes étudiantes en ingénierie"
                    state['algo_genere'] = """
# 1. Analyser df1 pour les données d'ingénierie par ville
# 2. Calculer le pourcentage de femmes par ville  
# 3. Identifier la ville avec le pourcentage maximum
# 4. Utiliser df0 pour les données linguistiques de cette région
"""
                else:
                    state['instruction_calcul'] = f"Analyser les données pour répondre à: {question}"
                    state['algo_genere'] = "# Analyser les dataframes selon la question posée"

                self._log("Instructions fallback créées", state)
                return "calculs"

        elif "REPONSE_DIRECTE" in reponse_analyseur:
            self._log("Réponse directe détectée", state)
            return "direct"

        else:
            # Question complexe -> calculs
            if any(word in state['question_utilisateur'].lower() for word in
                   ['combien', 'pourcentage', 'quelle ville', 'plus élevé', 'proportion']):
                self._log("Question nécessite probablement des calculs", state)
                state['instruction_calcul'] = f"Analyser les données pour répondre à: {state['question_utilisateur']}"
                state['algo_genere'] = "# Analyser les dataframes appropriés selon la question"
                return "calculs"
            else:
                self._log("Question semble factuelle", state)
                return "direct"

    def poser_question_id(self, question: str, session_id: str = None, username: str = None, email: str = None) -> str:
        """Interface principale avec gestion d'erreurs complète + historique"""
        return self.poser_question_with_permissions(question, session_id, self.user_permissions, username, email)

    def poser_question_with_permissions(self, question: str, session_id: str = None,
                                        user_permissions: List[str] = None, username: str = None,
                                        email: str = None) -> str:
        """
        Nouvelle méthode principale qui gère les permissions

        Args:
            question: Question de l'utilisateur
            session_id: ID de session
            user_permissions: Permissions spécifiques (override les permissions de l'instance)
        """
        print(f"[DEBUG PERMISSIONS] DÉBUT - self.user_permissions: {self.user_permissions}", file=sys.stderr)
        print(f"[DEBUG PERMISSIONS] DÉBUT - paramètre user_permissions: {user_permissions}", file=sys.stderr)

        start_time = time.time()
        active_permissions = user_permissions or self.user_permissions

        print(f"[DEBUG PERMISSIONS] active_permissions calculées: {active_permissions}", file=sys.stderr)

        # Validation existante
        if not question.strip():
            return "Veuillez poser une question valide."

        print(f"Question reçue pour {self.user_role}: '{question[:50]}...'", file=sys.stderr)

        # État initial avec tous les champs existants
        etat_initial = ChatbotState(
            # Tous les champs existants
            question_utilisateur=question.strip(),
            tableaux_pertinents=[],
            tableaux_charges=[],
            tableaux_pour_upload=[],
            tableaux_reference=[],
            explication_selection=None,
            reponse_analyseur_brute=None,
            besoin_calculs=False,
            instruction_calcul=None,
            tableau_pour_calcul=None,
            code_pandas=None,
            algo_genere=None,
            dataframes=[],
            resultat_pandas=None,
            erreur_pandas=None,
            reponse_finale="",
            historique=[],
            fichiers_gemini=[],
            documents_trouves=[],
            documents_selectionnes=[],
            pdfs_pour_contexte=[],
            reponse_analyseur_texte_brut=None,
            fichiers_csvs_local=[],
            session_id=session_id,
            user_role=self.user_role,
            user_permissions=active_permissions,
            username=username,
            email=email
        )

        try:
            # Log initial avec permissions
            self._log_with_permissions(f"Démarrage analyse avec niveau d'accès {self.user_role}", etat_initial)

            # Workflow existant
            etat_final = self.graph.invoke(etat_initial)

            # Logs de succès existants
            duration = time.time() - start_time
            self.perf_logger.log_request_metrics(question, duration, True)

            # Enrichir la réponse finale avec info de permissions
            reponse_base = etat_final.get('reponse_finale', "Aucune réponse générée.")
            reponse_enrichie = self._enrichir_reponse_avec_permissions(reponse_base, etat_final)

            # ============ NOUVEAU: SAUVEGARDE AUTOMATIQUE DANS L'HISTORIQUE ============
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
                        self._log(f" Conversation sauvegardée pour {username}", etat_final)

                        # Stats utilisateur
                        stats = conversation_memory.get_conversation_stats(username, email)
                        self._log(
                            f" Stats: {stats['total_conversations']} total, {stats['conversations_24h']} récentes",
                            etat_final)
                    else:
                        self._log(" Erreur sauvegarde conversation", etat_final)
                except Exception as e:
                    self._log_error(f"Erreur sauvegarde historique: {e}", etat_final)
            else:
                self._log(" Username/email manquants, pas de sauvegarde historique", etat_final)

            return reponse_enrichie

        except Exception as e:
            # Gestion d'erreur existante + ajout niveau d'accès
            duration = time.time() - start_time
            error_msg = f"Erreur système: {str(e)}"
            self.perf_logger.log_request_metrics(question, duration, False, error_msg)

            self.logger.error(f"Erreur critique pour {self.user_role}: {error_msg}")
            return f"ERREUR: {error_msg}. Votre niveau d'accès: {self.user_role.upper()}. Veuillez réessayer."

    def _enrichir_reponse_avec_permissions(self, reponse_base: str, etat_final: ChatbotState) -> str:
        # DÉBOGAGE IMMÉDIAT
        if self.user_permissions is None:
            print(f"[ERREUR TROUVÉE] self.user_permissions est None !", file=sys.stderr)
            print(f"[ERREUR TROUVÉE] self.user_role: {self.user_role}", file=sys.stderr)
            print(f"[ERREUR TROUVÉE] État final user_permissions: {etat_final.get('user_permissions')}",
                  file=sys.stderr)
            import traceback
            traceback.print_stack(file=sys.stderr)

        # Indicateurs visuels par rôle
        role_indicators = {
            'public': '**Accès Public**',
            'employee': '**Accès Employé**',
            'admin': '**Accès Administrateur**'
        }

        indicator = role_indicators.get(self.user_role, '**Accès Limité**')

        # Compter les documents utilisés par niveau d'accès
        tableaux_utilises = etat_final.get('tableaux_charges', [])
        stats_acces = {'public': 0, 'internal': 0, 'confidential': 0}

        for tableau in tableaux_utilises:
            if isinstance(tableau, dict):
                access_level = tableau.get('access_level', 'public')
                if access_level in stats_acces:
                    stats_acces[access_level] += 1

        # Construction de la réponse enrichie
        reponse_enrichie = f"{indicator}\n\n{reponse_base}"

        # Ajouter les stats d'accès si des documents ont été utilisés
        if sum(stats_acces.values()) > 0:
            reponse_enrichie += f"\n\n**Sources consultées :**\n"
            if stats_acces['public'] > 0:
                reponse_enrichie += f"- [PUBLIC] {stats_acces['public']} document(s) public(s)\n"
            if stats_acces['internal'] > 0:
                reponse_enrichie += f"- [INTERNE] {stats_acces['internal']} document(s) interne(s)\n"
            if stats_acces['confidential'] > 0:
                reponse_enrichie += f"- [CONFIDENTIEL] {stats_acces['confidential']} document(s) confidentiel(s)\n"

        # Info sur les permissions pour les admins
        if self.user_role == 'admin':
            # PROTECTION CRITIQUE contre None
            permissions_safe = self.user_permissions or ["unknown_permissions"]
            if isinstance(permissions_safe, list):
                permissions_str = ', '.join(permissions_safe)
            else:
                permissions_str = str(permissions_safe)

            reponse_enrichie += f"\n**Debug Admin :** Permissions actives: {permissions_str}"

        return reponse_enrichie

    def _aucun_document(self, state: ChatbotState) -> str:
        if not state.get('tableaux_pour_upload'):
            return "false"
        else:
            return "true"

    def get_user_conversation_history(self, username: str, email: str, limit: int = 10) -> dict:
        """
        Récupère l'historique des conversations d'un utilisateur

        Args:
            username: Nom d'utilisateur
            email: Email utilisateur
            limit: Nombre max de conversations à retourner

        Returns:
            dict: Historique formaté avec stats
        """
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
        """
        Supprime l'historique d'un utilisateur

        Returns:
            dict: Résultat de la suppression
        """
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
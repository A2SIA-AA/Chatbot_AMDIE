import time
from langgraph.graph import StateGraph, END
import google.generativeai as genai
import sys

from .state import ChatbotState
from ..agents.pandas_agent import SimplePandasAgent
from ..agents.rag_agent import RAGAgent
from ..agents.selector_agent import SelectorAgent
from ..agents.analyzer_agent import AnalyzerAgent
from ..agents.code_agent import CodeAgent
from ..agents.synthesis_agent import SynthesisAgent
from ..agents.rag_agent_all_file import RAGAgentAllFile
from ..agents.selector_file_agent import SelectorFileAgent
from ..agents.text_analyzer_agent import TextAnalyzerAgent
from config.logging import setup_logging, PerformanceLogger
from config.setting import get_settings


class ChatbotMarocVersion2:
    """Chatbot pour analyser les données du Maroc"""

    def __init__(self, rag_index, settings=None):
        # Configuration
        self.settings = get_settings()
        self.rag = rag_index

        # Setup logging
        self.logger = setup_logging(self.settings)
        self.perf_logger = PerformanceLogger(self.settings)

        # Configuration Gemini
        genai.configure(api_key=self.settings.gemini_api_key)
        self.gemini_model = genai.GenerativeModel('gemini-2.5-flash')

        # Agent pandas
        self.pandas_agent = SimplePandasAgent(self.gemini_model)

        # Initialiser tous les agents
        self.rag_agent = RAGAgentAllFile(self.rag, self)
        self.selector_agent = SelectorAgent(self.gemini_model, self)
        self.analyzer_agent = AnalyzerAgent(self.gemini_model, self)
        self.code_agent = CodeAgent(self.gemini_model, self)
        self.synthesis_agent = SynthesisAgent(self.gemini_model, self)
        self.analyzer_file_agent = TextAnalyzerAgent(self.gemini_model, self)
        self.selector_file_agent = SelectorFileAgent(self.gemini_model, self)

        # Créer le graphe LangGraph
        self.graph = self._creer_graphe()

        print("Chatbot initialisé avec succès!")

    # Dans votre ChatbotMaroc
    def _log(self, message: str, state: ChatbotState):
        """Ajoute un message au log ET l'affiche pour le frontend"""
        self.logger.info(message)
        state['historique'].append(message)

        # Ajouter cette ligne pour le frontend
        print(f"PROGRESS:{message}", file=sys.stderr)

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
        graph.add_node("selecteur_texte", self.selector_file_agent.execute)
        graph.add_node("analyseur_texte", self.analyzer_file_agent.execute)
        graph.add_node("analyseur", self.analyzer_agent.execute)
        graph.add_node("generateur_code", self.code_agent.execute)
        graph.add_node("synthese", self.synthesis_agent.execute)

        # Flux linéaire jusqu'à l'analyseur
        graph.add_edge("rag", "selecteur_texte")

        graph.add_conditional_edges(
            "selecteur_texte",
            self._est_texte,
            {
                "oui": "analyseur_texte",
                "non": "analyseur"
            }
        )

        graph.add_edge("analyseur_texte", "synthese")

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


    def _est_texte(self, state: ChatbotState) -> str:
        for doc in state['documents_trouves']:
            if "pdf" in doc.get('id'):
                return "oui"
        return "non"


    def poser_question(self, question: str) -> str:
        """Interface principale avec gestion d'erreurs complète"""

        print(f"\nQUESTION: {question}")
        start_time = time.time()

        # État initial avec validation
        if not question.strip():
            return "Veuillez poser une question valide."

        etat_initial = ChatbotState(
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
            fichiers_gemini=[]
        )

        try:
            # Exécuter le workflow
            etat_final = self.graph.invoke(etat_initial)

            # Log des métriques de succès
            duration = time.time() - start_time
            self.perf_logger.log_request_metrics(question, duration, True)

            # Afficher seulement le résultat final
            return etat_final.get('reponse_finale', "Aucune réponse générée.")

        except Exception as e:
            # Log des métriques d'erreur
            duration = time.time() - start_time
            error_msg = f"Erreur système: {str(e)}"
            self.perf_logger.log_request_metrics(question, duration, False, error_msg)

            self.logger.error(f"Erreur critique: {error_msg}")
            return f"{error_msg}. Veuillez réessayer avec une question plus simple."
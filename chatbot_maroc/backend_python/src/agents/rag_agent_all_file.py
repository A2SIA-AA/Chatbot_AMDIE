from typing import Dict
from ..core.state import ChatbotState


class RAGAgentAllFile:
    """Agent RAG pour rechercher des documents pertinents"""

    def __init__(self, rag_index, chatbot_instance):
        self.rag = rag_index
        self.chatbot = chatbot_instance

    def execute(self, state: ChatbotState) -> ChatbotState:
        """Point d'entrée principal de l'agent"""
        return self.agent_rag_all_file(state)

    def agent_rag_all_file(self, state: ChatbotState) -> ChatbotState:
        """Agent RAG avec gestion d'erreurs"""

        self.chatbot._log("Agent RAG tout fichier: Démarrage de la recherche", state)

        try:
            # Validation de la question
            if not state['question_utilisateur'].strip():
                raise ValueError("Question utilisateur vide")

            # Recherche RAG
            resultats_rag = self.rag.rechercher_tableaux(
                state['question_utilisateur'],
                n_results=10
            )

            if not resultats_rag or not resultats_rag.get('tableaux'):
                self.chatbot._log("Agent RAG: Aucun tableau trouvé", state)
                state['tableaux_pertinents'] = []
                state['tableaux_charges'] = []
                return state

            state['tableaux_pertinents'] = resultats_rag['tableaux']
            state['documents_trouves'] = resultats_rag['tableaux']
            self.chatbot._log(f"Agent RAG: {len(state['tableaux_pertinents'])} tableaux trouvés", state)

            # Chargement des données avec validation
            tableaux_complets = []
            for i, tableau_info in enumerate(state['tableaux_pertinents']):
                try:
                    tableau_path = tableau_info.get('tableau_path')
                    if not tableau_path:
                        self.chatbot._log(f"Tableau {i + 1}: Chemin manquant", state)
                        continue

                    donnees_completes = self.rag.get_tableau_data(tableau_path)
                    tableaux_complets.append(donnees_completes)
                    titre = donnees_completes.get('titre_contextuel', f'Tableau {i + 1}')
                    self.chatbot._log(f"Tableau chargé: {titre}", state)

                except Exception as e:
                    self.chatbot._log_error(f"Chargement tableau {i + 1}: {str(e)}", state)

            state['tableaux_charges'] = tableaux_complets
            state['tableaux_reference'] = tableaux_complets

        except Exception as e:
            self.chatbot._log_error(f"Agent RAG: {str(e)}", state)
            state['tableaux_charges'] = []

        return state
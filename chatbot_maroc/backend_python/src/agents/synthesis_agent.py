import pandas as pd
from typing import Dict, List
from ..core.state import ChatbotState
from ..utils.message_to_front import _send_to_frontend


class SynthesisAgent:
    """Agent synthèse pour formuler la réponse finale"""

    def __init__(self, gemini_model, chatbot_instance):
        self.gemini_model = gemini_model
        self.chatbot = chatbot_instance

    def execute(self, state: ChatbotState) -> ChatbotState:
        """Point d'entrée principal de l'agent"""
        return self.agent_synthese(state)

    def agent_synthese(self, state: ChatbotState) -> ChatbotState:
        """Agent synthèse adaptatif selon le workflow"""

        self.chatbot._log("Agent Synthèse: Formulation finale", state)
        session_id = state.get('session_id')
        _send_to_frontend(session_id,"Agent Synthèse: Formulation de la réponse finale...  ")

        # CAS 1: Réponse directe (workflow court)
        if not state.get('besoin_calculs') or state.get('reponse_finale'):
            if state.get('reponse_finale'):
                self.chatbot._log("Synthèse: Réponse directe conservée", state)
                # Enrichir avec les sources
                state['reponse_finale'] = self._enrichir_reponse_avec_sources(
                    state['reponse_finale'],
                    state.get('tableaux_pour_upload', [])
                )
            else:
                state['reponse_finale'] = "Aucune réponse générée par l'analyseur."
            return state

        # CAS 2: Après calculs (workflow complet)
        if state.get('besoin_calculs') and state.get('resultat_pandas') is not None:
            try:
                prompt_synthese = f"""Tu es un assistant expert des données du Maroc.

QUESTION: {state['question_utilisateur']}

RÉSULTATS OBTENUS: {state['resultat_pandas']}

SOURCES UTILISÉES: 
{self._extraire_sources_utilisees(state['dataframes'])}

CONTEXTE: Analyse basée sur {len(state['dataframes'])} sources de données officielles

MISSION: Formule une réponse claire et naturelle qui:
1. Répond directement à la question
2. Présente le résultat de manière compréhensible  
3. CITE les sources utilisées (titre + origine)
4. Reste factuel et précis
5. Donne de la crédibilité avec les références

RÉPONSE:"""

                response = self.gemini_model.generate_content(prompt_synthese)
                state['reponse_finale'] = response.text
                self.chatbot._log("Synthèse: Réponse finale générée", state)
                self.chatbot._log("MESSAGE DE SYNTHESE :", state)

            except Exception as e:
                self.chatbot._log_error(f"Synthèse: {str(e)}", state)
                state['reponse_finale'] = f"D'après mon analyse: {state['resultat_pandas']}"

        # CAS 3: Échec des calculs
        elif state.get('besoin_calculs') and state.get('erreur_pandas'):
            state['reponse_finale'] = f"""J'ai rencontré une difficulté technique lors de l'analyse.

Erreur: {state['erreur_pandas']}

Pouvez-vous reformuler votre question de manière plus simple ou plus spécifique ?"""

        # CAS 4: Par défaut
        else:
            state['reponse_finale'] = "Impossible de traiter votre demande. Veuillez reformuler."

        return state

    def _enrichir_reponse_avec_sources(self, reponse: str, tableaux: List[Dict]) -> str:
        """Enrichit une réponse directe avec les sources"""

        if not tableaux:
            return reponse

        sources = []
        for tableau in tableaux[:3]:
            titre = tableau.get('titre_contextuel', 'Source inconnue')
            source = tableau.get('fichier_source', 'N/A')
            if titre != 'Source inconnue':
                sources.append(f"• {titre} ({source})")

        if sources:
            reponse += f"\n\nSources consultées :\n" + "\n".join(sources)

        return reponse

    def _extraire_sources_utilisees(self, dataframes: List[pd.DataFrame]) -> str:
        """Extrait les sources pour la réponse finale"""

        sources = []
        for df in dataframes:
            attrs = getattr(df, 'attrs', {})
            titre = attrs.get('titre', 'Source non identifiée')
            source = attrs.get('source', 'N/A')
            sources.append(f"• {titre} (Source: {source})")

        return '\n'.join(sources)
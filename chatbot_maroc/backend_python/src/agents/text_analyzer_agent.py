import re
import pandas as pd
from typing import Dict, List
from google.genai import types
from google import genai
from ..core.state import ChatbotState
from dotenv import load_dotenv
import os
load_dotenv()

class TextAnalyzerAgent:
    """Agent analyseur pour déterminer le type de réponse nécessaire"""

    def __init__(self, gemini_model, chatbot_instance):
        self.gemini_model = gemini_model
        self.chatbot = chatbot_instance

    def execute(self, state: ChatbotState) -> ChatbotState:
        """Point d'entrée principal de l'agent"""
        return self.agent_text_analyseur(state)

    def agent_text_analyseur(self, state: ChatbotState) -> ChatbotState:
        """Agent analyseur avec validation"""

        self.chatbot._log("Agent Texte Analyseur: Début de l'analyse des fichiers textuels", state)

        # Validation des prérequis
        if not state['documents_trouves']:
            state['reponse_finale'] = "Aucune donnée textuel disponible pour répondre à votre question."
            return state

        # Préparation du contexte enrichi avec métadonnées
        contexte_complet = self._preparer_contexte_avec_metadata(state)

        # Prompt enrichi avec métadonnées
        prompt_unifie = f"""Tu es un expert en analyse de données du Maroc.

QUESTION UTILISATEUR: {state['question_utilisateur']}


{contexte_complet}


INSTRUCTIONS STRICTES:
1. Utilise les TITRES et CONTEXTES ci-dessus pour comprendre chaque document
2. Choisis les documents selon leur PERTINENCE à la question

FORMAT DE RÉPONSE OBLIGATOIRE:

=== REPONSE_TEXTE_ANALYSEUR ===

SOURCES_UTILISEES: [Mentionner les sources des données]
REPONSE: [Réponse complète avec références aux sources]
"""

        try:
            content = [prompt_unifie]
            API_KEY = os.getenv("GEMINI_API_KEY")
            client = genai.Client(api_key=API_KEY)

            response = client.models.generate_content(
                model="gemini-2.5-pro",
                contents=content,
                config=types.GenerateContentConfig(
                    thinking_config=types.ThinkingConfig(
                        include_thoughts=True
                    )
                )
            )

            answer = []
            thought = []

            for part in response.candidates[0].content.parts:
                if not part.text:
                    continue
                if part.thought:
                    thought.append(part.text)
                else:
                    answer.append(part.text)

            answer = '\n'.join(answer)

            # Sauvegarder la réponse
            state['reponse_analyseur_texte_brute'] = answer


            reponse = self._extraire_reponse_directe(answer)
            if reponse:
                state['besoin_calculs'] = False
                state['reponse_finale'] = reponse
                self.chatbot._log("Analyseur Texte: Réponse directe extraite", state)
            else:
                state['besoin_calculs'] = False
                state['reponse_finale'] = "Impossible d'extraire la réponse."

        except Exception as e:
            self.chatbot._log_error(f"Agent Texte Analyseur: {str(e)}", state)
            state['besoin_calculs'] = False
            state['reponse_finale'] = "Erreur lors de l'analyse des données."

        return state
    def _preparer_contexte_avec_metadata(self, state: ChatbotState) -> str:
        """Prépare un contexte enrichi avec toutes les métadonnées"""

        contexte = "DONNÉES TEXTUELS DISPONIBLES POUR L'ANALYSE:\n\n"

        # Utiliser les documents sélectionnés
        documents_a_analyser = state.get('documents_trouves', [])

        for i, doc in enumerate(documents_a_analyser):
            # Extraire les métadonnées
            source = doc.get('source', 'N/A')
            resume = doc.get('description', 'N/A')

            contexte += f"""DOCUMENT {i}:
   Source: {source}"
   APERÇU DES DONNÉES:\n {resume}
"""

        return contexte

    def _extraire_reponse_directe(self, texte: str) -> str:
        """Extraction de la réponse directe"""

        patterns = [
            r'REPONSE:\s*\n(.*?)(?===|$)',
            r'=== REPONSE_TEXTE_ANALYSEUR ===\s*\n.*?REPONSE:\s*\n(.*?)(?===|$)',
            r'REPONSE:\s*(.*?)(?===|$)'
        ]

        for pattern in patterns:
            match = re.search(pattern, texte, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return None


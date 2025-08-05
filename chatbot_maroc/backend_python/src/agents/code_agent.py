import re
import pandas as pd
from typing import List
from google.genai import types
from google import genai
from ..core.state import ChatbotState
import os
from dotenv import load_dotenv
from ..utils.message_to_front import _send_to_frontend

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

class CodeAgent:
    """Agent générateur et exécuteur de code"""

    def __init__(self, gemini_model, chatbot_instance):
        self.gemini_model = gemini_model
        self.chatbot = chatbot_instance

    def execute(self, state: ChatbotState) -> ChatbotState:
        """Point d'entrée principal de l'agent"""
        return self.agent_generateur_code(state)

    def agent_generateur_code(self, state: ChatbotState) -> ChatbotState:
        """Agent générateur avec exécution de code intégrée Gemini"""

        self.chatbot._log("Agent Générateur: Génération et exécution du code", state)
        session_id = state.get('session_id', None)

        try:
            # Créer les fichiers CSV temporaires
            fichiers_csv = self._creer_csvs_pour_gemini(state['dataframes'], state)
            fichiers_gemini, client = self._upload_fichier_to_gemini(fichiers_csv, state)
            state['fichiers_gemini'] = fichiers_gemini
            state['fichiers_csvs_local'] = fichiers_csv

            if not fichiers_csv:
                state['erreur_pandas'] = "Impossible de créer les fichiers CSV"
                return state

            # Prompt enrichi avec métadonnées
            prompt = f"""ANALYSE DE DONNÉES - MAROC

QUESTION: {state['question_utilisateur']}

PLAN D'ANALYSE: {state['instruction_calcul']}

ALGORITHME: {state['algo_genere']}

SOURCES DE DONNÉES DISPONIBLES:
{self._generer_guide_sources_csv(state['dataframes'])}

SOURCES RECOMMANDÉES: {self._extraire_sources_utilisees_prompt(state.get('reponse_analyseur_brute', ''))}

INSTRUCTIONS:
1. Charge chaque fichier CSV avec pandas (df0, df1, df2...)
2. Utilise le GUIDE DES SOURCES pour comprendre le contenu de chaque dataframe
3. Effectue l'analyse selon le PLAN et l'ALGORITHME fournis
4. Stocke le résultat final dans la variable 'result'  
5. IMPORTANT: Utilise les sources recommandées en priorité

Génère et exécute le code Python maintenant."""

            _send_to_frontend(session_id,"début de la génération/éxecution du code...")

            client = genai.Client(api_key=API_KEY)

            contents = [prompt]
            contents.extend(fichiers_gemini)

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=contents,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(code_execution=types.ToolCodeExecution)]
                ),
            )

            _send_to_frontend(session_id,"fin de la génération/éxecution du code...")

            code_parts = []
            execution_results = []
            text_parts = []

            for part in response.candidates[0].content.parts:
                if part.text is not None:
                    text_parts.append(part.text)
                if part.executable_code is not None:
                    code_parts.append(part.executable_code)
                if part.code_execution_result is not None:
                    execution_results.append(part.code_execution_result)

            # 1. Sauvegarder le code complet
            if code_parts:
                code_strings = []
                for code_obj in code_parts:
                    if hasattr(code_obj, 'code') and code_obj.code:
                        code_strings.append(code_obj.code)

                if code_strings:
                    state['code_pandas'] = '\n'.join(code_strings)
                    code_apercu = state['code_pandas'][:300] + "..." if len(state['code_pandas']) > 300 else state[
                        'code_pandas']
                    self.chatbot._log(f"CODE GÉNÉRÉ: {code_apercu}", state)

            result_trouve = False

            if execution_results:
                output_strings = []
                for result_obj in execution_results:
                    if hasattr(result_obj, 'output') and result_obj.output:
                        output_strings.append(result_obj.output)

                if output_strings:
                    # Combiner tous les outputs
                    output_complet = '\n'.join(output_strings)
                    state['resultat_pandas'] = output_complet
                    result_trouve = True

            if not result_trouve and text_parts:
                texte_complet = '\n'.join(text_parts)
                if texte_complet.strip():
                    state['resultat_pandas'] = texte_complet
                    result_trouve = True
                    self.chatbot._log("Résultat extrait des parts texte", state)

            # VALIDATION FINALE
            if result_trouve:
                self.chatbot._log("Code exécuté avec succès - Résultat extrait", state)
            else:
                state['erreur_pandas'] = "Aucun résultat obtenu de l'exécution du code"
                self.chatbot._log("ERREUR: Aucun résultat détecté dans l'exécution", state)

                # Debug : afficher ce qui a été reçu
                self.chatbot._log(f"DEBUG - Code parts: {len(code_parts)}", state)
                self.chatbot._log(f"DEBUG - Execution results: {len(execution_results)}", state)
                self.chatbot._log(f"DEBUG - Text parts: {len(text_parts)}", state)

        except Exception as e:
            error_msg = f"Erreur génération/exécution: {str(e)}"
            state['erreur_pandas'] = error_msg
            self.chatbot._log_error(f"Agent Générateur: {error_msg}", state)

        finally:
            # Nettoyage sécurisé
            #if 'fichiers_csv' in locals() and fichiers_csv:
            #    self._nettoyer_csvs_temporaires(fichiers_csv, state)
            if 'fichiers_gemini' in locals():
                self._nettoyer_fichiers_gemini(fichiers_gemini, client, state)

        return state

    def _generer_guide_sources_csv(self, dataframes: List[pd.DataFrame]) -> str:
        """Génère un guide des sources pour le prompt générateur"""

        guide = ""
        for i, df in enumerate(dataframes):
            attrs = getattr(df, 'attrs', {})

            guide += f"""df{i}.csv: {attrs.get('titre', f'Tableau {i}')}
  Source: {attrs.get('source', 'N/A')}
  Contexte: {attrs.get('description', 'Données statistiques')}  
  Colonnes clés: {', '.join(df.columns[:4].astype(str))}

"""
        return guide

    def _extraire_sources_utilisees_prompt(self, reponse_brute: str) -> str:
        """Extrait les sources utilisées de la réponse de l'analyseur"""

        patterns = [
            r'SOURCES_UTILISEES:\s*\n(.*?)(?=\n[A-Z]|$)',
            r'SOURCES_UTILISEES:\s*(.*?)(?=\n[A-Z]|$)'
        ]

        for pattern in patterns:
            match = re.search(pattern, reponse_brute, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return "Voir guide ci-dessus"

    def _upload_fichier_to_gemini(self, fichiers_csv: List[str], state: ChatbotState):
        client = genai.Client(api_key=API_KEY)

        fichiers_gemini = []
        for fichier_csv in fichiers_csv:
            try:
                fichier_uploade = client.files.upload(file=fichier_csv)
                fichiers_gemini.append(fichier_uploade)
                self.chatbot._log(f"Fichier uploadé: {fichier_csv}", state)
            except Exception as e:
                self.chatbot._log_error(f"Erreur upload {fichier_csv}: {str(e)}", state)
                raise e
        #suppression immédiate des csvs
        self._nettoyer_csvs_temporaires(fichiers_csv,state)
        return fichiers_gemini, client

    def _creer_csvs_pour_gemini(self, dataframes: List[pd.DataFrame], state: ChatbotState) -> List[str]:
        """Crée des fichiers CSV temporaires pour chaque DataFrame"""

        fichiers_csv = []

        try:
            for i, df in enumerate(dataframes):
                if df is not None and not df.empty:
                    nom_fichier = f'df{i}_analysis.csv'
                    df.to_csv(nom_fichier, index=False, encoding='utf-8')
                    fichiers_csv.append(nom_fichier)
                    self.chatbot._log(f"CSV créé: {nom_fichier} {df.shape}", state)
                else:
                    self.chatbot._log(f"DataFrame {i} vide ignoré", state)

        except Exception as e:
            self.chatbot._log_error(f"Erreur création CSV: {str(e)}", state)
            return []

        return fichiers_csv

    def _nettoyer_csvs_temporaires(self, fichiers_csv: List[str], state: ChatbotState):
        """Supprime les fichiers CSV temporaires"""

        for fichier in fichiers_csv:
            try:
                if os.path.exists(fichier):
                    os.remove(fichier)
                    self.chatbot._log(f"CSV local supprimé: {fichier}", state)
            except Exception as e:
                self.chatbot._log_error(f"Erreur suppression {fichier}: {str(e)}", state)

    def _nettoyer_fichiers_gemini(self, fichiers_gemini: List, client, state: ChatbotState):
        """Supprime les fichiers uploadés chez Gemini"""

        for fichier in fichiers_gemini:
            try:
                client.files.delete(name=fichier.name)
                self.chatbot._log(f"Fichier Gemini supprimé: {fichier.name}", state)
            except Exception as e:
                self.chatbot._log_error(f"Erreur suppression Gemini {fichier.name}: {str(e)}", state)

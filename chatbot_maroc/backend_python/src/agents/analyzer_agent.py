import re
import pandas as pd
from typing import Dict, List
from google.genai import types
from google import genai
from ..core.state import ChatbotState
from dotenv import load_dotenv
import os
from ..utils.message_to_front import _send_to_frontend

load_dotenv()

class AnalyzerAgent:
    """Agent analyseur pour déterminer le type de réponse nécessaire"""

    def __init__(self, gemini_model, chatbot_instance):
        self.gemini_model = gemini_model
        self.chatbot = chatbot_instance

    def execute(self, state: ChatbotState) -> ChatbotState:
        """Point d'entrée principal de l'agent"""
        return self.agent_analyseur(state)

    def agent_analyseur(self, state: ChatbotState) -> ChatbotState:
        """Agent analyseur avec validation"""

        self.chatbot._log("Agent Analyseur: Début de l'analyse", state)
        session_id = state['session_id']
        _send_to_frontend(session_id, f"Agent Analyse: Début Analyse sur '{state['question_utilisateur'][:50]}...'")

        # Validation des prérequis
        if not state['tableaux_pour_upload']:
            state['besoin_calculs'] = False
            state['reponse_finale'] = "Aucune donnée disponible pour répondre à votre question."
            return state

        # Création des DataFrames avec validation
        try:
            state['dataframes'] = self._creer_dataframes_valides(state['tableaux_pour_upload'], state)
            if not state['dataframes']:
                state['besoin_calculs'] = False
                state['reponse_finale'] = "Impossible de traiter les données trouvées."
                return state
        except Exception as e:
            self.chatbot._log_error(f"Création DataFrames: {str(e)}", state)
            state['besoin_calculs'] = False
            state['reponse_finale'] = "Erreur lors du traitement des données."
            return state

        # Préparation du contexte enrichi avec métadonnées
        contexte_complet = self._preparer_contexte_avec_metadata(state)

        fichier_csv = self._creer_csvs_pour_gemini(state['dataframes'], state)
        fichier_gemini, client = self._upload_fichier_to_gemini(fichier_csv, state)
        state['fichiers_gemini'] = fichier_gemini

        # Prompt enrichi avec métadonnées
        prompt_unifie = f"""Tu es un expert en analyse de données du Maroc.

QUESTION UTILISATEUR: {state['question_utilisateur']}


{contexte_complet}

SÉLECTION INTELLIGENTE:
{state.get('explication_selection', 'Tableaux sélectionnés automatiquement')}

INSTRUCTIONS STRICTES:
1. Utilise les TITRES et CONTEXTES ci-dessus pour comprendre chaque dataframe
2. Choisis les dataframes selon leur PERTINENCE à la question
3. Si la réponse est évidente : choisis REPONSE_DIRECTE  
4. Si tu dois croiser, calculer, filtrer : choisis CALCULS_NECESSAIRES

FORMAT DE RÉPONSE OBLIGATOIRE:
DECISION: [CALCULS_NECESSAIRES ou REPONSE_DIRECTE]

=== SI CALCULS_NECESSAIRES ===
SOURCES_UTILISEES: [Mentionner les titres des dataframes à utiliser]
ETAPES: [Décrire les étapes en référençant les sources]
ALGORITHME: [Pseudo-code avec df0, df1... ET leurs titres]

=== SI REPONSE_DIRECTE ===
SOURCES_UTILISEES: [Mentionner les sources des données]
REPONSE: [Réponse complète avec références aux sources]
"""

        try:
            _send_to_frontend(session_id, "début de la génération de réponse de l'agent analyseur...")
            content = [prompt_unifie]
            content.extend(fichier_gemini)

            response = client.models.generate_content(
                model="gemini-2.5-pro",
                contents=content,
                config=types.GenerateContentConfig(
                    thinking_config=types.ThinkingConfig(
                        include_thoughts=True
                    )
                )
            )
            _send_to_frontend(session_id, "Réponse de l'analyseur généré")

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
            state['reponse_analyseur_brute'] = answer

            # Parsing avec validation
            if "CALCULS_NECESSAIRES" in answer:
                _send_to_frontend(session_id, "calculs nécessaires: extraction des étapes et algorithme")
                etapes, algorithme = self._extraire_etapes_et_algo(answer)

                if etapes and algorithme:
                    state['besoin_calculs'] = True
                    state['instruction_calcul'] = etapes
                    state['algo_genere'] = algorithme
                    self.chatbot._log("Analyseur: Calculs nécessaires - algo extrait", state)
                    #self.chatbot._log(f"ETAPE : {etapes}", state)
                    #self.chatbot._log(f"ALGO : {algorithme}", state)
                else:
                    # Fallback intelligent
                    etapes_fallback, algo_fallback = self._extraction_fallback(answer)
                    if etapes_fallback and algo_fallback:
                        state['besoin_calculs'] = True
                        state['instruction_calcul'] = etapes_fallback
                        state['algo_genere'] = algo_fallback
                        self.chatbot._log("Analyseur: Extraction fallback réussie", state)
                    else:
                        state['besoin_calculs'] = False
                        state['reponse_finale'] = "Impossible d'extraire l'algorithme de calcul."

            elif "REPONSE_DIRECTE" in answer:
                _send_to_frontend(session_id,"réponse direct: extraction de la réponse directe")
                reponse = self._extraire_reponse_directe(answer)
                if reponse:
                    state['besoin_calculs'] = False
                    state['reponse_finale'] = reponse
                    self.chatbot._log("Analyseur: Réponse directe extraite", state)
                else:
                    state['besoin_calculs'] = False
                    state['reponse_finale'] = "Impossible d'extraire la réponse."

            else:
                # Analyse contextuelle de la question
                if self._question_necessite_calculs(state['question_utilisateur']):
                    state['besoin_calculs'] = True
                    state['instruction_calcul'] = f"Analyser les données pour répondre à: {state['question_utilisateur']}"
                    state['algo_genere'] = "# Analyser les dataframes appropriés selon la question"
                    self.chatbot._log("Analyseur: Fallback vers calculs détecté", state)
                else:
                    state['besoin_calculs'] = False
                    state['reponse_finale'] = "Format de réponse non reconnu de l'analyseur."

        except Exception as e:
            self.chatbot._log_error(f"Agent Analyseur: {str(e)}", state)
            state['besoin_calculs'] = False
            state['reponse_finale'] = "Erreur lors de l'analyse des données."

        finally:
            # Nettoyage sécurisé
            #if 'fichiers_csv' in locals() and fichiers_csv:
            #    self._nettoyer_csvs_temporaires(fichiers_csv, state)
            if 'fichiers_gemini' in locals():
                self._nettoyer_fichiers_gemini(fichier_gemini, client, state)

        return state

    def _preparer_contexte_avec_metadata(self, state: ChatbotState) -> str:
        """Prépare un contexte enrichi avec toutes les métadonnées"""

        contexte = "DONNÉES DISPONIBLES POUR L'ANALYSE:\n\n"

        # Utiliser les tableaux sélectionnés
        tableaux_a_analyser = state.get('tableaux_pour_upload', [])
        dataframes_a_analyser = state.get('dataframes', [])

        for i, (tableau, df) in enumerate(zip(tableaux_a_analyser, dataframes_a_analyser)):
            # Extraire les métadonnées
            titre = tableau.get('titre_contextuel', f'Tableau {i}')
            source = tableau.get('fichier_source', 'N/A')
            feuille = tableau.get('nom_feuille', 'N/A')

            # Métadonnées du dataframe
            df_attrs = getattr(df, 'attrs', {})

            contexte += f"""DATAFRAME df{i}: "{titre}"
   Source: {source} -> Feuille "{feuille}" 
   Contenu: {df_attrs.get('description', 'Données statistiques')}
   Structure: {len(df)} lignes × {len(df.columns)} colonnes
   Colonnes: {', '.join(df.columns.astype(str))}

"""

        # Ajouter un échantillon des données
        contexte += "APERÇU DES DONNÉES:\n"
        for i, df in enumerate(dataframes_a_analyser[:3]):
            if not df.empty:
                contexte += f"   df{i} (premiers éléments): {df.iloc[0].to_dict()}\n"

        return contexte

    def _question_necessite_calculs(self, question: str) -> bool:
        """Analyse la question pour déterminer si des calculs sont nécessaires"""

        question_lower = question.lower()

        calcul_keywords = ['total', 'combien', 'pourcentage', 'compare', 'plus', 'moins',
                           'moyenne', 'maximum', 'minimum', 'évolution', 'tendance']

        return any(keyword in question_lower for keyword in calcul_keywords)

    def _extraction_fallback(self, texte: str) -> tuple:
        """Méthodes alternatives d'extraction"""

        # Méthode 1: Recherche de mots-clés
        if "calcul" in texte.lower() or "pandas" in texte.lower():
            etapes = "Analyser les données selon les instructions détectées"
            algo = "# Analyser les dataframes selon la question posée"
            return etapes, algo

        # Méthode 2: Extraction par lignes
        lignes = texte.split('\n')
        etapes_candidates = [l for l in lignes if any(mot in l.lower() for mot in ['étape', 'step', '1.', '2.'])]
        algo_candidates = [l for l in lignes if any(mot in l.lower() for mot in ['df', 'dataframe', 'pandas'])]

        if etapes_candidates and algo_candidates:
            return '\n'.join(etapes_candidates), '\n'.join(algo_candidates)

        return None, None

    def _creer_dataframes_valides(self, tableaux_charges: List[Dict], state: ChatbotState) -> List[pd.DataFrame]:
        """Crée des DataFrames validés avec métadonnées"""
        dataframes = []

        for i, tableau in enumerate(tableaux_charges):
            try:
                df = self.chatbot.pandas_agent.creer_dataframe_propre(tableau)
                if df is not None and not df.empty:
                    # Ajouter les métadonnées au dataframe
                    df.attrs.update({
                        'titre': tableau.get('titre_contextuel', f'Tableau {i}'),
                        'source': tableau.get('fichier_source', 'N/A'),
                        'feuille': tableau.get('nom_feuille', 'N/A'),
                        'description': tableau.get('description', 'Données statistiques'),
                        'nb_lignes': len(df),
                        'nb_colonnes': len(df.columns)
                    })

                    dataframes.append(df)
                    self.chatbot._log(f"DataFrame {i} créé: {df.shape}", state)
                else:
                    self.chatbot._log(f"DataFrame {i} vide", state)
            except Exception as e:
                self.chatbot._log_error(f"Création DataFrame {i}: {str(e)}", state)

        return dataframes

    def _extraire_etapes_et_algo(self, texte: str) -> tuple:
        """Extraction robuste des étapes et algorithme"""

        try:
            # Log pour debug
            self.chatbot.logger.info(f"Texte à analyser (200 premiers chars): {texte[:200]}")

            # Patterns plus flexibles
            patterns_etapes = [
                r'ETAPES:\s*\n(.*?)(?=\n.*?ALGORITHME:|$)',
                r'ÉTAPES:\s*\n(.*?)(?=\n.*?ALGORITHME:|$)',
                r'### ETAPES:\s*\n(.*?)(?=\n.*?ALGORITHME:|$)',
                r'SOURCES_UTILISEES:.*?\n\n(.*?)(?=\n.*?ALGORITHME:|$)',
            ]

            patterns_algo = [
                r'ALGORITHME:\s*\n(.*?)(?=\n###|$)',
                r'ALGORITHME:\s*\n(.*?)(?=\n\n|$)',
                r'### ALGORITHME:\s*\n(.*?)(?=\n###|$)',
            ]

            etapes = None
            algorithme = None

            # Essayer d'extraire les étapes
            for pattern in patterns_etapes:
                try:
                    match = re.search(pattern, texte, re.DOTALL | re.IGNORECASE)
                    if match:
                        etapes_brut = match.group(1).strip()
                        if etapes_brut and len(etapes_brut) > 10:  # Validation minimale
                            etapes = etapes_brut
                            self.chatbot.logger.info(f"Étapes extraites avec pattern: {pattern[:30]}")
                            break
                except Exception as e:
                    self.chatbot.logger.warning(f"Erreur pattern étapes {pattern[:30]}: {e}")

            # Essayer d'extraire l'algorithme
            for pattern in patterns_algo:
                try:
                    match = re.search(pattern, texte, re.DOTALL | re.IGNORECASE)
                    if match:
                        algo_brut = match.group(1).strip()
                        if algo_brut and len(algo_brut) > 10:  # Validation minimale
                            algorithme = algo_brut
                            self.chatbot.logger.info(f"Algorithme extrait avec pattern: {pattern[:30]}")
                            break
                except Exception as e:
                    self.chatbot.logger.warning(f"Erreur pattern algo {pattern[:30]}: {e}")

            # Fallback : extraire des sections par mots-clés
            if not etapes or not algorithme:
                self.chatbot.logger.info("Tentative fallback d'extraction")

                # Chercher des lignes avec des mots-clés d'étapes
                lignes = texte.split('\n')
                etapes_lignes = []
                algo_lignes = []

                in_etapes = False
                in_algo = False

                for ligne in lignes:
                    ligne_clean = ligne.strip()

                    # Détecter le début des sections
                    if any(keyword in ligne_clean.lower() for keyword in ['étape', 'step', '1.', '2.', 'd\'abord']):
                        in_etapes = True
                        in_algo = False
                        etapes_lignes.append(ligne_clean)
                    elif any(keyword in ligne_clean.lower() for keyword in
                             ['algorithme', 'df0', 'df1', 'pandas', 'code']):
                        in_algo = True
                        in_etapes = False
                        algo_lignes.append(ligne_clean)
                    elif in_etapes and ligne_clean:
                        etapes_lignes.append(ligne_clean)
                    elif in_algo and ligne_clean:
                        algo_lignes.append(ligne_clean)

                if not etapes and etapes_lignes:
                    etapes = '\n'.join(etapes_lignes)
                    self.chatbot.logger.info("Étapes extraites par fallback")

                if not algorithme and algo_lignes:
                    algorithme = '\n'.join(algo_lignes)
                    self.chatbot.logger.info("Algorithme extrait par fallback")

            return etapes, algorithme

        except Exception as e:
            self.chatbot.logger.error(f"Erreur critique dans _extraire_etapes_et_algo: {e}")
            return None, None

    def _extraire_reponse_directe(self, texte: str) -> str:
        """Extraction de la réponse directe"""

        patterns = [
            r'REPONSE:\s*\n(.*?)(?===|$)',
            r'=== SI REPONSE_DIRECTE ===\s*\n.*?REPONSE:\s*\n(.*?)(?===|$)',
            r'REPONSE:\s*(.*?)(?===|$)'
        ]

        for pattern in patterns:
            match = re.search(pattern, texte, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return None

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

    def _upload_fichier_to_gemini(self, fichiers_csv: List[str], state: ChatbotState):
        API_KEY = os.getenv("GEMINI_API_KEY")
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

    def _nettoyer_fichiers_gemini(self, fichiers_gemini: List, client, state: ChatbotState):
        """Supprime les fichiers uploadés chez Gemini"""

        for fichier in fichiers_gemini:
            try:
                client.files.delete(name=fichier.name)
                self.chatbot._log(f"Fichier Gemini supprimé: {fichier.name}", state)
            except Exception as e:
                self.chatbot._log_error(f"Erreur suppression Gemini {fichier.name}: {str(e)}", state)


    def _nettoyer_csvs_temporaires(self, fichiers_csv: List[str], state: ChatbotState):
        """Supprime les fichiers CSV temporaires"""

        for fichier in fichiers_csv:
            try:
                if os.path.exists(fichier):
                    os.remove(fichier)
                    self.chatbot._log(f"CSV local supprimé: {fichier}", state)
            except Exception as e:
                self.chatbot._log_error(f"Erreur suppression {fichier}: {str(e)}", state)

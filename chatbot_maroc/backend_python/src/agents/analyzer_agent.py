import re
import pandas as pd
from typing import Dict, List
from google.genai import types
from google import genai
from ..core.state import ChatbotState
from dotenv import load_dotenv
import os
from ..utils.message_to_front import _send_to_frontend
from ..core.memory_store import get_user_context

load_dotenv()


class AnalyzerAgent:
    """Agent analyseur pour déterminer le type de réponse nécessaire avec historique utilisateur"""

    def __init__(self, gemini_model, chatbot_instance):
        self.gemini_model = gemini_model
        self.chatbot = chatbot_instance

    def execute(self, state: ChatbotState) -> ChatbotState:
        """Point d'entrée principal de l'agent"""
        return self.agent_analyseur(state)

    def agent_analyseur(self, state: ChatbotState) -> ChatbotState:
        """Agent analyseur avec validation et historique utilisateur"""

        self.chatbot._log("Agent Analyseur: Début de l'analyse avec historique", state)
        session_id = state['session_id']
        _send_to_frontend(session_id,
                          f"Agent Analyse: Début Analyse avec historique sur '{state['question_utilisateur'][:50]}...'")

        # Récupérer les informations utilisateur
        username, email = self._extract_user_info(state)

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

        # Récupérer l'historique utilisateur
        historique_contexte = ""
        if username and email:
            historique_contexte = get_user_context(username, email)
            if historique_contexte and "Aucune conversation précédente" not in historique_contexte:
                self.chatbot._log(f" Historique utilisateur récupéré pour {username}", state)
                _send_to_frontend(session_id, f"Historique des conversations récupéré pour {username}")
            else:
                self.chatbot._log(f" Première conversation pour {username}", state)

        fichier_csv = self._creer_csvs_pour_gemini(state['dataframes'], state)
        fichier_gemini, client = self._upload_fichier_to_gemini(fichier_csv, state)
        state['fichiers_gemini'] = fichier_gemini

        # Prompt enrichi avec métadonnées ET historique
        prompt_unifie = f"""Tu es un expert en analyse de données du Maroc avec accès à l'historique des conversations.

{historique_contexte}

QUESTION UTILISATEUR ACTUELLE: {state['question_utilisateur']}

{contexte_complet}

SÉLECTION INTELLIGENTE:
{state.get('explication_selection', 'Tableaux sélectionnés automatiquement')}

INSTRUCTIONS STRICTES:
1. PRENDS EN COMPTE L'HISTORIQUE pour comprendre le contexte de la question actuelle
2. Si l'utilisateur fait référence à "la question précédente", "comme avant", "par rapport à ce qu'on a vu", utilise l'historique
3. Utilise les TITRES et CONTEXTES ci-dessus pour comprendre chaque dataframe
4. Choisis les dataframes selon leur PERTINENCE à la question ET au contexte historique
5. Si la réponse est évidente et directe : choisis REPONSE_DIRECTE  
6. Si tu dois croiser, calculer, filtrer ou faire des analyses complexes : choisis CALCULS_NECESSAIRES
7. Si la question fait référence à des résultats précédents, utilise l'historique pour contextualiser

FORMAT DE RÉPONSE OBLIGATOIRE:
DECISION: [CALCULS_NECESSAIRES ou REPONSE_DIRECTE]

=== SI CALCULS_NECESSAIRES ===
CONTEXTE_HISTORIQUE: [Mentionner comment l'historique influence l'analyse]
SOURCES_UTILISEES: [Mentionner les titres des dataframes à utiliser]
ETAPES: [Décrire les étapes en référençant les sources ET l'historique si pertinent]
ALGORITHME: [Pseudo-code avec df0, df1... ET leurs titres]

=== SI REPONSE_DIRECTE ===
CONTEXTE_HISTORIQUE: [Mentionner comment l'historique influence la réponse]
SOURCES_UTILISEES: [Mentionner les sources des données]
REPONSE: [Réponse complète avec références aux sources ET continuité avec l'historique si applicable]
"""

        try:
            _send_to_frontend(session_id,
                              "Début de la génération de réponse de l'agent analyseur avec contexte historique...")
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
            _send_to_frontend(session_id, "Réponse de l'analyseur générée avec historique")

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
                _send_to_frontend(session_id, "Calculs nécessaires: extraction des étapes et algorithme")
                etapes, algorithme = self._extraire_etapes_et_algo(answer)

                if etapes and algorithme:
                    state['besoin_calculs'] = True
                    state['instruction_calcul'] = etapes
                    state['algo_genere'] = algorithme
                    self.chatbot._log("Analyseur: Calculs nécessaires - algo extrait avec historique", state)
                else:
                    # Fallback intelligent
                    etapes_fallback, algo_fallback = self._extraction_fallback(answer)
                    if etapes_fallback and algo_fallback:
                        state['besoin_calculs'] = True
                        state['instruction_calcul'] = etapes_fallback
                        state['algo_genere'] = algo_fallback
                        self.chatbot._log("Analyseur: Extraction fallback réussie avec historique", state)
                    else:
                        state['besoin_calculs'] = False
                        state['reponse_finale'] = "Impossible d'extraire l'algorithme de calcul."

            elif "REPONSE_DIRECTE" in answer:
                _send_to_frontend(session_id, "Réponse direct: extraction de la réponse directe")
                reponse = self._extraire_reponse_directe(answer)
                if reponse:
                    state['besoin_calculs'] = False
                    state['reponse_finale'] = reponse
                    self.chatbot._log("Analyseur: Réponse directe extraite avec contexte historique", state)
                else:
                    state['besoin_calculs'] = False
                    state['reponse_finale'] = "Impossible d'extraire la réponse."

            else:
                # Analyse contextuelle de la question avec historique
                if self._question_necessite_calculs(state['question_utilisateur']):
                    state['besoin_calculs'] = True
                    # Enrichir les instructions avec le contexte historique s'il existe
                    instruction_base = f"Analyser les données pour répondre à : {state['question_utilisateur']}"
                    if username and email and "Aucune conversation précédente" not in historique_contexte:
                        instruction_base += " (en tenant compte de l'historique des conversations)"

                    state['instruction_calcul'] = instruction_base
                    state['algo_genere'] = "# Analyser les dataframes appropriés selon la question et l'historique"
                    self.chatbot._log("Analyseur: Fallback vers calculs détecté avec historique", state)
                else:
                    state['besoin_calculs'] = False
                    state['reponse_finale'] = "Format de réponse non reconnu de l'analyseur."

        except Exception as e:
            self.chatbot._log_error(f"Agent Analyseur: {str(e)}", state)
            state['besoin_calculs'] = False
            state['reponse_finale'] = "Erreur lors de l'analyse des données."

        finally:
            # Nettoyage sécurisé
            if 'fichiers_gemini' in locals():
                self._nettoyer_fichiers_gemini(fichier_gemini, client, state)

        return state

    def _extract_user_info(self, state: ChatbotState) -> tuple:
        """
        Extrait les informations utilisateur du state

        Returns:
            tuple: (username, email) ou (None, None) si non disponible
        """
        try:
            # Récupérer depuis les permissions/état utilisateur
            session_id = state.get('session_id', '')

            # Vérifier si les infos utilisateur sont directement dans le state
            # (Tu devras les ajouter lors de la création du state initial)
            username = state.get('username')
            email = state.get('email')

            if username and email:
                return username, email

            # Fallback temporaire basé sur le session_id et le rôle
            user_role = state.get('user_role', '')

            if session_id:
                # Logique temporaire - à remplacer par tes vraies données utilisateur
                if 'admin' in session_id or user_role == 'admin':
                    return 'admin_user', 'admin@amdie.ma'
                elif 'employee' in session_id or user_role == 'employee':
                    return 'employee_user', 'employee@amdie.ma'
                else:
                    return 'public_user', 'public@amdie.ma'

            return None, None

        except Exception as e:
            self.chatbot._log_error(f"Erreur extraction info utilisateur: {e}", state)
            return None, None

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


"""

        # Ajouter un échantillon des données
        contexte += "APERÇU DES DONNÉES:\n"
        for i, df in enumerate(dataframes_a_analyser[:3]):
            if not df.empty:
                contexte += f"   df{i} (premiers éléments): {', '.join(str(col) for col in df.columns[:3])}{'...' if len(df.columns) > 3 else ''}\n"

        return contexte

    def _question_necessite_calculs(self, question: str) -> bool:
        """Analyse la question pour déterminer si des calculs sont nécessaires"""

        question_lower = question.lower()

        calcul_keywords = ['total', 'combien', 'pourcentage', 'compare', 'plus', 'moins',
                           'moyenne', 'maximum', 'minimum', 'évolution', 'tendance',
                           'calcul', 'analyser', 'statistiques']

        return any(keyword in question_lower for keyword in calcul_keywords)

    def _extraction_fallback(self, texte: str) -> tuple:
        """Méthodes alternatives d'extraction"""

        # Méthode 1: Recherche de mots-clés
        if "calcul" in texte.lower() or "pandas" in texte.lower():
            etapes = "Analyser les données selon les instructions détectées et l'historique"
            algo = "# Analyser les dataframes selon la question posée et le contexte historique"
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
        # suppression immédiate des csvs
        self._nettoyer_csvs_temporaires(fichiers_csv, state)
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
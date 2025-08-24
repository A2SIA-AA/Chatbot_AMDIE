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
    """
    Classe CodeAgent.

    Cette classe représente un agent capable de générer et d'exécuter du code Python à l'aide du modèle Gemini.
    Elle est principalement utilisée pour traiter des données, analyser des instructions et retourner les résultats
    exécutés. L'agent utilise plusieurs étapes, telles que la transformation des DataFrames en fichiers CSV, leur
    upload vers le modèle Gemini, ainsi que l'envoi des prompts enrichis pour obtenir les sorties de code.

    :ivar gemini_model: Instance du modèle Gemini utilisée pour la génération de code.
    :type gemini_model: Any
    :ivar chatbot: Instance de chatbot pour la gestion des interactions et des journaux.
    :type chatbot: Any
    """

    def __init__(self, gemini_model, chatbot_instance):
        """
        Initialise une instance de la classe avec les paramètres spécifiés.

        :param gemini_model: Modèle Gemini utilisé pour certains traitements internes.
        :type gemini_model: Any
        :param chatbot_instance: Instance du chatbot utilisée pour des interactions spécifiques.
        :type chatbot_instance: Any
        """
        self.gemini_model = gemini_model
        self.chatbot = chatbot_instance

    def execute(self, state: ChatbotState) -> ChatbotState:
        """
        Exécute une fonction pour générer l'état mis à jour à partir d'un état actuel donné en utilisant un agent de
        générateur de code.

        :param state: L'état actuel du chatbot.
        :type state: ChatbotState
        :return: Un nouvel état mis à jour produit par l'agent générateur de code.
        :rtype: ChatbotState
        """
        return self.agent_generateur_code(state)

    def agent_generateur_code(self, state: ChatbotState) -> ChatbotState:
        """
        Génère et exécute du code Python basé sur des données fournies et des instructions utilisateur.

        Cette fonction prend en entrée un état de chatbot avec des informations nécessaires telles
        que des dataframe, une question utilisateur, un plan d'analyse et des métadonnées. Elle
        génère un prompt, effectue un appel à un modèle pour générer le code Python, exécute le code
        et recueille les résultats. L'objectif est de fournir des résultats pertinents au chatbot en
        réponse à la question utilisateur.

        Sections importantes :
        1. Création et téléchargement des fichiers CSV temporaires pour l'analyse.
        2. Génération du prompt basé sur les métadonnées et la question utilisateur.
        3. Interaction avec un modèle pour générer et exécuter du code à partir du prompt fourni.
        4. Gestion des résultats de l'exécution, autant sous forme de sortie directe que de code généré.
        5. Nettoyage des données temporaires créées pendant le processus.

        :param state:
            La structure de données contenant l'état du chatbot, y compris les données d'entrée,
            les métadonnées, les instructions et les espaces destinés à stocker les résultats.

        :return:
            L'état mis à jour incluant :
            - Les fichiers temporaires créés pour l'analyse.
            - Le code Python généré.
            - Les résultats d'analyse extraits (si disponibles).
            - Les erreurs rencontrées, le cas échéant.
            - Toute autre information pertinente ou enrichie ajoutée pendant le processus.

        :raises:
            - Peut lever des exceptions si des erreurs interviennent lors des étapes de génération,
              d'exécution du code ou de manipulation des fichiers, avec des messages d'erreur
              enregistrés dans l'état.
        """
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
                self._nettoyer_fichiers_gemini(state['fichiers_gemini'], client, state)

        return state

    def _generer_guide_sources_csv(self, dataframes: List[pd.DataFrame]) -> str:
        """
        Génère un guide décrivant les fichiers sources CSV à partir d'une liste de DataFrames pandas.

        Le guide inclut les informations sur le titre, la source, le contexte et les colonnes clés de
        chaque DataFrame de la liste.

        :param dataframes: Liste d'objets pandas DataFrame, chacun représentant un ensemble de
          données avec des attributs facultatifs tels que 'titre', 'source' et 'description'.
        :type dataframes: List[pd.DataFrame]
        :return: Une chaîne de texte formatée décrivant les fichiers sources CSV et leurs contextes.
        :rtype: str
        """

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
        """
        Extrait les sources utilisées à partir d'une réponse brute donnée. La méthode
        analyse la chaîne de caractères en cherchant des motifs spécifiques qui
        correspondent à des sources documentées. Si aucune source n'est identifiée,
        une valeur par défaut est retournée.

        :param reponse_brute: Chaîne de caractères contenant une réponse brute.
        :return: Sources extraites sous forme de chaîne de caractères.
        :rtype: str
        """

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
        """
        Télécharge les fichiers CSV spécifiés vers Gemini via l'API fournie par `genai.Client`.
        Après un téléchargement réussi, les fichiers temporaires sont supprimés.

        :param fichiers_csv: Liste des chemins des fichiers CSV à télécharger.
        :param state: Contient l'état du chatbot, utilisé pour la journalisation.
        :return: Une liste des fichiers téléchargés avec succès dans Gemini, ainsi que le
            client utilisé pour les opérations.
        :rtype: Tuple[List[Any], genai.Client]
        :raises Exception: Si une erreur survient lors du téléchargement d'un fichier.
        """
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
        """
        Cette fonction génère des fichiers CSV à partir de plusieurs DataFrames fournis. Pour chaque DataFrame
        non vide, un fichier CSV est créé avec un nom unique. Un journal des opérations est tenu tout au long du
        processus. En cas d'erreur, un message d'erreur est enregistré et la fonction retourne une liste vide.

        :param dataframes: Liste de DataFrames à convertir en fichiers CSV. Chaque DataFrame doit être issu de la
            librairie pandas.
        :type dataframes: List[pd.DataFrame]
        :param state: État actuel du Chatbot utilisé pour enregistrer les journaux et les erreurs tout au long du
            processus d'exécution.
        :type state: ChatbotState
        :return: Liste des noms des fichiers CSV créés. Si une erreur survient, une liste vide est retournée.
        :rtype: List[str]
        """

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
        """
        Supprime les fichiers CSV temporaires spécifiés et enregistre les logs appropriés
        dans l'instance de chatbot.

        Cette méthode vérifie d'abord si chaque fichier dans la liste fournie existe dans
        le système de fichiers local. Si le fichier existe, il est supprimé, et un message
        de log est enregistré pour confirmer la suppression. En cas d'erreur pendant la
        suppression d'un fichier, un message d'erreur contenant les détails de l'exception
        est enregistré dans les logs.

        :param fichiers_csv: Liste des chemins des fichiers CSV temporaires à supprimer.
        :type fichiers_csv: List[str]
        :param state: État actuel du chatbot utilisé pour enregistrer les logs.
        :type state: ChatbotState
        :return: None
        """

        for fichier in fichiers_csv:
            try:
                if os.path.exists(fichier):
                    os.remove(fichier)
                    self.chatbot._log(f"CSV local supprimé: {fichier}", state)
            except Exception as e:
                self.chatbot._log_error(f"Erreur suppression {fichier}: {str(e)}", state)

    def _nettoyer_fichiers_gemini(self, fichiers_gemini: List, client, state: ChatbotState):
        """
        Nettoie les fichiers Gemini donnés en appelant une méthode pour les supprimer
        et génère des logs pour suivre les opérations. Si une erreur survient lors
        de la suppression d'un fichier, elle est capturée et un message d'erreur
        est enregistré dans les logs.

        :param fichiers_gemini: Liste des fichiers Gemini à nettoyer.
        :type fichiers_gemini: List
        :param client: Client utilisé pour interagir avec les fichiers et effectuer leur suppression.
        :param state: Instance actuelle de l'état du chatbot, requise pour le suivi et les journaux.
        :type state: ChatbotState
        :return: Aucun retour.
        """

        for fichier in fichiers_gemini:
            try:
                client.files.delete(name=fichier.name)
                self.chatbot._log(f"Fichier Gemini supprimé: {fichier.name}", state)
            except Exception as e:
                self.chatbot._log_error(f"Erreur suppression Gemini {fichier.name}: {str(e)}", state)

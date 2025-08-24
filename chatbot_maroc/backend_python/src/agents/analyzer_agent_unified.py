import re
from google.genai import types
from google import genai
from ..core.state import ChatbotState
from dotenv import load_dotenv
import os
from ..utils.message_to_front import _send_to_frontend
from ..core.memory_store import get_user_context
import sys

load_dotenv()


class AnalyzerAgentUnified:
    """

    La classe AnalyzerAgentUnified est responsable d'exécuter des tâches d'analyse complexes sur des données Excel
    et PDF en utilisant des modèles d'IA et des outils d'automatisation. Elle gère également la communication avec
    un chatbot et garantit une analyse robuste avec des étapes définies de traitement des données.

    :ivar gemini_model: Référence au modèle Gemini utilisé pour les opérations d'analyse.
    :ivar chatbot: Instance de chatbot utilisée pour la journalisation et les interactions avec l'utilisateur.
    """

    def __init__(self, gemini_model, chatbot_instance):
        self.gemini_model = gemini_model
        self.chatbot = chatbot_instance

    def execute(self, state: ChatbotState) -> ChatbotState:
        """
        Exécute une analyse sur l'état actuel du chatbot et retourne un nouvel état
        après traitement par l'agent analyseur unifié.

        Le comportement de cette méthode dépend de la logique d'analyse définie
        par l'agent analyseur unifié. Elle prend en entrée l'état actuel du chatbot et
        le traite pour retourner un état mis à jour.

        :param state: L'état actuel du chatbot à traiter.
        :type state: ChatbotState
        :return: Le nouvel état du chatbot après traitement par l'agent analyseur unifié.
        :rtype: ChatbotState
        """
        return self.agent_analyseur_unifie(state)

    def agent_analyseur_unifie(self, state: ChatbotState) -> ChatbotState:
        """
        Analyse et traitement unifiés des documents Excel et PDF basés sur l'état actuel
        du chatbot. Ce processus intègre l'historique de l'utilisateur et finalise l'état
        après traitement des documents.

        :param state: L'état actuel du chatbot, encapsulant les données nécessaires au
            traitement et à l'analyse des documents.
        :type state: ChatbotState
        :return: L'état mis à jour du chatbot après l'exécution complète des analyses
            Excel et PDF.
        :rtype: ChatbotState
        """

        self.chatbot._log("Agent Analyseur Unifié: Début de l'analyse Excel + PDF", state)
        session_id = state.get('session_id')

        try:
            _send_to_frontend(session_id, "Agent Analyseur Unifié: Traitement Excel + PDF...")
        except Exception as e:
            print(f"Warning: Envoi frontend échoué: {e}")

        # Récupérer les informations utilisateur
        username, email = self._extract_user_info(state)

        # Récupérer l'historique utilisateur
        historique_contexte = self._get_user_context(username, email, state)

        # ========== PARTIE 1: ANALYSE EXCEL ==========
        excel_processed = self._analyze_excel_documents(state, historique_contexte)

        # ========== PARTIE 2: ANALYSE PDF  ==========
        pdf_processed = self._analyze_pdf_documents(state, historique_contexte)

        # ========== PARTIE 3: ÉTAT FINAL ==========
        self._finalize_analysis_state(state, excel_processed, pdf_processed)

        return state

    def _analyze_excel_documents(self, state: ChatbotState, historique_contexte: str) -> bool:
        """
        Analyse et traite les documents Excel pour identifier les données valides, les traiter et
        préparer une réponse basée sur leur contenu.

        Cette méthode prend en charge plusieurs étapes, incluant la création des DataFrames à partir
        des fichiers Excel, la préparation du contexte pour traitement, la gestion des erreurs durant
        les processus d'analyse, et l'envoi des données pour une analyse approfondie via un système
        externe. Une fois analysées, les données retournées peuvent être traitées et interprétées pour
        en extraire les informations pertinentes.

        :param state: Instance d'état contenant les informations de la session en cours.
        :param historique_contexte: Historique contextuel pour enrichir le prompt d'analyse.
        :return: Un booléen indiquant si l'analyse des documents Excel a été effectuée avec succès.
        """

        # Vérifier s'il y a des Excel à traiter
        tableaux_pour_upload = state.get('tableaux_pour_upload', [])

        if not tableaux_pour_upload:
            self.chatbot._log("Aucun tableau Excel à analyser", state)
            state['excel_empty'] = True
            return False

        self.chatbot._log(f"Analyse de {len(tableaux_pour_upload)} tableaux Excel", state)

        try:
            # Création des DataFrames avec validation
            state['dataframes'] = self._creer_dataframes_valides(tableaux_pour_upload, state)
            if not state['dataframes']:
                state['besoin_calculs'] = False
                state['reponse_finale'] = "Impossible de traiter les données Excel trouvées."
                return False


            contexte_complet = self._preparer_contexte_excel_avec_metadata(state)

            # Variables pour le nettoyage
            fichier_gemini = []
            client = None

            try:
                fichier_csv = self._creer_csvs_pour_gemini(state['dataframes'], state)
                if not fichier_csv:
                    raise Exception("Aucun fichier CSV créé")

                fichier_gemini, client = self._upload_fichier_to_gemini(fichier_csv, state)
                state['fichiers_gemini'] = fichier_gemini

                prompt_excel = self._creer_prompt_excel_unifie(state, contexte_complet, historique_contexte)

                try:
                    _send_to_frontend(state.get('session_id'), "Génération de réponse Excel...")
                except:
                    pass

                content = [prompt_excel]
                content.extend(fichier_gemini)

                self.chatbot._log(f" PROMPT EXCEL: {prompt_excel[:500]}...", state)
                self.chatbot._log(f" FICHIERS GEMINI: {len(fichier_gemini)} fichiers", state)

                response = self._call_gemini_with_retry(client, content, state)
                self.chatbot._log(f" FINISH_REASON: {response.candidates[0].finish_reason}", state)
                self.chatbot._log(f" HAS PARTS: {hasattr(response.candidates[0].content, 'parts')}", state)

                answer_text = self._extraire_contenu_gemini_robuste(response, state)
                self.chatbot._log(f" REPONSE EXTRAITE: {answer_text}", state)

                if not answer_text:
                    self._apply_excel_fallback(state, historique_contexte)
                    return True

                state['reponse_analyseur_brute'] = answer_text

                calculs_detected = self._parse_excel_response_avec_garantie_calculs(answer_text, state,
                                                                                    historique_contexte)

                if not calculs_detected:
                    self._apply_excel_fallback(state, historique_contexte)

                self.chatbot._log(f"Analyse Excel terminée - Calculs nécessaires: {state.get('besoin_calculs', False)}",
                                  state)
                return True

            except Exception as e:
                self.chatbot._log_error(f"Erreur analyse Excel: {str(e)}", state)
                self._handle_excel_error(e, state)
                return False

            finally:
                # Nettoyage garanti
                if fichier_gemini and client:
                    try:
                        self._nettoyer_fichiers_gemini(fichier_gemini, client, state)
                    except Exception as e:
                        self.chatbot._log_error(f"Erreur nettoyage: {e}", state)

        except Exception as e:
            self.chatbot._log_error(f"Erreur création DataFrames Excel: {str(e)}", state)
            state['besoin_calculs'] = False
            state['reponse_finale'] = "Erreur lors du traitement des données Excel."
            return False

    def _analyze_pdf_documents(self, state: ChatbotState, historique_contexte: str) -> bool:
        """
        Analyse les documents PDF spécifiés dans l'état du chatbot et génère des réponses
        en fonction de leur contenu en utilisant le service Gemini.

        Cette méthode vérifie d'abord l'existence des documents PDF à analyser. Les documents
        sont ensuite téléchargés sur le service Gemini pour une analyse approfondie selon une
        question fournie par l'utilisateur. Si l'analyse est réussie, la réponse correspondante
        et les sources des documents sont stockées dans l'état. En cas d'échec, aucune réponse
        n'est générée.

        :param state: Un objet représentant l'état actuel du chatbot, contenant des
                      informations nécessaires pour l'analyse.
        :type state: ChatbotState
        :param historique_contexte: Une chaîne représentant l'historique contextuel du
                                     chatbot durant l'interaction.
        :type historique_contexte: str
        :return: Indique si l'analyse des documents PDF a réussi ou échoué.
        :rtype: bool

        :raises Exception: Si une erreur inattendue survient lors de l'analyse ou du
                           téléchargement des documents.
        """

        pdfs_pour_upload = state.get('pdfs_pour_upload', [])

        if not pdfs_pour_upload:
            self.chatbot._log("Aucun document PDF à analyser", state)
            state['reponse_finale_pdf'] = ""
            state['sources_pdf'] = []
            return False

        self.chatbot._log(f" DEBUG PDF: {len(pdfs_pour_upload)} PDFs à analyser", state)

        try:
            # Upload des PDFs vers Gemini
            fichiers_pdf_gemini = []
            client = None

            for i, pdf_info in enumerate(pdfs_pour_upload):
                self.chatbot._log(f" DEBUG PDF {i}: {pdf_info.keys()}", state)

                pdf_path = pdf_info.get('pdf_path') or pdf_info.get('tableau_path')
                self.chatbot._log(f" PDF path: {pdf_path}", state)

                if pdf_path and os.path.exists(pdf_path):
                    self.chatbot._log(f" PDF existe: {pdf_path}", state)
                    try:
                        if not client:
                            API_KEY = os.getenv("GEMINI_API_KEY")
                            client = genai.Client(api_key=API_KEY)

                        # Upload du PDF vers Gemini
                        self.chatbot._log(f" Upload PDF vers Gemini...", state)
                        fichier_pdf = client.files.upload(file=pdf_path)
                        fichiers_pdf_gemini.append(fichier_pdf)
                        self.chatbot._log(f" PDF {i + 1} uploadé: {fichier_pdf.name}", state)
                    except Exception as e:
                        self.chatbot._log_error(f" Erreur upload PDF {i + 1}: {e}", state)
                else:
                    self.chatbot._log(f" PDF {i + 1} inexistant: {pdf_path}", state)

            if not fichiers_pdf_gemini:
                self.chatbot._log(" Aucun PDF uploadé avec succès", state)
                return False

            self.chatbot._log(f" {len(fichiers_pdf_gemini)} PDFs uploadés, analyse...", state)

            # Créer le prompt avec les PDFs uploadés
            prompt_pdf = f"""Tu es un expert qui analyse le contenu COMPLET des documents PDF.

    QUESTION: {state['question_utilisateur']}

    INSTRUCTIONS:
    1. Lis attentivement le contenu de tous les PDFs fournis
    2. Réponds directement à la question avec les informations des PDFs
    3. Si les PDFs ne contiennent pas d'info pertinente, dis-le clairement

    RÉPONSE:"""

            # Appel Gemini avec les PDFs
            content = [prompt_pdf]
            content.extend(fichiers_pdf_gemini)

            self.chatbot._log(" Appel Gemini avec PDFs...", state)

            response = client.models.generate_content(
                model="gemini-2.5-pro",
                contents=content,
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    candidate_count=1,
                    max_output_tokens=8192
                )
            )

            # Extraction et stockage
            #self.chatbot._log(f"REPONSE GEMINI : {response}",state)
            answer_text_pdf = self._extraire_contenu_gemini_robuste(response, state)

            self.chatbot._log(f" Réponse PDF: {answer_text_pdf[:100] if answer_text_pdf else 'None'}...", state)

            if answer_text_pdf:
                state['reponse_finale_pdf'] = answer_text_pdf
                state['sources_pdf'] = [pdf.get('titre_contextuel', 'PDF') for pdf in pdfs_pour_upload]
                self.chatbot._log(" Analyse PDF réussie", state)

                # Nettoyage Gemini
                for fichier in fichiers_pdf_gemini:
                    try:
                        client.files.delete(name=fichier.name)
                    except:
                        pass

                return True
            else:
                self.chatbot._log(" Extraction réponse PDF échouée", state)
                return False

        except Exception as e:
            self.chatbot._log_error(f" Erreur analyse PDF: {e}", state)
            import traceback
            self.chatbot._log_error(f"Traceback: {traceback.format_exc()}", state)
            return False

    def _parse_excel_response_avec_garantie_calculs(self, answer_text, state, historique_contexte):
        """
        Analyse et traite une réponse Excel fournie afin de déterminer si elle nécessite des
        calculs ou si elle contient une réponse directe. Si des calculs sont nécessaires,
        génère des étapes d'instructions et un algorithme correspondant. En cas de réponse
        directe, extrait et retourne cette réponse. Garantit une analyse ou une réponse
        adéquate même en cas d'erreur.

        :param answer_text: Texte de réponse à analyser et traiter
        :type answer_text: str
        :param state: Dictionnaire contenant l'état courant, incluant la question, les résultats
                      intermédiaires et les données contextuelles
        :type state: dict
        :param historique_contexte: Historique des interactions ou contexte supplémentaire
        :type historique_contexte: list
        :return: Indique si une analyse ou un traitement des calculs ont été réalisés
        :rtype: bool
        """

        if not answer_text or not isinstance(answer_text, str):
            self.chatbot._log_error("answer_text invalide pour parsing Excel", state)
            return False

        self.chatbot._log(f" DEBUT PARSING - Longueur: {len(answer_text)}", state)
        self.chatbot._log(f" APERÇU RÉPONSE: '{answer_text[:200]}...'", state)

        try:
            self.chatbot._log(f"Parsing Excel de '{answer_text[:150]}...'", state)

            patterns_calculs = [
                r'TYPE\s*:\s*CALCULS',
                r'CALCULS_NECESSAIRES',
                r'FORMAT\s*1',
                r'ETAPES?\s*:',
                r'ALGORITHME\s*:',
                r'```python',
                r'df\d+\.',
                r'besoin.*calcul',
                r'exécuter.*code',
                r'analyser.*données'
            ]

            patterns_direct = [
                r'TYPE\s*:\s*DIRECT',
                r'REPONSE_DIRECTE',
                r'FORMAT\s*2',
                r'REPONSE\s*:',
            ]

            is_calculs = False
            is_direct = False

            for pattern in patterns_calculs:
                if re.search(pattern, answer_text, re.IGNORECASE):
                    is_calculs = True
                    break

            for pattern in patterns_direct:
                if re.search(pattern, answer_text, re.IGNORECASE):
                    is_direct = True
                    break

            question = state.get('question_utilisateur', '').lower()
            question_needs_calculs = any(word in question for word in [
                'combien', 'pourcentage', 'total', 'moyenne', 'maximum', 'minimum',
                'calcul', 'analyse', 'compare', 'évolution', 'statistique',
                'quelle ville', 'plus élevé', 'proportion', 'tendance'
            ])

            self.chatbot._log(f" PATTERNS - CALCULS: {is_calculs}, DIRECT: {is_direct}", state)
            if is_calculs or (question_needs_calculs and not is_direct):
                self.chatbot._log(" BRANCHE CALCULS ACTIVÉE", state)
                self.chatbot._log("CALCULS DÉTECTÉS - Extraction des étapes", state)

                etapes, algorithme = self._extraire_etapes_et_algo_flexible(answer_text)

                if etapes and algorithme:
                    state['besoin_calculs'] = True
                    state['instruction_calcul'] = etapes
                    state['algo_genere'] = algorithme
                    self.chatbot._log(" CALCULS GARANTIS - Étapes et algo extraits", state)
                    return True
                else:
                    self.chatbot._log(" FALLBACK CALCULS - Génération automatique", state)
                    state['besoin_calculs'] = True
                    state[
                        'instruction_calcul'] = f"Analyser les données pour répondre à : {state['question_utilisateur']}"

                    # Algo intelligent basé sur la question
                    if 'total' in question or 'somme' in question:
                        state['algo_genere'] = "# Calculer les totaux\nresultat = df0.sum(numeric_only=True)"
                    elif 'moyenne' in question:
                        state['algo_genere'] = "# Calculer les moyennes\nresultat = df0.mean(numeric_only=True)"
                    elif 'compare' in question:
                        state['algo_genere'] = "# Comparer les données\nresultat = df0.groupby(df0.columns[0]).sum()"
                    else:
                        state['algo_genere'] = "# Analyser les données selon la question\nresultat = df0.describe()"

                    self.chatbot._log(" CALCULS GARANTIS - Fallback appliqué", state)
                    return True

            elif is_direct:
                self.chatbot._log("RÉPONSE DIRECTE DÉTECTÉE", state)
                reponse = self._extraire_reponse_directe_flexible(answer_text)
                if reponse:
                    state['besoin_calculs'] = False
                    state['reponse_finale'] = reponse
                    self.chatbot._log("Réponse directe Excel extraite", state)
                    return True

            # FALLBACK FINAL BASÉ SUR LA QUESTION
            if question_needs_calculs:
                self.chatbot._log(" GARANTIE FINALE - Question nécessite des calculs", state)
                state['besoin_calculs'] = True
                state['instruction_calcul'] = f"Analyser les données pour : {state['question_utilisateur']}"
                state['algo_genere'] = "# Analyser les dataframes selon la question\nresultat = df0.describe()"
                return True
            else:
                self.chatbot._log("Question factuelle - pas de calculs nécessaires", state)
                return False

        except Exception as e:
            self.chatbot._log_error(f"Erreur parsing Excel: {e}", state)
            # MÊME EN CAS D'ERREUR, SI LA QUESTION NÉCESSITE DES CALCULS, ON LES FAIT
            question = state.get('question_utilisateur', '').lower()
            if any(word in question for word in ['combien', 'pourcentage', 'calcul', 'analyse']):
                self.chatbot._log(" ERREUR MAIS CALCULS FORCÉS", state)
                state['besoin_calculs'] = True
                state['instruction_calcul'] = f"Analyser les données pour : {state['question_utilisateur']}"
                state['algo_genere'] = "# Analyse de base\nresultat = df0.describe()"
                return True
            return False

    def _finalize_analysis_state(self, state: ChatbotState, excel_processed: bool, pdf_processed: bool):
        """
        Met à jour et enregistre l'état final de l'analyse en fonction des résultats
        des traitements effectués sur les fichiers Excel et PDF. Cette méthode
        enregistre des messages de journalisation en fonction des conditions remplies
        et vérifie également la présence des réponses issues des analyses Excel, PDF,
        ainsi que des calculs éventuels.

        :param state: L'état actuel du chatbot. Contient des informations sur les calculs
            et les réponses déjà générées.
        :type state: ChatbotState
        :param excel_processed: Indique si le fichier Excel a été traité avec succès.
        :type excel_processed: bool
        :param pdf_processed: Indique si le fichier PDF a été traité avec succès.
        :type pdf_processed: bool
        :return: Aucun résultat n'est retourné.
        :rtype: None
        """

        if excel_processed and pdf_processed:
            self.chatbot._log(" Analyses Excel + PDF terminées avec succès", state)
        elif excel_processed:
            self.chatbot._log(" Analyse Excel seule terminée", state)
        elif pdf_processed:
            self.chatbot._log(" Analyse PDF seule terminée", state)
        else:
            self.chatbot._log(" Aucune analyse n'a abouti", state)

        # Debug des résultats
        has_calculs = state.get('besoin_calculs', False)
        has_excel_response = bool(state.get('reponse_finale', ''))
        has_pdf_response = bool(state.get('reponse_finale_pdf', ''))

        self.chatbot._log(
            f"État final: calculs={has_calculs}, excel_response={has_excel_response}, pdf_response={has_pdf_response}",
            state)


    def _get_user_context(self, username, email, state):
        """
        Récupère le contexte utilisateur basé sur le nom d'utilisateur et l'email. Si le contexte
        peut être récupéré et qu'il n'indique aucune conversation précédente, un message de
        journalisation est enregistré. En cas d'erreur, un message d'erreur est enregistré
        et une chaîne vide est retournée.

        :param username: Le nom d'utilisateur pour identifier l'utilisateur.
        :type username: str
        :param email: L'adresse email associée à l'utilisateur.
        :type email: str
        :param state: L'état actuel ou contexte d'exécution en cours.
        :type state: Any
        :return: Une chaîne contenant le contexte utilisateur ou une chaîne vide si le contexte
                 ne peut pas être récupéré.
        :rtype: str
        """
        historique_contexte = ""
        try:
            if username and email:
                historique_contexte = get_user_context(username, email)
                if historique_contexte and "Aucune conversation précédente" not in historique_contexte:
                    self.chatbot._log(f"Historique utilisateur récupéré pour {username}", state)
                else:
                    self.chatbot._log(f"Première conversation pour {username}", state)
        except Exception as e:
            self.chatbot._log_error(f"Récupération historique: {e}", state)
            historique_contexte = ""
        return historique_contexte

    def _extract_user_info(self, state: ChatbotState) -> tuple:
        """
        Extrait les informations de l'utilisateur depuis l'état d'un chatbot. Cette méthode analyse
        l'état fourni pour identifier et retourner le nom d'utilisateur et l'adresse email correspondante.
        Si les informations ne sont pas directement disponibles, elle établit des valeurs par défaut en
        fonction du rôle d'utilisateur trouvé dans l'état. En cas d'erreur, une journalisation est effectuée.

        :param state: Représente l'état actuel du chatbot contenant les informations de l'utilisateur.
        :type state: ChatbotState

        :return: Une paire (tuple) contenant le nom d'utilisateur et son adresse email. Retourne
                 (None, None) en cas d'échec ou si les informations ne sont pas disponibles.
        :rtype: tuple
        """
        try:
            session_id = state.get('session_id', '')
            username = state.get('username')
            email = state.get('email')

            if username and email:
                return username, email

            user_role = state.get('user_role', '')

            if session_id:
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

    def _creer_prompt_excel_unifie(self, state, contexte_complet, historique_contexte):
        """
        Crée un prompt unifié pour une analyse de données basée sur le contexte donné. Le prompt généré
        fournit une structure strictement formatée pour répondre aux questions des utilisateurs sur des
        données Excel avec une perspective spécifique au Maroc.

        :param state: Dictionnaire contenant la question de l'utilisateur sous la clé
            'question_utilisateur'.
        :type state: dict
        :param contexte_complet: Chaîne représentant le contexte complet qui sera intégré au prompt.
        :type contexte_complet: str
        :param historique_contexte: Historique ou contexte supplémentaire qui peut être utilisé pour
            enrichir le prompt.
        :type historique_contexte: str
        :return: Une chaîne formatée qui constitue le prompt pour répondre à la question utilisateur.
        :rtype: str
        """

        prompt = f"""Tu es un expert en analyse de données du Maroc.

    QUESTION: {state['question_utilisateur']}

    {contexte_complet}

    RÈGLE SIMPLE: 
    - Si la question nécessite des CALCULS (pourcentage, total, comparaison) → réponds "TYPE: CALCULS"
    - Sinon → réponds "TYPE: DIRECT" suivi de ta réponse

    FORMAT DE RÉPONSE OBLIGATOIRE:
TYPE: CALCULS

INSTRUCTION_CALCUL: [description des étapes]

ALGORITHME: [étapes détaillées]

SOURCES_UTILISEES: [sources]
"""



        return prompt


    def _extraire_contenu_gemini_robuste(self, response, state):
        """
        Extrait de manière robuste le contenu textuel depuis la réponse d'un service Gemini.

        Ce traitement analyse les composants de la réponse pour extraire toutes les parties textuelles
        disponibles et les concatène en une seule chaîne de caractères. Si aucune partie textuelle
        n'est disponible ou si une erreur se produit durant cette extraction, la fonction retourne `None`.

        :param response: La réponse du service Gemini contenant potentiellement des données candidates
            avec du contenu structuré.
        :type response: object
        :param state: État courant de l'application ou de la session permettant de journaliser les informations.
        :type state: object
        :return: Une chaîne de texte combinée issue des parties disponibles, ou `None` si rien n'est extrait
            ou qu'une erreur survient.
        :rtype: Optional[str]
        """
        try:
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'content') and candidate.content:
                    if hasattr(candidate.content, 'parts') and candidate.content.parts:

                        self.chatbot._log(f" PARTS COUNT: {len(candidate.content.parts)}", state)
                        for i, part in enumerate(candidate.content.parts):
                            self.chatbot._log(f" PART {i}: {type(part)} - hasattr text: {hasattr(part, 'text')}",
                                              state)
                            if hasattr(part, 'text'):
                                self.chatbot._log(f" PART {i} TEXT: {part.text}", state)

                        all_text = []
                        for part in candidate.content.parts:
                            if hasattr(part, 'text') and part.text:
                                all_text.append(part.text)
                        if all_text:
                            return '\n'.join(all_text).strip()
            return None
        except Exception as e:
            self.chatbot._log_error(f"Erreur extraction: {e}", state)
            return None

    def _extraire_etapes_et_algo_flexible(self, texte):
        """
        Extrait les étapes et l'algorithme d'un texte donné en utilisant des expressions
        régulières pour garantir une extraction flexible et robuste. Cette méthode
        accepte un texte structuré contenant des sections telles que "ETAPES" et
        "ALGORITHME". Elle tente de localiser et de découper ces sections en fonction
        de plusieurs motifs prédéfinis.

        Si aucune section valide n'est trouvée, la méthode retourne None.

        :param texte: Contenu textuel à partir duquel les étapes et l'algorithme
            seront extraits.
        :type texte: str
        :return: Une paire composée des étapes extraites sous forme de texte
            et de l'algorithme extrait. Si aucun élément n'est trouvé,
            retourne deux valeurs None.
        :rtype: Tuple[Optional[str], Optional[str]]
        """
        if not texte or not isinstance(texte, str):
            return None, None

        # Patterns multiples pour extraction robuste
        patterns_etapes = [
            r'ETAPES?\s*:?\s*\n(.*?)(?=ALGORITHME|```|$)',
            r'(\d+\..*?)(?=ALGORITHME|```|$)',
        ]

        patterns_algo = [
            r'ALGORITHME\s*:?\s*\n(.*?)(?=```|$)',
            r'```python\s*(.*?)```',
            r'```\s*(.*?)```',
        ]

        etapes = None
        algorithme = None

        # Extraction des étapes
        for pattern in patterns_etapes:
            try:
                match = re.search(pattern, texte, re.DOTALL | re.IGNORECASE)
                if match and match.group(1):
                    extracted = match.group(1).strip()
                    if len(extracted) > 10:
                        etapes = extracted
                        break
            except:
                continue

        # Extraction de l'algorithme
        for pattern in patterns_algo:
            try:
                match = re.search(pattern, texte, re.DOTALL | re.IGNORECASE)
                if match and match.group(1):
                    extracted = match.group(1).strip()
                    if len(extracted) > 5:
                        algorithme = extracted
                        break
            except:
                continue

        return etapes, algorithme

    def _extraire_reponse_directe_flexible(self, texte):
        """
        Extrait une réponse directe depuis une chaîne de texte en utilisant des expressions
        régulières pour identifier des modèles spécifiques. Le processus tente
        d'abord les motifs les plus restrictifs avant de passer à ceux plus généraux.

        :param texte: Chaîne de texte contenant des informations structurées
            à analyser.
        :type texte: str
        :return: La réponse directe extraite si trouvée et valide, ou None sinon.
        :rtype: str | None
        """

        if not texte or not isinstance(texte, str) or len(texte) < 10:
            return None

        try:
            patterns_reponse = [
                # Pattern 1: Directement après TYPE: DIRECT
                r'TYPE\s*:\s*DIRECT\s*\n(.*?)(?=\n\s*===|$)',
                r'TYPE\s*:\s*DIRECT\s+(.*?)(?=\n\s*===|$)',

                r'REPONSE\s*:?\s*(.*?)(?=\n\s*===|$)',
                r'TYPE\s*:\s*DIRECT.*?REPONSE\s*:?\s*(.*?)(?=\n\s*===|$)',
                r'(?:TYPE.*?\n|HISTORIQUE.*?\n)+(.*?)$',
            ]

            for pattern in patterns_reponse:
                try:
                    match = re.search(pattern, texte, re.DOTALL | re.IGNORECASE)
                    if match and match.group(1):
                        reponse = match.group(1).strip()
                        if reponse and len(reponse) > 15 and not reponse.isspace():
                            # Nettoyer la réponse
                            reponse = re.sub(r'\n+', '\n', reponse)
                            self.chatbot._log(f" REPONSE EXTRAITE: '{reponse[:100]}...'", {})
                            return reponse
                except Exception as e:
                    continue

            return None

        except Exception as e:
            self.chatbot._log_error(f"Erreur extraction reponse directe: {e}", {})
            return None



    def _apply_excel_fallback(self, state, historique_contexte):
        """
        Analyse le contexte d'une question utilisateur pour déterminer si une analyse
        basée sur des calculs est nécessaire et applique des instructions adaptées en
        conséquence.

        Cette méthode évalue si une question utilisateur contient des mots-clés
        impliquant un besoin d'analyse ou de calcul via l'exploration de données dans
        un contexte donné. Si un besoin de calcul est détecté, une réponse spécifique
        et des instructions de calcul sont générées. Sinon, une réponse générique est
        assignée au contexte.

        :param state: L'état courant du processus d'analyse, contenant notamment la
            question utilisateur sous forme de chaîne de caractères et d'autres
            informations sur le contexte.
        :type state: dict
        :param historique_contexte: L'historique du contexte pour maintenir une traçabilité
            des interactions.
        :type historique_contexte: list
        :return: Cette méthode ne retourne rien. Elle modifie directement le dictionnaire
            `state` en fonction de l'analyse réalisée.
        :rtype: None
        """
        question = state.get('question_utilisateur', '').lower()

        if any(word in question for word in ['combien', 'pourcentage', 'calcul', 'analyse', 'total']):
            state['besoin_calculs'] = True
            state['instruction_calcul'] = f"Analyser les données pour : {state['question_utilisateur']}"
            state['algo_genere'] = "# Analyse fallback\nresultat = df0.describe()"
            self.chatbot._log(" FALLBACK EXCEL - Calculs forcés", state)
        else:
            state['besoin_calculs'] = False
            state['reponse_finale'] = f"Analyse en cours pour : {state['question_utilisateur']}"
            self.chatbot._log(" FALLBACK EXCEL - Réponse directe", state)

    def _handle_excel_error(self, error, state):
        """
        Gère une erreur technique liée à Excel en modifiant l'état fourni et en enregistrant un message d'erreur.

        L'état est mis à jour pour indiquer qu'aucun calcul supplémentaire n'est nécessaire, et un message d'erreur
        est enregistré pour permettre un retour clair à l'utilisateur.

        :param error: Objet représentant l'erreur technique capturée.
        :type error: Exception
        :param state: Dictionnaire représentant l'état courant, qui sera modifié pour inclure l'information liée à l'erreur.
        :type state: dict
        :return: Aucun retour explicite. L'état est modifié directement.
        :rtype: None
        """
        state['besoin_calculs'] = False
        state['reponse_finale'] = f"Erreur technique Excel: {str(error)[:100]}..."

    def _preparer_contexte_excel_avec_metadata(self, state):
        """
        Prépare un contexte Excel avec des métadonnées pour l'analyse.

        Cette fonction génère une chaîne de caractères décrivant les données disponibles
        pour l'analyse, notamment les tableaux et dataframes présents, leur structure,
        et les colonnes qu'ils contiennent. Cela inclut des détails tels que le titre
        contextuel, le fichier source et la feuille associée. Seules les colonnes
        des cinq premières colonnes sont affichées pour chaque dataframe.

        :param state: Un dictionnaire contenant des informations sur les tableaux importés
                      et les dataframes correspondants, avec les clés 'tableaux_pour_upload'
                      et 'dataframes'.
        :type state: dict

        :return: Une chaîne de caractères contenant un résumé formaté des tableaux et
                 dataframes disponibles pour l'analyse.
        :rtype: str
        """
        contexte = "DONNÉES DISPONIBLES POUR L'ANALYSE:\n\n"
        tableaux_a_analyser = state.get('tableaux_pour_upload', [])
        dataframes_a_analyser = state.get('dataframes', [])

        for i, (tableau, df) in enumerate(zip(tableaux_a_analyser, dataframes_a_analyser)):
            titre = tableau.get('titre_contextuel', f'Tableau {i}')
            source = tableau.get('fichier_source', 'N/A')
            feuille = tableau.get('nom_feuille', 'N/A')

            contexte += f"""DATAFRAME df{i}: "{titre}"
   Source: {source} -> Feuille "{feuille}" 
   Structure: {len(df)} lignes × {len(df.columns)} colonnes
   Colonnes: {', '.join(str(col) for col in df.columns[:5])}

"""
        return contexte



    def _creer_dataframes_valides(self, tableaux_charges, state):
        """
        Génère une liste de DataFrames valides à partir d'une liste de tableaux
        fournis en entrée. Chaque DataFrame passe par un processus de nettoyage,
        puis est complété avec des méta-données provenant des tableaux d'origine.
        Si une erreur survient lors de la création ou du nettoyage d'un DataFrame,
        l'erreur est enregistrée mais l'exécution continue pour les tableaux
        suivants.

        :param tableaux_charges: Liste de dictionnaires représentant les tableaux
            à convertir en DataFrames. Chaque dictionnaire doit inclure des
            informations comme le titre contextuel, le fichier source, et le nom
            de la feuille (si applicables).
        :type tableaux_charges: list[dict]
        :param state: Dictionnaire ou objet contenant l'état actuel, utilisé
            pour enregistrer des informations concernant les erreurs
            ou événements lors du processus.
        :type state: dict
        :return: Liste de pandas DataFrames valides, accompagnés
            de leurs méta-données.
        :rtype: list[pandas.DataFrame]
        """
        dataframes = []
        for i, tableau in enumerate(tableaux_charges):
            try:
                df = self.chatbot.pandas_agent.creer_dataframe_propre(tableau)
                if df is not None and not df.empty:
                    df.attrs.update({
                        'titre': tableau.get('titre_contextuel', f'Tableau {i}'),
                        'source': tableau.get('fichier_source', 'N/A'),
                        'feuille': tableau.get('nom_feuille', 'N/A'),
                    })
                    dataframes.append(df)
            except Exception as e:
                self.chatbot._log_error(f"Création DataFrame {i}: {str(e)}", state)
        return dataframes

    def _creer_csvs_pour_gemini(self, dataframes, state):
        """
        Génère un ensemble de fichiers CSV à partir d'une liste de DataFrames fournie.
        Chaque DataFrame valide (non vide et non nul) est converti en fichier CSV et nommé
        de manière incrémentale. Retourne une liste des noms de fichiers CSV créés. En cas
        d'erreur, un message est enregistré dans le journal.

        :param dataframes: Liste de pandas.DataFrame à convertir en fichiers CSV
        :param state: État actuel du programme, utilisé pour consigner les erreurs dans le journal
        :return: Liste des chemins des fichiers CSV générés
        :rtype: list
        """
        fichiers_csv = []
        try:
            for i, df in enumerate(dataframes):
                if df is not None and not df.empty:
                    nom_fichier = f'df{i}_analysis.csv'
                    df.to_csv(nom_fichier, index=False, encoding='utf-8')
                    fichiers_csv.append(nom_fichier)
        except Exception as e:
            self.chatbot._log_error(f"Erreur création CSV: {str(e)}", state)
        return fichiers_csv

    def _upload_fichier_to_gemini(self, fichiers_csv, state):
        """
        Télécharge une liste de fichiers CSV vers Gemini via l'API.

        Cette méthode reçoit une liste de fichiers CSV, les télécharge vers la plateforme
        Gemini à l'aide de son API, et retourne les fichiers téléchargés ainsi que
        le client utilisé pour l'opération. En cas d'échec, une exception est levée
        et consignée dans les journaux d'erreur.

        :param fichiers_csv: Liste des fichiers CSV à télécharger.
        :type fichiers_csv: list[str]
        :param state: État ou contexte lié au processus actuel utilisé pour journaliser
            des erreurs.
        :type state: Any
        :return: Une liste des fichiers téléchargés et le client utilisé pour l'opération.
        :rtype: tuple[list[object], genai.Client]
        :raises Exception: Si une erreur survient lors du téléchargement des fichiers.
        """
        API_KEY = os.getenv("GEMINI_API_KEY")
        client = genai.Client(api_key=API_KEY)
        fichiers_gemini = []
        for fichier_csv in fichiers_csv:
            try:
                fichier_uploade = client.files.upload(file=fichier_csv)
                fichiers_gemini.append(fichier_uploade)
            except Exception as e:
                self.chatbot._log_error(f"Erreur upload {fichier_csv}: {str(e)}", state)
                raise e
        self._nettoyer_csvs_temporaires(fichiers_csv, state)
        return fichiers_gemini, client

    def _nettoyer_fichiers_gemini(self, fichiers_gemini, client, state):
        """
        Nettoie une liste de fichiers Gemini en supprimant chacun d'entre eux via le client spécifié.
        En cas d'erreur lors de la suppression d'un fichier, l'erreur est enregistrée à l'aide
        du système de journalisation du chatbot.

        :param fichiers_gemini: Liste des fichiers Gemini à supprimer.
        :param client: Instance du client utilisé pour la suppression des fichiers.
        :param state: Objet représentant l'état à utiliser pour enregistrer les erreurs.
        :return: Aucun.
        """
        for fichier in fichiers_gemini:
            try:
                client.files.delete(name=fichier.name)
            except Exception as e:
                self.chatbot._log_error(f"Erreur suppression Gemini: {str(e)}", state)

    def _nettoyer_csvs_temporaires(self, fichiers_csv, state):
        """
        Supprime les fichiers CSV temporaires spécifiés.

        Cette méthode parcourt une liste de fichiers CSV et tente de les supprimer s'ils
        existent. En cas d'erreur lors de la suppression, un message d'erreur est
        enregistré grâce à la méthode `_log_error` de l'objet chatbot. Cette méthode est
        utile pour nettoyer les fichiers temporaires inutilisés après leur traitement.

        :param fichiers_csv: Une liste contenant les chemins des fichiers CSV à supprimer.
        :type fichiers_csv: list[str]
        :param state: État ou contexte utilisé pour enregistrer les erreurs pendant la suppression.
        :type state: Any
        :return: Cette fonction ne renvoie aucune valeur.
        :rtype: None
        """
        for fichier in fichiers_csv:
            try:
                if os.path.exists(fichier):
                    os.remove(fichier)
            except Exception as e:
                self.chatbot._log_error(f"Erreur suppression {fichier}: {str(e)}", state)

    def _call_gemini_with_retry(self, client, content, state, max_retries=3):
        """
        Exécute un appel à l'API Gemini avec des tentatives automatiques en cas de
        défaillances. Cette méthode effectue un maximum de `max_retries` tentatives
        avant de lever une exception en cas d'échec.

        Les délais entre les tentatives augmentent de manière exponentielle, suivant
        la formule 2 ** attempt.

        :param client: Client utilisé pour interagir avec l'API Gemini.
        :type client: object
        :param content: Contenu à envoyer dans la requête pour la génération.
        :type content: list ou str
        :param state: État ou contexte associé à la génération.
        :type state: dict
        :param max_retries: Nombre maximum de tentatives autorisées en cas d'échec.
        Valeur par défaut : 3.
        :type max_retries: int

        :return: La réponse générée par l'API Gemini si réussie.
        :rtype: object

        :raises Exception: Si tous les essais échouent ou si la réponse est invalide.
        """
        import time
        for attempt in range(max_retries):
            try:

                response = client.models.generate_content(
                    model="gemini-2.5-pro",
                    contents=content,
                    config=types.GenerateContentConfig(
                        temperature=0.1,
                        candidate_count=1,
                        max_output_tokens=8192,
                        thinking_config=types.ThinkingConfig(include_thoughts=False)
                    )
                )
                if response and response.candidates:
                    return response
                else:
                    raise Exception("Réponse Gemini invalide")
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                else:
                    raise e
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
    """Agent analyseur unifié qui gère Excel ET PDFs avec GARANTIE des calculs Excel"""

    def __init__(self, gemini_model, chatbot_instance):
        self.gemini_model = gemini_model
        self.chatbot = chatbot_instance

    def execute(self, state: ChatbotState) -> ChatbotState:
        """Point d'entrée principal de l'agent"""
        return self.agent_analyseur_unifie(state)

    def agent_analyseur_unifie(self, state: ChatbotState) -> ChatbotState:
        """
        Agent analyseur unifié avec GARANTIE des calculs Excel

        LOGIQUE:
        1. Analyser Excel (calculs si nécessaire)
        2. Analyser PDFs (réponse textuelle)
        3. Les deux analyses sont indépendantes mais complémentaires
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
        Analyse des documents Excel avec GARANTIE de détection des calculs
        Reprend EXACTEMENT la logique de l'analyzer_agent.py qui fonctionne
        """

        # Vérifier s'il y a des Excel à traiter
        tableaux_pour_upload = state.get('tableaux_pour_upload', [])

        if not tableaux_pour_upload:
            self.chatbot._log("Aucun tableau Excel à analyser", state)
            state['excel_empty'] = True
            return False

        self.chatbot._log(f"Analyse de {len(tableaux_pour_upload)} tableaux Excel", state)

        try:
            # Création des DataFrames avec validation robuste (LOGIQUE ORIGINALE)
            state['dataframes'] = self._creer_dataframes_valides(tableaux_pour_upload, state)
            if not state['dataframes']:
                state['besoin_calculs'] = False
                state['reponse_finale'] = "Impossible de traiter les données Excel trouvées."
                return False

            # Préparation du contexte Excel (LOGIQUE ORIGINALE)
            contexte_complet = self._preparer_contexte_excel_avec_metadata(state)

            # Variables pour le nettoyage
            fichier_gemini = []
            client = None

            try:
                # Upload vers Gemini (LOGIQUE ORIGINALE)
                fichier_csv = self._creer_csvs_pour_gemini(state['dataframes'], state)
                if not fichier_csv:
                    raise Exception("Aucun fichier CSV créé")

                fichier_gemini, client = self._upload_fichier_to_gemini(fichier_csv, state)
                state['fichiers_gemini'] = fichier_gemini

                # Prompt Excel avec historique (LOGIQUE ORIGINALE AMÉLIORÉE)
                prompt_excel = self._creer_prompt_excel_unifie(state, contexte_complet, historique_contexte)

                try:
                    _send_to_frontend(state.get('session_id'), "Génération de réponse Excel...")
                except:
                    pass

                # Appel Gemini (LOGIQUE ORIGINALE)
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

                # PARSING AVEC GARANTIE DE CALCULS (LOGIQUE ORIGINALE RENFORCÉE)
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
        """Analyse des documents PDF avec upload direct vers Gemini"""

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
        PARSING EXCEL AVEC GARANTIE ABSOLUE DE DÉTECTION DES CALCULS
        Reprend la logique de l'analyzer_agent.py qui fonctionne + renforcements
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
                    # FALLBACK CALCULS GARANTI
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
        """Finalise l'état après les deux analyses"""

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
        """Récupère l'historique utilisateur"""
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
        """Extrait les informations utilisateur du state"""
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
        """Prompt Excel simplifié et plus directif"""

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

    def _creer_prompt_pdf_unifie(self, state, contexte_pdf, historique_contexte):
        """Crée le prompt pour l'analyse PDF"""

        prompt = f"""Tu es un expert en analyse de données du Maroc.

{historique_contexte}

QUESTION UTILISATEUR: {state['question_utilisateur']}

{contexte_pdf}

INSTRUCTIONS STRICTES:
1. Utilise l'HISTORIQUE ci-dessus pour comprendre le contexte des conversations précédentes
2. Utilise les TITRES et CONTEXTES des documents pour comprendre chaque document
3. Choisis les documents selon leur PERTINENCE à la question
4. Si l'historique contient des informations pertinentes, fais le lien avec la question actuelle

FORMAT DE RÉPONSE OBLIGATOIRE:

=== REPONSE_TEXTE_ANALYSEUR ===

HISTORIQUE: [Comment l'historique influence cette analyse]
SOURCES_UTILISEES: [Mentionner les sources des données]
REPONSE: [Réponse complète avec références aux sources et liens avec l'historique si pertinent]
"""
        return prompt

    # Dans votre méthode d'extraction, ajoutez :
    def _extraire_contenu_gemini_robuste(self, response, state):
        try:
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'content') and candidate.content:
                    if hasattr(candidate.content, 'parts') and candidate.content.parts:

                        # AJOUTEZ CE LOG DE DEBUG
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
        """Extraction flexible des étapes et algorithmes (logique originale)"""
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
        """Extraction flexible de la réponse directe - VERSION CORRIGÉE"""

        if not texte or not isinstance(texte, str) or len(texte) < 10:
            return None

        try:
            # NOUVEAU PATTERN PRINCIPAL : Tout après "TYPE: DIRECT"
            patterns_reponse = [
                # Pattern 1: Directement après TYPE: DIRECT (NOUVEAU - PRIORITAIRE)
                r'TYPE\s*:\s*DIRECT\s*\n(.*?)(?=\n\s*===|$)',
                r'TYPE\s*:\s*DIRECT\s+(.*?)(?=\n\s*===|$)',

                # Patterns existants (fallback)
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

    def _extraire_reponse_pdf_directe(self, texte):
        """Extraction de la réponse PDF"""
        if not texte or not isinstance(texte, str):
            return None

        patterns = [
            r'REPONSE:\s*\n(.*?)(?===|$)',
            r'REPONSE:\s*(.*?)(?===|$)',
        ]

        for pattern in patterns:
            try:
                match = re.search(pattern, texte, re.DOTALL | re.IGNORECASE)
                if match:
                    reponse = match.group(1).strip()
                    if len(reponse) > 20:
                        return reponse
            except:
                continue
        return None

    def _extraire_sources_depuis_texte(self, texte):
        """Extraction des sources PDF"""
        try:
            patterns = [
                r"SOURCES_UTILISEES[:\-\s]*(.+?)(?=\n\n|\nREPONSE|$)",
                r"SOURCES?[:\-\s]*(.+?)(?=\n\n|\nREPONSE|$)"
            ]
            for pattern in patterns:
                m = re.search(pattern, texte, re.IGNORECASE | re.DOTALL)
                if m:
                    bloc = m.group(1).strip()
                    lignes = [l.strip("- • ").strip() for l in bloc.splitlines() if l.strip()]
                    return [l for l in lignes if len(l) > 2][:6]
        except:
            pass
        return []

    def _apply_excel_fallback(self, state, historique_contexte):
        """Fallback pour Excel avec garantie de calculs si nécessaire"""
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
        """Gestion d'erreur Excel"""
        state['besoin_calculs'] = False
        state['reponse_finale'] = f"Erreur technique Excel: {str(error)[:100]}..."

    # Méthodes utilitaires pour DataFrames, CSV, etc. (reprises de l'original)
    def _preparer_contexte_excel_avec_metadata(self, state):
        """Prépare le contexte Excel"""
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

    def _preparer_contexte_pdf_avec_metadata(self, state, pdf_docs):
        """Prépare le contexte PDF"""
        contexte = "DONNÉES TEXTUELLES DISPONIBLES POUR L'ANALYSE:\n\n"

        for i, doc in enumerate(pdf_docs):
            titre = doc.get('titre_contextuel', f'Document {i + 1}')
            source = doc.get('source', doc.get('fichier_source', 'N/A'))
            description = doc.get('description', doc.get('resume_gemini', 'Pas de description'))

            if len(description) > 300:
                description = description[:300] + "..."

            contexte += f"""DOCUMENT {i + 1}:
   - Titre: {titre}
   - Source: {source}
   - Aperçu: {description}

"""
        return contexte

    def _creer_dataframes_valides(self, tableaux_charges, state):
        """Crée des DataFrames validés avec métadonnées"""
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
        """Crée des fichiers CSV temporaires"""
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
        """Upload vers Gemini"""
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
        """Supprime les fichiers uploadés chez Gemini"""
        for fichier in fichiers_gemini:
            try:
                client.files.delete(name=fichier.name)
            except Exception as e:
                self.chatbot._log_error(f"Erreur suppression Gemini: {str(e)}", state)

    def _nettoyer_csvs_temporaires(self, fichiers_csv, state):
        """Supprime les fichiers CSV temporaires"""
        for fichier in fichiers_csv:
            try:
                if os.path.exists(fichier):
                    os.remove(fichier)
            except Exception as e:
                self.chatbot._log_error(f"Erreur suppression {fichier}: {str(e)}", state)

    def _call_gemini_with_retry(self, client, content, state, max_retries=3):
        """Appelle Gemini avec retry automatique"""
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
import re
from google.genai import types
from google import genai
from ..core.state import ChatbotState
from dotenv import load_dotenv
import os
from ..core.memory_store import get_user_context

load_dotenv()


class TextAnalyzerAgent:
    """Agent analyseur pour déterminer le type de réponse nécessaire sur les PDF"""

    def __init__(self, gemini_model, chatbot_instance):
        self.gemini_model = gemini_model
        self.chatbot = chatbot_instance

    def execute(self, state: ChatbotState) -> ChatbotState:
        """Point d'entrée principal de l'agent"""
        return self.agent_text_analyseur(state)

    def agent_text_analyseur(self, state: ChatbotState) -> ChatbotState:
        """Agent analyseur avec validation et historique - VERSION CORRIGÉE"""

        self.chatbot._log("Agent Texte Analyseur: Début de l'analyse des fichiers textuels", state)

        # CORRECTION: Validation plus flexible des prérequis
        pdf_docs = (state.get('documents_pdf') or
                    state.get('documents_selectionnes') or
                    [])

        if not pdf_docs:
            self.chatbot._log("Aucun document PDF pertinent trouvé", state)
            # CORRECTION: Ne pas bloquer, juste marquer comme vide
            state['reponse_finale_pdf'] = ""
            state['sources_pdf'] = []
            return state

        # Récupérer les informations utilisateur
        username, email = self._extract_user_info(state)

        # Récupérer l'historique utilisateur avec fallback
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

        # Préparation du contexte enrichi avec métadonnées
        contexte_complet = self._preparer_contexte_avec_metadata(state, pdf_docs)

        # Prompt enrichi avec historique ET métadonnées
        prompt_unifie = f"""Tu es un expert en analyse de données du Maroc.

{historique_contexte}

QUESTION UTILISATEUR: {state['question_utilisateur']}

{contexte_complet}

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

        try:
            content = [prompt_unifie]
            API_KEY = os.getenv("GEMINI_API_KEY")
            client = genai.Client(api_key=API_KEY)

            response = client.models.generate_content(
                model="gemini-2.5-pro",
                contents=content,
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    candidate_count=1,
                    max_output_tokens=2048,
                    thinking_config=types.ThinkingConfig(
                        include_thoughts=False
                    )
                )
            )

            # Extraction simple et robuste du contenu
            answer_text = self._extraire_contenu_gemini_robuste(response, state)

            if not answer_text:
                state['reponse_finale_pdf'] = ""
                state['sources_pdf'] = []
                self.chatbot._log("Erreur lors de l'extraction de la réponse PDF", state)
                return state

            # Sauvegarder la réponse
            state['reponse_analyseur_texte_brut'] = answer_text

            reponse = self._extraire_reponse_directe(answer_text)
            if reponse:
                state['reponse_finale_pdf'] = reponse
                state['sources_pdf'] = self._extraire_sources_depuis_texte(answer_text)
                self.chatbot._log("Analyseur Texte: Réponse PDF directe extraite avec historique", state)
            else:
                # CORRECTION: Utiliser le texte brut comme fallback
                state['reponse_finale_pdf'] = answer_text
                state['sources_pdf'] = [doc.get('titre_contextuel', 'Document PDF') for doc in pdf_docs]
                self.chatbot._log("Fallback: Utilisation du texte brut comme réponse PDF", state)

        except Exception as e:
            self.chatbot._log_error(f"Agent Texte Analyseur: {str(e)}", state)
            # CORRECTION: Fallback plus informatif
            state['reponse_finale_pdf'] = f"Erreur lors de l'analyse des documents PDF: {str(e)}"
            state['sources_pdf'] = []

        return state

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

    def _extraire_sources_depuis_texte(self, texte: str):
        """Extraction très simple des 'SOURCES:' si présentes dans la réponse du modèle."""
        try:
            import re
            # CORRECTION: Pattern plus flexible
            patterns = [
                r"SOURCES_UTILISEES[:\-\s]*(.+?)(?=\n\n|\nREPONSE|$)",
                r"SOURCES?[:\-\s]*(.+?)(?=\n\n|\nREPONSE|$)",
                r"Sources[:\-\s]*(.+?)(?=\n\n|$)"
            ]

            for pattern in patterns:
                m = re.search(pattern, texte, re.IGNORECASE | re.DOTALL)
                if m:
                    bloc = m.group(1).strip()
                    lignes = [l.strip("- • ").strip() for l in bloc.splitlines() if l.strip()]
                    return [l for l in lignes if len(l) > 2][:6]
        except Exception:
            pass
        return []

    def _extraire_contenu_gemini_robuste(self, response, state):
        """Extraction simple et directe du contenu Gemini"""

        try:
            # Méthode 1: response.text directement
            if hasattr(response, 'text') and response.text:
                text_content = response.text.strip()
                if len(text_content) > 10:
                    self.chatbot._log(f"Contenu PDF extrait directement: {len(text_content)} chars", state)
                    return text_content

            # Méthode 2: Via candidates
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'content') and candidate.content:
                    if hasattr(candidate.content, 'parts') and candidate.content.parts:
                        all_text = []
                        for part in candidate.content.parts:
                            if hasattr(part, 'text') and part.text:
                                all_text.append(part.text)

                        if all_text:
                            combined_text = '\n'.join(all_text).strip()
                            if len(combined_text) > 10:
                                self.chatbot._log(f"Contenu PDF extrait des parts: {len(combined_text)} chars", state)
                                return combined_text

            self.chatbot._log_error("Aucun contenu PDF extractible", state)
            return None

        except Exception as e:
            self.chatbot._log_error(f"Erreur extraction PDF: {e}", state)
            return None

    def _preparer_contexte_avec_metadata(self, state: ChatbotState, pdf_docs: list) -> str:
        """Prépare un contexte enrichi avec toutes les métadonnées - VERSION CORRIGÉE"""

        contexte = "DONNÉES TEXTUELLES DISPONIBLES POUR L'ANALYSE:\n\n"

        # CORRECTION: Utiliser les documents PDF passés en paramètre
        for i, doc in enumerate(pdf_docs):
            titre = doc.get('titre_contextuel', f'Document {i + 1}')
            source = doc.get('source', doc.get('fichier_source', 'N/A'))
            description = doc.get('description', doc.get('resume_gemini', 'Pas de description disponible'))

            # CORRECTION: Limiter la longueur de la description
            if len(description) > 300:
                description = description[:300] + "..."

            contexte += f"""DOCUMENT {i + 1}:
   - Titre: {titre}
   - Source: {source}
   - Aperçu: {description}

"""

        return contexte

    def _extraire_reponse_directe(self, texte: str) -> str:
        """Extraction de la réponse directe avec patterns flexibles - VERSION AMÉLIORÉE"""

        if not texte or not isinstance(texte, str):
            return None

        patterns = [
            r'REPONSE:\s*\n(.*?)(?===|$)',
            r'=== REPONSE_TEXTE_ANALYSEUR ===\s*\n.*?REPONSE:\s*\n(.*?)(?===|$)',
            r'REPONSE:\s*(.*?)(?===|$)',
            r'HISTORIQUE:.*?REPONSE:\s*\n(.*?)(?===|$)',
            r'SOURCES_UTILISEES:.*?REPONSE:\s*\n(.*?)(?===|$)'
        ]

        for pattern in patterns:
            try:
                match = re.search(pattern, texte, re.DOTALL | re.IGNORECASE)
                if match:
                    reponse = match.group(1).strip()
                    # CORRECTION: Validation plus stricte
                    if reponse and len(reponse) > 20 and not reponse.isspace():
                        # Nettoyage basique
                        reponse = re.sub(r'\n+', '\n', reponse)
                        return reponse
            except Exception as e:
                self.chatbot._log_error(f"Erreur pattern reponse: {e}", {})
                continue

        # CORRECTION: Fallback plus intelligent
        # Si aucun pattern ne marche, extraire le contenu après les headers
        lignes = texte.split('\n')
        contenu_lignes = []
        dans_reponse = False

        for ligne in lignes:
            ligne = ligne.strip()
            if not ligne:
                continue

            # Détecter le début de la réponse
            if any(marker in ligne.upper() for marker in ['REPONSE:', 'RÉPONSE:']):
                dans_reponse = True
                # Inclure le contenu après le ":" s'il existe
                if ':' in ligne:
                    content_after_colon = ligne.split(':', 1)[1].strip()
                    if content_after_colon:
                        contenu_lignes.append(content_after_colon)
                continue

            # Ignorer les headers avant la réponse
            if not dans_reponse and any(header in ligne.upper() for header in
                                        ['TYPE:', 'HISTORIQUE:', 'SOURCES_UTILISEES:', '===']):
                continue

            # Collecter les lignes de contenu
            if dans_reponse or (not any(header in ligne.upper() for header in
                                        ['TYPE:', 'HISTORIQUE:', 'SOURCES:', '==='])):
                contenu_lignes.append(ligne)

        if contenu_lignes:
            contenu = '\n'.join(contenu_lignes).strip()
            if len(contenu) > 20:
                return contenu

        return None
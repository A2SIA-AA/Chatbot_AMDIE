import re
import sys
from typing import List

from ..core.state import ChatbotState
sys.path[:0] = ['../../']
from config.logging import setup_logging, PerformanceLogger
from config.setting import get_settings


class SelectorFileAgent:
    """Agent sélecteur Gemini pour choisir les documents pertinents"""

    def __init__(self, gemini_model, chatbot_instance):
        self.gemini_model = gemini_model
        self.chatbot = chatbot_instance

    def execute(self, state: ChatbotState) -> ChatbotState:
        """Point d'entrée principal de l'agent"""
        return self.agent_selecteur_documents_gemini(state)

    def _log(self, message: str, state: ChatbotState, settings=None):
        """Ajoute un message au log ET l'affiche pour le frontend - VERSION SÉCURISÉE"""
        settings = get_settings() if settings is None else settings

        # Setup logging existant
        logger = setup_logging(settings)
        logger.info(message)

        # CORRECTION : Vérifier si 'historique' existe avant d'y accéder
        if 'historique' not in state:
            state['historique'] = []

        state['historique'].append(message)

        # Ligne pour le frontend
        print(f"PROGRESS:{message}", file=sys.stderr)

    def agent_selecteur_documents_gemini(self, state: ChatbotState) -> ChatbotState:
        """Selector avec logique CORRIGÉE pour vos documents"""

        self._log("Agent Sélecteur: Gemini analyse les fichiers", state)

        all_docs = state.get('documents_trouves', [])

        if not all_docs:
            self._log("Aucun document trouvé pour sélection", state)
            state['tableaux_pour_upload'] = []
            state['documents_selectionnes'] = []
            return state

        # CORRECTION: Utiliser la classification du dispatcher (cohérente)
        excel_docs = state.get('documents_excel', [])
        pdf_docs = state.get('documents_pdf', [])

        self._log(f"UTILISATION classification dispatcher: {len(excel_docs)} Excel, {len(pdf_docs)} PDF", state)

        # Si le dispatcher n'a pas encore classé, faire notre propre classification
        if not excel_docs and not pdf_docs:
            self._log("Classification manuelle car dispatcher n'a pas classé", state)
            for i, doc in enumerate(all_docs):
                doc_id = doc.get('id', f'doc_{i}').lower()

                # LOGIQUE SIMPLIFIÉE BASÉE SUR VOS LOGS
                if doc_id.startswith('tableau_') or 'tableau_path' in doc:
                    excel_docs.append(doc)
                    self._log(f"  MANUAL: Doc '{doc_id}' → EXCEL", state)
                elif doc_id.startswith('pdf_') or ('description' in doc and 'tableau_path' not in doc):
                    pdf_docs.append(doc)
                    self._log(f"  MANUAL: Doc '{doc_id}' → PDF", state)
                else:
                    # Par défaut selon l'ID
                    if 'tableau' in doc_id:
                        excel_docs.append(doc)
                    else:
                        pdf_docs.append(doc)

            # Mettre à jour l'état
            state['documents_excel'] = excel_docs
            state['documents_pdf'] = pdf_docs

        self._log(f"RÉSULTAT SELECTOR: {len(excel_docs)} fichiers Excel, {len(pdf_docs)} fichiers PDF", state)

        # Continuer avec la sélection Gemini normale...
        try:
            catalogue_documents = self._preparer_catalogue_tous_documents(all_docs)

            prompt_selection = f"""Tu es un expert en sélection de données pour répondre à des questions sur le Maroc.

    QUESTION À ANALYSER: {state['question_utilisateur']}

    DOCUMENTS DISPONIBLES:
    {catalogue_documents}

    MISSION: 
    Sélectionne les 5 documents les PLUS PERTINENTS pour répondre à cette question.

    FORMAT DE RÉPONSE OBLIGATOIRE:
    DOCUMENTS_SELECTIONNES: [numéros séparés par des virgules, ex: 1,3,7]
    JUSTIFICATION: [Explication courte de ton choix]

    RÉPONSE:"""

            response = self.gemini_model.generate_content(prompt_selection)
            documents_choisis = self._parser_selection_gemini(response.text)

            if documents_choisis:
                documents_selectionnes = [
                    all_docs[i] for i in documents_choisis
                    if i < len(all_docs)
                ]

                # Séparer les sélectionnés par type
                excel_selectionnes = [doc for doc in documents_selectionnes
                                      if doc in excel_docs]
                pdf_selectionnes = [doc for doc in documents_selectionnes
                                    if doc in pdf_docs]

                state['tableaux_pour_upload'] = excel_selectionnes
                state['documents_selectionnes'] = pdf_selectionnes
                state['explication_selection'] = response.text

                self._log(f"Gemini a sélectionné {len(documents_selectionnes)} documents: {documents_choisis}", state)
                self._log(f"Excel sélectionnés: {len(excel_selectionnes)}, PDF sélectionnés: {len(pdf_selectionnes)}",
                          state)

            else:
                # Fallback
                state['tableaux_pour_upload'] = excel_docs[:3]
                state['documents_selectionnes'] = pdf_docs[:3]
                self._log("Fallback: premiers documents sélectionnés", state)

        except Exception as e:
            self._log(f"Erreur sélection Gemini: {str(e)}", state)
            state['tableaux_pour_upload'] = excel_docs[:3]
            state['documents_selectionnes'] = pdf_docs[:3]

        return state

    def _preparer_catalogue_tous_documents(self, documents: List[dict]) -> str:
        """Prépare un catalogue unifié pour tous types de documents"""

        catalogue = ""
        for i, doc in enumerate(documents):
            titre = doc.get('titre_contextuel', f'Document {i + 1}')
            source = doc.get('fichier_source', doc.get('source', 'N/A'))

            # Détecter le type pour l'affichage
            doc_id = doc.get('id', '').lower()
            if ('xlsx' in doc_id or 'csv' in doc_id or 'tableau' in doc):
                # Document Excel
                headers = doc.get('tableau', [[]])[0] if doc.get('tableau') else []
                colonnes = ', '.join(str(h) for h in headers[:5] if h)
                nb_lignes = len(doc.get('tableau', [])) - 1 if doc.get('tableau') else 0

                catalogue += f"""
DOCUMENT {i + 1} [EXCEL]:
  - Titre: {titre}
  - Source: {source}
  - Colonnes: {colonnes}
  - Lignes: {nb_lignes}
"""
            else:
                # Document PDF ou autre
                description = doc.get('description', doc.get('resume_gemini', 'Pas de description'))
                if len(description) > 200:
                    description = description[:200] + "..."

                catalogue += f"""
DOCUMENT {i + 1} [PDF]:
  - Titre: {titre}
  - Source: {source}
  - Description: {description}
"""

        return catalogue

    def _preparer_catalogue_pdfs(self, pdf_charges):
        """Prépare un catalogue lisible des pdfs"""
        catalogue = ""
        for i, pdf in enumerate(pdf_charges):
            titre = pdf.get('titre_contextuel', f'PDF {i + 1}')
            source = pdf.get('source', 'N/A')

            # Extraire le résumé
            resume = pdf.get('description', " ")

            catalogue += f"""
        DOCUMENT {i + 1}:
          - Titre: {titre}
          - Source: {source}
          - Resume: {resume}
        """

        return catalogue

    def _preparer_catalogue_tableaux(self, tableaux_charges):
        """Prépare un catalogue lisible des tableaux"""

        catalogue = ""
        for i, tableau in enumerate(tableaux_charges):
            titre = tableau.get('titre_contextuel', f'Tableau {i + 1}')
            source = tableau.get('fichier_source', 'N/A')
            feuille = tableau.get('nom_feuille', 'N/A')

            # Extraire quelques colonnes représentatives
            headers = tableau.get('tableau', [[]])[0] if tableau.get('tableau') else []
            colonnes = ', '.join(str(h) for h in headers[:5] if h)

            # Taille du tableau
            nb_lignes = len(tableau.get('tableau', [])) - 1

            catalogue += f"""
TABLEAU {i + 1}:
  - Titre: {titre}
  - Source: {source} -> {feuille}  
  - Colonnes: {colonnes}
  - Lignes: {nb_lignes}
"""

        return catalogue

    def _parser_selection_gemini(self, response_text):
        """Parse la réponse de Gemini pour extraire les numéros de documents"""

        # Chercher le pattern "DOCUMENTS_SELECTIONNES: 1,2,3"
        match = re.search(r'DOCUMENTS_SELECTIONNES:\s*\[?([0-9,\s]+)\]?', response_text)

        if match:
            # Extraire les numéros
            numeros_str = match.group(1)
            numeros = [int(n.strip()) - 1 for n in numeros_str.split(',') if n.strip().isdigit()]
            return numeros

        # Fallback: chercher des numéros dans le texte
        numeros = re.findall(r'\b([1-9]|10)\b', response_text)
        if numeros:
            return [int(n) - 1 for n in numeros[:5]]

        return []

    def _preparer_catalogue_documents(self, documents_charges: List[dict]) -> str:
        """Préparation du catalogue des documents de type différent"""
        catalogue_document = ""
        for i, doc in enumerate(documents_charges):
            if 'pdf' in doc.get('id', '').lower():
                catalogue_document += self._preparer_catalogue_pdfs([doc])
            else:
                catalogue_document += self._preparer_catalogue_tableaux([doc])

        return catalogue_document
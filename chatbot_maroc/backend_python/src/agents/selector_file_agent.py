import re
from typing import List

from ..core.state import ChatbotState


class SelectorFileAgent:
    """Agent sélecteur Gemini pour choisir les documents pertinents"""

    def __init__(self, gemini_model, chatbot_instance):
        self.gemini_model = gemini_model
        self.chatbot = chatbot_instance

    def execute(self, state: ChatbotState) -> ChatbotState:
        """Point d'entrée principal de l'agent"""
        return self.agent_selecteur_documents_gemini(state)

    def agent_selecteur_documents_gemini(self, state: ChatbotState) -> ChatbotState:
        """Gemini choisit les documents les plus pertinents"""

        self.chatbot._log("Agent Sélecteur: Gemini analyse les 10 documents", state)

        if not state['documents_trouves']:
            return state

        try:
            # Préparer les métadonnées des 10 documents
            catalogue_documents = self._preparer_catalogue_documents(state['documents_trouves'])

            prompt_selection = f"""Tu es un expert en sélection de données pour répondre à des questions sur le Maroc.

QUESTION À ANALYSER: {state['question_utilisateur']}

DOCUMENTS DISPONIBLES:
{catalogue_documents}

MISSION: 
Sélectionne les 3 à 5 documents les PLUS PERTINENTS pour répondre à cette question.

CRITÈRES:
- Privilégie les documents qui contiennent directement les données nécessaires
- Choisis des documents complémentaires si la question nécessite du croisement
- Évite les documents redondants ou marginalement liés

FORMAT DE RÉPONSE OBLIGATOIRE:
DOCUMENTS_SELECTIONNES: [numéros séparés par des virgules, ex: 1,3,7]
JUSTIFICATION: [Explication courte de ton choix]

RÉPONSE:"""

            response = self.gemini_model.generate_content(prompt_selection)

            #self.chatbot._log("REPONSE SELECTEUR DE GEMINI: ", state)

            # Parser la réponse
            documents_choisis = self._parser_selection_gemini(response.text)

            if documents_choisis:
                # Récupérer les tableaux sélectionnés
                documents_selectionnes = [
                    state['documents_trouves'][i] for i in documents_choisis
                    if i < len(state['documents_trouves'])
                ]

                state['tableaux_pour_upload'] = documents_selectionnes
                state['explication_selection'] = response.text

                self.chatbot._log(f"Gemini a sélectionné {len(documents_selectionnes)} tableaux: {documents_choisis}",
                                  state)

            else:
                # Fallback : prendre les 3 premiers
                state['tableaux_pour_upload'] = state['tableaux_charges'][:3]
                self.chatbot._log("Fallback: 3 premiers tableaux sélectionnés", state)

        except Exception as e:
            self.chatbot._log_error(f"Erreur sélection Gemini: {str(e)}", state)
            state['tableaux_pour_upload'] = state['tableaux_charges'][:3]

        return state


    def _preparer_catalogue_pdfs(self, pdf_charges):
        """Prépare un catalogue lisible des pdfs"""
        catalogue = ""
        for i, pdf in enumerate(pdf_charges):
            titre = pdf.get('titre_contextuel', f'PDF {i + 1}')
            source = pdf.get('source', 'N/A')

            # Extraire le résumé
            resume = pdf.get('description', " ")


            catalogue += f"""
        TABLEAU {i + 1}:
          - Titre: {titre}
          - Source: {source}
          - Resume: {resume}
        """

        return catalogue

    def _preparer_catalogue_tableaux(self, tableaux_charges):
        """Prépare un catalogue lisible des 10 tableaux"""

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
        """Parse la réponse de Gemini pour extraire les numéros de tableaux"""

        # Chercher le pattern "DOCUMENTS_SELECTIONNES: 1,2,3 par exemple"
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

    def _preparer_catalogue_documents(self, documents_charges: List[dict])-> str:
        """" Préparation du catalogue des documents de type différent"""
        catalogue_document = ""
        for i, doc in enumerate(documents_charges):
            if 'pdf' in doc.get('id'):
                catalogue_document += self._preparer_catalogue_pdfs([doc])
            else:
                catalogue_document += self._preparer_catalogue_tableaux([doc])

        return catalogue_document
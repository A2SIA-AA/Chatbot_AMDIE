import re
from ..core.state import ChatbotState
from ..utils.message_to_front import _send_to_frontend


class SelectorAgentUnified:
    """Agent sélecteur Gemini pour choisir les tableaux ET PDFs pertinents"""

    def __init__(self, gemini_model, chatbot_instance):
        self.gemini_model = gemini_model
        self.chatbot = chatbot_instance

    def execute(self, state: ChatbotState) -> ChatbotState:
        """Point d'entrée principal de l'agent"""
        return self.agent_selecteur_unifie(state)

    def agent_selecteur_unifie(self, state: ChatbotState) -> ChatbotState:
        """Sélecteur unifié reprenant la logique robuste du selector_agent original"""

        # Récupérer les documents chargés des nouveaux champs unified
        tableaux_charges = state.get('tableaux_charges', [])
        pdfs_charges = state.get('pdfs_charges', [])

        total_documents = len(tableaux_charges) + len(pdfs_charges)

        self.chatbot._log(f"Agent Sélecteur Unifié: Analyse {len(tableaux_charges)} Excel + {len(pdfs_charges)} PDFs",
                          state)
        session_id = state['session_id']
        _send_to_frontend(session_id, f"Agent Sélecteur: Gemini analyse {total_documents} documents")

        # Cas où il n'y a aucun document
        if total_documents == 0:
            state['tableaux_pour_upload'] = []
            state['pdfs_pour_upload'] = []
            return state

        # Cas où il n'y a que des Excel (logique originale)
        if tableaux_charges and not pdfs_charges:
            return self._selectionner_excel_seulement(state, tableaux_charges, session_id)

        # Cas où il n'y a que des PDFs
        elif pdfs_charges and not tableaux_charges:
            return self._selectionner_pdfs_seulement(state, pdfs_charges, session_id)

        # Cas mixte : Excel + PDFs (nouvelle logique)
        else:
            return self._selectionner_documents_mixtes(state, tableaux_charges, pdfs_charges, session_id)

    def _selectionner_excel_seulement(self, state: ChatbotState, tableaux_charges, session_id):
        """Sélection Excel uniquement - LOGIQUE ORIGINALE PRÉSERVÉE"""

        try:
            # Préparer le catalogue Excel (méthode originale)
            catalogue_tableaux = self._preparer_catalogue_tableaux(tableaux_charges)

            prompt_selection = f"""Tu es un expert en sélection de données pour répondre à des questions sur le Maroc.

QUESTION À ANALYSER: {state['question_utilisateur']}

TABLEAUX DISPONIBLES (métadonnées uniquement):
{catalogue_tableaux}

MISSION: 
Sélectionne les 3 à 5 tableaux les PLUS PERTINENTS pour répondre à cette question.

CRITÈRES:
- Privilégie les tableaux qui contiennent directement les données nécessaires
- Choisis des tableaux complémentaires si la question nécessite du croisement
- Évite les tableaux redondants ou marginalement liés

FORMAT DE RÉPONSE OBLIGATOIRE:
TABLEAUX_SELECTIONNES: [numéros séparés par des virgules, ex: 1,3,7]
JUSTIFICATION: [Explication courte de ton choix]

RÉPONSE:"""

            response = self.gemini_model.generate_content(prompt_selection)

            # Parser la réponse (méthode originale)
            tableaux_choisis = self._parser_selection_gemini(response.text)
            _send_to_frontend(session_id, f"Tableaux sélectionnés: {tableaux_choisis}")

            if tableaux_choisis:
                # Récupérer les tableaux sélectionnés
                tableaux_selectionnes = [
                    tableaux_charges[i] for i in tableaux_choisis
                    if i < len(tableaux_charges)
                ]

                state['tableaux_pour_upload'] = tableaux_selectionnes
                state['pdfs_pour_upload'] = []  # Aucun PDF
                state['explication_selection'] = response.text

                self.chatbot._log(f"Gemini a sélectionné {len(tableaux_selectionnes)} tableaux: {tableaux_choisis}",
                                  state)

            else:
                # Fallback original : prendre les 3 premiers
                state['tableaux_pour_upload'] = tableaux_charges[:3]
                state['pdfs_pour_upload'] = []
                self.chatbot._log("Fallback: 3 premiers tableaux sélectionnés", state)

        except Exception as e:
            self.chatbot._log_error(f"Erreur sélection Excel: {str(e)}", state)
            state['tableaux_pour_upload'] = tableaux_charges[:3]
            state['pdfs_pour_upload'] = []

        return state

    def _selectionner_pdfs_seulement(self, state: ChatbotState, pdfs_charges, session_id):
        """Sélection PDFs uniquement - NOUVELLE LOGIQUE COHÉRENTE"""

        try:
            # Préparer le catalogue PDFs (nouvelle méthode)
            catalogue_pdfs = self._preparer_catalogue_pdfs(pdfs_charges)

            prompt_selection = f"""Tu es un expert en sélection de données pour répondre à des questions sur le Maroc.

QUESTION À ANALYSER: {state['question_utilisateur']}

DOCUMENTS PDF DISPONIBLES:
{catalogue_pdfs}

MISSION: 
Sélectionne les 3 à 5 documents PDF les PLUS PERTINENTS pour répondre à cette question.

CRITÈRES:
- Privilégie les documents qui contiennent directement l'information nécessaire
- Choisis des documents complémentaires pour avoir une vision complète
- Évite les documents redondants ou marginalement liés

FORMAT DE RÉPONSE OBLIGATOIRE:
DOCUMENTS_SELECTIONNES: [numéros séparés par des virgules, ex: 1,3,5]
JUSTIFICATION: [Explication courte de ton choix]

RÉPONSE:"""

            response = self.gemini_model.generate_content(prompt_selection)

            # Parser la réponse (méthode adaptée)
            pdfs_choisis = self._parser_selection_documents_gemini(response.text)
            _send_to_frontend(session_id, f"PDFs sélectionnés: {pdfs_choisis}")

            if pdfs_choisis:
                # Récupérer les PDFs sélectionnés
                pdfs_selectionnes = [
                    pdfs_charges[i] for i in pdfs_choisis
                    if i < len(pdfs_charges)
                ]

                state['tableaux_pour_upload'] = []  # Aucun Excel
                state['pdfs_pour_upload'] = pdfs_selectionnes
                state['explication_selection'] = response.text

                self.chatbot._log(f"Gemini a sélectionné {len(pdfs_selectionnes)} PDFs: {pdfs_choisis}", state)

            else:
                # Fallback : prendre les 3 premiers
                state['tableaux_pour_upload'] = []
                state['pdfs_pour_upload'] = pdfs_charges[:3]
                self.chatbot._log("Fallback: 3 premiers PDFs sélectionnés", state)

        except Exception as e:
            self.chatbot._log_error(f"Erreur sélection PDFs: {str(e)}", state)
            state['tableaux_pour_upload'] = []
            state['pdfs_pour_upload'] = pdfs_charges[:3]

        return state

    def _selectionner_documents_mixtes(self, state: ChatbotState, tableaux_charges, pdfs_charges, session_id):
        """Sélection mixte Excel + PDFs - NOUVELLE LOGIQUE UNIFIÉE"""

        try:
            # Créer un catalogue unifié
            catalogue_unifie = self._preparer_catalogue_unifie(tableaux_charges, pdfs_charges)

            prompt_selection = f"""Tu es un expert en sélection de données pour répondre à des questions sur le Maroc.

QUESTION À ANALYSER: {state['question_utilisateur']}

DOCUMENTS DISPONIBLES (Excel et PDFs mélangés):
{catalogue_unifie}

MISSION: 
Sélectionne les 5 documents les PLUS PERTINENTS pour répondre à cette question.
Tu peux choisir des tableaux Excel (pour les données chiffrées) ET des documents PDF (pour les informations textuelles).
"""
            prompt_selection += f"""IMPORTANT: Tu DOIS considérer à la fois les tableaux Excel (données chiffrées) ET les documents PDF (informations contextuelles).

            ÉQUILIBRE REQUIS: Sélectionne un MIX de documents Excel et PDF selon la pertinence de la question.

            Si la question nécessite des données chiffrées → privilégie les Excel
            Si la question nécessite du contexte/analyse → privilégie les PDF  
            Si la question est complexe → combine les deux types
            
            CRITÈRES:
- Privilégie les documents qui contiennent directement l'information nécessaire
- Combine Excel (données) et PDFs (contexte) si la question l'exige
- Évite les documents redondants

FORMAT DE RÉPONSE OBLIGATOIRE:
DOCUMENTS_SELECTIONNES: [numéros séparés par des virgules, ex: 1,3,7,9]
JUSTIFICATION: [Explication de ton choix mixte Excel/PDF]

RÉPONSE:
            """

            response = self.gemini_model.generate_content(prompt_selection)

            # Parser et séparer les sélections
            documents_choisis = self._parser_selection_documents_gemini(response.text)
            _send_to_frontend(session_id, f"Documents mixtes sélectionnés: {documents_choisis}")

            if documents_choisis:
                excel_selectionnes, pdfs_selectionnes = self._separer_selections_mixtes(
                    documents_choisis, tableaux_charges, pdfs_charges
                )

                state['tableaux_pour_upload'] = excel_selectionnes
                state['pdfs_pour_upload'] = pdfs_selectionnes
                state['explication_selection'] = response.text

                self.chatbot._log(
                    f"Gemini sélection mixte: {len(excel_selectionnes)} Excel + {len(pdfs_selectionnes)} PDFs", state)

            else:
                # Fallback : prendre quelques-uns de chaque
                state['tableaux_pour_upload'] = tableaux_charges[:2]
                state['pdfs_pour_upload'] = pdfs_charges[:2]
                self.chatbot._log("Fallback mixte: 2 Excel + 2 PDFs", state)

        except Exception as e:
            self.chatbot._log_error(f"Erreur sélection mixte: {str(e)}", state)
            state['tableaux_pour_upload'] = tableaux_charges[:2]
            state['pdfs_pour_upload'] = pdfs_charges[:2]

        return state

    def _preparer_catalogue_tableaux(self, tableaux_charges):
        """Prépare un catalogue lisible des tableaux - MÉTHODE ORIGINALE PRÉSERVÉE"""

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

    def _preparer_catalogue_pdfs(self, pdfs_charges):
        """Prépare un catalogue lisible des PDFs - NOUVELLE MÉTHODE COHÉRENTE"""

        catalogue = ""
        for i, pdf in enumerate(pdfs_charges):
            titre = pdf.get('titre_contextuel', f'PDF {i + 1}')
            source = pdf.get('fichier_source', 'N/A')

            # Extraire le résumé (tronqué)
            resume = pdf.get('resume_gemini', 'Pas de résumé disponible')
            if len(resume) > 200:
                resume = resume[:200] + "..."

            catalogue += f"""
DOCUMENT {i + 1}:
  - Titre: {titre}
  - Source: {source}
  - Résumé: {resume}
"""

        return catalogue

    def _preparer_catalogue_unifie(self, tableaux_charges, pdfs_charges):
        """Prépare un catalogue unifié Excel + PDFs avec numérotation continue"""

        catalogue = ""
        index = 1

        # D'abord les tableaux Excel
        for i, tableau in enumerate(tableaux_charges):
            titre = tableau.get('titre_contextuel', f'Tableau {i + 1}')
            source = tableau.get('fichier_source', 'N/A')
            feuille = tableau.get('nom_feuille', 'N/A')

            headers = tableau.get('tableau', [[]])[0] if tableau.get('tableau') else []
            colonnes = ', '.join(str(h) for h in headers[:5] if h)
            nb_lignes = len(tableau.get('tableau', [])) - 1

            catalogue += f"""
DOCUMENT {index} [EXCEL]:
  - Titre: {titre}
  - Source: {source} -> {feuille}  
  - Colonnes: {colonnes}
  - Lignes: {nb_lignes}
"""
            index += 1

        # Ensuite les PDFs
        for i, pdf in enumerate(pdfs_charges):
            titre = pdf.get('titre_contextuel', f'PDF {i + 1}')
            source = pdf.get('fichier_source', 'N/A')

            resume = pdf.get('resume_gemini', 'Pas de résumé disponible')
            if len(resume) > 200:
                resume = resume[:200] + "..."

            catalogue += f"""
DOCUMENT {index} [PDF]:
  - Titre: {titre}
  - Source: {source}
  - Résumé: {resume}
"""
            index += 1

        return catalogue

    def _separer_selections_mixtes(self, documents_choisis, tableaux_charges, pdfs_charges):
        """Sépare les sélections selon le mapping unifié"""

        excel_selectionnes = []
        pdfs_selectionnes = []

        nb_excels = len(tableaux_charges)

        for doc_index in documents_choisis:
            if doc_index < nb_excels:
                # C'est un Excel (indices 0 à nb_excels-1)
                excel_selectionnes.append(tableaux_charges[doc_index])
            else:
                # C'est un PDF (indices nb_excels et plus)
                pdf_index = doc_index - nb_excels
                if pdf_index < len(pdfs_charges):
                    pdfs_selectionnes.append(pdfs_charges[pdf_index])

        return excel_selectionnes, pdfs_selectionnes

    def _parser_selection_gemini(self, response_text):
        """Parse la réponse de Gemini pour les tableaux - MÉTHODE ORIGINALE PRÉSERVÉE"""

        # Chercher le pattern "TABLEAUX_SELECTIONNES: 1,2,3 par exemple"
        match = re.search(r'TABLEAUX_SELECTIONNES:\s*\[?([0-9,\s]+)\]?', response_text)

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

    def _parser_selection_documents_gemini(self, response_text):
        """Parse la réponse de Gemini pour les documents (PDFs ou mixtes)"""

        # Chercher le pattern "DOCUMENTS_SELECTIONNES: 1,2,3"
        match = re.search(r'DOCUMENTS_SELECTIONNES:\s*\[?([0-9,\s]+)\]?', response_text)

        if match:
            # Extraire les numéros
            numeros_str = match.group(1)
            numeros = [int(n.strip()) - 1 for n in numeros_str.split(',') if n.strip().isdigit()]
            return numeros

        # Fallback: chercher des numéros dans le texte
        numeros = re.findall(r'\b([1-9]|1[0-5])\b', response_text)  # Jusqu'à 15 documents
        if numeros:
            return [int(n) - 1 for n in numeros[:5]]

        return []
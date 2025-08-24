import re
from ..core.state import ChatbotState
from ..utils.message_to_front import _send_to_frontend


class SelectorAgentUnified:
    """
    Classe qui gère la sélection unifiée d'éléments (tableaux Excel et documents PDF) à partir d'un
    état donné, en utilisant divers modèles et mécanismes décisionnels.

    Cette classe a pour objectif de traiter les données d'état du chatbot en analysant les ressources
    disponibles (Excel, PDFs, ou une combinaison des deux), en appliquant une logique prédéfinie et en
    mettant à jour l'état pour faciliter un traitement ultérieur.

    :ivar gemini_model: Modèle utilisé pour générer du contenu et des suggestions basées sur les questions
                        de l'utilisateur et les documents chargés.
    :type gemini_model: any
    :ivar chatbot: Instance du chatbot utilisée pour enregistrer des journaux et interagir avec l'interface
                   frontend.
    :type chatbot: any
    """

    def __init__(self, gemini_model, chatbot_instance):
        """
        Initialise une instance de la classe avec les composants nécessaires.

        :param gemini_model: Modèle Gemini utilisé pour les prédictions et analyses.
        :param chatbot_instance: Instance du chatbot chargé de traiter les interactions
            utilisateur.
        """
        self.gemini_model = gemini_model
        self.chatbot = chatbot_instance

    def execute(self, state: ChatbotState) -> ChatbotState:
        """
        Exécute le processus principal en appliquant une fonction de sélection d'agent unifiée.

        La méthode prend un état de chatbot en paramètre, applique une logique spécifique
        pour traiter cet état et retourne le nouvel état mis à jour.

        :param state: L'état actuel du chatbot à traiter
        :type state: ChatbotState
        :return: L'état modifié du chatbot après traitement
        :rtype: ChatbotState
        """
        return self.agent_selecteur_unifie(state)

    def agent_selecteur_unifie(self, state: ChatbotState) -> ChatbotState:
        """
        Analyse et sélectionne les documents chargés pour traitement dans une session, en fonction du type
        de documents (Excels, PDFs ou un mix des deux). Diverses stratégies sont appliquées pour gérer
        les cas spécifiques en rapport avec les fichiers Excel, les PDFs ou un ensemble mixte.

        :param state: L'état actuel du chatbot, incluant les informations liées aux documents chargés
                      et aux données de session.
        :type state: ChatbotState
        :return: Le nouvel état du chatbot après sélection des documents pertinents.
        :rtype: ChatbotState
        """

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

        # Cas où il n'y a que des Excel
        if tableaux_charges and not pdfs_charges:
            return self._selectionner_excel_seulement(state, tableaux_charges, session_id)

        # Cas où il n'y a que des PDFs
        elif pdfs_charges and not tableaux_charges:
            return self._selectionner_pdfs_seulement(state, pdfs_charges, session_id)

        # Cas mixte : Excel + PDFs
        else:
            return self._selectionner_documents_mixtes(state, tableaux_charges, pdfs_charges, session_id)

    def _selectionner_excel_seulement(self, state: ChatbotState, tableaux_charges, session_id):
        """
        Sélectionne un ensemble réduit de tableaux Excel parmi les tableaux disponibles en analysant
        la question de l'utilisateur et en utilisant un modèle pour fournir une réponse formatée.
        Les tableaux sélectionnés sont destinés à un traitement ultérieur.

        :param state: État actuel du chatbot, utilisé pour stocker et mettre à jour les données durant
            la session. Doit inclure des informations telles que la question de l'utilisateur.
        :type state: ChatbotState
        :param tableaux_charges: Liste des tableaux Excel disponibles à analyser et parmi lesquels
            faire une sélection.
        :type tableaux_charges: list
        :param session_id: Identifiant unique de la session en cours pour faciliter les communications
            avec le frontend.
        :type session_id: str
        :return: État mis à jour du chatbot contenant les tableaux sélectionnés et prêts pour upload, ainsi
            que des informations supplémentaires comme l'explication de la sélection.
        :rtype: ChatbotState
        """

        try:
            # Préparer le catalogue Excel
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

            # Parser la réponse
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
        """
        Sélectionne les documents PDF les plus pertinents parmi une liste afin de répondre à une question
        posée par l'utilisateur. Cette fonction utilise un modèle de génération de contenu pour analyser
        la Requête et produire un ensemble de PDFs sélectionnés, accompagnés d'une justification. Si le
        modèle échoue ou renvoie une sélection vide, une stratégie de secours est appliquée.

        :param state: Dictionnaire représentant l'état actuel du chatbot, contenant des informations
                      relatives au contexte de la session, comme la question posée par l'utilisateur.
        :type state: ChatbotState
        :param pdfs_charges: Liste des documents PDF disponibles qui peuvent être utilisés pour
                             répondre à la question.
        :param session_id: Identifiant unique de la session en cours. Utilisé pour rapporter et transmettre
                           des informations à l'interface frontend.
        :return: L'état mis à jour incluant les PDFs sélectionnés pour upload ainsi que la justification
                 produite par le modèle.
        """

        try:
            # Préparer le catalogue PDFs
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

            # Parser la réponse
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
        """
        Sélectionne les documents mixtes (tableaux Excel et PDFs) les plus pertinents pour répondre à une question utilisateur.
        Cette méthode analyse une question utilisateur et sélectionne un mélange équilibré entre des fichiers Excel et PDF
        selon les besoins en données chiffrées ou informations contextuelles.

        :param state: État du chatbot contenant des informations telles que la question posée par l'utilisateur.
        :type state: ChatbotState
        :param tableaux_charges: Liste des tableaux Excel disponibles pour la sélection.
        :param pdfs_charges: Liste des documents PDF disponibles pour la sélection.
        :param session_id: Identifiant de session permettant de contextualiser la sélection.
        :return: État mis à jour du chatbot après la sélection des documents pertinents.
        :rtype: dict
        """

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
        """
        Prépare une représentation textuelle du catalogue des tableaux en analysant
        et extrayant des informations nécessaires des tableaux fournis.

        .. note::
            Ce catalogue donne un aperçu des tableaux en affichant leur titre,
            source, feuille, colonnes représentatives et nombre de lignes.

        :param tableaux_charges: Une liste de dictionnaires contenant les
            informations des tableaux. Chaque entrée doit inclure des données
            telles que 'titre_contextuel', 'fichier_source', 'nom_feuille' et
            les informations du tableau sous la clé 'tableau'.
        :return: Une chaîne de caractères représentant le catalogue des tableaux
            avec leurs informations formatées.
        :rtype: str
        """

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
        """
        Prépare un catalogue textuel des PDF chargés en générant une liste détaillée avec
        titre, source, et résumé tronqué pour chaque document.

        :param pdfs_charges: Liste de dictionnaires contenant les informations sur
            les PDF. Chaque dictionnaire doit inclure les clés suivantes :
            - 'titre_contextuel': Titre textuel du document. Par défaut, 'PDF {index}'.
            - 'fichier_source': Chemin ou nom de fichier source. Par défaut, 'N/A'.
            - 'resume_gemini': Résumé textuel du document. Par défaut, 'Pas de résumé
              disponible'.
        :type pdfs_charges: list[dict]
        :return: Une chaîne de caractères contenant le catalogue structuré des documents
            PDF, avec un résumé tronqué à 200 caractères pour chaque document.
        :rtype: str
        """

        catalogue = ""
        for i, pdf in enumerate(pdfs_charges):
            titre = pdf.get('titre_contextuel', f'PDF {i + 1}')
            source = pdf.get('fichier_source', 'N/A')

            # Extraire le résumé
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
        """
        Prépare un catalogue unifié sous forme de chaîne de caractères, décrivant des tableaux Excel et des
        documents PDF fournis.

        La fonction itère d'abord à travers les tableaux Excel et extrait des informations telles que le titre
        contextuel, la source, la feuille, les colonnes (avec un maximum de cinq colonnes), ainsi que le
        nombre de lignes. Ensuite, elle traite les fichiers PDF pour fournir des informations similaires,
        y compris un résumé d'un maximum de 200 caractères.

        :param tableaux_charges: Une liste de dictionnaires contenant les informations des tableaux Excel à
            inclure dans le catalogue. Chaque dictionnaire doit inclure les clés 'titre_contextuel',
            'fichier_source', 'nom_feuille', et 'tableau' pour fournir respectivement le titre, le chemin
            du fichier source, le nom de la feuille Excel, et les données du tableau.
        :type tableaux_charges: list[dict]

        :param pdfs_charges: Une liste de dictionnaires contenant les informations des fichiers PDF à
            inclure dans le catalogue. Chaque dictionnaire doit inclure les clés 'titre_contextuel',
            'fichier_source', et 'resume_gemini' pour fournir respectivement le titre, le chemin du
            fichier source, et un résumé du contenu PDF.
        :type pdfs_charges: list[dict]

        :return: Une chaîne de caractères détaillant la liste des documents Excel et PDF et leurs
            caractéristiques principales, formatée en sections numérotées.
        :rtype: str
        """

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
        """
        Sépare les sélections mixtes de documents en deux listes distinctes : une pour les tableaux Excel
        et une autre pour les fichiers PDF. Cette méthode analyse les indices fournis et les répartit
        correctement en fonction de leur type respectif (Excel ou PDF).

        :param documents_choisis: Liste contenant les indices des documents sélectionnés.
        :type documents_choisis: list[int]
        :param tableaux_charges: Liste des tableaux Excel chargés.
        :type tableaux_charges: list
        :param pdfs_charges: Liste des fichiers PDF chargés.
        :type pdfs_charges: list
        :return: Deux listes : la première contient les tableaux Excel sélectionnés, et la seconde,
                 les fichiers PDF sélectionnés.
        :rtype: tuple[list, list]
        """

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
        """
        Analyse une chaîne de texte et extrait les indices des tableaux sélectionnés.

        Cette méthode cherche dans le texte un motif spécifique pour identifier les
        tableaux sélectionnés. Si un motif précis est trouvé, les indices sont extraits
        et réduits de 1 (pour correspondre aux indices de tableau basés sur zéro).
        En l'absence d'un motif explicite, elle essaie de trouver et de traiter des
        numéros individuels inclus dans le texte en tant que potentiel substitut.

        :param response_text: Texte source analysé pour extraire les indices des tableaux.
        :type response_text: str
        :return: La liste des indices des tableaux sélectionnés. Les indices sont basés sur
                 zéro avec un maximum de 5 indices si aucun motif explicite n'est trouvé.
        :rtype: list[int]
        """

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
        """
        Analyse et extrait les indices des documents sélectionnés dans un texte donné en fonction d'un certain
        format ou d'un fallback. La méthode recherche des motifs spécifiques dans le texte pour déterminer les
        documents sélectionnés. Si aucun motif spécifique n'est trouvé, elle effectue une recherche alternative
        de numéros dans le texte et retourne une liste d'indices correspondants.

        :param response_text: Le texte contenant potentiellement les informations sur les documents
            sélectionnés.
        :type response_text: str

        :return: Une liste d'indices (entiers) correspondant aux documents sélectionnés, ou une liste vide
            si aucun document sélectionné ne peut être identifié dans le texte.
        :rtype: list[int]
        """

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
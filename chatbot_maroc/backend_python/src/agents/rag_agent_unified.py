from typing import Dict
from ..core.state import ChatbotState
from ..utils.message_to_front import _send_to_frontend


class RAGAgentUnified:
    """
    Agent RAG unifié pour la gestion des recherches et des documents Excel et PDF.

    Ce module intègre des fonctionnalités avancées telles que la gestion des erreurs, les permissions JWT,
    et le traitement des résultats. Les résultats des recherches sont filtrés en fonction des permissions
    d'accès et séparés en fichiers Excel et PDF. Les données valides et accessibles sont ensuite chargées
    et mises à disposition dans l'état du chatbot.

    :ivar rag: Instance de l'index RAG utilisé pour effectuer les recherches.
    :type rag: Any
    :ivar chatbot: Instance du chatbot utilisé pour la journalisation et la communication avec le frontend.
    :type chatbot: Any
    """

    def __init__(self, rag_index, chatbot_instance):
        self.rag = rag_index
        self.chatbot = chatbot_instance

    def execute(self, state: ChatbotState) -> ChatbotState:
        """
        Exécute l'état actuel dans un contexte de chatbot et retourne le nouvel état
        après application potentielle des transformations définies par l'agent RAG
        (unifié).

        :param state: L'état actuel du chatbot représenté par une instance de la
            classe ChatbotState
        :type state: ChatbotState
        :return: Le nouvel état du chatbot après l'exécution de la logique métier
        :rtype: ChatbotState
        """
        return self.agent_rag_unified(state)

    def agent_rag_unified(self, state: ChatbotState) -> ChatbotState:
        """
        Exécute le processus d'agent RAG unifié qui inclut la validation des questions,
        la recherche de tableaux et PDF, le filtrage des documents autorisés, et le
        chargement des documents complets en fonction des autorisations et des types.

        :param state:
            Un objet `ChatbotState` représentant l'état actuel de la session de chatbot.
            Il doit contenir des informations nécessaires, telles que la question de
            l'utilisateur et tout paramètre ou rôle utilisateur pertinent.

        :return:
            Un objet `ChatbotState` mis à jour avec les résultats organisés et filtrés
            selon les autorisations et la disponibilité des documents.
        """

        self.chatbot._log("Agent RAG Unifié: Démarrage de la recherche", state)
        session_id = state.get('session_id')
        _send_to_frontend(session_id, f"Agent RAG: Début recherche sur '{state['question_utilisateur'][:50]}...'",
                          "SEARCH")

        try:
            # Validation de la question
            if not state['question_utilisateur'].strip():
                raise ValueError("Question utilisateur vide")

            user_role = state.get("user_role", "public")

            # Recherche RAG (retourne Excel + PDFs mélangés)
            resultats_rag = self.rag.rechercher_tableaux(
                state['question_utilisateur'],
                user_role=user_role,
                n_results=10
            )

            # Vérification robuste des résultats
            if not resultats_rag or not isinstance(resultats_rag, dict):
                self.chatbot._log("Agent RAG: Résultats de recherche invalides", state)
                self._nettoyer_etat_zero_documents(state, "Résultats invalides")
                return state

            documents_bruts = resultats_rag.get('tableaux', [])
            if not documents_bruts or not isinstance(documents_bruts, list):
                self.chatbot._log("Agent RAG: Aucun document trouvé dans la recherche", state)
                self._nettoyer_etat_zero_documents(state, "Aucun document trouvé")
                return state

            # Filtrage sécurisé avec gestion des permissions JWT
            user_role = state.get("user_role", "public")
            documents_autorises = []

            for i, doc in enumerate(documents_bruts):
                try:
                    # Vérification que doc est un dictionnaire
                    if not isinstance(doc, dict):
                        self.chatbot._log(f"Document {i + 1}: Format invalide (pas un dict)", state)
                        continue

                    # Gestion sécurisée des access_level avec validation
                    access_level = doc.get("access_level")

                    # Protection contre les valeurs None/vides
                    if access_level is None or access_level == "":
                        access_level = "public"

                    # Normalisation pour éviter les erreurs de casse
                    access_level = str(access_level).lower().strip()

                    # Validation des valeurs autorisées
                    if access_level not in ['public', 'internal', 'confidential']:
                        self.chatbot._log(f"Niveau d'accès invalide '{access_level}', défaut à 'public'", state)
                        access_level = "public"

                    # Vérification des permissions JWT
                    if self._role_est_autorise(user_role, access_level):
                        # Préserver l'access_level normalisé
                        doc['access_level'] = access_level
                        documents_autorises.append(doc)
                    else:
                        self.chatbot._log(
                            f"Document '{doc.get('titre', 'Unknown')}' refusé: niveau {access_level} > rôle {user_role}",
                            state)

                except Exception as e:
                    self.chatbot._log_error(f"Erreur filtrage document {i + 1}: {str(e)}", state)
                    continue

            # Gestion explicite du cas 0 documents autorisés
            if not documents_autorises:
                self.chatbot._log(
                    f"Agent RAG: Aucun document accessible au rôle '{user_role}' (sur {len(documents_bruts)} trouvés)",
                    state)
                _send_to_frontend(session_id, f"Aucun document accessible avec votre rôle ({user_role})", "WARNING")
                self._nettoyer_etat_zero_documents(state, f"Aucun accès pour rôle {user_role}")
                return state

            # SÉPARATION Excel/PDF selon l'ID
            tableaux_autorises = []
            pdfs_autorises = []

            for doc in documents_autorises:
                doc_id = doc.get('id', '')
                if 'tableau' in doc_id:
                    tableaux_autorises.append(doc)
                elif 'pdf' in doc_id:
                    pdfs_autorises.append(doc)
                else:
                    # Par défaut, traiter comme tableau
                    self.chatbot._log(f"Document type inconnu (ID: {doc_id}), traité comme tableau", state)
                    tableaux_autorises.append(doc)

            # Stockage des résultats séparés
            state['tableaux_pertinents'] = tableaux_autorises
            state['pdfs_pertinents'] = pdfs_autorises
            state['documents_trouves'] = documents_autorises  # Tous mélangés pour compatibilité

            self.chatbot._log(
                f"Agent RAG: {len(tableaux_autorises)} Excel + {len(pdfs_autorises)} PDFs accessibles au rôle '{user_role}'",
                state)

            # CHARGEMENT UNIFIÉ DES DOCUMENTS
            documents_complets = []

            # Traitement des Excel
            for i, tableau_info in enumerate(tableaux_autorises):
                try:
                    tableau_path = tableau_info.get('tableau_path')
                    if not tableau_path:
                        self.chatbot._log(f"Excel {i + 1}: Chemin manquant", state)
                        continue

                    donnees_completes = self.rag.get_tableau_data(tableau_path)
                    if self._valider_donnees_tableau(donnees_completes):
                        donnees_completes['access_level'] = tableau_info.get('access_level', 'public')
                        donnees_completes['document_type'] = 'excel'
                        documents_complets.append(donnees_completes)

                        titre = donnees_completes.get('titre_contextuel', f'Excel {i + 1}')
                        access_level = tableau_info.get('access_level', 'public')
                        nb_lignes = len(donnees_completes.get('tableau', [])) - 1
                        self.chatbot._log(f" Excel chargé: {titre} [{nb_lignes} lignes] [niveau: {access_level}]",
                                          state)
                    else:
                        self.chatbot._log(f" Excel {i + 1} invalide", state)

                except Exception as e:
                    self.chatbot._log_error(f"Chargement Excel {i + 1}: {str(e)}", state)

            # Traitement des PDFs
            for i, pdf_info in enumerate(pdfs_autorises):
                try:
                    pdf_path = pdf_info.get('tableau_path')
                    if not pdf_path:
                        self.chatbot._log(f"PDF {i + 1}: Chemin manquant", state)
                        continue

                    # Pour les PDFs, créer structure minimale
                    if pdf_path.endswith('.pdf'):
                        donnees_pdf = {
                            'type': 'pdf',
                            'pdf_path': pdf_path,
                            'titre_contextuel': pdf_info.get('titre', f'PDF {i + 1}'),
                            'fichier_source': pdf_info.get('source', pdf_path),
                            'description': pdf_info.get('description', 'Document PDF'),
                            'access_level': pdf_info.get('access_level', 'public'),
                            'document_type': 'pdf',
                            'id': pdf_info.get('id', f'pdf_{i}')
                        }

                        documents_complets.append(donnees_pdf)
                        titre = donnees_pdf.get('titre_contextuel', f'PDF {i + 1}')
                        access_level = pdf_info.get('access_level', 'public')
                        self.chatbot._log(f" PDF préparé: {titre} [niveau: {access_level}]", state)
                    else:
                        self.chatbot._log(f" PDF {i + 1}: Extension invalide", state)

                except Exception as e:
                    self.chatbot._log_error(f"Chargement PDF {i + 1}: {str(e)}", state)

            # Séparer à la fin
            tableaux_complets = [doc for doc in documents_complets if doc.get('document_type') == 'excel']
            pdfs_complets = [doc for doc in documents_complets if doc.get('document_type') == 'pdf']

            # Stockage final
            state['tableaux_charges'] = tableaux_complets
            state['pdfs_charges'] = pdfs_complets
            state['tableaux_reference'] = tableaux_complets

            # Vérification finale
            total_documents = len(tableaux_complets) + len(pdfs_complets)
            if total_documents == 0:
                self.chatbot._log("Agent RAG: Aucun document valide après chargement", state)
                self._nettoyer_etat_zero_documents(state, "Aucun document valide après chargement")
                return state

            self.chatbot._log(f" Chargement terminé: {len(tableaux_complets)} Excel + {len(pdfs_complets)} PDFs",
                              state)
            _send_to_frontend(session_id,
                              f"Chargement terminé: {len(tableaux_complets)} Excel + {len(pdfs_complets)} PDFs",
                              "SUCCESS")

            return state

        except Exception as e:
            self.chatbot._log_error(f"Agent RAG Unifié: {str(e)}", state)
            self._nettoyer_etat_zero_documents(state, f"Erreur: {str(e)}")
            return state

    def _nettoyer_etat_zero_documents(self, state: ChatbotState, raison: str):
        """
        Nettoie l'état du chatbot en réinitialisant les attributs liés aux
        tableaux et documents. Cette méthode est destinée à garantir
        un contexte propre avant le chargement ou la manipulation de nouveaux
        données.

        :param state: Une instance de l'état actuel du chatbot, où les
            informations sur les tableaux et documents sont stockées.
        :param raison: Une chaîne décrivant la raison du nettoyage
            effectué, ajoutée pour traçabilité.
        :return: None
        """
        # Nettoyage des champs Excel
        state['tableaux_pertinents'] = []
        state['tableaux_charges'] = []
        state['tableaux_reference'] = []

        # Nettoyage des champs PDF
        state['pdfs_pertinents'] = []
        state['pdfs_charges'] = []

        # Nettoyage des champs communs
        state['documents_trouves'] = []
        state['documents_selectionnes'] = []

        # Nettoyage des autres champs (pour compatibilité)
        state['tableaux_pour_upload'] = []
        state['dataframes'] = []
        state['fichiers_gemini'] = []
        state['fichiers_csvs_local'] = []
        state['pdfs_pour_contexte'] = []

        # Message informatif
        self.chatbot._log(f"État nettoyé: {raison}", state)

    def _valider_donnees_tableau(self, tableau_data: Dict) -> bool:
        """
        Valide les données fournies pour un tableau en vérifiant leur structure et leur contenu.

        Cette fonction examine si les données concernant un tableau sont conformes aux exigences
        préalables, à savoir que le tableau n'est pas vide, possède au moins deux lignes,
        et chaque ligne contient au moins une colonne. Si les validations échouent, la fonction retourne "False".
        Sinon, elle retourne "True".

        :param tableau_data: Dictionnaire contenant les données du tableau à valider.
        :type tableau_data: Dict
        :return: Booléen indiquant si les données du tableau sont valides ou non. Retourne "True" si valides, sinon "False".
        :rtype: bool
        """
        if not tableau_data:
            return False

        tableau = tableau_data.get('tableau')
        if not tableau or len(tableau) < 2:
            return False

        nb_cols = len(tableau[0])
        if nb_cols == 0:
            return False

        return True

    def _valider_donnees_pdf(self, pdf_data: Dict) -> bool:
        """
        Valide les données fournies dans un dictionnaire `pdf_data`.

        Cette méthode vérifie si les données PDF contiennent au moins une source
        d'information pertinente et un chemin ou une source associée. Si aucune de
        ces conditions n'est remplie, la validation échoue et la méthode retourne False.

        :param pdf_data: Dictionnaire contenant les données PDF à valider.
                         Les clés possibles incluent `resume_gemini`, `description`,
                         `titre_contextuel`, `tableau_path`, `fichier_source` et `source`.
        :type pdf_data: Dict
        :return: Retourne True si les données sont valides, autrement False.
        :rtype: bool
        """
        if not pdf_data:
            return False

        # Vérifier qu'on a AU MOINS une source d'information
        has_content = (
                pdf_data.get('resume_gemini') or
                pdf_data.get('description') or
                pdf_data.get('titre_contextuel')
        )

        has_path = (
                pdf_data.get('tableau_path') or
                pdf_data.get('fichier_source') or
                pdf_data.get('source')
        )

        return bool(has_content and has_path)

    def _role_est_autorise(self, role: str, access_level: str) -> bool:
        """
        Vérifie si un rôle donné est autorisé pour accéder à un certain niveau.

        Cette méthode assure que les permissions d'un rôle utilisateur sont comparées
        au niveau d'accès requis afin de déterminer les autorisations d'accès. Si un rôle ou
        un niveau d'accès spécifié est vide, des valeurs par défaut (public) sont appliquées.
        De plus, les valeurs pour le rôle et le niveau sont normalisées (en minuscules,
        sans espaces) pour éviter les erreurs.

        :param role: Le rôle de l'utilisateur sous forme de chaîne de caractères
        :param access_level: Le niveau d'accès requis (ex. public, internal, confidential)
        :return: True si le rôle est autorisé pour le niveau d'accès donné, sinon False
        :rtype: bool
        """

        if not role:
            role = "public"
        if not access_level:
            access_level = "public"

        # Normalisation pour éviter les erreurs
        role = str(role).lower().strip()
        access_level = str(access_level).lower().strip()

        # Mapping des permissions JWT
        droits = {
            "public": ["public"],  # Utilisateurs publics
            "employee": ["public", "internal"],  # Salariés
            "admin": ["public", "internal", "confidential"]  # Administrateurs
        }

        # Récupération des niveaux autorisés pour ce rôle
        niveaux_autorises = droits.get(role, ["public"])  # Fallback sécurisé

        # Vérification finale
        est_autorise = access_level in niveaux_autorises

        return est_autorise
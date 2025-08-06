from typing import Dict
from ..core.state import ChatbotState
from ..utils.message_to_front import _send_to_frontend
#from backend_python.src.core.state import ChatbotState
#from backend_python.src.utils.message_to_front import _send_to_frontend

class RAGAgent:
    """Agent RAG pour rechercher des tableaux pertinents avec système JWT"""

    def __init__(self, rag_index, chatbot_instance):
        self.rag = rag_index
        self.chatbot = chatbot_instance

    def execute(self, state: ChatbotState) -> ChatbotState:
        """Point d'entrée principal de l'agent"""
        return self.agent_rag(state)


    def agent_rag(self, state: ChatbotState) -> ChatbotState:
        """
        Agent RAG avec gestion d'erreurs et permissions JWT
        """

        self.chatbot._log("Agent RAG: Démarrage de la recherche", state)
        session_id = state.get('session_id')
        _send_to_frontend(session_id, f"Agent RAG: Début recherche sur '{state['question_utilisateur'][:50]}...'",
                          "SEARCH")

        try:
            # Validation de la question
            if not state['question_utilisateur'].strip():
                raise ValueError("Question utilisateur vide")

            user_role = state.get("user_role", "public")

            # Recherche RAG (sans filtrage - sera fait après)
            resultats_rag = self.rag.rechercher_tableaux(
                state['question_utilisateur'],
                user_role=user_role,
                n_results=10
            )

            #  Vérification plus robuste des résultats
            if not resultats_rag or not isinstance(resultats_rag, dict):
                self.chatbot._log("Agent RAG: Résultats de recherche invalides", state)
                self._nettoyer_etat_zero_documents(state, "Résultats invalides")
                return state

            tableaux_bruts = resultats_rag.get('tableaux', [])
            if not tableaux_bruts or not isinstance(tableaux_bruts, list):
                self.chatbot._log("Agent RAG: Aucun tableau trouvé dans la recherche", state)
                self._nettoyer_etat_zero_documents(state, "Aucun tableau trouvé")
                return state

            #Filtrage sécurisé avec gestion des cas vides
            user_role = state.get("user_role", "public")
            tableaux_autorises = []

            for i, tab in enumerate(tableaux_bruts):
                try:
                    # Vérification que tab est un dictionnaire
                    if not isinstance(tab, dict):
                        self.chatbot._log(f"Tableau {i + 1}: Format invalide (pas un dict)", state)
                        continue

                    # Gestion sécurisée des access_level avec validation
                    access_level = tab.get("access_level")

                    # Protection contre les valeurs None/vides qui causaient l'erreur
                    if access_level is None or access_level == "":
                        access_level = "public"  # Valeur par défaut sécurisée

                    # Normalisation pour éviter les erreurs de casse
                    access_level = str(access_level).lower().strip()

                    # Validation des valeurs autorisées
                    if access_level not in ['public', 'internal', 'confidential']:
                        self.chatbot._log(f"Niveau d'accès invalide '{access_level}', défaut à 'public'", state)
                        access_level = "public"

                    # Vérification des permissions JWT
                    if self._role_est_autorise(user_role, access_level):
                        # Préserver l'access_level normalisé
                        tab['access_level'] = access_level
                        tableaux_autorises.append(tab)
                    else:
                        self.chatbot._log(
                            f"Tableau '{tab.get('titre', 'Unknown')}' refusé: niveau {access_level} > rôle {user_role}",
                            state)

                except Exception as e:
                    self.chatbot._log_error(f"Erreur filtrage tableau {i + 1}: {str(e)}", state)
                    continue

            # Gestion explicite du cas 0 documents autorisés
            if not tableaux_autorises:
                self.chatbot._log(
                    f"Agent RAG: Aucun tableau accessible au rôle '{user_role}' (sur {len(tableaux_bruts)} trouvés)",
                    state)
                _send_to_frontend(session_id, f"Aucun document accessible avec votre rôle ({user_role})", "WARNING")
                self._nettoyer_etat_zero_documents(state, f"Aucun accès pour rôle {user_role}")
                return state

            # Si on arrive ici, il y a des documents autorisés
            state['tableaux_pertinents'] = tableaux_autorises
            state['documents_trouves'] = tableaux_autorises
            self.chatbot._log(f"Agent RAG: {len(tableaux_autorises)} tableaux accessibles au rôle '{user_role}'", state)

            # Chargement des données avec validation
            tableaux_complets = []
            for i, tableau_info in enumerate(state['tableaux_pertinents']):
                try:
                    tableau_path = tableau_info.get('tableau_path')
                    if not tableau_path:
                        self.chatbot._log(f"Tableau {i + 1}: Chemin manquant", state)
                        continue

                    donnees_completes = self.rag.get_tableau_data(tableau_path)
                    if self._valider_donnees_tableau(donnees_completes):
                        # Préserver les métadonnées d'accès pour le JWT
                        donnees_completes['access_level'] = tableau_info.get('access_level', 'public')
                        tableaux_complets.append(donnees_completes)
                        titre = donnees_completes.get('titre_contextuel', f'Tableau {i + 1}')
                        access_level = tableau_info.get('access_level', 'public')
                        self.chatbot._log(f"Tableau chargé: {titre} [niveau: {access_level}]", state)
                    else:
                        self.chatbot._log(f"Tableau {i + 1} invalide", state)

                except Exception as e:
                    self.chatbot._log_error(f"Chargement tableau {i + 1}: {str(e)}", state)

            #Vérification finale après chargement
            if not tableaux_complets:
                self.chatbot._log("Agent RAG: Aucun tableau valide après chargement", state)
                self._nettoyer_etat_zero_documents(state, "Aucun tableau valide après chargement")
                return state

            state['tableaux_charges'] = tableaux_complets
            state['tableaux_reference'] = tableaux_complets

            return state

        except Exception as e:
            self.chatbot._log_error(f"Agent RAG: {str(e)}", state)
            self._nettoyer_etat_zero_documents(state, f"Erreur: {str(e)}")
            return state

    def _nettoyer_etat_zero_documents(self, state: ChatbotState, raison: str):
        """
        Nettoie proprement l'état quand 0 documents sont accessibles
        """
        state['tableaux_pertinents'] = []
        state['tableaux_charges'] = []
        state['tableaux_reference'] = []
        state['documents_trouves'] = []
        state['documents_selectionnes'] = []
        state['tableaux_pour_upload'] = []
        state['dataframes'] = []
        state['fichiers_gemini'] = []
        state['fichiers_csvs_local'] = []
        state['pdfs_pour_contexte'] = []

        # Message informatif dans l'historique
        self.chatbot._log(f"État nettoyé: {raison}", state)

    def _valider_donnees_tableau(self, tableau_data: Dict) -> bool:
        """Valide la structure d'un tableau"""
        if not tableau_data:
            return False

        tableau = tableau_data.get('tableau')
        if not tableau or len(tableau) < 2:
            return False

        nb_cols = len(tableau[0])
        if nb_cols == 0:
            return False

        return True

    def _role_est_autorise(self, role: str, access_level: str) -> bool:
        """
        Règles d'accès JWT

        LOGIQUE :
        - public -> peut voir seulement les documents publics
        - salarie (employee) -> peut voir public + internal
        - admin -> peut voir public + internal + confidential
        """
        if not role:
            role = "public"
        if not access_level:
            access_level = "public"

        # Normalisation pour éviter les erreurs
        role = str(role).lower().strip()
        access_level = str(access_level).lower().strip()

        # Votre mapping des permissions JWT
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
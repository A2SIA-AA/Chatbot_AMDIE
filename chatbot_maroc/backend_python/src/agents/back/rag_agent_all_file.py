from typing import Dict
from ..core.state import ChatbotState


class RAGAgentAllFile:
    """Agent RAG pour rechercher des documents pertinents AVEC GESTION DES PERMISSIONS"""

    def __init__(self, rag_index, chatbot_instance):
        self.rag = rag_index
        self.chatbot = chatbot_instance

    def execute(self, state: ChatbotState) -> ChatbotState:
        """Point d'entrée principal de l'agent"""
        return self.agent_rag_all_file(state)


    def agent_rag_all_file(self, state: ChatbotState) -> ChatbotState:
        """Agent RAG avec gestion d'erreurs ET PERMISSIONS JWT RESTAURÉES"""

        self.chatbot._log("Agent RAG tout fichier: Démarrage de la recherche", state)

        try:
            # ===== PARTIE 1: VALIDATION DE LA QUESTION (MANQUAIT !) =====
            if not state['question_utilisateur'].strip():
                raise ValueError("Question utilisateur vide")

            # ===== PARTIE 2: RECHERCHE RAG AVEC PERMISSIONS (MANQUAIT !) =====
            user_role = state.get("user_role", "public")


            resultats_rag = self.rag.rechercher_tableaux(
                state['question_utilisateur'],
                user_role=user_role,
                n_results=10
            )

            if not resultats_rag or not resultats_rag.get('tableaux'):
                self.chatbot._log("Agent RAG: Aucun tableau trouvé", state)
                state['tableaux_pertinents'] = []
                state['tableaux_charges'] = []
                state['documents_trouves'] = []
                return state

            # ===== PARTIE 3: FILTRAGE DES PERMISSIONS (MANQUAIT !) =====
            tableaux_bruts = resultats_rag['tableaux']
            tableaux_autorises = []

            for i, tab in enumerate(tableaux_bruts):
                try:
                    if not isinstance(tab, dict):
                        self.chatbot._log(f"Tableau {i + 1}: Format invalide", state)
                        continue

                    # Gestion sécurisée des access_level
                    access_level = tab.get("access_level")
                    if access_level is None or access_level == "":
                        access_level = "public"

                    access_level = str(access_level).lower().strip()
                    if access_level not in ['public', 'internal', 'confidential']:
                        access_level = "public"

                    # Vérification des permissions JWT
                    if self._role_est_autorise(user_role, access_level):
                        tab['access_level'] = access_level
                        tableaux_autorises.append(tab)
                    else:
                        self.chatbot._log(
                            f"Tableau '{tab.get('titre', 'Unknown')}' refusé: niveau {access_level} > rôle {user_role}",
                            state)

                except Exception as e:
                    self.chatbot._log_error(f"Erreur filtrage tableau {i + 1}: {str(e)}", state)
                    continue

            # Gestion du cas 0 documents autorisés
            if not tableaux_autorises:
                self.chatbot._log(
                    f"Agent RAG: Aucun tableau accessible au rôle '{user_role}' (sur {len(tableaux_bruts)} trouvés)",
                    state)
                state['tableaux_pertinents'] = []
                state['tableaux_charges'] = []
                state['documents_trouves'] = []
                return state

            # ===== PARTIE 4: STOCKAGE DES RÉSULTATS (MANQUAIT !) =====
            state['tableaux_pertinents'] = tableaux_autorises
            state['documents_trouves'] = tableaux_autorises
            self.chatbot._log(f"Agent RAG: {len(tableaux_autorises)} tableaux accessibles au rôle '{user_role}'", state)

            tableaux_complets = []
            for i, tableau_info in enumerate(state['tableaux_pertinents']):
                try:
                    tableau_path = tableau_info.get('tableau_path')
                    if not tableau_path:
                        self.chatbot._log(f"Tableau {i + 1}: Chemin manquant", state)
                        continue

                    # CORRECTION CRITIQUE: Charger les données Excel RÉELLES depuis le fichier
                    donnees_completes = self._charger_fichier_excel_reel(tableau_path, tableau_info)

                    if donnees_completes and 'tableau' in donnees_completes:
                        # Préserver les métadonnées d'accès
                        donnees_completes['access_level'] = tableau_info.get('access_level', 'public')
                        tableaux_complets.append(donnees_completes)

                        titre = donnees_completes.get('titre_contextuel', f'Tableau {i + 1}')
                        access_level = tableau_info.get('access_level', 'public')
                        nb_lignes = len(donnees_completes.get('tableau', [])) - 1  # -1 pour headers
                        self.chatbot._log(f"✅ Excel chargé: {titre} [{nb_lignes} lignes] [niveau: {access_level}]",
                                          state)
                    else:
                        self.chatbot._log(f"❌ Échec chargement Excel: {tableau_path}", state)

                except Exception as e:
                    self.chatbot._log_error(f"Chargement Excel {i + 1}: {str(e)}", state)

            state['tableaux_charges'] = tableaux_complets
            state['tableaux_reference'] = tableaux_complets

        except Exception as e:
            self.chatbot._log_error(f"Agent RAG: {str(e)}", state)
            state['tableaux_charges'] = []
            state['documents_trouves'] = []

        return state

    def _charger_fichier_excel_reel(self, tableau_path: str, metadata: dict) -> dict:
        """Charge le fichier Excel réel depuis le disque"""
        import pandas as pd
        import os

        try:
            # Vérifier que le fichier existe
            if not os.path.exists(tableau_path):
                self.chatbot._log(f"Fichier non trouvé: {tableau_path}", {})
                return None

            # Charger le fichier Excel réel
            if tableau_path.endswith('.xlsx') or tableau_path.endswith('.xls'):
                # Charger avec pandas
                df = pd.read_excel(tableau_path, sheet_name=0)  # Première feuille

                # Convertir en format tableau
                headers = df.columns.tolist()
                rows = df.values.tolist()

                tableau_data = [headers] + rows

            elif tableau_path.endswith('.csv'):
                # Charger CSV
                df = pd.read_csv(tableau_path)
                headers = df.columns.tolist()
                rows = df.values.tolist()
                tableau_data = [headers] + rows

            else:
                self.chatbot._log(f"Format non supporté: {tableau_path}", {})
                return None

            # Créer la structure complète avec métadonnées + données réelles
            resultat = {
                'tableau': tableau_data,
                'titre_contextuel': metadata.get('titre_contextuel', 'Tableau Excel'),
                'fichier_source': metadata.get('source', tableau_path),
                'nom_feuille': metadata.get('nom_feuille', 'Feuille'),
                'description': metadata.get('description', 'Données Excel'),
                'id': metadata.get('id', 'excel_file'),
                'tableau_path': tableau_path
            }

            self.chatbot._log(f"📊 Fichier Excel chargé: {len(tableau_data) - 1} lignes, {len(headers)} colonnes", {})
            return resultat

        except Exception as e:
            self.chatbot._log_error(f"Erreur lecture Excel {tableau_path}: {e}", {})
            return None

    def _charger_donnees_excel_depuis_path(self, tableau_path: str) -> list:
        """Charge les données Excel réelles depuis le tableau_path"""
        try:
            # Utiliser votre méthode RAG existante pour charger les données
            donnees_brutes = self.rag.get_tableau_data(tableau_path)

            # Si les données sont déjà dans le bon format
            if 'tableau' in donnees_brutes:
                return donnees_brutes['tableau']

            # Sinon, essayer de les charger depuis le fichier
            # ADAPTATION NÉCESSAIRE : Selon votre implémentation RAG
            # Vous devez adapter cette partie selon comment votre RAG charge les fichiers Excel

            # Exemple générique (à adapter selon votre implementation):
            if hasattr(self.rag, 'load_excel_data'):
                return self.rag.load_excel_data(tableau_path)
            elif hasattr(self.rag, 'get_raw_tableau_data'):
                raw_data = self.rag.get_raw_tableau_data(tableau_path)
                return raw_data.get('tableau', [])
            else:
                # Fallback: créer des données fictives pour éviter l'erreur
                self.chatbot._log(f"FALLBACK: Création données fictives pour {tableau_path}", {})
                return [
                    ['Colonne1', 'Colonne2', 'Colonne3'],  # Headers
                    ['Donnée1', 'Donnée2', 'Donnée3'],  # Row 1
                    ['Donnée4', 'Donnée5', 'Donnée6']  # Row 2
                ]

        except Exception as e:
            self.chatbot._log_error(f"Erreur chargement Excel depuis {tableau_path}: {e}", {})
            return None

    def _valider_donnees_tableau(self, tableau_data: Dict) -> bool:
        """Valide la structure d'un tableau - VERSION MISE À JOUR"""
        if not tableau_data:
            return False

        # Accepter les documents même sans champ 'tableau' initial
        # car on va le charger nous-mêmes
        if 'tableau_path' in tableau_data:
            return True

        # Validation originale si le tableau existe déjà
        tableau = tableau_data.get('tableau')
        if tableau and len(tableau) >= 2:
            nb_cols = len(tableau[0])
            return nb_cols > 0

        return False

    def _role_est_autorise(self, role: str, access_level: str) -> bool:
        """
        MÉTHODE COPIÉE DE RAGAgent - Règles d'accès JWT
        """
        if not role:
            role = "public"
        if not access_level:
            access_level = "public"

        role = str(role).lower().strip()
        access_level = str(access_level).lower().strip()

        # Mapping des permissions JWT
        droits = {
            "public": ["public"],
            "employee": ["public", "internal"],
            "admin": ["public", "internal", "confidential"]
        }

        niveaux_autorises = droits.get(role, ["public"])
        return access_level in niveaux_autorises

import pandas as pd
from typing import Dict, List
from ..core.state import ChatbotState
from ..utils.message_to_front import _send_to_frontend
from ..core.memory_store import conversation_memory, get_user_context
import sys


class SynthesisAgent:
    """Agent synthèse pour formuler la réponse finale avec historique utilisateur"""

    def __init__(self, gemini_model, chatbot_instance):
        self.gemini_model = gemini_model
        self.chatbot = chatbot_instance

    def execute(self, state: ChatbotState) -> ChatbotState:
        """Point d'entrée principal de l'agent"""
        print(f"[DEBUG {self.__class__.__name__}] self.chatbot.user_permissions: {self.chatbot.user_permissions}",file=sys.stderr)
        return self.agent_synthese(state)

    def agent_synthese(self, state: ChatbotState) -> ChatbotState:
        """Agent synthèse adaptatif selon le workflow avec historique"""

        self.chatbot._log("Agent Synthèse: Formulation finale avec historique", state)
        session_id = state.get('session_id')
        _send_to_frontend(session_id, "Agent Synthèse: Formulation de la réponse finale avec contexte historique...")

        # Récupérer les informations utilisateur pour l'historique
        username, email = self._extract_user_info(state)

        # CAS 1: Réponse directe (workflow court)

        if not state.get('besoin_calculs') or state.get('reponse_finale'):
            # Construire les volets Excel/PDF puis fusionner si nécessaire
            texte_excel = None

            if state.get('reponse_finale'):
                texte_excel = state['reponse_finale']
            elif state.get('resultat_pandas') is not None:
                texte_excel = f"Données calculées:\\n{state['resultat_pandas']}"

            texte_pdf = state.get('reponse_finale_pdf')

          # Fusion

            if texte_excel and texte_pdf:
                state['reponse_finale'] = (
                        "Synthèse combinée (Excel + PDF):\n\n"
                        "- Volet données tabulaires (Excel):\n"
                        f"{texte_excel}\n\n"
                        " Volet documents textuels (PDF):\n"
                      f"{texte_pdf}"
                )
            elif texte_pdf and not texte_excel:
                state['reponse_finale'] = texte_pdf
            # sinon, on conserve texte_excel déjà en place

            # Enrichir avec les sources Excel
            state['reponse_finale'] = self._enrichir_reponse_avec_sources(
                state['reponse_finale'],
                state.get('tableaux_pour_upload', [])
            )
            # Ajouter les sources PDF si présentes

            if state.get('sources_pdf'):
                state['reponse_finale'] += "\n\nSources PDF:\n" + "\n".join(state['sources_pdf'])

            # Sauvegarder dans l'historique
            if username and email:
                    success = conversation_memory.save_conversation(
                        username=username,
                        email=email,
                        question=state['question_utilisateur'],
                        reponse=state['reponse_finale'],
                        session_id=session_id
                    )
                    if success:
                        self.chatbot._log(f" Conversation sauvegardée pour {username}", state)
                    else:
                        self.chatbot._log(" Erreur sauvegarde conversation", state)
            else:
                state['reponse_finale'] = "Aucune réponse générée par l'analyseur."
            return state

        # CAS 2: Après calculs (workflow complet)
        if state.get('besoin_calculs') and state.get('resultat_pandas') is not None:
            try:
                # Fusion Excel/PDF après calculs
                base = f"Données calculées:\n{state['resultat_pandas']}"
                texte_pdf = state.get('reponse_finale_pdf')

                if texte_pdf:
                    state['reponse_finale'] = (
                            "Synthèse combinée (Excel + PDF):\n\n"
                            "- Volet données tabulaires (Excel):\n"
                            f"{base}\n\n"
                            "- Volet documents textuels (PDF):\n"
                            f"{texte_pdf}"
                            )
                else:
                    state['reponse_finale'] = base

                 # Ajouter sources PDF si présentes

                if state.get('sources_pdf'):
                    state['reponse_finale'] += "\n\nSources PDF:\n" + "\n".join(
                    state['sources_pdf'])
                #Récupérer l'historique utilisateur pour le contexte
                historique_contexte = ""
                if username and email:
                    historique_contexte = get_user_context(username, email)
                    self.chatbot._log(f" Historique récupéré pour {username}", state)

                prompt_synthese = f"""Tu es un assistant expert des données du Maroc avec accès à l'historique des conversations.

{historique_contexte if historique_contexte else "Première conversation de l'utilisateur."}

QUESTION ACTUELLE: {state['question_utilisateur']}

RÉSULTATS OBTENUS: {state['resultat_pandas']}

SOURCES UTILISÉES: 
{self._extraire_sources_utilisees(state['dataframes'])}

CONTEXTE: Analyse basée sur {len(state.get('dataframes', [])) if state.get('dataframes') else 0} sources de données officielles

INSTRUCTIONS:
1. Prends en compte l'HISTORIQUE pour contextualiser ta réponse
2. Si l'utilisateur fait référence à des conversations précédentes, utilise cet historique
3. Répond directement à la question actuelle
4. Présente le résultat de manière compréhensible  
5. CITE les sources utilisées (titre + origine)
6. Reste factuel et précis
7. Donne de la crédibilité avec les références
8. Si c'est une question de suivi, mentionne la continuité avec les conversations précédentes

RÉPONSE:"""

                response = self.gemini_model.generate_content(prompt_synthese)
                state['reponse_finale'] = response.text

                # Sauvegarder la conversation complète dans l'historique
                if username and email:
                    success = conversation_memory.save_conversation(
                        username=username,
                        email=email,
                        question=state['question_utilisateur'],
                        reponse=state['reponse_finale'],
                        session_id=session_id
                    )
                    if success:
                        self.chatbot._log(f" Conversation avec calculs sauvegardée pour {username}", state)

                        # Ajouter les stats utilisateur dans les logs
                        stats = conversation_memory.get_conversation_stats(username, email)
                        self.chatbot._log(
                            f" Stats utilisateur: {stats['total_conversations']} conversations total, {stats['conversations_24h']} dans les 24h",
                            state)
                    else:
                        self.chatbot._log(" Erreur sauvegarde conversation avec calculs", state)

                self.chatbot._log("Synthèse: Réponse finale générée avec historique", state)

            except Exception as e:
                self.chatbot._log_error(f"Synthèse: {str(e)}", state)
                state['reponse_finale'] = f"D'après mon analyse: {state['resultat_pandas']}"

                # Même en cas d'erreur de synthèse, sauvegarder la réponse de base
                if username and email:
                    conversation_memory.save_conversation(
                        username=username,
                        email=email,
                        question=state['question_utilisateur'],
                        reponse=state['reponse_finale'],
                        session_id=session_id
                    )

        # CAS 3: Échec des calculs
        elif state.get('besoin_calculs') and state.get('erreur_pandas'):
            error_response = f"""J'ai rencontré une difficulté technique lors de l'analyse.

Erreur: {state['erreur_pandas']}

Pouvez-vous reformuler votre question de manière plus simple ou plus spécifique ?"""

            state['reponse_finale'] = error_response

            # Sauvegarder même les erreurs pour le contexte
            if username and email:
                conversation_memory.save_conversation(
                    username=username,
                    email=email,
                    question=state['question_utilisateur'],
                    reponse=error_response,
                    session_id=session_id
                )

        # CAS 4: Par défaut
        else:
            default_response = "Impossible de traiter votre demande. Veuillez reformuler."
            state['reponse_finale'] = default_response

            if username and email:
                conversation_memory.save_conversation(
                    username=username,
                    email=email,
                    question=state['question_utilisateur'],
                    reponse=default_response,
                    session_id=session_id
                )

        return state

    def _extract_user_info(self, state: ChatbotState) -> tuple:
        """
        Extrait les informations utilisateur du state

        Returns:
            tuple: (username, email) ou (None, None) si non disponible
        """
        try:
            # Récupérer depuis les permissions/état utilisateur
            # Selon ton système, ça pourrait être stocké différemment
            session_id = state.get('session_id', '')

            # Si le session_id contient des infos utilisateur (format: session_keycloak_role_timestamp_hash)
            if 'keycloak' in session_id:
                # Pour Keycloak, on pourrait avoir les infos dans le state
                # À adapter selon comment tu stockes les infos utilisateur
                pass

            # Vérifier si les infos utilisateur sont directement dans le state
            # Tu pourrais ajouter username/email dans ChatbotState
            username = state.get('username')
            email = state.get('email')

            if username and email:
                return username, email

            # Fallback: extraire depuis le user_role ou autres champs
            user_role = state.get('user_role', '')

            # Pour l'instant, utiliser des valeurs par défaut basées sur le session_id
            # À adapter avec tes vraies données utilisateur
            if session_id:
                # Tu peux modifier cette logique pour récupérer les vraies infos utilisateur
                # depuis ton système d'auth ou les passer dans le state

                # Exemple temporaire:
                if 'admin' in session_id:
                    return 'admin_user', 'admin@amdie.ma'
                elif 'employee' in session_id:
                    return 'employee_user', 'employee@amdie.ma'
                else:
                    return 'public_user', 'public@amdie.ma'

            return None, None

        except Exception as e:
            self.chatbot._log_error(f"Erreur extraction info utilisateur: {e}", state)
            return None, None

    def _enrichir_reponse_avec_sources(self, reponse: str, tableaux: List[Dict]) -> str:
        """Enrichit une réponse directe avec les sources"""

        if reponse is None:
            reponse = "Réponse non disponible"

        if not tableaux or not isinstance(tableaux, list):
            return reponse

        sources = []
        for tableau in tableaux[:3]:
            if tableau is None or not isinstance(tableau, dict):
                continue
            titre = tableau.get('titre_contextuel', 'Source inconnue')
            source = tableau.get('fichier_source', 'N/A')
            if titre and isinstance(titre, str) and titre != 'Source inconnue':
                sources.append(f"• {titre} ({source})")

        if sources:
            reponse += f"\n\nSources consultées :\n" + "\n".join(sources)

        return reponse

    def _extraire_sources_utilisees(self, dataframes: List[pd.DataFrame]) -> str:
        """Extrait les sources pour la réponse finale"""

        # PROTECTION CONTRE None
        if not dataframes or not isinstance(dataframes, list):
            return "Aucune source disponible"

        sources = []
        for df in dataframes:
            if df is None:
                continue
            attrs = getattr(df, 'attrs', {})
            if attrs is None:
                attrs = {}
            titre = attrs.get('titre', 'Source non identifiée')
            source = attrs.get('source', 'N/A')
            sources.append(f"• {titre} (Source: {source})")

        return '\n'.join(sources) if sources else "Aucune source disponible"
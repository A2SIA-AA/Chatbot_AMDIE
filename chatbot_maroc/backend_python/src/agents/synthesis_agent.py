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
        """Agent synthèse adaptatif avec réponse UNIFIÉE et NATURELLE"""

        self.chatbot._log("Agent Synthèse: Formulation finale unifiée", state)
        session_id = state.get('session_id')

        # Récupérer les informations utilisateur pour l'historique
        username, email = self._extract_user_info(state)

        # Collecter TOUTES les informations disponibles
        contenu_excel = None
        contenu_pdf = None
        sources_utilisees = []

        # 1. Récupérer le contenu Excel s'il existe
        if state.get('reponse_finale') and state.get('reponse_finale') != "":
            contenu_excel = state['reponse_finale']
        elif state.get('resultat_pandas'):
            contenu_excel = f"Données calculées:\n{state['resultat_pandas']}"

        # 2. Récupérer le contenu PDF s'il existe
        if state.get('reponse_finale_pdf') and state.get('reponse_finale_pdf') != "":
            contenu_pdf = state['reponse_finale_pdf']

        # 3. Collecter les sources
        if state.get('tableaux_pour_upload'):
            for tableau in state['tableaux_pour_upload']:
                titre = tableau.get('titre_contextuel', 'Document Excel')
                source = tableau.get('fichier_source', 'N/A')
                sources_utilisees.append(f"• {titre} ({source})")

        if state.get('sources_pdf'):
            for source_pdf in state['sources_pdf']:
                sources_utilisees.append(f"• {source_pdf}")

        # 4. GÉNÉRATION D'UNE RÉPONSE UNIFIÉE ET NATURELLE
        try:
            # Récupérer l'historique utilisateur
            historique_contexte = ""
            if username and email:
                historique_contexte = get_user_context(username, email)

            prompt_unifie = f"""Tu es un assistant expert qui doit donner UNE RÉPONSE NATURELLE et DIRECTE.

    {historique_contexte if historique_contexte else "Première conversation de l'utilisateur."}

    QUESTION: {state['question_utilisateur']}

    INFORMATIONS DISPONIBLES:
    {f"DONNÉES EXCEL: {contenu_excel}" if contenu_excel else ""}
    {f"DONNÉES PDF: {contenu_pdf}" if contenu_pdf else ""}

    SOURCES: {chr(10).join(sources_utilisees) if sources_utilisees else "Aucune source disponible"}

    INSTRUCTIONS CRITIQUES:
    1. Réponds DIRECTEMENT à la question de manière naturelle
    2. NE MENTIONNE PAS les types de sources (Excel, PDF) dans ta réponse
    3. Utilise TOUTES les informations pertinentes de manière fluide
    4. Si aucune information ne répond à la question, dis-le clairement
    5. Cite les sources à la fin sans mentionner leur format
    6. Tiens compte de l'historique si pertinent

    RÉPONSE:"""

            response = self.gemini_model.generate_content(prompt_unifie)
            reponse_unifiee = response.text

            # Ajouter les sources de manière discrète
            if sources_utilisees:
                reponse_unifiee += f"\n\nSources consultées :\n{chr(10).join(sources_utilisees)}"

            state['reponse_finale'] = reponse_unifiee

            # Sauvegarder dans l'historique
            if username and email:
                success = conversation_memory.save_conversation(
                    username=username,
                    email=email,
                    question=state['question_utilisateur'],
                    reponse=reponse_unifiee,
                    session_id=session_id
                )
                if success:
                    self.chatbot._log(f"Conversation unifiée sauvegardée pour {username}", state)

        except Exception as e:
            self.chatbot._log_error(f"Erreur synthèse unifiée: {e}", state)

            # Fallback : réponse simple basée sur le contenu disponible
            if contenu_pdf and contenu_excel:
                state['reponse_finale'] = f"{contenu_pdf}\n\nInformations complémentaires : {contenu_excel}"
            elif contenu_pdf:
                state['reponse_finale'] = contenu_pdf
            elif contenu_excel:
                state['reponse_finale'] = contenu_excel
            else:
                state['reponse_finale'] = "Aucune information trouvée pour répondre à votre question."

            # Ajouter sources en fallback
            if sources_utilisees:
                state['reponse_finale'] += f"\n\nSources : {', '.join(sources_utilisees)}"

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
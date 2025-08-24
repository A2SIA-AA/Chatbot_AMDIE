import pandas as pd
from typing import Dict, List
from ..core.state import ChatbotState
from ..utils.message_to_front import _send_to_frontend
from ..core.memory_store import conversation_memory, get_user_context
import sys


class SynthesisAgent:
    """
    Agent de synthèse adaptatif pour la génération de réponses unifiées et naturelles.

    Cet agent a pour but d'intégrer différentes sources d'informations, telles que des contenus
    Excel ou PDF, afin de synthétiser une seule réponse cohérente et naturelle pour l'utilisateur.
    Il s'appuie sur un modèle de langage (représenté par ``gemini_model``) et un chatbot
    pour interagir avec l'utilisateur et maintenir un historique des discussions.

    Ce mécanisme comprend la collecte des données disponibles, leur contextualisation,
    et la génération de réponses en fonction des informations pertinentes. Si aucune donnée
    n'est disponible ou si une erreur survient, une réponse alternative ou un fallback
    est retourné.

    :ivar gemini_model: Modèle de langage utilisé pour générer les réponses unifiées.
    :ivar chatbot: Instance du chatbot utilisée pour l'interaction utilisateur et la gestion
        de l'historique des conversations.
    """

    def __init__(self, gemini_model, chatbot_instance):
        """
        Initialise une instance de la classe avec les composants nécessaires.

        Cette méthode initialise deux objets principaux requis pour le fonctionnement
        de la classe : un modèle spécifié et une instance de chatbot. Ces éléments
        seront utilisés par d'autres méthodes de la classe pour opérer sur les données
        ou répondre aux exigences fonctionnelles.

        :param gemini_model: Modèle principal utilisé pour les processus de
            prédiction ou d'analyse.
        :param chatbot_instance: Instance de chatbot qui gère l'interaction
            utilisateur ou les flux de conversation.
        """
        self.gemini_model = gemini_model
        self.chatbot = chatbot_instance

    def execute(self, state: ChatbotState) -> ChatbotState:
        """
        Point d'entrée principal de l'agent.

        Cette méthode agit comme le point d'interaction principal avec l'état d'un
        chatbot. Elle récupère les permissions utilisateur actuelles et délègue
        ensuite la logique à une méthode de synthèse spécifique.

        :param state:
            L'état actuel du chatbot sous forme d'un objet `ChatbotState`.
        :type state: ChatbotState

        :return:
            L'état mis à jour du chatbot après traitement par l'agent de synthèse.
        :rtype: ChatbotState
        """
        """Point d'entrée principal de l'agent"""
        print(f"[DEBUG {self.__class__.__name__}] self.chatbot.user_permissions: {self.chatbot.user_permissions}",file=sys.stderr)
        return self.agent_synthese(state)

    def agent_synthese(self, state: ChatbotState) -> ChatbotState:
        """
        Synthétise une réponse unifiée et naturelle à partir des données structurées et non
        structurées disponibles dans l'état actuel d'un chatbot. La méthode alimente une
        intelligence artificielle pour générer une réponse directe et intégrée, en s'appuyant
        sur des sources multiples (Excel, PDF, historique de l'utilisateur). Elle vise à
        produire une formulation finale cohérente et naturelle tout en sauvegardant un
        historique de conversation si possible.

        :param state: État actuel du chatbot contenant la question de l'utilisateur, les
            données disponibles (Excel, PDF, etc.) et les informations contextuelles comme
            l'historique utilisateur.
        :type state: ChatbotState
        :return: État mis à jour du chatbot, incluant la réponse synthétisée à la question de
            l'utilisateur.
        :rtype: ChatbotState
        :raises KeyError: Si des clés nécessaires dans `state` sont absentes.
        :raises TypeError: Si des données dans `state` ne correspondent pas aux attentes
            (par exemple, format de données incorrect).
        :raises Exception: En cas de problème non spécifié durant la génération de la réponse.
        """

        self.chatbot._log("Agent Synthèse: Formulation finale unifiée", state)
        session_id = state.get('session_id')

        # Récupérer les informations utilisateur pour l'historiquehistorique
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
        Extrait les informations de l'utilisateur depuis l'état d'un chatbot. Cette méthode analyse
        l'état fourni pour identifier et retourner le nom d'utilisateur et l'adresse email correspondante.
        Si les informations ne sont pas directement disponibles, elle établit des valeurs par défaut en
        fonction du rôle d'utilisateur trouvé dans l'état. En cas d'erreur, une journalisation est effectuée.

        :param state: Représente l'état actuel du chatbot contenant les informations de l'utilisateur.
        :type state: ChatbotState

        :return: Une paire (tuple) contenant le nom d'utilisateur et son adresse email. Retourne
                 (None, None) en cas d'échec ou si les informations ne sont pas disponibles.
        :rtype: tuple
        """
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
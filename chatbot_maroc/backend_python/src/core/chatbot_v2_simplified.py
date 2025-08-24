import time
from langgraph.graph import StateGraph, END
import google.generativeai as genai
import sys
from typing import List

from .state import ChatbotState
from ..agents.pandas_agent import SimplePandasAgent
from ..agents.code_agent import CodeAgent
from ..agents.synthesis_agent import SynthesisAgent

# AGENTS UNIFIÉS
from ..agents.rag_agent_unified import RAGAgentUnified
from ..agents.selector_agent_unified import SelectorAgentUnified
from ..agents.analyzer_agent_unified import AnalyzerAgentUnified

from ..core.memory_store import conversation_memory
from dotenv import load_dotenv
import os
load_dotenv()

sys.path[:0] = ['../../']
from config.logging import setup_logging, PerformanceLogger
from config.setting import get_settings


class ChatbotMarocV2Simplified:
    """
    Classe représentant un chatbot avancé avec une architecture simplifiée et une gestion
    unifiée pour les flux Excel et PDF. Ce chatbot est conçu pour offrir une expérience
    utilisateur personnalisée en fonction des permissions et du rôle des utilisateurs.

    :ivar settings: Configuration globale utilisée par le chatbot.
    :type settings: dict
    :ivar rag: Index RAG existant pour gérer les données de type Retrieval-Augmented Generation.
    :type rag: RAGIndex
    :ivar logger: Instance de journalisation pour les événements du chatbot.
    :type logger: Logger
    :ivar perf_logger: Instance utilisée pour enregistrer les performances.
    :type perf_logger: PerformanceLogger
    :ivar gemini_model: Modèle generatif Gemini utilisé pour le traitement des données et les réponses.
    :type gemini_model: GenerativeModel
    :ivar user_permissions: Liste des permissions utilisateur actuellement en cours.
    :type user_permissions: list[str]
    :ivar user_role: Rôle de l'utilisateur (exemple: public, employé, administrateur).
    :type user_role: str
    :ivar pandas_agent: Agent Panda pour intégrer la manipulation de dataframe avec Gemini.
    :type pandas_agent: SimplePandasAgent
    :ivar rag_agent: Agent RAG utilisé pour la récupération et le traitement des informations.
    :type rag_agent: RAGAgentUnified
    :ivar selector_agent: Agent de sélection unifié pour les documents et les informations.
    :type selector_agent: SelectorAgentUnified
    :ivar analyzer_agent: Agent d'analyse unifié pour traiter les données complexes.
    :type analyzer_agent: AnalyzerAgentUnified
    :ivar code_agent: Agent de génération de code pour exécuter des calculs nécessaires.
    :type code_agent: CodeAgent
    :ivar synthesis_agent: Agent de synthèse pour générer des réponses finales après traitement.
    :type synthesis_agent: SynthesisAgent
    :ivar graph: Graphe ultra-simplifié représentant le flux de travail entre agents.
    :type graph: StateGraph
    """

    def __init__(self, rag_index, user_permissions: List[str] = None, user_role: str = "guest", settings=None):
        """
        Initialise une instance de Chatbot V2 Simplifié avec les agents et
        configurations nécessaires pour fournir des fonctionnalités unifiées
        et robustes. Le système inclut la gestion des permissions utilisateur
        ainsi qu'une configuration adaptative basée sur les paramètres fournis.

        Attributes:
            rag_index : Objet RAG utilisé comme index principal dans les agents
                du chatbot.
            user_permissions : Liste des permissions accordées à l'utilisateur.
                Si aucune permission n'est spécifiée, une valeur par défaut sera
                utilisée.
            user_role : Rôle de l'utilisateur, déterminant ses privilèges au sein
                du système. Le rôle par défaut est "guest".
            settings : Configuration à inclure pour le système. Si non spécifiée,
                une configuration par défaut sera générée.

        :param rag_index: Index RAG utilisé pour différentes opérations.
        :param user_permissions: Liste des permissions autorisées pour l'utilisation.
            Peut être `None`, dans ce cas une valeur par défaut sera appliquée.
        :param user_role: Rôle de l'utilisateur sous forme de chaîne de caractères,
            comme "admin", "editor", ou "guest". La valeur par défaut est "guest".
        :param settings: Configuration système optionnelle. Si non fournie, une
            configuration générée dynamiquement sera utilisée.

        """

        # Configuration existante
        self.settings = get_settings() if settings is None else settings
        self.rag = rag_index

        # Setup logging existant
        self.logger = setup_logging(self.settings)
        self.perf_logger = PerformanceLogger(self.settings)

        # Configuration Gemini existante
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        self.gemini_model = genai.GenerativeModel('gemini-2.5-flash')

        # Support des permissions utilisateur
        self.user_permissions = user_permissions or ["read_public_docs"]
        self.user_role = user_role

        # Agent pandas existant
        self.pandas_agent = SimplePandasAgent(self.gemini_model)

        # AGENTS UNIFIÉS (SIMPLES ET ROBUSTES)
        self.rag_agent = RAGAgentUnified(self.rag, self)
        self.selector_agent = SelectorAgentUnified(self.gemini_model, self)
        self.analyzer_agent = AnalyzerAgentUnified(self.gemini_model, self)
        self.code_agent = CodeAgent(self.gemini_model, self)
        self.synthesis_agent = SynthesisAgent(self.gemini_model, self)

        # Créer le graphe LangGraph ULTRA-SIMPLIFIÉ
        self.graph = self._creer_graphe_simplifie()

        print(f"Chatbot V2 Simplifié initialisé pour utilisateur {user_role} avec permissions: {user_permissions}")

    def _log(self, message: str, state: ChatbotState):
        """
        Enregistre un message dans l'historique d'état d'un chatbot et le journalise.
        Cette fonction met également à jour l'interface utilisateur via une sortie standard.

        :param message: Message à enregistrer et afficher.
        :type message: str
        :param state: Etat actuel du chatbot, contenant notamment un historique des messages.
        :type state: ChatbotState
        """
        self.logger.info(message)

        # Vérifier si 'historique' existe avant d'y accéder
        if 'historique' not in state:
            state['historique'] = []

        state['historique'].append(message)

        # Ligne pour le frontend
        print(f"PROGRESS:{message}", file=sys.stderr)

    def _log_with_permissions(self, message: str, state: ChatbotState):
        """
        Ajoute un message enrichi dans l'historique d'état et affiche une progression
        avec des autorisations indicatives en fonction du rôle de l'utilisateur.

        :param message: Message texte à enregistrer dans l'historique et à afficher.
        :type message: str
        :param state: Objet d'état du chatbot contenant, entre autres, un historique
                      des messages comme clé 'historique'.
        :type state: ChatbotState
        :return: Aucun
        :rtype: None
        """
        enriched_message = f"[{self.user_role.upper()}] {message}"
        self.logger.info(enriched_message)

        # Vérifier si 'historique' existe avant d'y accéder
        if 'historique' not in state:
            state['historique'] = []

        state['historique'].append(enriched_message)

        # Pour le frontend avec indicateur de permission
        role_indicator = {'public': '[PUBLIC]', 'employee': '[EMPLOYE]', 'admin': '[ADMIN]'}.get(self.user_role,
                                                                                                 '[USER]')
        print(f"PROGRESS:{role_indicator} {message}", file=sys.stderr)

    def _log_error(self, error: str, state: ChatbotState):
        """
        Enregistre un message d'erreur spécifique dans le journal et l'ajoute à l'historique
        contenu dans l'état du Chatbot donné. Cette méthode garantit qu'une entrée au journal
        et à l'historique est systématiquement effectuée lors de la détection d'erreurs.

        :param error: Message d'erreur à enregistrer dans le journal et à ajouter à
                      l'historique.
        :type error: str
        :param state: État courant du Chatbot contenant un éventuel historique des erreurs.
                      Si l'historique n'existe pas dans l'état, il sera initialisé avant
                      d'y ajouter le message d'erreur.
        :type state: ChatbotState
        """
        error_msg = f"ERREUR: {error}"
        self.logger.error(error_msg)

        # Vérifier si 'historique' existe avant d'y accéder
        if 'historique' not in state:
            state['historique'] = []

        state['historique'].append(error_msg)

    def _creer_graphe_simplifie(self) -> StateGraph:
        """
        Crée et compile un graphe simplifié de traitement d'état pour un chatbot.

        Ce graphe structure le flux d'exécution entre différents agents, chacun responsable
        d'une tâche spécifique comme la sélection de documents, l'analyse, ou encore la
        génération de code. Les transitions conditionnelles permettent de s'adapter à
        chaque scénario via des vérifications de disponibilité des documents et des
        calculs nécessaires, aboutissant inévitablement à une synthèse finale.

        :return: Un objet `StateGraph` compilé représentant le flux linéaire et conditionnel.
        :rtype: StateGraph

        :raises ValueError: Si des erreurs spécifiques lors de la compilation du graphe se produisent.
        """

        graph = StateGraph(ChatbotState)

        # NOEUDS PRINCIPAUX (SIMPLES)
        graph.add_node("rag_unified", self.rag_agent.execute)
        graph.add_node("selector_unified", self.selector_agent.execute)
        graph.add_node("analyzer_unified", self.analyzer_agent.execute)
        graph.add_node("generateur_code", self.code_agent.execute)
        graph.add_node("synthese", self.synthesis_agent.execute)

        # FLUX LINÉAIRE ULTRA-SIMPLE
        graph.set_entry_point("rag_unified")
        graph.add_edge("rag_unified", "selector_unified")

        # Vérification documents disponibles
        graph.add_conditional_edges(
            "selector_unified",
            self._has_documents,
            {
                "no_documents": "synthese",  # Aucun document → Synthèse directe
                "has_documents": "analyzer_unified"  # Documents disponibles → Analyse
            }
        )

        # UNE SEULE CONDITION : Calculs nécessaires ?
        graph.add_conditional_edges(
            "analyzer_unified",
            self._needs_calculations,
            {
                "calculations": "generateur_code",  # Calculs détectés → Code
                "direct": "synthese"  # Réponse directe → Synthèse
            }
        )

        # Après calculs → Synthèse
        graph.add_edge("generateur_code", "synthese")

        # Fin
        graph.add_edge("synthese", END)

        return graph.compile()

    def _has_documents(self, state: ChatbotState) -> str:
        """
        Détermine si des documents sont disponibles pour le traitement en fonction de
        l'état fourni.

        Cette méthode vérifie la présence de fichiers Excel et PDF dans l'état donné
        et retourne une chaîne indiquant la disponibilité des documents.

        :param state: L'état courant du chatbot contenant les informations sur
            les fichiers à traiter.
        :type state: ChatbotState
        :return: Une chaîne indiquant si des documents sont disponibles ("has_documents")
            ou non ("no_documents").
        :rtype: str
        """
        tableaux = state.get('tableaux_pour_upload', [])
        pdfs = state.get('pdfs_pour_upload', [])

        total_documents = len(tableaux) + len(pdfs)

        if total_documents > 0:
            self._log(f"Documents disponibles: {len(tableaux)} Excel + {len(pdfs)} PDFs", state)
            return "has_documents"
        else:
            self._log("Aucun document disponible pour traitement", state)
            return "no_documents"

    def _needs_calculations(self, state: ChatbotState) -> str:
        """
        Détermine si des calculs sont nécessaires en fonction de l'état du chatbot.

        Cette méthode vérifie une condition spécifique dans l'état pour décider si des calculs
        sont nécessaires. Si des calculs sont requis, les prérequis nécessaires sont vérifiés
        pour s'assurer qu'ils sont disponibles. En cas d'absence d'un ou plusieurs prérequis,
        une synthèse directe est choisie. Sinon, des calculs sont effectués.

        :param state: L'état courant du chatbot contenant les données nécessaires pour
                      déterminer le besoin et les prérequis des calculs.
        :type state: ChatbotState
        :return: Renvoie une chaîne de texte indiquant soit "calculations" si des calculs sont
                 nécessaires et les prérequis sont présents, soit "direct" si des calculs ne
                 sont pas requis ou si les prérequis font défaut.
        :rtype: str
        """

        besoin_calculs = state.get('besoin_calculs', False)

        if besoin_calculs:
            # Vérifier que les prérequis sont présents
            if state.get('algo_genere') and state.get('instruction_calcul') and state.get('dataframes'):
                self._log("CALCULS NÉCESSAIRES - Génération de code", state)
                return "calculations"
            else:
                # Problème avec les prérequis calculs
                self._log("ERREUR: Calculs demandés mais prérequis manquants - Synthèse directe", state)
                return "direct"
        else:
            # Réponse directe ou pas de calculs nécessaires
            self._log("PAS DE CALCULS - Synthèse directe", state)
            return "direct"

    def poser_question_id(self, question: str, session_id: str = None, username: str = None, email: str = None) -> str:
        """
        Pose une question en tenant compte des autorisations de l'utilisateur.

        Cette méthode enrobe un appel à une méthode interne en fournissant les autorisations
        de l'utilisateur pour poser une question. Elle permet de passer divers paramètres
        liés à la question et à l'utilisateur.

        :param question: La question à poser.
        :type question: str
        :param session_id: Identifiant de session, optionnel.
        :type session_id: str, optionnel
        :param username: Nom d'utilisateur, optionnel.
        :type username: str, optionnel
        :param email: Adresse email de l'utilisateur, optionnelle.
        :type email: str, optionnel
        :return: Une chaîne représentant le statut ou le résultat de la question posée.
        :rtype: str
        """
        return self.poser_question_with_permissions(question, session_id, self.user_permissions, username, email)

    def poser_question_with_permissions(self, question: str, session_id: str = None,
                                        user_permissions: List[str] = None, username: str = None,
                                        email: str = None) -> str:
        """
        Fournit une réponse enrichie à une question en utilisant les permissions
        et les informations spécifiques à l'utilisateur. Cette méthode prend en compte
        des données sensibles comme le rôle de l'utilisateur et ses permissions, et
        met en œuvre une analyse approfondie avant de générer une réponse finale.
        Elle permet également de sauvegarder les conversations dans une base de
        données si les informations d'utilisateur sont fournies.

        :param question: La question posée par l'utilisateur.
        :type question: str
        :param session_id: Identifiant de session pour suivre l'interaction.
        :type session_id: str, facultatif
        :param user_permissions: Liste des permissions utilisateur à utiliser.
            Si non spécifié, les permissions par défaut de l'utilisateur sont utilisées.
        :type user_permissions: List[str], facultatif
        :param username: Nom d'utilisateur de l'individu interactant avec le système.
        :type username: str, facultatif
        :param email: Adresse e-mail de l'utilisateur permettant de sauvegarder
            l'historique des conversations.
        :type email: str, facultatif
        :return: Une réponse enrichie basée sur la question et le contexte utilisateur.
        :rtype: str
        :raises Exception: Peut lever une exception en cas d'erreur dans le traitement
            ou la sauvegarde des données de conversation.
        """
        start_time = time.time()
        active_permissions = user_permissions or self.user_permissions

        # Validation existante
        if not question.strip():
            return "Veuillez poser une question valide."

        print(f"Question reçue pour {self.user_role}: '{question[:50]}...'", file=sys.stderr)

        # État initial COMPLET avec tous les champs nécessaires
        etat_initial = ChatbotState(
            # Champs de base
            question_utilisateur=question.strip(),
            session_id=session_id,
            user_role=self.user_role,
            user_permissions=active_permissions,
            username=username,
            email=email,
            historique=[],

            # Champs RAG
            documents_trouves=[],
            tableaux_pertinents=[],
            pdfs_pertinents=[],

            # Champs chargement
            tableaux_charges=[],
            pdfs_charges=[],
            tableaux_reference=[],

            # Champs sélection
            tableaux_pour_upload=[],
            pdfs_pour_upload=[],
            explication_selection=None,

            # Champs analyse Excel
            dataframes=[],
            reponse_analyseur_brute=None,
            besoin_calculs=False,
            instruction_calcul=None,
            algo_genere=None,
            excel_empty="",

            # Champs calculs
            code_pandas=None,
            resultat_pandas=None,
            erreur_pandas=None,
            fichiers_gemini=[],
            fichiers_csvs_local=[],
            tableau_pour_calcul=None,

            # Champs analyse PDF
            reponse_analyseur_texte_brut=None,
            reponse_finale_pdf="",
            sources_pdf=[],

            # Champs compatibilité
            documents_selectionnes=[],
            pdfs_pour_contexte=[],
            documents_excel=[],
            documents_pdf=[],

            # Résultat final
            reponse_finale="",

            processing_mode=""
        )

        try:
            # Log initial avec permissions
            self._log_with_permissions(f"Démarrage analyse avec niveau d'accès {self.user_role}", etat_initial)

            # WORKFLOW SIMPLIFIÉ
            etat_final = self.graph.invoke(etat_initial)

            # Logs de succès
            duration = time.time() - start_time
            self.perf_logger.log_request_metrics(question, duration, True)

            # Enrichir la réponse finale avec info de permissions
            reponse_base = etat_final.get('reponse_finale', "Aucune réponse générée.")
            reponse_enrichie = self._enrichir_reponse_avec_permissions(reponse_base, etat_final)

            # SAUVEGARDE AUTOMATIQUE DANS L'HISTORIQUE
            if username and email:
                try:
                    success = conversation_memory.save_conversation(
                        username=username,
                        email=email,
                        question=question.strip(),
                        reponse=reponse_enrichie,
                        session_id=session_id
                    )
                    if success:
                        self._log(f"Conversation sauvegardée pour {username}", etat_final)
                        stats = conversation_memory.get_conversation_stats(username, email)
                        self._log(f"Stats: {stats['total_conversations']} total, {stats['conversations_24h']} récentes",
                                  etat_final)
                    else:
                        self._log("Erreur sauvegarde conversation", etat_final)
                except Exception as e:
                    self._log_error(f"Erreur sauvegarde historique: {e}", etat_final)
            else:
                self._log("Username/email manquants, pas de sauvegarde historique", etat_final)

            return reponse_enrichie

        except Exception as e:
            # Gestion d'erreur
            duration = time.time() - start_time
            error_msg = f"Erreur système: {str(e)}"
            self.perf_logger.log_request_metrics(question, duration, False, error_msg)

            self.logger.error(f"Erreur critique pour {self.user_role}: {error_msg}")
            return f"ERREUR: {error_msg}. Votre niveau d'accès: {self.user_role.upper()}. Veuillez réessayer."

    def _enrichir_reponse_avec_permissions(self, reponse_base: str, etat_final: ChatbotState) -> str:
        """
        Enrichit une réponse de base avec des informations supplémentaires liées aux permissions
        de l'utilisateur et aux documents consultés durant l'échange avec le chatbot.

        La méthode ajoute un indicateur clair du rôle utilisateur (public, employé, administrateur),
        décompte les documents consultés selon leur niveau d'accès (public, interne, confidentiel),
        et inclut des métadonnées supplémentaires pour les administrateurs, comme les permissions
        actives.

        :param reponse_base: La réponse générée initialement par le chatbot
        :type reponse_base: str
        :param etat_final: L'état final contenant les informations de contexte, y compris les documents
            chargés et leurs niveaux d'accès
        :type etat_final: ChatbotState
        :return: Retourne une chaîne enrichie contenant les informations sur les permissions et les
            statistiques sur les documents consultés
        :rtype: str
        """

        # Indicateurs visuels par rôle
        role_indicators = {
            'public': '**Accès Public**',
            'employee': '**Accès Employé**',
            'admin': '**Accès Administrateur**'
        }

        indicator = role_indicators.get(self.user_role, '**Accès Limité**')

        # Compter les documents utilisés par niveau d'accès
        tableaux_utilises = etat_final.get('tableaux_charges', [])
        pdfs_utilises = etat_final.get('pdfs_charges', [])

        stats_acces = {'public': 0, 'internal': 0, 'confidential': 0}

        # Compter Excel
        for tableau in tableaux_utilises:
            if isinstance(tableau, dict):
                access_level = tableau.get('access_level', 'public')
                if access_level in stats_acces:
                    stats_acces[access_level] += 1

        # Compter PDFs
        for pdf in pdfs_utilises:
            if isinstance(pdf, dict):
                access_level = pdf.get('access_level', 'public')
                if access_level in stats_acces:
                    stats_acces[access_level] += 1

        # Construction de la réponse enrichie
        reponse_enrichie = f"{indicator}\n\n{reponse_base}"

        # Ajouter les stats d'accès si des documents ont été utilisés
        total_docs = sum(stats_acces.values())
        if total_docs > 0:
            reponse_enrichie += f"\n\n**Sources consultées :**\n"
            if stats_acces['public'] > 0:
                reponse_enrichie += f"- [PUBLIC] {stats_acces['public']} document(s) public(s)\n"
            if stats_acces['internal'] > 0:
                reponse_enrichie += f"- [INTERNE] {stats_acces['internal']} document(s) interne(s)\n"
            if stats_acces['confidential'] > 0:
                reponse_enrichie += f"- [CONFIDENTIEL] {stats_acces['confidential']} document(s) confidentiel(s)\n"

        # Info debug pour les admins
        if self.user_role == 'admin':
            permissions_safe = self.user_permissions or ["unknown_permissions"]
            if isinstance(permissions_safe, list):
                permissions_str = ', '.join(permissions_safe)
            else:
                permissions_str = str(permissions_safe)
            reponse_enrichie += f"\n**Debug Admin :** Permissions actives: {permissions_str}"

        return reponse_enrichie

    def get_user_conversation_history(self, username: str, email: str, limit: int = 10) -> dict:
        """
        Récupère l'historique des conversations d'un utilisateur dans les dernières 24 heures, ainsi que
        les statistiques et le contexte pour une IA. Si une erreur se produit, retourne des données par
        défaut avec un message d'erreur.

        :param username: Identifiant de l'utilisateur pour lequel récupérer les données
        :param email: Adresse e-mail de l'utilisateur
        :param limit: Nombre maximum de conversations à retourner (par défaut : 10)
        :type username: str
        :type email: str
        :type limit: int
        :return: Dictionnaire contenant les informations suivantes :
                 - username : Identifiant de l'utilisateur
                 - email : Adresse e-mail de l'utilisateur
                 - conversations : Liste des conversations de l'utilisateur
                 - stats : Statistiques des conversations, incluant le nombre total
                           et celui des dernières 24 heures
                 - context_for_ai : Contexte condensé des conversations pour une IA
                 - total_returned : Nombre total de conversations retournées
                 - error : Message d'erreur en cas de problème
        :rtype: dict
        """
        try:
            history = conversation_memory.get_user_history_24h(username, email, limit)
            stats = conversation_memory.get_conversation_stats(username, email)
            context = conversation_memory.format_history_for_context(username, email, limit // 2)

            return {
                "username": username,
                "email": email,
                "conversations": history,
                "stats": stats,
                "context_for_ai": context,
                "total_returned": len(history)
            }
        except Exception as e:
            self.logger.error(f"Erreur récupération historique: {e}")
            return {
                "username": username,
                "email": email,
                "conversations": [],
                "stats": {"total_conversations": 0, "conversations_24h": 0},
                "context_for_ai": "",
                "total_returned": 0,
                "error": str(e)
            }



    def poser_question(self, question: str, username: str = None, email: str = None) -> str:
        """
        Pose une question en vérifiant les permissions et les informations de l'utilisateur.

        La méthode permet de poser une question en optionnant les informations associées,
        comme le nom d'utilisateur ou l'e-mail. L'interaction sous-jacente contrôle les
        permissions et agit en conséquence pour admettre ou refuser l'opération.

        :param question: Question à poser.
        :type question: str
        :param username: Nom d'utilisateur facultatif. Si présent, il est utilisé pour
            associer la question à ce compte.
        :type username: str, optionnel
        :param email: Adresse e-mail facultative. Peut être utilisée pour contacter ou
            identifier le demandeur.
        :type email: str, optionnel
        :return: Une chaîne représentant la réponse du système ou une confirmation.
        :rtype: str
        """
        return self.poser_question_with_permissions(
            question=question,
            session_id=None,
            user_permissions=None,
            username=username,
            email=email
        )
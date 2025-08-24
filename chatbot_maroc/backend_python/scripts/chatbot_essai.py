from dotenv import load_dotenv
import os

load_dotenv()

from ..src.core.chatbot_v2_simplified import ChatbotMarocV2Simplified
from ..src.rag.indexer import RAGTableIndex


def creer_chatbot():
    """
    Créer et initialiser un chatbot personnalisé.

    Cette fonction permet d'initialiser un chatbot en configurant son index RAG
    et en récupérant une clé API sécurisée. Elle change également le répertoire
    de travail courant pour correspondre au dossier de projet spécifié dans la
    variable d'environnement `PROJECT_DIR`.

    :raises EnvironmentError: Si les variables d'environnement nécessaires,
        telles que `PROJECT_DIR` ou `GEMINI_API_KEY`, ne sont pas configurées,
        ou si les chemins associés ne sont pas valides.
    :raises Exception: Si toute autre erreur se produit pendant le processus
        d'initialisation du chatbot, comme l'échec de création de l'index RAG
        ou l'instanciation du chatbot.

    :return: Une instance du chatbot initialisé.
    :rtype: ChatbotMarocV2Simplified
    """
    dir_dossier = os.getenv("PROJECT_DIR")
    os.chdir(dir_dossier)

    chroma_db_path = "./chroma_db"

    # Initialiser le RAG avec le chemin absolu
    rag_index = RAGTableIndex(db_path=str(chroma_db_path))

    # Récupérer la clé API de manière sécurisée
    gemini_key = os.getenv("GEMINI_API_KEY")

    # Créer le chatbot
    chatbot = ChatbotMarocV2Simplified(rag_index, gemini_key)

    print(f"Chatbot initialisé")
    return chatbot


def tester_chatbot():
    """Fonction de test avec questions variées"""

    print("CHATBOT MAROC")
    print("=" * 60)

    # Créer le chatbot
    chatbot = creer_chatbot()

    # Questions de test pour valider les améliorations
    questions_test = [
        # Question simple (devrait utiliser workflow direct)
        "Qu'est-ce qu'un ingénieur selon les définitions disponibles ?",

        # Question de calcul (devrait utiliser workflow complet)
        "Quel est le nombre total de diplômées féminines en 2021 ?",

        # Question de comparaison (devrait utiliser workflow complet)
        "Quelle filière d'ingénierie a le pourcentage de femmes le plus élevé en 2021 ?",

        # Question complexe multi-tableaux
        "En 2021, quelle ville a le pourcentage de femmes étudiante, en ingénierie, le plus élevé ? Dans la région de cette ville, quelle est la proportion de la population utilisant 'Arabe, Francais et Anglais' ?"
    ]

    for i, question in enumerate(questions_test, 1):
        print(f"\n[TEST {i}/{len(questions_test)}]")
        print(f"Question: {question}")
        print("-" * 60)

        # Poser la question et mesurer le temps
        import time
        debut = time.time()
        reponse = chatbot.poser_question_id(question,"session123","test", "test@gmail.com")
        duree = time.time() - debut

        print(f"Réponse: {reponse}")
        print(f"Temps de traitement: {duree:.2f}s")
        print("=" * 60)


def test_question_unique():
    """Test d'une seule question spécifique"""

    print("TEST QUESTION UNIQUE")
    print("=" * 40)

    chatbot = creer_chatbot()

    question = "Quelle filière d'ingénierie a le pourcentage de femmes le plus élevé en 2021 ?"
    print(f"Question: {question}")
    print("-" * 40)

    reponse = chatbot.poser_question(question)
    print(f"Réponse: {reponse}")


if __name__ == "__main__":
    print("DÉMARRAGE DU SYSTÈME")
    print()

    # Choisir le type de test
    mode_test = "unique"  # "complet" ou "unique"

    if mode_test == "complet":
        tester_chatbot()
    else:
        test_question_unique()
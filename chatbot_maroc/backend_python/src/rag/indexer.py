import json
import chromadb
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any
import uuid
from datetime import datetime
from .description import traiter_index_complet
import os


class RAGTableIndex:
    """
    Classe permettant de gérer un index RAG pour les tableaux.

    Cette classe assure la gestion des opérations d'indexation, la génération
    d'embeddings pour la recherche, ainsi que la manipulation des métadonnées
    des tableaux pour des analyses et recherches avancées. Elle repose sur un
    modèle d'embeddings basé sur `sentence-transformers` et un stockage dans
    une base de données persistante gérée par ChromaDB.

    :ivar db_path: Chemin vers la base de données persistante ChromaDB.
    :type db_path: str
    :ivar model_name: Nom du modèle pré-entraîné sentence-transformers utilisé.
    :type model_name: str
    :ivar embedding_model: Instance du modèle d'embeddings chargé.
    :type embedding_model: SentenceTransformer
    :ivar client: Instance du client ChromaDB configuré.
    :type client: chromadb.PersistentClient
    :ivar collection: Collection spécifique pour stocker les tableaux indexés.
    :type collection: chromadb.Collection
    """
    def __init__(self, db_path: str = "./chroma_db", model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        """
        Initialise une instance pour gérer les embeddings et la base de données persistante avec ChromaDB.

        L'initialisation implique le chargement d'un modèle de calcul d'embeddings à utiliser
        pour le traitement des données, ainsi que la connexion ou la création d'une collection
        de la base de données persistante.

        :param db_path: Chemin vers la base de données persistante Chroma (par défaut "./chroma_db")
        :type db_path: str
        :param model_name: Nom ou chemin du modèle d'embeddings à charger (par défaut
            "sentence-transformers/all-MiniLM-L6-v2")
        :type model_name: str
        """
        self.db_path = db_path
        self.model_name = model_name

        # Initialiser le modèle d'embeddings
        print(f"Chargement du modèle d'embeddings: {model_name}")
        self.embedding_model = SentenceTransformer(model_name)
        print("Modèle d'embeddings chargé!")

        # Initialiser ChromaDB
        self.client = chromadb.PersistentClient(path=db_path)

        # Collection pour nos tableaux
        collection_name = "tableaux_maroc"
        try:
            self.collection = self.client.get_collection(collection_name)
            print(f"Collection existante '{collection_name}' chargée")
            print(f"Chemin de la base Chroma : {db_path}")
        except:
            self.collection = self.client.create_collection(collection_name)
            print(f"Nouvelle collection '{collection_name}' créée")

    def generer_embeddings(self, descriptions: List[str]) -> List[List[float]]:
        """
        Génère des représentations numériques (embeddings) pour une liste de descriptions.
        Ces embeddings sont issus du modèle d'encodage défini dans l'objet et permettent
        de représenter le contenu textuel dans un espace vectoriel.

        :param descriptions: Une liste de chaînes de caractères pour lesquelles les embeddings
            doivent être générés.
        :type descriptions: List[str]
        :return: Une liste de listes de flottants représentant les embeddings générés pour
            chaque description donnée.
        :rtype: List[List[float]]
        """
        print(f"Génération des embeddings pour {len(descriptions)} descriptions...")
        embeddings = self.embedding_model.encode(descriptions, convert_to_tensor=False)
        print("Embeddings générés!")
        return embeddings.tolist()

    def _determiner_niveau_acces_par_dossier(self, metadata: Dict) -> str:
        """
        Détermine le niveau d'accès d'un dossier en fonction des métadonnées fournies.

        Le niveau d'accès est déterminé selon une logique de priorité basée sur plusieurs
        champs des métadonnées, à savoir 'access_level', 'access_indicator',
        'document_type', et 'source_directory'. Si aucun de ces champs n'est pertinent,
        une analyse de chaînes dans les chemins et titres associés au fichier est effectuée.

        :param metadata: Les métadonnées du dossier. Ces métadonnées peuvent inclure
                         les informations suivantes :
                         - 'access_level': Niveau d'accès préexistant (str).
                         - 'access_indicator': Indicateur textuel d'accès (str).
                         - 'document_type': Type de document (str).
                         - 'source_directory': Répertoire source (str).
                         - 'fichier_source': Chemin vers le fichier source (str).
                         - 'tableau_path': Chemin vers le tableau associé (str).
                         - 'titre_contextuel': Titre ou description contextuelle (str).
        :type metadata: Dict
        :return: Le niveau d'accès déterminé, parmi 'public', 'internal' ou 'confidential'.
        :rtype: str
        """


        access_level_existant = metadata.get('access_level')
        if access_level_existant:
            # Normaliser la valeur
            access_level = str(access_level_existant).lower().strip()
            if access_level in ['public', 'internal', 'confidential']:
                print(f"DEBUG indexer: Utilisation access_level existant: {access_level}")
                return access_level

        access_indicator = metadata.get('access_indicator', '')
        if access_indicator:
            access_indicator_lower = str(access_indicator).lower()
            if 'confidentiel' in access_indicator_lower or 'confidential' in access_indicator_lower:
                print(f"DEBUG indexer: Détecté access_indicator confidentiel: {access_indicator}")
                return 'confidential'
            elif 'interne' in access_indicator_lower or 'internal' in access_indicator_lower:
                print(f"DEBUG indexer: Détecté access_indicator interne: {access_indicator}")
                return 'internal'
            elif 'public' in access_indicator_lower:
                print(f"DEBUG indexer: Détecté access_indicator public: {access_indicator}")
                return 'public'

        document_type = metadata.get('document_type', '')
        if document_type:
            document_type_lower = str(document_type).lower()
            if 'admin' in document_type_lower:
                print(f"DEBUG indexer: Détecté document_type admin: {document_type}")
                return 'confidential'
            elif 'salarie' in document_type_lower or 'internal' in document_type_lower:
                print(f"DEBUG indexer: Détecté document_type interne: {document_type}")
                return 'internal'
            elif 'public' in document_type_lower:
                print(f"DEBUG indexer: Détecté document_type public: {document_type}")
                return 'public'

        source_directory = metadata.get('source_directory', '')
        if source_directory:
            source_dir_lower = str(source_directory).lower()
            if 'admin' in source_dir_lower:
                print(f"DEBUG indexer: Détecté source_directory admin: {source_directory}")
                return 'confidential'
            elif 'salarie' in source_dir_lower or 'employee' in source_dir_lower:
                print(f"DEBUG indexer: Détecté source_directory salarie: {source_directory}")
                return 'internal'
            elif 'public' in source_dir_lower:
                print(f"DEBUG indexer: Détecté source_directory public: {source_directory}")
                return 'public'

        print(f"DEBUG indexer: Aucun champ d'accès trouvé, fallback vers analyse des chemins")

        fichier_source = str(metadata.get('fichier_source', '')).lower()
        tableau_path = str(metadata.get('tableau_path', '')).lower()
        titre_contextuel = str(metadata.get('titre_contextuel', '')).lower()

        chemin_complet = f"{fichier_source} {tableau_path} {titre_contextuel}"

        # Mots-clés de fallback
        if any(mot in chemin_complet for mot in ['admin', 'confidentiel', 'secret', 'direction']):
            print(f"DEBUG indexer: Fallback - détecté admin dans chemin")
            return 'confidential'
        elif any(mot in chemin_complet for mot in ['salarie', 'employe', 'interne', 'personnel']):
            print(f"DEBUG indexer: Fallback - détecté interne dans chemin")
            return 'internal'
        else:
            print(f"DEBUG indexer: Fallback - aucun indicateur, défaut public")
            return 'public'

    def indexer_tableaux(self, index_path: str, tableaux_dir: str, force_reindex: bool = False):
        """
        Indexe les descriptions de tableaux dans une base de données ChromaDB. Cette méthode permet de gérer
        l'indexation de tableaux, de leurs métadonnées, et des descriptions textuelles associées. L'option
        de réindexation force la suppression et la recréation de l'index existant.

        :param index_path: Le chemin vers le fichier ou dossier contenant le fichier d'index.
        :type index_path: str
        :param tableaux_dir: Le chemin vers le répertoire contenant les tableaux à traiter.
        :type tableaux_dir: str
        :param force_reindex: Indique si l'index existant doit être supprimé et recréé. Par défaut `False`.
        :type force_reindex: bool
        :return: Aucun retour.
        :rtype: None
        """
        if force_reindex:
            print("Suppression de l'index existant...")
            try:
                self.client.delete_collection(self.collection.name)
                self.collection = self.client.create_collection(self.collection.name)
            except Exception as e:
                print(f"Erreur lors de la suppression: {e}")

        # Vérifier si déjà indexé
        existing_count = self.collection.count()
        if existing_count > 0 and not force_reindex:
            print(f"Index déjà créé avec {existing_count} tableaux. Utilisez force_reindex=True pour recréer.")
            return

        print("Traitement des descriptions des tableaux...")

        # Générer les descriptions
        descriptions_data = self.traiter_index_complets(index_path, tableaux_dir)

        if not descriptions_data:
            print("Aucun tableau traité. Vérifiez vos chemins.")
            return

        # Extraire les descriptions textuelles
        descriptions = [item['description'] for item in descriptions_data]

        # Générer les embeddings
        embeddings = self.generer_embeddings(descriptions)

        # Préparer les données pour ChromaDB
        ids = []
        metadatas = []
        documents = []

        for i, item in enumerate(descriptions_data):
            # ID unique
            ids.append(f"tableau_{i}_{uuid.uuid4().hex[:8]}")

            access_level = self._determiner_niveau_acces_par_dossier(item['metadata'])

            # Nettoyer les métadonnées pour ChromaDB
            # ChromaDB n'accepte que str, int, float, bool, None
            metadata_clean = {}

            for key, value in item['metadata'].items():
                if value is None:
                    metadata_clean[key] = None
                elif isinstance(value, (str, int, float, bool)):
                    metadata_clean[key] = value
                elif isinstance(value, list):
                    # Convertir les listes en strings (séparées par virgules)
                    metadata_clean[key] = ', '.join(str(v) for v in value) if value else ""
                else:
                    # Convertir tout le reste en string
                    metadata_clean[key] = str(value)

            # Métadonnées enrichies avec niveau d'accès
            metadata = {
                **metadata_clean,  # Métadonnées nettoyées
                'nb_lignes': item['stats'].get('nb_lignes', 0),
                'nb_colonnes': item['stats'].get('nb_colonnes', 0),
                'headers_str': ', '.join(item['stats'].get('headers', [])),
                'types_colonnes_str': str(item['stats'].get('types_colonnes', {})),
                'timestamp': datetime.now().isoformat(),
                'description_length': len(item['description']),
                'access_level': access_level
            }
            metadatas.append(metadata)

            # Document = description complète
            documents.append(item['description'])

        # Ajouter à ChromaDB
        print(f"Ajout de {len(descriptions_data)} tableaux à ChromaDB...")
        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas
        )

        print(f"Index créé avec succès! {len(descriptions_data)} tableaux indexés.")
        print(f"Base de données sauvegardée dans: {self.db_path}")

    def rechercher_tableaux(self, query: str, user_role: str, n_results: int = 10) -> Dict[str, Any]:
        """
        Permet d'effectuer une recherche en utilisant un modèle d'embedding pour retrouver des tableaux
        correspondant à une requête donnée dans une base de données spécifique (ChromaDB). La méthode
        retourne une structure contenant les informations des tableaux trouvés ainsi que des
        métadonnées associées à ces tableaux.

        :param query: La requête de recherche sous forme de chaîne de caractères.
        :type query: str
        :param user_role: Le rôle utilisateur, utilisé pour déterminer les niveaux d'accès.
        :type user_role: str
        :param n_results: Le nombre maximum de résultats à retourner. Par défaut, égale à 10.
        :type n_results: int
        :return: Un dictionnaire contenant :
            - query: La requête de recherche utilisée.
            - nb_resultats: Le nombre total de résultats retournés.
            - tableaux: Une liste de dictionnaires décrivant les tableaux trouvés, y compris leurs
              attributs tels que titre, source, feuille, nombre de lignes, colonnes,
              chemin d'accès et description.
        :rtype: Dict[str, Any]
        """
        print(f"Recherche: '{query}'")

        # Générer embedding de la query
        query_embedding = self.embedding_model.encode([query], convert_to_tensor=False)

        # Rechercher dans ChromaDB
        results = self.collection.query(
            query_embeddings=query_embedding.tolist(),
            n_results=n_results,
            include=['documents', 'metadatas', 'distances']
        )

        formatted_results = {
            'query': query,
            'nb_resultats': len(results['ids'][0]),
            'tableaux': []
        }

        for i in range(len(results['ids'][0])):
            metadata = results['metadatas'][0][i]

            tableau = {
                'id': results['ids'][0][i],
                'titre': metadata.get('titre_contextuel', 'N/A'),
                'source': metadata.get('fichier_source', 'N/A'),
                'feuille': metadata.get('nom_feuille', 'N/A'),
                'nb_lignes': metadata.get('nb_lignes', 0),
                'colonnes': self.extraire_colonnes_de_description(results['documents'][0][i]),
                'tableau_path': metadata.get('tableau_path', ''),
                'description': results['documents'][0][i],
                'access_level': metadata.get('access_level', 'public')
            }

            if "pdf" in results['ids'][0][i]:
                tableau["tableau_path"] = metadata.get('pdf_path', '')

            formatted_results['tableaux'].append(tableau)

        return formatted_results

    def afficher_resultats(self, results: Dict[str, Any]):
        """
        Affiche les résultats d'une recherche sous forme lisible.

        Cette méthode affiche une représentation textuelle des résultats
        fournis pour une requête donnée. Elle affiche des informations
        détaillées sur chaque tableau trouvé, y compris son titre, sa
        source, le nombre de lignes, le niveau d'accès, les colonnes et
        le chemin d'accès.

        :param results: Contient les informations sur les résultats de la requête.
            - query (str): Le terme de la requête.
            - nb_resultats (int): Nombre total de tableaux trouvés.
            - tableaux (List[Dict]): Liste des informations relatives
              aux tableaux trouvés. Chaque tableau contient :
                - titre (str): Titre du tableau.
                - source (str): Source du tableau.
                - feuille (str): Nom de la feuille correspondante.
                - nb_lignes (int): Nombre de lignes contenues.
                - access_level (Optional[str]): Niveau d'accès (public
                  par défaut si absent).
                - colonnes (List[str]): Liste des noms des colonnes
                  (limitées à 5 colonnes en affichage).
                - tableau_path (str): Chemin vers le fichier du tableau.

        :return: Cette méthode ne retourne aucune valeur.
        """
        print(f"\nRésultats pour: '{results['query']}'")
        print(f"{results['nb_resultats']} tableaux trouvés\n")

        for i, tableau in enumerate(results['tableaux'], 1):
            print(f"{i}. {tableau['titre']}")
            print(f"   Source: {tableau['source']} -> {tableau['feuille']}")
            print(f"   Données: {tableau['nb_lignes']} lignes")
            print(f"   Niveau d'accès: {tableau.get('access_level', 'public')}")
            print(f"   Colonnes: {', '.join(tableau['colonnes'][:5])}")
            if len(tableau['colonnes']) > 5:
                print(f"    ... et {len(tableau['colonnes']) - 5} autres")
            print(f"   Chemin: {tableau['tableau_path']}")
            print()

    def get_tableau_data(self, tableau_path: str) -> Dict:
        """
        Lit et charge les données d'un fichier JSON à partir du chemin spécifié.

        Cette fonction permet de lire un fichier JSON depuis un chemin donné et renvoie
        les données contenues dans ce fichier sous forme de dictionnaire. En cas d'erreur
        lors de l'ouverture ou du traitement du fichier, elle affiche un message
        d'erreur et renvoie un dictionnaire vide.

        :param tableau_path: Chemin d'accès complet au fichier JSON à charger.
        :type tableau_path: str
        :return: Dictionnaire contenant les données extraites du fichier JSON.
          Retourne un dictionnaire vide en cas d'échec.
        :rtype: Dict
        :raises FileNotFoundError: Si le fichier spécifié est introuvable.
        :raises JSONDecodeError: Si le fichier n'est pas un fichier JSON valide.
        """
        try:
            with open(tableau_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Erreur lors du chargement de {tableau_path}: {e}")
            return {}

    def stats_index(self):
        """
        Affiche les statistiques de l'index, y compris le nombre de tableaux indexés,
        les informations sur la base de données et le modèle d'embeddings, ainsi qu'un
        échantillon de métadonnées si disponible.

        :return: Aucune valeur de retour.
        """
        count = self.collection.count()
        print(f"Statistiques de l'index:")
        print(f"   - Nombre de tableaux indexés: {count}")
        print(f"   - Base de données: {self.db_path}")
        print(f"   - Modèle d'embeddings: {self.model_name}")

        if count > 0:
            # Échantillon de métadonnées
            sample = self.collection.peek(limit=3)
            print(f"   - Exemple de sources: ")
            for meta in sample['metadatas']:
                access_level = meta.get('access_level', 'N/A')
                print(
                    f"     - {meta.get('fichier_source', 'N/A')} -> {meta.get('nom_feuille', 'N/A')} [Niveau: {access_level}]")

    def traiter_index_complets(self, index_path: str, tableaux_dir: str) -> List[Dict]:
        """
        Traite les indexes complets en prenant un chemin d'index et un répertoire
        de tableaux, et retourne une liste de dictionnaires contenant les données
        traitées.

        :param index_path: Chemin du fichier d'index à traiter.
        :type index_path: str
        :param tableaux_dir: Répertoire contenant les tableaux nécessaires pour
        traiter l'index.
        :type tableaux_dir: str
        :return: Une liste de dictionnaires contenant les données traitées à
        partir de l'index complet.
        :rtype: List[Dict]
        """
        return traiter_index_complet(index_path, tableaux_dir)

    def extraire_colonnes_de_description(self, description: str) -> List[str]:
        """
        Analyse et extrait les colonnes listées dans une description textuelle.

        Cette méthode analyse un texte de type description, identifie une éventuelle ligne
        contenant des colonnes sous le format "COLONNES:", et retourne une liste des
        colonnes spécifiées, après suppression des espaces superflus.

        :param description: La description textuelle contenant potentiellement une
            liste de colonnes à extraire, sous le format "COLONNES: colonne1, colonne2, ...".
        :type description: str
        :return: Une liste de chaînes de caractères correspondant aux noms des colonnes
            extraites. Si aucune ligne contenant "COLONNES:" n'est trouvée, la méthode
            retourne une liste vide.
        :rtype: List[str]
        """
        lines = description.split('\n')
        for line in lines:
            if line.startswith('COLONNES:'):
                colonnes_str = line.replace('COLONNES:', '').strip()
                return [col.strip() for col in colonnes_str.split(',') if col.strip()]
        return []


# Exemple d'utilisation complète
def demo_rag_pipeline():
    """
    Exécute une démonstration de pipeline de recherche assisté par un récupérateur d'information
    (RAG - Retrieval-Augmented Generation). Ce programme commence par charger le
    répertoire du projet via une variable d'environnement, puis utilise le module RAG
    pour afficher des statistiques et démontrer des recherches sur des tableaux de données.

    :param dir_dossier: Le répertoire principal du projet défini par la variable d'environnement
        "PROJECT_DIR".
    :type dir_dossier: str

    :param queries: Liste des requêtes de recherche utilisées pour explorer la base de données.
    :type queries: List[str]

    :return: Cette fonction ne retourne aucune valeur, elle affiche directement les résultats
        des tests de recherche dans la console.
    """
    dir_dossier = os.getenv("PROJECT_DIR")
    os.chdir(dir_dossier)

    # Statistiques
    rag.stats_index()

    # Exemples de recherches
    queries = [
        "Quelles sont les 5 spécialités avec le plus de diplômés ?",
    ]

    for query in queries:
        results = rag.rechercher_tableaux(query, "admin", n_results=3)
        print("DEBUG premier résultat:")
        print("- headers_str:", results['tableaux'][0].get('titre'))
        print("- tableaux:", results['tableaux'][0])
        rag.afficher_resultats(results)
        print("=" * 80)


if __name__ == "__main__":
    # Test simple
    rag = RAGTableIndex()
    rag.stats_index()
    # Pour ré-indexer:
    rag.indexer_tableaux("output/index.json", "output", force_reindex=True)
    demo_rag_pipeline()
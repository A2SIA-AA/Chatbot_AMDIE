import json
import chromadb
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any
import uuid
from datetime import datetime
from .description import traiter_index_complet
import os


class RAGTableIndex:
    def __init__(self, db_path: str = "./chroma_db", model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        """
        Initialise l'index RAG pour les tableaux

        Args:
            db_path: Chemin vers la base ChromaDB
            model_name: Modèle sentence-transformers à utiliser
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
        Génère les embeddings pour une liste de descriptions
        """
        print(f"Génération des embeddings pour {len(descriptions)} descriptions...")
        embeddings = self.embedding_model.encode(descriptions, convert_to_tensor=False)
        print("Embeddings générés!")
        return embeddings.tolist()

    def _determiner_niveau_acces_par_dossier(self, metadata: Dict) -> str:
        """
        Utilise l'access_level déjà présent dans le JSON
        Si absent, fait la classification automatique en fallback
        """

        # PRIORITÉ 1: Utiliser l'access_level déjà dans les métadonnées (depuis le JSON)
        access_level_existant = metadata.get('access_level')
        if access_level_existant:
            # Normaliser la valeur
            access_level = str(access_level_existant).lower().strip()
            if access_level in ['public', 'internal', 'confidential']:
                print(f"DEBUG indexer: Utilisation access_level existant: {access_level}")
                return access_level

        # PRIORITÉ 2: Utiliser l'indicateur d'accès si présent
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

        # PRIORITÉ 3: Utiliser le document_type si présent
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

        # PRIORITÉ 4: Utiliser le source_directory si présent
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
        Indexe tous les tableaux dans ChromaDB

        MODIFICATION: Ajoute maintenant les niveaux d'accès basés sur les dossiers

        Args:
            index_path: Chemin vers index.json
            tableaux_dir: Dossier contenant les tableaux JSON
            force_reindex: Si True, supprime et recrée l'index
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
        Recherche sémantique dans les tableaux

        CORRECTION: Suppression du filtrage ici - sera fait dans rag_agent.py
        (Cause de l'erreur NoneType was not iterable)

        Args:
            query: Question ou terme de recherche
            user_role: Rôle utilisateur (pour logs uniquement)
            n_results: Nombre de résultats à retourner

        Returns:
            Dictionnaire avec résultats et métadonnées
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

        # Formatter les résultats sans filtrage par rôle
        # Le filtrage sera fait dans rag_agent.py pour éviter l'erreur NoneType
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
                # IMPORTANT: Inclure le niveau d'accès pour le filtrage JWT
                'access_level': metadata.get('access_level', 'public')
            }

            if "pdf" in results['ids'][0][i]:
                tableau["tableau_path"] = metadata.get('pdf_path', '')

            formatted_results['tableaux'].append(tableau)

        return formatted_results

    def afficher_resultats(self, results: Dict[str, Any]):
        """
        Affiche les résultats de recherche de manière lisible
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
        Récupère les données complètes d'un tableau
        """
        try:
            with open(tableau_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Erreur lors du chargement de {tableau_path}: {e}")
            return {}

    def stats_index(self):
        """
        Affiche les statistiques de l'index
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
        """Utilise la fonction du module descriptions"""
        return traiter_index_complet(index_path, tableaux_dir)

    def extraire_colonnes_de_description(self, description: str) -> List[str]:
        lines = description.split('\n')
        for line in lines:
            if line.startswith('COLONNES:'):
                colonnes_str = line.replace('COLONNES:', '').strip()
                return [col.strip() for col in colonnes_str.split(',') if col.strip()]
        return []


# Exemple d'utilisation complète
def demo_rag_pipeline():
    """
    Démonstration complète du pipeline RAG
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
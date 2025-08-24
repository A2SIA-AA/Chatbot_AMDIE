import os
import json
from pathlib import Path
from google import genai
import chromadb
from sentence_transformers import SentenceTransformer
import uuid
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()


class PDFToChroma:
    """
    Cette classe est conçue pour traiter les documents PDF afin de déterminer leur
    niveau d'accès, générer des résumés à l'aide d'une API Gemini et les ajouter à
    une base de données existante sous forme de vecteurs d'embedding.

    La classe facilite également la gestion des contenus PDF au sein d'une
    collection ChromaDB, tout en créant des fichiers JSON structurés pour chaque document.

    :ivar client: Instance du client utilisé pour communiquer avec l'API Gemini.
    :type client: genai.Client
    :ivar chroma_client: Instance du client persistant pour accéder à ChromaDB.
    :type chroma_client: chromadb.PersistentClient
    :ivar collection: Collection ChromaDB utilisée pour enregistrer les données liées aux documents PDF.
    :type collection: chromadb.collection.Collection
    :ivar embedding_model: Modèle utilisé pour générer des embeddings de texte basés sur le contenu des documents.
    :type embedding_model: SentenceTransformer
    """
    def __init__(self):
        """
        Cette classe configure et initialise les composants nécessaires pour un chatbot.
        Elle est responsable de la configuration du client Gemini, de l'accès à ChromaDB,
        et de l'initialisation du modèle d'embeddings de phrases.

        Attributs
        ---------
        client : genai.Client
            Un client configuré pour interagir avec le service Gemini.
        chroma_client : chromadb.PersistentClient
            Client configuré pour l'accès à une base ChromaDB persistante.
        collection : chromadb.Collection
            Collection accessible dans ChromaDB contenant les données existantes.
        embedding_model : SentenceTransformer
            Modèle utilisé pour générer des embeddings à partir de phrases.
        """
        os.chdir("/home/aissa/Bureau/Projet_Chatbot/Chatbot_AMDIE/chatbot_maroc/backend_python")
        # Configuration Gemini
        self.client = genai.Client()

        # Configuration ChromaDB - collection existante
        db_path = os.getenv("RAG_DB_PATH")
        self.chroma_client = chromadb.PersistentClient(path=db_path)
        self.collection = self.chroma_client.get_collection("tableaux_maroc")

        # Modèle d'embeddings
        self.embedding_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

        print(f"Collection tableaux_maroc: {self.collection.count()} documents existants")

    def _determiner_niveau_acces_pdf(self, pdf_path: Path) -> str:
        """
        Détermine le niveau d'accès pour un fichier PDF en fonction de son chemin, de ses dossiers
        parents et de son nom.

        La fonction analyse plusieurs aspects du chemin et des noms associés pour extraire des
        informations permettant de classifier le fichier en niveaux d'accès. Les niveaux possibles
        sont "confidential", "internal", ou "public". Les priorités d'analyse incluent le nom du
        dossier parent, le chemin complet, et le nom du fichier lui-même.

        :param pdf_path: Chemin du fichier PDF devant être analysé
        :type pdf_path: Path
        :return: Niveau d'accès déterminé pour le fichier ("confidential", "internal", ou "public")
        :rtype: str
        """
        # Obtenir le chemin complet en minuscules pour l'analyse
        chemin_complet = str(pdf_path).lower()
        dossier_parent = str(pdf_path.parent).lower()

        print(f"DEBUG PDF: Analyse du chemin: {chemin_complet}")
        print(f"DEBUG PDF: Dossier parent: {dossier_parent}")

        nom_dossier = pdf_path.parent.name.lower()
        print(f"DEBUG PDF: Nom dossier direct: {nom_dossier}")

        if nom_dossier in ['admin', 'administratif', 'confidentiel', 'secret', 'direction']:
            print(f"DEBUG PDF: Détecté niveau CONFIDENTIEL via nom dossier: {nom_dossier}")
            return 'confidential'
        elif nom_dossier in ['salarie', 'employe', 'interne', 'personnel', 'internal', 'employee']:
            print(f"DEBUG PDF: Détecté niveau INTERNE via nom dossier: {nom_dossier}")
            return 'internal'
        elif nom_dossier in ['public', 'publique']:
            print(f"DEBUG PDF: Détecté niveau PUBLIC via nom dossier: {nom_dossier}")
            return 'public'

        if any(mot in chemin_complet for mot in ['admin', 'confidentiel', 'secret', 'direction']):
            print(f"DEBUG PDF: Détecté niveau CONFIDENTIEL via chemin complet")
            return 'confidential'
        elif any(mot in chemin_complet for mot in
                 ['salarie', 'employe', 'interne', 'personnel', 'internal', 'employee']):
            print(f"DEBUG PDF: Détecté niveau INTERNE via chemin complet")
            return 'internal'
        elif any(mot in chemin_complet for mot in ['public', 'publique']):
            print(f"DEBUG PDF: Détecté niveau PUBLIC via chemin complet")
            return 'public'

        nom_fichier = pdf_path.name.lower()
        if any(mot in nom_fichier for mot in ['admin', 'confidentiel', 'secret', 'direction']):
            print(f"DEBUG PDF: Détecté niveau CONFIDENTIEL via nom fichier")
            return 'confidential'
        elif any(mot in nom_fichier for mot in ['salarie', 'employe', 'interne', 'personnel']):
            print(f"DEBUG PDF: Détecté niveau INTERNE via nom fichier")
            return 'internal'

        # Par défaut: public
        print(f"DEBUG PDF: Aucun indicateur trouvé, niveau par défaut: PUBLIC")
        return 'public'

    def trouver_pdfs(self, dossier="data"):
        """
        Analyse un dossier donné et recherche récursivement tous les fichiers PDF
        dans celui-ci et ses sous-dossiers. La fonction détermine également un
        niveau d'accès pour chaque fichier PDF trouvé. Les résultats incluent le
        chemin complet du fichier et son niveau d'accès.

        :param dossier: Le chemin du dossier dans lequel rechercher les fichiers PDF.
        :type dossier: str, optionnel
        :return: Une liste de tuples contenant pour chaque fichier PDF trouvé son chemin
                 et son niveau d'accès (sous forme de chaîne).
        :rtype: list[tuple[Path, str]]
        """
        dossier_path = Path(dossier)
        pdfs_avec_acces = []

        print(f"Recherche de PDFs dans {dossier} et ses sous-dossiers...")

        # Parcourir récursivement tous les dossiers
        for racine, repertoires, fichiers in os.walk(dossier_path):
            racine_path = Path(racine)

            for fichier in fichiers:
                if fichier.lower().endswith('.pdf'):
                    pdf_path = racine_path / fichier
                    access_level = self._determiner_niveau_acces_pdf(pdf_path)

                    pdfs_avec_acces.append((pdf_path, access_level))
                    print(f"  Trouvé: {pdf_path.name} -> Niveau: {access_level}")

        print(f"Total PDFs trouvés: {len(pdfs_avec_acces)}")

        # Statistiques par niveau
        stats_niveaux = {}
        for _, niveau in pdfs_avec_acces:
            stats_niveaux[niveau] = stats_niveaux.get(niveau, 0) + 1

        print(f"Répartition par niveau d'accès:")
        for niveau, count in stats_niveaux.items():
            print(f"  - {niveau}: {count} PDF(s)")

        return pdfs_avec_acces

    def traiter_pdf_avec_gemini(self, pdf_path):
        """
        Traite un document PDF en utilisant l'API Gemini pour en générer un résumé en français. Cette
        fonction télécharge un fichier PDF, utilise le modèle Gemini pour générer un texte résumé en
        fonction d'une invite, et supprime ensuite le fichier distant pour optimiser l'espace.

        :param pdf_path: Le chemin du fichier PDF à traiter.
        :type pdf_path: str
        :return: Le résumé du document PDF, ou None si une erreur s'est produite ou que la génération
                 ne contient pas de texte.
        :rtype: str, optional
        :raises Exception: Exception générique si une erreur survient lors du processus.
        """
        print(f"Traitement: {pdf_path.name}")

        try:
            # Upload du PDF vers Gemini File API
            sample_file = self.client.files.upload(file=pdf_path)
            print(f"  Uploaded: {sample_file.name}")

            # Demander résumé
            prompt = "Résume ce document PDF, en français, en identifiant le titre, le type de document, le sujet principal et un résumé en 4-5 phrases."

            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[sample_file, prompt]
            )

            # Supprimer le fichier uploadé pour économiser l'espace
            self.client.files.delete(name=sample_file.name)
            print(f"  Fichier supprimé: {sample_file.name}")

            if response and response.text:
                return response.text
            else:
                return None

        except Exception as e:
            print(f"  Erreur: {str(e)}")
            return None

    def creer_json_resume(self, pdf_path, access_level, resume_gemini):
        """
        Génère un fichier JSON résumant les informations d'un fichier PDF donné, en incluant
        des métadonnées telles que le chemin d'accès, la taille du fichier, le niveau d'accès
        et un résumé fourni.

        :param pdf_path: Chemin du fichier PDF source. Doit être de type Path.
        :type pdf_path: Path
        :param access_level: Niveau d'accès associé au PDF.
        :type access_level: str
        :param resume_gemini: Résumé du document donné sous forme de chaîne de caractères.
        :type resume_gemini: str
        :return: Dictionnaire contenant les métadonnées et informations générées pour le JSON.
        :rtype: dict
        """
        # Sauvegarder le JSON
        output_path = Path("output")
        output_path.mkdir(exist_ok=True)

        json_file = output_path / f"pdf_{pdf_path.stem}.json"

        json_data = {
            "resume_gemini": resume_gemini,
            "fichier_source": pdf_path.name,
            "type_document": "pdf",
            "taille_fichier": pdf_path.stat().st_size,
            "titre_contextuel": str(pdf_path.parent),
            "pdf_path": str(pdf_path),
            "source_directory": str(pdf_path.parent),
            "access_level": access_level,
            "document_type": f"pdf_{access_level}",
            "access_indicator": f"PDF {access_level}",
            "timestamp": datetime.now().isoformat()
        }

        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)

        print(f"  JSON sauvé: {json_file}")
        print(f"  Niveau d'accès: {access_level}")
        return json_data

    def ajouter_a_chromadb(self, json_data):
        """
        Ajoute un document PDF et ses métadonnées à une collection ChromaDB. Cette méthode
        génère une description textuelle basée sur les données du document, crée un embedding
        avec un modèle d'encodage fourni, et enregistre les métadonnées ainsi que le contenu
        associé dans la base de données.

        :param json_data: Un dictionnaire contenant les informations concernant le
            fichier PDF à traiter et à ajouter dans la base de données.
        :type json_data: dict
        :return: L'identifiant unique (ID) généré pour le document ajouté dans ChromaDB.
        :rtype: str
        """

        # Créer description pour la recherche
        description = f"""DOCUMENT PDF: {json_data['fichier_source']}
TYPE: Document PDF
NIVEAU D'ACCÈS: {json_data['access_level']}
DOSSIER: {json_data['source_directory']}
CONTENU: {json_data['resume_gemini']}"""

        # Générer embedding
        embedding = self.embedding_model.encode([description])

        # Métadonnées pour ChromaDB avec niveau d'accès
        metadata = {
            'fichier_source': json_data['fichier_source'],
            'type_document': 'pdf',
            'taille_fichier': json_data['taille_fichier'],
            'pdf_path': json_data['pdf_path'],
            'source_directory': json_data['source_directory'],
            'access_level': json_data['access_level'],
            'document_type': json_data['document_type'],
            'access_indicator': json_data['access_indicator'],
            'titre_contextuel': json_data['titre_contextuel'],
            'timestamp': json_data['timestamp'],
            'description_length': len(description)
        }

        # Ajouter à la collection
        doc_id = f"pdf_{uuid.uuid4().hex[:8]}"
        self.collection.add(
            ids=[doc_id],
            embeddings=[embedding[0].tolist()],
            documents=[description],
            metadatas=[metadata]
        )

        print(f"  Ajouté à ChromaDB: {doc_id} (niveau: {json_data['access_level']})")
        return doc_id

    def traiter_tous_les_pdfs(self, dossier="data"):
        """
        Traite tous les fichiers PDF dans un dossier donné, génère des résumés,
        et les stocke dans une base de données avec un niveau d'accès spécifié.
        Cette méthode utilise un flux de traitement qui comprend la recherche des PDF,
        leur analyse via un outil de résumé, la création de métadonnées adéquates et
        l'ajout à une base de données.

        Le traitement effectue les étapes suivantes :
        - Recherche des PDF dans un dossier, avec identification de leur niveau d'accès.
        - Création de résumés pour chaque fichier PDF.
        - Création de documents JSON contenant les résumés et leurs métadonnées associées.
        - Insertion des documents JSON dans une collection d'une base de données.

        Cette méthode fournit un résumé détaillé sur les statistiques des fichiers PDF analysés
        et donne un aperçu final des données ajoutées dans la base.

        :param dossier: Chemin du dossier contenant les fichiers PDF à traiter. Par défaut, "data".
        :type dossier: str
        :return: Aucune valeur n'est retournée. Les opérations de traitement sont réalisées en place.
        :rtype: None
        """

        print("=== DÉBUT DU TRAITEMENT ===")

        # 1. Trouver les PDFs avec leurs niveaux d'accès
        pdfs_avec_acces = self.trouver_pdfs(dossier)

        if not pdfs_avec_acces:
            print("Aucun PDF trouvé")
            return

        success_count = 0
        stats_par_niveau = {'public': 0, 'internal': 0, 'confidential': 0}

        # 2. Traiter chaque PDF
        for pdf_path, access_level in pdfs_avec_acces:
            print(f"\n--- {pdf_path.name} (Niveau: {access_level}) ---")

            # Résumé avec Gemini
            resume = self.traiter_pdf_avec_gemini(pdf_path)

            if resume:
                # Créer JSON avec niveau d'accès
                json_data = self.creer_json_resume(pdf_path, access_level, resume)

                # Ajouter à ChromaDB
                doc_id = self.ajouter_a_chromadb(json_data)

                if doc_id:
                    success_count += 1
                    stats_par_niveau[access_level] += 1
                    print(f"  Succès")
            else:
                print(f"  Échec")

        # 3. Résultats finaux
        print(f"\n=== RÉSULTATS ===")
        print(f"PDFs traités avec succès: {success_count}/{len(pdfs_avec_acces)}")
        print(f"Répartition par niveau d'accès traités:")
        for niveau, count in stats_par_niveau.items():
            print(f"  - {niveau}: {count} PDF(s)")
        print(f"Collection ChromaDB: {self.collection.count()} documents total")

    def rechercher_pdfs(self, query, user_role="public", n_results=5):
        """
        Rechercher des fichiers PDF dans une collection en fonction d'une requête donnée,
        du rôle utilisateur et du nombre de résultats souhaités. Les résultats retournés
        sont filtrés en fonction du niveau d'accès autorisé pour le rôle spécifié.

        :param query: La requête de recherche sous forme de texte.
        :type query: str
        :param user_role: Le rôle de l'utilisateur effectuant la recherche (public, internal,
            admin). Par défaut, il est défini sur "public".
        :type user_role: str
        :param n_results: Le nombre de résultats à retourner après filtrage basé sur le
            rôle utilisateur. Par défaut, 5 résultats sont retournés.
        :type n_results: int
        :return: Une liste des résultats filtrés contenant des informations sur les fichiers
            trouvés, telles que le nom du fichier, le type du document, le niveau
            d'accès, la pertinence et le dossier source. Si aucun résultat n'est trouvé,
            retourne une liste vide.
        :rtype: list[dict]
        """
        # Mapping des rôles utilisateur vers les niveaux d'accès autorisés
        roles_access = {
            'public': ['public'],
            'internal': ['public', 'internal'],
            'admin': ['public', 'internal', 'confidential']
        }

        niveaux_autorises = roles_access.get(user_role, ['public'])
        print(f"Recherche pour rôle '{user_role}' - Niveaux autorisés: {niveaux_autorises}")

        # Générer embedding de la requête
        query_embedding = self.embedding_model.encode([query])

        # Rechercher (plus de résultats pour permettre le filtrage)
        results = self.collection.query(
            query_embeddings=[query_embedding[0].tolist()],
            n_results=n_results * 3,  # Plus de résultats pour filtrage
            include=['documents', 'metadatas', 'distances']
        )

        print(f"\nRésultats pour '{query}' (rôle: {user_role}):")

        if not results['ids'] or not results['ids'][0]:
            print("Aucun résultat trouvé")
            return

        resultats_filtres = []

        for i in range(len(results['ids'][0])):
            metadata = results['metadatas'][0][i]
            access_level = metadata.get('access_level', 'public')

            # Filtrer selon le rôle utilisateur
            if access_level in niveaux_autorises:
                distance = results['distances'][0][i]

                resultats_filtres.append({
                    'fichier': metadata.get('fichier_source', 'N/A'),
                    'type': metadata.get('type_document', 'tableau'),
                    'access_level': access_level,
                    'pertinence': 1 - distance,
                    'dossier': metadata.get('source_directory', 'N/A')
                })

                if len(resultats_filtres) >= n_results:
                    break

        # Afficher les résultats filtrés
        for i, resultat in enumerate(resultats_filtres, 1):
            print(f"  {i}. {resultat['fichier']}")
            print(f"     Type: {resultat['type']} | Niveau: {resultat['access_level']}")
            print(f"     Dossier: {resultat['dossier']}")
            print(f"     Pertinence: {resultat['pertinence']:.3f}")
            print()

        return resultats_filtres

    def stats_collection(self):
        """
        Calcule et affiche des statistiques sur une collection de documents.

        Cette méthode permet de collecter des statistiques sur la répartition des types
        de documents et les niveaux d'accès associés dans une collection donnée.
        Les informations sont extraites des métadonnées des documents.

        :return: Rien. Cette méthode imprime directement les statistiques dans la console.
        :rtype: None
        """

        # Récupérer tous les documents
        all_docs = self.collection.get(include=['metadatas'])

        # Compteurs
        stats_par_type = {'tableau': 0, 'pdf': 0}
        stats_par_niveau = {'public': 0, 'internal': 0, 'confidential': 0, 'non_defini': 0}

        for metadata in all_docs['metadatas']:
            # Type de document
            doc_type = metadata.get('type_document', 'tableau')
            if doc_type == 'pdf':
                stats_par_type['pdf'] += 1
            else:
                stats_par_type['tableau'] += 1

            # Niveau d'accès
            access_level = metadata.get('access_level')
            if access_level in stats_par_niveau:
                stats_par_niveau[access_level] += 1
            else:
                stats_par_niveau['non_defini'] += 1

        print(f"\n=== STATISTIQUES COLLECTION ===")
        print(f"Total documents: {self.collection.count()}")
        print(f"\nRépartition par type:")
        for type_doc, count in stats_par_type.items():
            print(f"  - {type_doc}: {count}")

        print(f"\nRépartition par niveau d'accès:")
        for niveau, count in stats_par_niveau.items():
            print(f"  - {niveau}: {count}")

    def tester_acces_par_role(self):
        """
        Effectue un test des niveaux d'accès à une fonctionnalité de recherche de PDF selon
        des rôles spécifiques.

        Le test est effectué pour les rôles suivants : 'public', 'internal' et 'admin'.
        Pour chacun de ces rôles, une recherche est réalisée avec un mot-clé donné, et les
        résultats sont imprimés pour inspection. Cette méthode sert à évaluer si les restrictions
        d'accès basées sur les rôles fonctionnent correctement.

        :param query_test: La chaîne de recherche utilisée pour tester la fonctionnalité.
        :type query_test: str

        :return: Aucun retour. Les résultats sont affichés dans la sortie standard.
        """
        query_test = "rapport"

        print("\n=== TEST DES NIVEAUX D'ACCÈS ===")

        for role in ['public', 'internal', 'admin']:
            print(f"\n--- Test pour rôle: {role} ---")
            resultats = self.rechercher_pdfs(query_test, user_role=role, n_results=3)


def main():
    """
    Classe principale pour la gestion et le traitement des documents PDF en vue d'une conversion
    en représentations chromatiques. Cette classe intègre également une gestion des niveaux
    d'accès basés sur différents rôles.

    Méthodes :
        - traiter_tous_les_pdfs : Méthode permettant de traiter un ensemble de fichiers PDF
          à partir d'un répertoire donné.
        - stats_collection : Méthode permettant d'afficher les statistiques associées
          au traitement des fichiers PDF.
        - tester_acces_par_role : Méthode utilisée pour tester les autorisations d'accès
          basées sur les rôles d'utilisateur ou les niveaux d'autorisation.
    """

    processor = PDFToChroma()

    # Traiter tous les PDFs avec gestion des niveaux d'accès
    processor.traiter_tous_les_pdfs("data")

    # Afficher statistiques avec niveaux d'accès
    processor.stats_collection()

    # Test des niveaux d'accès
    processor.tester_acces_par_role()


if __name__ == "__main__":
    main()
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
    def __init__(self):
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
        Détermine le niveau d'accès d'un PDF basé sur son chemin

        Args:
            pdf_path: Path vers le fichier PDF

        Returns:
            str: 'public', 'internal', ou 'confidential'
        """
        # Obtenir le chemin complet en minuscules pour l'analyse
        chemin_complet = str(pdf_path).lower()
        dossier_parent = str(pdf_path.parent).lower()

        print(f"DEBUG PDF: Analyse du chemin: {chemin_complet}")
        print(f"DEBUG PDF: Dossier parent: {dossier_parent}")

        # PRIORITÉ 1: Analyse du nom de dossier direct
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

        # PRIORITÉ 2: Analyse du chemin complet
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

        # PRIORITÉ 3: Analyse du nom du fichier
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
        Trouve tous les PDFs dans le dossier et ses sous-dossiers
        Retourne une liste de tuples (pdf_path, access_level)
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
        """Upload PDF vers Gemini et récupère le résumé"""
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
        Crée un JSON structuré à partir du résumé Gemini avec niveau d'accès
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
        """Ajoute le JSON à la collection ChromaDB existante avec niveau d'accès"""

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
        """Workflow complet: PDFs -> Gemini -> JSON -> ChromaDB avec niveaux d'accès"""

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
        Recherche dans la collection (tableaux + PDFs) avec filtrage par rôle
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
        """Affiche les statistiques de la collection avec niveaux d'accès"""

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
        """Test des différents niveaux d'accès"""
        query_test = "rapport"

        print("\n=== TEST DES NIVEAUX D'ACCÈS ===")

        for role in ['public', 'internal', 'admin']:
            print(f"\n--- Test pour rôle: {role} ---")
            resultats = self.rechercher_pdfs(query_test, user_role=role, n_results=3)


def main():
    """Fonction principale"""

    processor = PDFToChroma()

    # Traiter tous les PDFs avec gestion des niveaux d'accès
    processor.traiter_tous_les_pdfs("data")

    # Afficher statistiques avec niveaux d'accès
    processor.stats_collection()

    # Test des niveaux d'accès
    processor.tester_acces_par_role()


if __name__ == "__main__":
    main()
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
        os.chdir("/home/aissa/Bureau/Projet_Chatbot/Chatbot_AMDIE/chatbot_maroc")
        # Configuration Gemini
        self.client = genai.Client()

        # Configuration ChromaDB - collection existante
        self.chroma_client = chromadb.PersistentClient(path="./chroma_db")
        self.collection = self.chroma_client.get_collection("tableaux_maroc")

        # Modèle d'embeddings
        self.embedding_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

        print(f"Collection tableaux_maroc: {self.collection.count()} documents existants")

    def trouver_pdfs(self, dossier="data"):
        """Trouve tous les PDFs dans le dossier"""
        dossier_path = Path(dossier)
        pdf_files = list(dossier_path.glob("*.pdf"))
        print(f"PDFs trouvés dans {dossier}: {len(pdf_files)}")
        return pdf_files

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

    def creer_json_resume(self, pdf_path, resume_gemini):
        """Crée un JSON structuré à partir du résumé Gemini"""

        # Sauvegarder le JSON
        output_path = Path("output")
        output_path.mkdir(exist_ok=True) #si le dossier n'existe pas, on le crée

        json_file = output_path / f"index_{pdf_path.stem}.json"

        json_data = {
            "resume_gemini": resume_gemini,
            "fichier_source": pdf_path.name,
            "type_document": "pdf",
            "taille_fichier": pdf_path.stat().st_size,
            "titre_contextuel": str(pdf_path.parent),
            "pdf_path": str(json_file)
        }


        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)

        print(f" JSON sauvé: {json_file}")
        return json_data

    def ajouter_a_chromadb(self, json_data):
        """Ajoute le JSON à la collection ChromaDB existante"""

        # Créer description pour la recherche
        description = f"""DOCUMENT PDF: {json_data['fichier_source']}
TYPE: Document PDF
CONTENU: {json_data['resume_gemini']}"""

        # Générer embedding
        embedding = self.embedding_model.encode([description])

        # Métadonnées pour ChromaDB
        metadata = {
            'fichier_source': json_data['fichier_source'],
            'type_document': 'pdf',
            'taille_fichier': json_data['taille_fichier'],
            'pdf_path': json_data['pdf_path']
        }

        # Ajouter à la collection
        doc_id = f"pdf_{uuid.uuid4().hex[:8]}"
        self.collection.add(
            ids=[doc_id],
            embeddings=[embedding[0].tolist()],
            documents=[description],
            metadatas=[metadata]
        )

        print(f"  Ajouté à ChromaDB: {doc_id}")
        return doc_id

    def traiter_tous_les_pdfs(self, dossier="data"):
        """Workflow complet: PDFs -> Gemini -> JSON -> ChromaDB"""

        print("=== DÉBUT DU TRAITEMENT ===")

        # 1. Trouver les PDFs
        pdf_files = self.trouver_pdfs(dossier)

        if not pdf_files:
            print("Aucun PDF trouvé")
            return

        success_count = 0

        # 2. Traiter chaque PDF
        for pdf_path in pdf_files:
            print(f"\n--- {pdf_path.name} ---")

            # Résumé avec Gemini
            resume = self.traiter_pdf_avec_gemini(pdf_path)

            if resume:
                # Créer JSON
                json_data = self.creer_json_resume(pdf_path, resume)

                # Ajouter à ChromaDB
                doc_id = self.ajouter_a_chromadb(json_data)

                if doc_id:
                    success_count += 1
                    print(f"  Succès")
            else:
                print(f"  Échec")

        # 3. Résultats finaux
        print(f"\n=== RÉSULTATS ===")
        print(f"PDFs traités avec succès: {success_count}/{len(pdf_files)}")
        print(f"Collection ChromaDB: {self.collection.count()} documents total")

    def rechercher_pdfs(self, query, n_results=5):
        """Recherche dans la collection (tableaux + PDFs)"""

        # Générer embedding de la requête
        query_embedding = self.embedding_model.encode([query])

        # Rechercher
        results = self.collection.query(
            query_embeddings=[query_embedding[0].tolist()],
            n_results=n_results,
            include=['documents', 'metadatas', 'distances']
        )

        print(f"\nRésultats pour '{query}':")

        if not results['ids'] or not results['ids'][0]:
            print("Aucun résultat trouvé")
            return

        for i in range(len(results['ids'][0])):
            metadata = results['metadatas'][0][i]
            distance = results['distances'][0][i]
            content_type = metadata.get('content_type', 'tableau')

            print(f"  {i + 1}. {metadata.get('fichier_source', 'N/A')}")
            print(f"     Type: {content_type}")
            print(f"     Pertinence: {1 - distance:.3f}")

    def stats_collection(self):
        """Affiche les statistiques de la collection"""

        # Compter par type
        all_docs = self.collection.get(include=['metadatas'])

        tableaux_count = 0
        pdfs_count = 0

        for metadata in all_docs['metadatas']:
            if metadata.get('content_type') == 'pdf':
                pdfs_count += 1
            else:
                tableaux_count += 1

        print(f"\n=== STATISTIQUES COLLECTION ===")
        print(f"Total documents: {self.collection.count()}")
        print(f"Tableaux Excel: {tableaux_count}")
        print(f"Documents PDF: {pdfs_count}")


def main():
    """Fonction principale"""

    processor = PDFToChroma()

    # Traiter tous les PDFs
    processor.traiter_tous_les_pdfs("data")

    # Afficher statistiques
    processor.stats_collection()

    # Test de recherche
    #processor.rechercher_pdfs("rapport", n_results=3)
    #processor.rechercher_pdfs("statistiques", n_results=3)


if __name__ == "__main__":
    main()
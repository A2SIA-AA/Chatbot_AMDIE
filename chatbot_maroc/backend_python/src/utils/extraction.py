from openpyxl import load_workbook
import numpy as np
import json
import os
from google import genai
from dotenv import load_dotenv
from pathlib import Path
from google.genai import types
import re


# =============================
# NOUVEAU: GESTION DES PERMISSIONS
# =============================

def detect_access_level_from_path(file_path: str) -> tuple:
    """
    Détecte le niveau d'accès d'un fichier basé sur sa structure de dossier

    Structure attendue: data/{type}/{nom_fichier.xlsx}

    Args:
        file_path: Chemin vers le fichier (ex: "data/public/stats.xlsx")

    Returns:
        tuple: (access_level, document_type, required_permissions)
    """

    # Normaliser le chemin
    normalized_path = Path(file_path).as_posix().lower()
    path_parts = Path(file_path).parts

    # Mapping des dossiers vers les niveaux d'accès
    folder_mappings = {
        # Niveaux d'accès principaux
        'public': {
            'access_level': 'public',
            'document_type': 'public_data',
            'required_permissions': ['read_public_docs']
        },
        'interne': {
            'access_level': 'internal',
            'document_type': 'internal_data',
            'required_permissions': ['read_internal_docs', 'read_public_docs']
        },
        'internal': {
            'access_level': 'internal',
            'document_type': 'internal_data',
            'required_permissions': ['read_internal_docs', 'read_public_docs']
        },
        'admin': {
            'access_level': 'confidential',
            'document_type': 'admin_data',
            'required_permissions': ['read_confidential_docs', 'read_internal_docs', 'read_public_docs']
        },
        'confidential': {
            'access_level': 'confidential',
            'document_type': 'confidential_data',
            'required_permissions': ['read_confidential_docs', 'read_internal_docs', 'read_public_docs']
        },
        'confidentiel': {
            'access_level': 'confidential',
            'document_type': 'confidential_data',
            'required_permissions': ['read_confidential_docs', 'read_internal_docs', 'read_public_docs']
        },
        # Types de documents spécifiques
        'statistiques': {
            'access_level': 'internal',
            'document_type': 'statistics',
            'required_permissions': ['read_internal_docs', 'read_public_docs']
        },
        'finances': {
            'access_level': 'confidential',
            'document_type': 'financial',
            'required_permissions': ['read_confidential_docs', 'read_internal_docs', 'read_public_docs']
        },
        'rh': {
            'access_level': 'internal',
            'document_type': 'hr_data',
            'required_permissions': ['read_internal_docs', 'read_public_docs']
        },
        'strategie': {
            'access_level': 'confidential',
            'document_type': 'strategy',
            'required_permissions': ['read_confidential_docs', 'read_internal_docs', 'read_public_docs']
        }
    }

    # Chercher dans les parties du chemin
    for part in path_parts:
        part_lower = part.lower()
        if part_lower in folder_mappings:
            mapping = folder_mappings[part_lower]
            print(f"Détecté niveau d'accès '{mapping['access_level']}' pour dossier '{part}' dans {file_path}")
            return mapping['access_level'], mapping['document_type'], mapping['required_permissions']

    # Fallback : chercher dans le chemin complet pour des mots-clés
    for keyword, mapping in folder_mappings.items():
        if keyword in normalized_path:
            print(f"Détecté niveau d'accès '{mapping['access_level']}' par mot-clé '{keyword}' dans {file_path}")
            return mapping['access_level'], mapping['document_type'], mapping['required_permissions']

    # Par défaut : public
    print(f"Aucun niveau d'accès détecté pour {file_path}, utilisation de 'public' par défaut")
    return 'public', 'general', ['read_public_docs']


def enrich_metadata_with_permissions(metadata: dict, file_path: str) -> dict:
    """
    Enrichit les métadonnées avec les informations de permissions

    Args:
        metadata: Métadonnées existantes du tableau
        file_path: Chemin vers le fichier source

    Returns:
        dict: Métadonnées enrichies
    """

    access_level, document_type, required_permissions = detect_access_level_from_path(file_path)

    # Enrichir les métadonnées
    enriched_metadata = {
        **metadata,
        # Nouvelles informations de permissions
        'access_level': access_level,
        'document_type': document_type,
        'required_permissions': ','.join(required_permissions),  # String pour ChromaDB
        'permissions_list': required_permissions,  # Liste pour usage interne
        # Informations de traçabilité
        'source_directory': str(Path(file_path).parent),
        'detected_from_path': True,
        'extraction_timestamp': str(Path().cwd())  # Pour debug
    }

    return enriched_metadata


# =============================
# 1. EXTRACTION DES TABLEAUX (MODIFIÉE)
# =============================

def sheet_to_presence_matrix(sheet):
    """
    Transforme la feuille Excel en matrice de présence (1 si cellule non vide, 0 sinon)
    Pour détecter les blocs de données (tableaux/titres).
    """
    max_row = sheet.max_row
    max_col = sheet.max_column
    matrix = np.zeros((max_row, max_col), dtype=int)

    for row in range(1, max_row + 1):
        for col in range(1, max_col + 1):
            value = sheet.cell(row=row, column=col).value
            if value is not None and str(value).strip() != "":
                matrix[row - 1, col - 1] = 1
    return matrix


from scipy.ndimage import label


def find_blocks(matrix):
    """
    Détecte les blocs connexes de cellules non vides dans la matrice (2D connexité).
    Chaque bloc représente potentiellement un tableau ou un titre.
    """
    structure = np.ones((3, 3))  # Connexité 8
    labeled, num_features = label(matrix, structure=structure)
    blocks = []
    for block_id in range(1, num_features + 1):
        positions = np.argwhere(labeled == block_id)
        rows = positions[:, 0]
        cols = positions[:, 1]
        min_row, max_row = rows.min(), rows.max()
        min_col, max_col = cols.min(), cols.max()
        blocks.append({
            "min_row": min_row,
            "max_row": max_row,
            "min_col": min_col,
            "max_col": max_col,
            "positions": positions
        })
    return blocks


def extract_table(sheet, block):
    """
    Extrait les valeurs Excel d'un bloc donné (sous forme de matrice python).
    """
    table = []
    for r in range(block["min_row"] + 1, block["max_row"] + 2):
        row = []
        for c in range(block["min_col"] + 1, block["max_col"] + 2):
            row.append(sheet.cell(row=r, column=c).value)
        table.append(row)
    return table


def is_title_block(table):
    """
    Un bloc d'une seule ligne, contenant une phrase >10 caractères = probablement un titre de section/tableau.
    """
    if len(table) == 1:
        if any(isinstance(cell, str) and len(cell.strip()) > 10 for cell in table[0]):
            return True
    return False


def assign_titles_to_tables(sheet, blocks):
    """
    Associe à chaque tableau détecté le dernier titre trouvé juste avant.
    """
    title_context = None
    result_tables = []
    for idx, block in enumerate(blocks):
        table = extract_table(sheet, block)
        if is_title_block(table):
            title_context = " ".join([str(cell) for cell in table[0] if cell])
            continue  # on saute le stockage des titres seuls
        else:
            result_tables.append({
                "titre": title_context,
                "tableau": table,
                "coordonnees": (block['min_row'] + 1, block['max_row'] + 1, block['min_col'] + 1, block['max_col'] + 1)
            })
    return result_tables


def safe_filename(s):
    """
    Nettoie un nom de fichier pour éviter tout caractère gênant.
    """
    return "".join(c if c.isalnum() or c in " ._-" else "_" for c in str(s))


def save_table_json(table, meta, output_dir, idx):
    """
    Sauvegarde chaque tableau extrait sous forme JSON, avec ses métadonnées enrichies.
    """
    filename = f"tableau_{idx:03d}.json"
    path = os.path.join(output_dir, filename)

    # Ajouter un indicateur visuel du niveau d'accès dans le JSON
    access_indicator = {
        'public': '[PUBLIC]',
        'internal': '[INTERNE]',
        'confidential': '[CONFIDENTIEL]'
    }.get(meta.get('access_level', 'public'), '[DOCUMENT]')

    json_data = {
        "tableau": table,
        "access_indicator": access_indicator,  # Pour faciliter la lecture
        **meta
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)

    print(f"Sauvegardé: {access_indicator} {filename}")
    return path


def full_extraction_to_json(xlsx_path, output_base):
    """
    Parcours tout le fichier Excel, extrait chaque tableau de chaque feuille,
    détecte automatiquement les permissions, et stocke tout en JSON + index.
    """
    wb = load_workbook(xlsx_path, data_only=True)
    base_name = os.path.splitext(os.path.basename(xlsx_path))[0]
    output_file_dir = os.path.join(output_base, safe_filename(base_name))
    os.makedirs(output_file_dir, exist_ok=True)
    global_index = []

    # Détecter le niveau d'accès du fichier
    access_level, document_type, required_permissions = detect_access_level_from_path(xlsx_path)
    print(f"\nFichier {xlsx_path}:")
    print(f"  Niveau d'accès détecté: {access_level}")
    print(f"  Type de document: {document_type}")
    print(f"  Permissions requises: {required_permissions}")

    for sheetname in wb.sheetnames:
        sheet = wb[sheetname]
        matrix = sheet_to_presence_matrix(sheet)
        blocks = find_blocks(matrix)
        tables = assign_titles_to_tables(sheet, blocks)
        feuille_dir = os.path.join(output_file_dir, safe_filename(sheetname))
        os.makedirs(feuille_dir, exist_ok=True)

        for idx, t in enumerate(tables, 1):
            # Métadonnées de base
            base_meta = {
                "fichier_source": base_name,
                "nom_feuille": sheetname,
                "range_bloc": f"{t['coordonnees']}",
                "titre_contextuel": t['titre'],
            }

            # NOUVEAU: Enrichir avec les permissions
            enriched_meta = enrich_metadata_with_permissions(base_meta, xlsx_path)

            table_json_path = save_table_json(
                t['tableau'], enriched_meta, feuille_dir, idx
            )

            # Index global avec informations de permissions
            global_index.append({
                "fichier_source": base_name,
                "nom_feuille": sheetname,
                "titre_contextuel": t['titre'],
                "tableau_json": os.path.relpath(table_json_path, output_base),
                "access_level": access_level,
                "document_type": document_type,
                "required_permissions": ','.join(required_permissions),
                "permissions_summary": f"{access_level.upper()} - {document_type}"
            })

    # Sauvegarde de l'index global pour la recherche
    index_path = os.path.join(output_base, "index.json")
    with open(index_path, "w", encoding="utf-8") as idxf:
        json.dump(global_index, idxf, ensure_ascii=False, indent=2)

    # Statistiques par niveau d'accès
    stats_by_level = {}
    for item in global_index:
        level = item['access_level']
        stats_by_level[level] = stats_by_level.get(level, 0) + 1

    print(f"\nExtraction terminée ! {len(global_index)} tableaux enregistrés.")
    print("Répartition par niveau d'accès:")
    for level, count in stats_by_level.items():
        indicator = {'public': '[PUBLIC]', 'internal': '[INTERNE]', 'confidential': '[CONFIDENTIEL]'}.get(level,
                                                                                                          '[AUTRE]')
        print(f"  {indicator} {level}: {count} tableaux")

    print(f"Index sauvegardé dans: {index_path}")


# =============================
# 2. EXTRACTION DES PDFs
# =============================
def extract_pdf_text(pdf_path):
    """
    Extrait le texte des PDFs avec détection automatique des permissions
    """
    client = genai.Client(api_key="AIzaSyAlgDF_78gtHpOVYcQ5-ucU6wp47vIc8Ns")
    data_file = Path(pdf_path)

    for file in data_file.iterdir():
        if file.suffix == ".pdf":
            # NOUVEAU: Détecter le niveau d'accès du PDF
            access_level, document_type, required_permissions = detect_access_level_from_path(str(file))

            prompt = (f"Voici le chemin vers le fichier PDF : {file}"
                      "Fait un résumé de ce fichier PDF"
                      "Produit un JSON respectant la forme suivante :"
                      "Resume = { 'fichier_source': string, 'resume': string, 'chemin': string, "
                      f"'access_level': '{access_level}', 'document_type': '{document_type}', "
                      f"'required_permissions': '{','.join(required_permissions)}' }}"
                      "Return: Resume")

            try:
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=[
                        types.Part.from_bytes(
                            data=file.read_bytes(),
                            mime_type='application/pdf',
                        ),
                        prompt])

                # Enrichir la réponse avec les métadonnées de permissions
                texte = nettoyer_json(response.text)

                # Ajouter les informations de permissions si elles manquent
                try:
                    resume_data = json.loads(texte)
                    resume_data.update({
                        'access_level': access_level,
                        'document_type': document_type,
                        'required_permissions': ','.join(required_permissions),
                        'pdf_path': str(file),
                        'extraction_method': 'gemini_ai'
                    })
                    texte = json.dumps(resume_data, ensure_ascii=False, indent=2)
                except json.JSONDecodeError:
                    print(f"Erreur parsing JSON pour {file}, utilisation texte brut")

                output_file = f"output/index_{file.stem}_{access_level}.json"
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(texte)

                access_indicator = {'public': '[PUBLIC]', 'internal': '[INTERNE]',
                                    'confidential': '[CONFIDENTIEL]'}.get(access_level, '[PDF]')
                print(f"PDF traité: {access_indicator} {file.name} -> {output_file}")

            except Exception as e:
                print(f"Erreur traitement PDF {file}: {e}")

    return "Extraction PDF terminée"


def nettoyer_json(texte):
    """
    Nettoie le texte JSON retourné par Gemini
    """
    pattern = r'^```json\s*\n?|```\s*$'
    texte = re.sub(pattern, '', texte, flags=re.MULTILINE).strip()
    return texte


# =============================
# NOUVEAU: FONCTIONS UTILITAIRES
# =============================

def analyze_directory_structure(data_dir: str):
    """
    Analyse la structure des dossiers data/ et affiche les niveaux d'accès détectés
    """
    data_path = Path(data_dir)

    if not data_path.exists():
        print(f"Dossier {data_dir} non trouvé")
        return

    print(f"Analyse de la structure: {data_path}")
    print("=" * 50)

    file_count_by_level = {}

    for file_path in data_path.rglob("*.xlsx"):
        access_level, document_type, required_permissions = detect_access_level_from_path(str(file_path))

        if access_level not in file_count_by_level:
            file_count_by_level[access_level] = []

        file_count_by_level[access_level].append({
            'file': file_path.name,
            'path': str(file_path.relative_to(data_path)),
            'document_type': document_type
        })

    # Afficher les résultats
    for level, files in file_count_by_level.items():
        indicator = {'public': '[PUBLIC]', 'internal': '[INTERNE]', 'confidential': '[CONFIDENTIEL]'}.get(level,
                                                                                                          '[AUTRE]')
        print(f"\n{indicator} Niveau {level.upper()} ({len(files)} fichiers):")
        for file_info in files:
            print(f"  - {file_info['path']} ({file_info['document_type']})")

    return file_count_by_level


def extract_all_files_in_directory(data_dir: str, output_base: str = "output"):
    """
    Extrait tous les fichiers Excel d'un dossier data/ en préservant les niveaux d'accès
    """
    data_path = Path(data_dir)

    if not data_path.exists():
        print(f"Dossier {data_dir} non trouvé")
        return

    print(f"Extraction de tous les fichiers dans: {data_path}")

    excel_files = list(data_path.rglob("*.xlsx"))
    print(f"Trouvé {len(excel_files)} fichiers Excel")

    for file_path in excel_files:
        print(f"\nTraitement: {file_path}")
        try:
            full_extraction_to_json(str(file_path), output_base)
        except Exception as e:
            print(f"Erreur avec {file_path}: {e}")

    print(f"\n Extraction complète terminée!")
    print(f"Résultats dans: {output_base}/")


if __name__ == "__main__":
    # Configuration
    os.chdir("/home/aissa/Bureau/Projet_Chatbot/chatbot_maroc/backend_python")

    # Exemple d'utilisation avec la nouvelle structure

    # 1. Analyser la structure des dossiers
    print("1. ANALYSE DE LA STRUCTURE:")
    analyze_directory_structure("data")

    # 2. Exemple d'extraction d'un fichier spécifique
    print("\n2. EXTRACTION D'UN FICHIER:")
    # xlsx_path = "data/public/stats_publiques.xlsx"  # Sera détecté comme public
    # xlsx_path = "data/internal/rapport_interne.xlsx"  # Sera détecté comme internal
    # xlsx_path = "data/admin/finances_confidentielles.xlsx"  # Sera détecté comme confidential

    xlsx_path = "data/admin/20230420_Capital Humain au Maroc_V-Final-2.xlsx"  # Sera détecté comme admin
    output_base = "output"
    full_extraction_to_json(xlsx_path, output_base)

    # 3. Extraction de tous les fichiers (optionnel)
    # print("\n3. EXTRACTION COMPLÈTE:")
    # extract_all_files_in_directory("data", "output")

    # 4. Extraction PDF avec permissions (optionnel)
    # print("\n4. EXTRACTION PDF:")
    # pdf_path = Path("data")
    # extract_pdf_text(pdf_path)
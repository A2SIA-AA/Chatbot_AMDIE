import json
import os
from pathlib import Path
from typing import Dict, List, Any
from dotenv import load_dotenv

load_dotenv()


def __init__():
    pass


def generer_description_tableau(tableau_path: str) -> Dict[str, Any]:
    """
    Génère une description pour un tableau JSON donné. Cette fonction lit un fichier JSON, extrait
    les informations métadonnées, analyse le contenu du tableau et génère une description textuelle
    ainsi que des statistiques sur le tableau.

    :param tableau_path: Chemin du fichier JSON contenant les données du tableau.
    :return: Un dictionnaire contenant la description textuelle, les métadonnées, les statistiques
             et un échantillon des données du tableau.

    """
    # Charger le tableau JSON
    with open(tableau_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    metadata = {
        # Champs originaux
        'fichier_source': data.get('fichier_source', ''),
        'nom_feuille': data.get('nom_feuille', ''),
        'titre_contextuel': data.get('titre_contextuel', ''),
        'range_bloc': data.get('range_bloc', ''),
        'tableau_path': tableau_path,
        'access_level': data.get('access_level'),
        'access_indicator': data.get('access_indicator'),
        'document_type': data.get('document_type'),
        'source_directory': data.get('source_directory'),
        'required_permissions': data.get('required_permissions'),
        'permissions_list': data.get('permissions_list'),
        'detected_from_path': data.get('detected_from_path'),
        'extraction_timestamp': data.get('extraction_timestamp'),


        **{k: v for k, v in data.items() if k not in [
            'tableau', 'fichier_source', 'nom_feuille', 'titre_contextuel', 'range_bloc'
        ]}
    }

    if metadata.get('access_level'):
        print(f"DEBUG description.py: {tableau_path}")
        print(f"  access_level trouvé: {metadata.get('access_level')}")
        print(f"  access_indicator: {metadata.get('access_indicator')}")

    # Extraire le tableau
    tableau_data = data.get('tableau', [])

    if not tableau_data:
        return {
            'description': f"Tableau vide - {metadata['titre_contextuel']}",
            'metadata': metadata,
            'stats': {'nb_lignes': 0, 'nb_colonnes': 0}
        }

    # Analyse du tableau
    nb_lignes = len(tableau_data)
    nb_colonnes = len(tableau_data[0]) if tableau_data else 0

    # Première ligne = headers (souvent)
    headers = tableau_data[0] if tableau_data else []
    data_rows = tableau_data[1:] if len(tableau_data) > 1 else []

    # Nettoyer et analyser les headers
    headers_clean = [str(h).strip() if h is not None else "Colonne_vide" for h in headers]

    # Échantillon de données (3-5 lignes max)
    echantillon_size = min(5, len(data_rows))
    echantillon = data_rows[:echantillon_size]

    # Analyse des types de données par colonne
    types_colonnes = analyser_types_colonnes(data_rows, headers_clean)

    # Statistiques basiques
    stats = {
        'nb_lignes': nb_lignes - 1,  # -1 pour exclure header
        'nb_colonnes': nb_colonnes,
        'headers': headers_clean,
        'types_colonnes': types_colonnes
    }

    # Générer la description textuelle
    description = construire_description_textuelle(metadata, stats, echantillon)

    return {
        'description': description,
        'metadata': metadata,
        'stats': stats,
        'echantillon': echantillon
    }


def analyser_types_colonnes(data_rows: List[List], headers: List[str]) -> Dict[str, str]:
    """
    Analyse les types dominants des colonnes d'un ensemble de données. Pour chaque colonne,
    une analyse est effectuée sur un sous-ensemble des premières lignes non nulles, afin de déterminer
    le type de données dominant parmi les valeurs disponibles.

    :param data_rows: Une liste de listes représentant les lignes d'un tableau de données. Chaque sous-liste
                      contient les valeurs de différentes colonnes pour une ligne donnée.
    :type data_rows: List[List]
    :param headers: Une liste de chaînes de caractères représentant les noms des colonnes du tableau de données.
    :type headers: List[str]
    :return: Un dictionnaire associant chaque nom de colonne à une chaîne de caractères indiquant son type dominant
             ("vide" si aucune valeur n'est présente).
    :rtype: Dict[str, str]
    """
    if not data_rows or not headers:
        return {}

    types_colonnes = {}
    nb_cols = len(headers)

    for col_idx in range(nb_cols):
        col_name = headers[col_idx]

        # Échantillonner quelques valeurs de cette colonne
        valeurs = []
        for row in data_rows[:10]:  # Analyser max 10 lignes
            if col_idx < len(row) and row[col_idx] is not None:
                valeurs.append(row[col_idx])

        if not valeurs:
            types_colonnes[col_name] = "vide"
            continue

        # Détecter le type dominant
        type_detecte = detecter_type_dominant(valeurs)
        types_colonnes[col_name] = type_detecte

    return types_colonnes


def detecter_type_dominant(valeurs: List[Any]) -> str:
    """
    Détecte le type de données dominant dans une liste donnée.

    Cette fonction analyse une liste d'éléments pour déterminer quel type de données
    (principalement "numérique", "texte", "pourcentage" ou "ville") est le plus dominant
    parmi les valeurs fournies. Si la liste est vide, elle retourne "vide".

    Le type dominant est déterminé en comptabilisant le nombre d'apparitions de chaque type
    et en sélectionnant celui qui a la fréquence la plus élevée.

    :param valeurs: Liste contenant des valeurs à analyser.
                    Ces valeurs peuvent être de divers types (numériques,
                    chaînes de caractères, etc.).
    :type valeurs: List[Any]
    :return: Le type de données dominant parmi les éléments de la liste.
             Peut être l'un des suivants : "numerique", "texte", "pourcentage",
             "ville", ou "vide" si la liste est vide.
    :rtype: str
    """
    if not valeurs:
        return "vide"

    types_counts = {'numerique': 0, 'texte': 0, 'pourcentage': 0, 'ville': 0}

    for val in valeurs:
        val_str = str(val).strip().lower()

        # Numérique
        try:
            float(val_str.replace(',', '.'))
            types_counts['numerique'] += 1
            continue
        except ValueError:
            pass

        # Pourcentage
        if '%' in val_str or 'pourcentage' in val_str:
            types_counts['pourcentage'] += 1
            continue

        # Villes/Régions (heuristique simple)
        villes_maroc = ['casablanca', 'rabat', 'fès', 'marrakech', 'agadir', 'tanger', 'meknès', 'oujda']
        if any(ville in val_str for ville in villes_maroc):
            types_counts['ville'] += 1
            continue

        # Par défaut : texte
        types_counts['texte'] += 1

    # Retourner le type dominant
    return max(types_counts.items(), key=lambda x: x[1])[0]


def construire_description_textuelle(metadata: Dict, stats: Dict, echantillon: List[List]) -> str:
    """
    Construit une description textuelle structurée des métadonnées, des statistiques et d'un
    échantillon de données représentées sous forme de tableau.

    Résumé des sections inclues :
    - Contexte et source : décrit le contexte et la source des données (titre contextuel, fichier
      source et feuille).
    - Structure du tableau : fournit des informations statistiques telles que le nombre d'entrées
      et de colonnes.
    - Colonnes disponibles : liste les noms des colonnes dans le tableau, si disponibles.
    - Types de données : associe chaque colonne à son type de données, si cette information est
      disponible.
    - Échantillon de données : extrait et affiche quelques lignes et colonnes en tant qu'échantillon
      pour illustrer le contenu du tableau.

    Paramètres :
    :param metadata: Métadonnées du tableau, incluant au minimum les clés suivantes :
        - 'titre_contextuel' (str) : le titre ou le contexte de la table,
        - 'fichier_source' (str) : nom du fichier source d'origine,
        - 'nom_feuille' (str) : nom de la feuille contenant les données.
    :param stats: Statistiques descriptives du tableau, contenant :
        - 'nb_lignes' (int) : le nombre total de lignes,
        - 'nb_colonnes' (int) : le nombre total de colonnes,
        - 'headers' (List[str]) : une liste des noms des colonnes si disponibles,
        - 'types_colonnes' (Dict[str, str]) : un dictionnaire associant les colonnes à leur type.
    :param echantillon: Une liste de listes représentant les premières données du tableau
        sous forme de lignes, typiquement destiné à afficher un échantillon.

    Retourne :
    :return: Une chaîne de caractères structurée décrivant les métadonnées, statistiques, et
             un échantillon du tableau.
    """
    desc_parts = []

    # Contexte et source
    desc_parts.append(f"CONTEXTE: {metadata['titre_contextuel']}")
    desc_parts.append(f"SOURCE: Fichier '{metadata['fichier_source']}', Feuille '{metadata['nom_feuille']}'")

    # Structure du tableau
    desc_parts.append(f"DONNÉES: Tableau de {stats['nb_lignes']} entrées avec {stats['nb_colonnes']} colonnes")

    # Colonnes disponibles
    if stats['headers']:
        colonnes_str = ', '.join(stats['headers'])
        desc_parts.append(f"COLONNES: {colonnes_str}")

    # Types de données
    if stats['types_colonnes']:
        types_str = ', '.join([f"{col}({type_})" for col, type_ in stats['types_colonnes'].items()])
        desc_parts.append(f"TYPES: {types_str}")

    # Échantillon de données
    if echantillon:
        desc_parts.append("ÉCHANTILLON:")
        for i, row in enumerate(echantillon[:3]):  # Max 3 lignes d'échantillon
            row_clean = [str(cell) if cell is not None else "N/A" for cell in row]
            desc_parts.append(f"  Ligne {i + 1}: {' | '.join(row_clean[:5])}")  # Max 5 cols

    return '\n'.join(desc_parts)


def traiter_index_complet(index_path: str, tableaux_dir: str) -> List[Dict]:
    """
    Traite un index JSON et génère des descriptions pour chaque tableau référencé dans
    l'index. Chaque tableau est représenté par un fichier JSON localisé dans un dossier
    spécifié.

    Ce traitement parcourt chaque élément de l'index fourni, vérifie la validité des
    chemins vers les fichiers JSON des tableaux et procède à la génération de descriptions
    pour ceux qui existent.

    :param index_path: Chemin vers le fichier JSON contenant l'index des données.
    :param tableaux_dir: Chemin vers le dossier contenant les fichiers JSON des tableaux.
    :return: Une liste de dictionnaires contenant les descriptions générées pour chaque
        tableau valide.
    :rtype: List[Dict]
    :raises FileNotFoundError: Si le fichier d'index spécifié ou le chemin d'un tableau
        n'est pas valide.
    :raises json.JSONDecodeError: Si le fichier JSON de l'index contient des erreurs de
        formatage.
    :raises RuntimeError: Pour d'autres erreurs liées au traitement, comme lors de la
        génération des descriptions des fichiers JSON des tableaux.
    """
    # Charger l'index
    dir_dossier = os.getenv("PROJECT_DIR")
    os.chdir(dir_dossier)
    with open(index_path, 'r', encoding='utf-8') as f:
        index_data = json.load(f)

    descriptions = []

    for item in index_data:
        tableau_json_path = item.get('tableau_json', '')
        if not tableau_json_path:
            continue

        # Construire le chemin complet
        full_path = Path(tableaux_dir) / tableau_json_path

        if full_path.exists():
            try:
                description = generer_description_tableau(str(full_path))
                descriptions.append(description)
                print(f"Traité: {tableau_json_path}")
            except Exception as e:
                print(f"Erreur avec {tableau_json_path}: {e}")
        else:
            print(f"  Fichier non trouvé: {full_path}")

    return descriptions


# Exemple d'utilisation
if __name__ == "__main__":
    # Test avec un seul tableau
    # description = generer_description_tableau("output/20230420_Capital Humain au Maroc_V-Final-2/_Ingénieurs/tableau_001.json")
    # print(description['description'])
    # Traitement complet
    dir_dossier = os.getenv("PROJECT_DIR")
    os.chdir(dir_dossier)
    descriptions = traiter_index_complet("output/index.json", "output")
    print(f"\n {len(descriptions)} tableaux traités avec succès!")
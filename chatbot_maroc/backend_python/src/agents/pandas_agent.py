from typing import Dict
import pandas as pd


# =============================================================================
# FONCTIONS UTILES AGENTS CODE
# =============================================================================

class SimplePandasAgent:
    """
    Classe responsable de la création et du nettoyage de DataFrames à partir de données de tableau données.

    Cette classe utilise un modèle Gemini pour l'analyse sous-jacente et fournit des fonctionnalités pour
    générer et contextualiser des DataFrames selon des métadonnées et des critères spécifiques.

    :ivar gemini_model: Modèle Gemini utilisé pour l'analyse des données.
    :type gemini_model: Any
    """

    def __init__(self, gemini_model):
        self.gemini_model = gemini_model

    def creer_dataframe_propre(self, tableau_data: Dict) -> pd.DataFrame:
        """
        Cette fonction crée un DataFrame propre à partir des données d'un tableau en dictionnaire. Elle gère les cas où
        le tableau est inexistant dans les données fournies en générant une structure minimale basée sur les métadonnées.
        Le DataFrame final est nettoyé (supression des lignes vides ou inappropriées) et enrichi avec des métadonnées.

        :param tableau_data: Un dictionnaire contenant les données d'un tableau, des métadonnées, et des informations
            complémentaires comme le titre contextuel et la source du tableau.
        :type tableau_data: Dict
        :return: Un DataFrame propre contenant le tableau filtré et nettoyé, avec des métadonnées ajoutées à ses attributs.
        :rtype: pd.DataFrame
        :raises KeyError: Si certaines clés nécessaires dans `tableau_data` sont absentes lors du traitement.
        """

        if 'tableau' not in tableau_data:
            # Créer une structure tableau minimale depuis les métadonnées
            titre = tableau_data.get('titre_contextuel', 'Sans titre')
            description = tableau_data.get('description', 'Pas de description')
            source = tableau_data.get('source', tableau_data.get('fichier_source', 'Source inconnue'))
            doc_id = tableau_data.get('id', 'ID_inconnu')

            # Créer un tableau simple avec les métadonnées disponibles
            tableau_data['tableau'] = [
                ['Titre', 'Description', 'Source', 'ID'],  # Headers
                [titre, description, source, doc_id]  # Données
            ]

            print(f"[PANDAS_AGENT] Tableau créé depuis métadonnées pour: {titre}")


        donnees_tableau = tableau_data['tableau']
        headers = donnees_tableau[0]
        rows = donnees_tableau[1:]

        # Nettoyer les données (supprimer lignes vides, sources, etc.)
        rows_propres = []
        for row in rows:
            if (row and row[0] and
                    str(row[0]).upper() not in ['SOURCE', 'TOTAL', '', 'N/A', 'NOTE'] and
                    not str(row[0]).upper().startswith('SOURCE')):
                rows_propres.append(row)

        # Créer le DataFrame
        df = pd.DataFrame(rows_propres, columns=headers)

        # Convertir les colonnes numériques intelligemment
        for col in df.columns:
            if col and any(keyword in str(col).lower() for keyword in
                           ['total', 'nombre', 'effectif', 'diplômé', '%', 'pourcentage', 'taux']):
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # Ajouter les métadonnées au dataframe
        df.attrs.update({
            'titre': tableau_data.get('titre_contextuel', 'Tableau sans titre'),
            'source': tableau_data.get('fichier_source', tableau_data.get('source', 'Source inconnue')),
            'feuille': tableau_data.get('nom_feuille', 'N/A'),
            'description': self._generer_description_contexte(tableau_data, df),
            'nb_lignes': len(df),
            'nb_colonnes': len(df.columns),
            'range_bloc': tableau_data.get('range_bloc', 'N/A')
        })

        return df

    def _generer_description_contexte(self, tableau_data: Dict, df: pd.DataFrame) -> str:
        """
        Génère une description contextuelle basée sur les données fournies.

        Cette méthode analyse un dictionnaire contenant des informations de titre et
        un DataFrame pour extraire ou générer une description textuelle pertinente.
        La description varie selon les mots-clés présents dans le titre ou les colonnes
        du DataFrame.

        :param tableau_data: Dictionnaire contenant des métadonnées comme le titre.
            Les clés peuvent inclure 'titre_contextuel'.
        :type tableau_data: Dict
        :param df: DataFrame contenant des données structurées utilisées pour
            affiner la description contextuelle.
        :type df: pd.DataFrame
        :return: Une chaîne décrivant contextuellement les données traitées en
            fonction des règles de correspondance.
        :rtype: str
        """

        titre = tableau_data.get('titre_contextuel', '')

        # Analyser le contenu pour générer une description
        if 'ingénieur' in titre.lower():
            if any('femme' in str(col).lower() for col in df.columns):
                return "Statistiques des ingénieurs avec répartition par genre"
            elif any('ville' in str(col).lower() for col in df.columns):
                return "Répartition géographique des ingénieurs"
            else:
                return "Données statistiques sur les ingénieurs"
        elif 'diplôm' in titre.lower():
            return "Statistiques de diplômés"
        elif any(term in titre.lower() for term in ['population', 'démograph']):
            return "Données démographiques"
        elif any(term in titre.lower() for term in ['ville', 'région', 'géograph']):
            return "Données géographiques"
        else:
            return f"Données statistiques - {titre}"
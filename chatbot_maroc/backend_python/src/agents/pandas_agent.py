from typing import Dict
import pandas as pd


# =============================================================================
# FONCTIONS UTILES AGENTS CODE
# =============================================================================

class SimplePandasAgent:
    """Agent simple pour générer et exécuter du code pandas"""

    def __init__(self, gemini_model):
        self.gemini_model = gemini_model

    def creer_dataframe_propre(self, tableau_data: Dict) -> pd.DataFrame:
        """Crée un DataFrame propre à partir des données de tableau avec métadonnées"""

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
            'source': tableau_data.get('fichier_source', 'Source inconnue'),
            'feuille': tableau_data.get('nom_feuille', 'N/A'),
            'description': self._generer_description_contexte(tableau_data, df),
            'nb_lignes': len(df),
            'nb_colonnes': len(df.columns),
            'range_bloc': tableau_data.get('range_bloc', 'N/A')
        })

        return df

    def _generer_description_contexte(self, tableau_data: Dict, df: pd.DataFrame) -> str:
        """Génère une description contextuelle du tableau"""

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
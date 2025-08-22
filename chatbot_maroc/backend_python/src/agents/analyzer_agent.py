import re
import pandas as pd
from typing import Dict, List
from google.genai import types
from google import genai
from ..core.state import ChatbotState
from dotenv import load_dotenv
import os
from ..utils.message_to_front import _send_to_frontend
from ..core.memory_store import get_user_context
import sys

load_dotenv()


class AnalyzerAgent:
    """Agent analyseur pour déterminer le type de réponse nécessaire avec historique utilisateur"""

    def __init__(self, gemini_model, chatbot_instance):
        self.gemini_model = gemini_model
        self.chatbot = chatbot_instance

    def execute(self, state: ChatbotState) -> ChatbotState:
        """Point d'entrée principal de l'agent"""
        print(f"[DEBUG {self.__class__.__name__}] self.chatbot.user_permissions: {self.chatbot.user_permissions}",file=sys.stderr)
        return self.agent_analyseur(state)

    def agent_analyseur(self, state: ChatbotState) -> ChatbotState:
        """Agent analyseur avec gestion d'erreurs robuste"""

        self.chatbot._log("Agent Analyseur: Début de l'analyse avec historique", state)
        session_id = state['session_id']

        try:
            _send_to_frontend(session_id, f"Agent Analyse: Début Analyse sur '{state['question_utilisateur'][:50]}...'")
        except Exception as e:
            print(f"Warning: Envoi frontend échoué: {e}")

        # Récupérer les informations utilisateur
        username, email = self._extract_user_info(state)

        # Validation des prérequis
        if not state.get('tableaux_pour_upload'):
            state['besoin_calculs'] = False
            state['excel_empty'] = True  # indicateur pour la synthèse/flux
            self.chatbot._log("Analyzer: aucun tableau Excel à analyser (on laisse la main au PDF)", state)

            return state

        # Création des DataFrames avec validation robuste
        try:
            state['dataframes'] = self._creer_dataframes_valides(state['tableaux_pour_upload'], state)
            if not state['dataframes']:
                state['besoin_calculs'] = False
                state['reponse_finale'] = "Impossible de traiter les données trouvées."
                return state
        except Exception as e:
            self.chatbot._log_error(f"Création DataFrames: {str(e)}", state)
            state['besoin_calculs'] = False
            state['reponse_finale'] = "Erreur lors du traitement des données."
            return state

        # Préparation du contexte avec gestion d'erreurs
        try:
            contexte_complet = self._preparer_contexte_avec_metadata(state)
        except Exception as e:
            self.chatbot._log_error(f"Préparation contexte: {e}", state)
            contexte_complet = "DONNÉES DISPONIBLES POUR L'ANALYSE:\nTableaux de données statistiques du Maroc\n"

        # Récupérer l'historique utilisateur avec fallback
        historique_contexte = ""
        try:
            if username and email:
                historique_contexte = get_user_context(username, email)
                if historique_contexte and "Aucune conversation précédente" not in historique_contexte:
                    self.chatbot._log(f"Historique utilisateur récupéré pour {username}", state)
                    try:
                        _send_to_frontend(session_id, f"Historique récupéré pour {username}")
                    except:
                        pass
                else:
                    self.chatbot._log(f"Première conversation pour {username}", state)
        except Exception as e:
            self.chatbot._log_error(f"Récupération historique: {e}", state)
            historique_contexte = ""

        # Variables pour le nettoyage
        fichier_gemini = []
        client = None

        # BLOC PRINCIPAL avec gestion d'erreurs COMPLÈTE
        try:
            # Étape 1: Création des fichiers CSV
            fichier_csv = self._creer_csvs_pour_gemini(state['dataframes'], state)
            if not fichier_csv:
                raise Exception("Aucun fichier CSV créé")

            # Étape 2: Upload vers Gemini
            fichier_gemini, client = self._upload_fichier_to_gemini(fichier_csv, state)
            state['fichiers_gemini'] = fichier_gemini

            # Étape 3: Préparation du prompt AMÉLIORÉ
            prompt_unifie = self._creer_prompt_ameliore(state, contexte_complet, historique_contexte)

            # Étape 4: Notification frontend
            try:
                _send_to_frontend(session_id, "Génération de réponse...")
            except:
                pass

            # Étape 5: Préparation du contenu pour Gemini
            content = [prompt_unifie]
            content.extend(fichier_gemini)


            # Étape 6: Appel à Gemini avec gestion d'erreurs
            response = self._call_gemini_with_retry(client, content, state)

            # Étape 7: Extraction AMÉLIORÉE du contenu
            answer_text = self._extraire_contenu_gemini_robuste(response, state)

            if not answer_text:
                # FALLBACK SIMPLE : générer une réponse basique
                self.chatbot._log("Fallback: génération réponse basique", state)
                state['besoin_calculs'] = False
                state['reponse_finale'] = f"""Analyse des données en cours.

            Question: {state['question_utilisateur']}

            Les données sont disponibles mais le service d'analyse rencontre une difficulté technique temporaire.
            Veuillez reformuler votre question ou réessayer."""
                return state

            state['reponse_analyseur_brute'] = answer_text

            # Log de la réponse réussie
            self.chatbot._log(f"Réponse Gemini extraite avec succès: {len(answer_text)} caractères", state)
            self.chatbot._log(f"Aperçu: '{answer_text[:200]}...'", state)

            # Parsing AMÉLIORÉ avec validation
            success = self._parse_gemini_response_ameliore(answer_text, state, historique_contexte)

            if not success:
                self._apply_fallback_strategy_ameliore(state, historique_contexte, answer_text)

        except Exception as e:
            # GESTION D'ERREUR UNIFIÉE pour tout le bloc principal
            self.chatbot._log_error(f"Erreur dans le traitement principal: {str(e)}", state)
            self._handle_gemini_error(e, state)

        finally:
            # Nettoyage garanti - s'exécute TOUJOURS
            if fichier_gemini and client:
                try:
                    self._nettoyer_fichiers_gemini(fichier_gemini, client, state)
                except Exception as e:
                    self.chatbot._log_error(f"Erreur nettoyage: {e}", state)

        return state

    def _creer_prompt_ameliore(self, state, contexte_complet, historique_contexte):
        """Crée un prompt plus directif et structuré"""

        prompt = f"""ROLE: Tu es un expert en analyse de données du Maroc. Tu dois ABSOLUMENT répondre dans un format spécifique.

{historique_contexte}

QUESTION UTILISATEUR: {state['question_utilisateur']}

{contexte_complet}

INSTRUCTIONS CRITIQUES - RESPECTE EXACTEMENT UN DE CES DEUX FORMATS :

=== FORMAT 1 : POUR CALCULS COMPLEXES ===
TYPE: CALCULS
HISTORIQUE: [Comment l'historique influence cette analyse]
ETAPES:
1. [Première étape précise]
2. [Deuxième étape précise]  
3. [Troisième étape précise]
ALGORITHME:
```python
# Code Python utilisant df0, df1, df2, etc.
# Exemple: resultat = df0.groupby('colonne').sum()
```

=== FORMAT 2 : POUR RÉPONSE DIRECTE ===
TYPE: DIRECT
HISTORIQUE: [Comment l'historique influence cette réponse]
REPONSE: [Réponse complète et détaillée avec sources]

RÈGLES ABSOLUES:
- Commence TOUJOURS par "TYPE: CALCULS" ou "TYPE: DIRECT"
- Si la question nécessite des calculs/agrégations/comparaisons complexes → FORMAT 1
- Si la question est factuelle et directe → FORMAT 2
- Inclure TOUJOURS la section HISTORIQUE
- Pour FORMAT 1: fournir un code Python fonctionnel
- Pour FORMAT 2: donner une réponse complète avec sources

ANALYSE ET RÉPONSE:"""

        return prompt

    def _extraire_contenu_gemini_robuste(self, response, state):
        """Extraction simple et directe du contenu Gemini"""

        try:
            # MÉTHODE 1: response.text directement (le plus simple)
            if hasattr(response, 'text') and response.text:
                text_content = response.text.strip()
                if len(text_content) > 10:
                    self.chatbot._log(f"Contenu extrait directement: {len(text_content)} chars", state)
                    return text_content

            # MÉTHODE 2: Si pas de .text, essayer la méthode classique mais simplifiée
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'content') and candidate.content:
                    if hasattr(candidate.content, 'parts') and candidate.content.parts:
                        # Extraire tout le texte des parts
                        all_text = []
                        for part in candidate.content.parts:
                            if hasattr(part, 'text') and part.text:
                                all_text.append(part.text)

                        if all_text:
                            combined_text = '\n'.join(all_text).strip()
                            if len(combined_text) > 10:
                                self.chatbot._log(f"Contenu extrait des parts: {len(combined_text)} chars", state)
                                return combined_text

            # Si rien ne marche, retourner None
            self.chatbot._log_error("Aucun contenu extractible", state)
            return None

        except Exception as e:
            self.chatbot._log_error(f"Erreur extraction: {e}", state)
            return None

    def _parse_gemini_response_ameliore(self, answer_text, state, historique_contexte):
        """Parsing amélioré avec patterns multiples et flexibles - VERSION CORRIGÉE"""

        # PROTECTION CONTRE None - CRITIQUE ET RENFORCÉE
        if answer_text is None:
            self.chatbot._log_error("answer_text est None dans parsing", state)
            return False

        if not isinstance(answer_text, str):
            self.chatbot._log_error(f"answer_text n'est pas string: {type(answer_text)}", state)
            return False

        answer_text = answer_text.strip()
        if len(answer_text) < 10:
            self.chatbot._log_error(f"answer_text trop court: {len(answer_text)} chars", state)
            return False

        try:
            self.chatbot._log(f"Parsing de '{answer_text[:150]}...'", state)

            patterns_calculs = [
                r'TYPE\s*:\s*CALCULS',
                r'CALCULS_NECESSAIRES',
                r'FORMAT\s*1',
                r'DECISION\s*:\s*CALCULS',
                r'ETAPES?\s*:',
                r'ALGORITHME\s*:',
                r'```python',
                r'df\d+\.',
            ]

            patterns_direct = [
                r'TYPE\s*:\s*DIRECT',
                r'REPONSE_DIRECTE',
                r'FORMAT\s*2',
                r'DECISION\s*:\s*REPONSE',
                r'REPONSE\s*:',
                r'D\'après.*données',
                r'Selon.*statistiques',
            ]

            is_calculs = False
            is_direct = False

            try:
                # Vérification avec patterns flexibles - SÉCURISÉE ET CORRIGÉE
                if answer_text and isinstance(answer_text, str):  # Protection double
                    for pattern in patterns_calculs:
                        try:
                            if re.search(pattern, answer_text, re.IGNORECASE):
                                is_calculs = True
                                break
                        except Exception as e:
                            self.chatbot._log_error(f"Erreur pattern calculs '{pattern}': {e}", state)
                            continue

                    for pattern in patterns_direct:
                        try:
                            if re.search(pattern, answer_text, re.IGNORECASE):
                                is_direct = True
                                break
                        except Exception as e:
                            self.chatbot._log_error(f"Erreur pattern direct '{pattern}': {e}", state)
                            continue

            except Exception as e:
                self.chatbot._log_error(f"Erreur dans détection patterns: {e}", state)
                is_calculs = False
                is_direct = False

            self.chatbot._log(f"Détection - CALCULS: {is_calculs}, DIRECT: {is_direct}", state)

            # TRAITEMENT CALCULS avec protection
            if is_calculs and not is_direct:
                try:
                    _send_to_frontend(state['session_id'], "Extraction des étapes de calcul...")
                except:
                    pass

                etapes, algorithme = self._extraire_etapes_et_algo_flexible(answer_text)

                if etapes and algorithme:
                    state['besoin_calculs'] = True
                    state['instruction_calcul'] = etapes
                    state['algo_genere'] = algorithme
                    self.chatbot._log("Calculs extraits avec succès", state)
                    return True

            # TRAITEMENT DIRECT avec protection
            elif is_direct:
                try:
                    _send_to_frontend(state['session_id'], "Extraction de la réponse directe...")
                except:
                    pass

                reponse = self._extraire_reponse_directe_flexible(answer_text)
                if reponse and isinstance(reponse, str) and len(reponse.strip()) > 15:
                    state['besoin_calculs'] = False
                    state['reponse_finale'] = reponse
                    self.chatbot._log("Réponse directe extraite", state)
                    return True

            self.chatbot._log("Aucun format reconnu avec certitude", state)
            return False

        except Exception as e:
            self.chatbot._log_error(f"Erreur parsing amélioré: {e}", state)
            return False

    def _extraire_etapes_et_algo_flexible(self, texte):
        """Extraction flexible des étapes et algorithmes avec multiples patterns"""

        # PROTECTION CRITIQUE contre None - CORRIGÉE
        if texte is None:
            self.chatbot._log_error("Texte None dans extraction étapes/algo", {})
            return None, None

        if not isinstance(texte, str):
            self.chatbot._log_error(f"Texte n'est pas string: {type(texte)}", {})
            return None, None

        if len(texte) < 10:
            return None, None

        try:
            # PATTERNS MULTIPLES pour étapes
            patterns_etapes = [
                r'ETAPES?\s*:?\s*\n(.*?)(?=ALGORITHME|```|$)',
                r'(?:1\.|2\.|3\.)(.*?)(?=ALGORITHME|```|$)',
                r'HISTORIQUE:(.*?)(?=ETAPES|ALGORITHME|$).*?ETAPES?:?\s*(.*?)(?=ALGORITHME|```|$)',
                r'(\d+\..*?)(?=ALGORITHME|```|$)',
            ]

            patterns_algo = [
                r'ALGORITHME\s*:?\s*\n(.*?)(?=```|$)',
                r'```python\s*(.*?)```',
                r'```\s*(.*?)```',
                r'(?:# |df\d+)(.*?)(?=\n\n|$)',
                r'(df\d+\..*?)(?=\n[A-Z]|$)',
            ]

            etapes = None
            algorithme = None

            # Extraction étapes avec validation et protection RENFORCÉE
            for pattern in patterns_etapes:
                try:
                    # PROTECTION: vérifier que texte n'est pas None ET est string
                    if texte is None or not isinstance(texte, str):
                        break

                    match = re.search(pattern, texte, re.DOTALL | re.IGNORECASE)
                    if match:
                        # Protection contre les groupes None
                        if match.lastindex and match.lastindex >= 1:
                            extracted = match.group(1) if match.lastindex == 1 else match.group(match.lastindex)
                        else:
                            extracted = match.group(0) if match.group(0) else None

                        # VALIDATION RENFORCÉE
                        if extracted and isinstance(extracted, str) and len(extracted.strip()) > 10:
                            etapes = extracted.strip()
                            self.chatbot._log("Étapes extraites avec pattern flexible", {})
                            break
                except Exception as e:
                    self.chatbot._log_error(f"Erreur pattern étapes: {e}", {})
                    continue

            # Extraction algorithme avec validation et protection RENFORCÉE
            for pattern in patterns_algo:
                try:
                    # PROTECTION: vérifier que texte n'est pas None ET est string
                    if texte is None or not isinstance(texte, str):
                        break

                    match = re.search(pattern, texte, re.DOTALL | re.IGNORECASE)
                    if match:
                        extracted = match.group(1) if match.group(1) else None
                        # VALIDATION RENFORCÉE
                        if extracted and isinstance(extracted, str) and len(extracted.strip()) > 5:
                            algorithme = extracted.strip()
                            self.chatbot._log("Algorithme extrait avec pattern flexible", {})
                            break
                except Exception as e:
                    self.chatbot._log_error(f"Erreur pattern algo: {e}", {})
                    continue

            # FALLBACK: Analyse ligne par ligne avec protection RENFORCÉE
            if (not etapes or not algorithme) and texte and isinstance(texte, str):
                try:
                    # Protection contre split sur None
                    lignes = texte.split('\n') if texte and isinstance(texte, str) else []
                    lignes = [l.strip() for l in lignes if l and isinstance(l, str) and l.strip()]

                    etapes_lignes = []
                    algo_lignes = []
                    capture_algo = False

                    for ligne in lignes:
                        # PROTECTION RENFORCÉE pour chaque ligne
                        if not ligne or not isinstance(ligne, str):
                            continue

                        try:
                            # Protection pour les opérations 'in' sur ligne
                            ligne_lower = ligne.lower() if ligne and isinstance(ligne, str) else ""

                            # CORRECTION CRITIQUE: vérifier que ligne_lower n'est pas None
                            if ligne_lower and isinstance(ligne_lower, str):
                                if any(keyword in ligne_lower for keyword in ['algorithme', '```', 'df']):
                                    capture_algo = True
                                    # Protection supplémentaire pour ligne
                                    if ligne and isinstance(ligne, str) and any(
                                            keyword in ligne for keyword in ['df', '#']):
                                        algo_lignes.append(ligne)
                                elif capture_algo and ligne and isinstance(ligne, str):
                                    if (any(keyword in ligne for keyword in ['df', '#']) or ligne.startswith(' ')):
                                        algo_lignes.append(ligne)
                                elif any(keyword in ligne_lower for keyword in ['étape', 'step']) or (
                                        ligne and isinstance(ligne, str) and re.search(r'\d+\.', ligne)):
                                    etapes_lignes.append(ligne)

                        except Exception as e:
                            self.chatbot._log_error(f"Erreur traitement ligne: {e}", {})
                            continue

                    if not etapes and etapes_lignes:
                        etapes = '\n'.join(etapes_lignes[:5])
                    if not algorithme and algo_lignes:
                        algorithme = '\n'.join(algo_lignes[:5])

                except Exception as e:
                    self.chatbot._log_error(f"Erreur fallback ligne par ligne: {e}", {})

            # Validation finale avec protection RENFORCÉE
            try:
                if etapes and isinstance(etapes, str) and len(etapes) < 10:
                    etapes = None
                if algorithme and isinstance(algorithme, str) and len(algorithme) < 5:
                    algorithme = None
            except Exception as e:
                self.chatbot._log_error(f"Erreur validation finale: {e}", {})
                etapes = None
                algorithme = None

            return etapes, algorithme

        except Exception as e:
            self.chatbot._log_error(f"Erreur critique extraction flexible: {e}", {})
            return None, None

    def _extraire_reponse_directe_flexible(self, texte):
        """Extraction flexible de la réponse directe - VERSION CORRIGÉE"""

        # PROTECTION INITIALE RENFORCÉE
        if texte is None or not isinstance(texte, str) or len(texte) < 10:
            return None

        try:
            patterns_reponse = [
                r'REPONSE\s*:?\s*(.*?)(?=\n\s*===|$)',
                r'TYPE\s*:\s*DIRECT.*?REPONSE\s*:?\s*(.*?)(?=\n\s*===|$)',
                r'HISTORIQUE:.*?REPONSE\s*:?\s*(.*?)(?=\n\s*===|$)',
                r'(?:HISTORIQUE:.*?\n)?(.*?)(?=\n\s*Sources|$)',
                r'(?:TYPE.*?\n|HISTORIQUE.*?\n)+(.*?)$',
            ]

            for pattern in patterns_reponse:
                try:
                    # PROTECTION: vérifier texte avant regex
                    if not texte or not isinstance(texte, str):
                        continue

                    match = re.search(pattern, texte, re.DOTALL | re.IGNORECASE)
                    if match and match.group(1):
                        reponse = match.group(1).strip()
                        # Validation du contenu RENFORCÉE
                        if reponse and isinstance(reponse, str) and len(reponse) > 15 and not reponse.isspace():
                            # Nettoyer la réponse
                            reponse = re.sub(r'\n+', '\n', reponse)
                            reponse = re.sub(r'^\s*[-*•]\s*', '', reponse, flags=re.MULTILINE)
                            return reponse.strip()
                except Exception as e:
                    self.chatbot._log_error(f"Erreur pattern reponse: {e}", {})
                    continue

            # FALLBACK ULTIME avec protection renforcée
            if texte and isinstance(texte, str):
                lignes = texte.split('\n')
                contenu_lignes = []
                skip_headers = True

                for ligne in lignes:
                    # PROTECTION pour chaque ligne
                    if not ligne or not isinstance(ligne, str):
                        continue

                    ligne = ligne.strip()
                    if not ligne:
                        continue

                    try:
                        # CORRECTION CRITIQUE: protection pour les opérations 'in'
                        ligne_upper = ligne.upper() if ligne and isinstance(ligne, str) else ""

                        if skip_headers and ligne_upper and isinstance(ligne_upper, str):
                            if any(header in ligne_upper for header in ['TYPE:', 'HISTORIQUE:', 'REPONSE:']):
                                if 'REPONSE:' in ligne_upper:
                                    skip_headers = False
                                    # Inclure le contenu après REPONSE: s'il existe
                                    if ':' in ligne:
                                        content = ligne.split(':', 1)[1].strip()
                                        if content and isinstance(content, str):
                                            contenu_lignes.append(content)
                                continue

                        if not skip_headers:
                            contenu_lignes.append(ligne)

                    except Exception as e:
                        self.chatbot._log_error(f"Erreur traitement ligne fallback: {e}", {})
                        continue

                if contenu_lignes:
                    contenu = '\n'.join(contenu_lignes).strip()
                    if contenu and isinstance(contenu, str) and len(contenu) > 15:
                        return contenu

            return None

        except Exception as e:
            self.chatbot._log_error(f"Erreur extraction reponse directe: {e}", {})
            return None

    def _apply_fallback_strategy_ameliore(self, state, historique_contexte, answer_text):
        """Stratégie de fallback améliorée avec analyse intelligente - VERSION CORRIGÉE"""

        self.chatbot._log("Application stratégie fallback améliorée", state)

        # PROTECTION INITIALE pour tous les paramètres
        question = state.get('question_utilisateur', '').lower() if state.get('question_utilisateur') else ''
        texte_brut = answer_text.lower() if answer_text and isinstance(answer_text, str) else ""

        # Indicateurs de calculs nécessaires
        calcul_indicators = [
            'total', 'combien', 'pourcentage', 'compare', 'évolution',
            'moyenne', 'maximum', 'minimum', 'calcul', 'analyse',
            'statistique', 'tendance', 'croissance', 'répartition'
        ]

        # Indicateurs de réponse directe
        direct_indicators = [
            'qu\'est-ce que', 'définition', 'signifie', 'explique',
            'liste', 'nom', 'qui est', 'où se trouve', 'quand'
        ]

        # PROTECTION pour les opérations 'in' avec validation
        question_needs_calculs = False
        question_is_direct = False
        content_has_code = False
        content_is_explanatory = False

        try:
            if question and isinstance(question, str):
                question_needs_calculs = any(indicator in question for indicator in calcul_indicators)
                question_is_direct = any(indicator in question for indicator in direct_indicators)

            if texte_brut and isinstance(texte_brut, str):
                content_has_code = any(keyword in texte_brut for keyword in ['df', 'pandas', 'groupby', 'sum', 'mean'])
                content_is_explanatory = len(texte_brut) > 100 and not content_has_code

        except Exception as e:
            self.chatbot._log_error(f"Erreur analyse fallback: {e}", state)
            # Valeurs par défaut sécurisées
            question_needs_calculs = False
            question_is_direct = True
            content_has_code = False
            content_is_explanatory = True

        # DÉCISION INTELLIGENTE
        if question_needs_calculs or content_has_code:
            # Mode calculs avec protection
            state['besoin_calculs'] = True

            user_question = state.get('question_utilisateur', 'Question non disponible')
            instruction_base = f"Analyser les données pour répondre à: {user_question}"

            if (historique_contexte and isinstance(historique_contexte, str) and
                    "Aucune conversation précédente" not in historique_contexte):
                instruction_base += "\n(Tenir compte du contexte historique des conversations précédentes)"

            state['instruction_calcul'] = instruction_base

            # Algorithme intelligent basé sur la question avec protection
            if question and isinstance(question, str):
                if 'total' in question or 'somme' in question:
                    algo = "# Calculer les totaux\nresultat = df0.sum(numeric_only=True)"
                elif 'moyenne' in question:
                    algo = "# Calculer les moyennes\nresultat = df0.mean(numeric_only=True)"
                elif 'compare' in question or 'comparaison' in question:
                    algo = "# Comparer les données\nresultat = df0.groupby(df0.columns[0]).sum()"
                else:
                    algo = "# Analyser les données selon la question\nresultat = df0.describe()"
            else:
                algo = "# Analyser les données\nresultat = df0.describe()"

            state['algo_genere'] = algo
            self.chatbot._log("Fallback intelligent vers calculs appliqué", state)

        else:
            # Mode réponse directe avec protection
            state['besoin_calculs'] = False

            if answer_text and isinstance(answer_text, str) and len(answer_text) > 20:
                # Utiliser le contenu brut nettoyé avec protection
                reponse = answer_text.strip()
                # Nettoyer les artefacts de format avec protection
                try:
                    reponse = re.sub(r'TYPE\s*:.*?\n', '', reponse, flags=re.IGNORECASE)
                    reponse = re.sub(r'HISTORIQUE\s*:.*?\n', '', reponse, flags=re.IGNORECASE)
                    reponse = re.sub(r'\*\*.*?\*\*', '', reponse)
                    reponse = re.sub(r'\n+', '\n', reponse)
                except Exception as e:
                    self.chatbot._log_error(f"Erreur nettoyage reponse: {e}", state)

                if reponse and isinstance(reponse, str) and len(reponse.strip()) > 15:
                    state['reponse_finale'] = reponse.strip()
                else:
                    state['reponse_finale'] = self._generer_reponse_fallback_generique(state)
            else:
                state['reponse_finale'] = self._generer_reponse_fallback_generique(state)

            self.chatbot._log("Fallback intelligent vers réponse directe appliqué", state)

    def _generer_reponse_fallback_generique(self, state):
        """Génère une réponse de fallback générique mais informative"""

        tableaux_info = []
        for i, tableau in enumerate(state.get('tableaux_pour_upload', [])):
            titre = tableau.get('titre_contextuel', f'Tableau {i + 1}')
            source = tableau.get('fichier_source', 'N/A')
            tableaux_info.append(f"• {titre} ({source})")

        sources_text = '\n'.join(tableaux_info) if tableaux_info else "Aucune source disponible"

        return f"""Analyse des données en cours - Le système traite votre demande.

Question analysée: "{state['question_utilisateur']}"

Sources consultées:
{sources_text}

Le système d'analyse rencontre une difficulté de traitement de format. 
Veuillez reformuler votre question de manière plus spécifique ou réessayer.

Permissions actives: {', '.join(state.get('user_permissions', []))}"""

    def _call_gemini_with_retry(self, client, content, state, max_retries=3):
        """Appelle Gemini avec retry automatique et configuration optimisée"""

        import time

        for attempt in range(max_retries):
            try:
                self.chatbot._log(f"Tentative Gemini {attempt + 1}/{max_retries}", state)

                # Configuration optimisée pour éviter les thoughts excessifs
                response = client.models.generate_content(
                    model="gemini-2.5-pro",
                    contents=content,
                    config=types.GenerateContentConfig(
                        temperature=0.1,  # Plus déterministe
                        candidate_count=1,
                        max_output_tokens=2048,
                        # Réduire l'usage des thoughts
                        thinking_config=types.ThinkingConfig(include_thoughts=False)
                    )
                )

                # Vérifier que la réponse est valide
                if response and response.candidates and len(response.candidates) > 0:
                    return response
                else:
                    raise Exception("Réponse Gemini invalide ou vide")

            except Exception as e:
                error_msg = str(e)
                self.chatbot._log_error(f"Erreur Gemini tentative {attempt + 1}: {error_msg}", state)

                # Si c'est une erreur 500, attendre avant de retry
                if "500" in error_msg or "INTERNAL" in error_msg:
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt  # Backoff exponentiel
                        self.chatbot._log(f"Attente {wait_time}s avant retry...", state)
                        time.sleep(wait_time)
                        continue

                # Pour les autres erreurs, ne pas retry
                if attempt == max_retries - 1:
                    raise e

        raise Exception("Échec de tous les appels Gemini")

    def _handle_gemini_error(self, error, state):
        """Gère les différents types d'erreurs avec plus de contexte"""

        error_msg = str(error)

        if "500" in error_msg or "INTERNAL" in error_msg:
            state['besoin_calculs'] = False
            state['reponse_finale'] = """Service d'analyse temporairement indisponible. 

Les données sont accessibles mais l'analyse avancée rencontre une difficulté technique.
Veuillez réessayer dans quelques minutes ou reformuler votre question.

Sources disponibles : données officielles du Maroc"""

        elif "quota" in error_msg.lower() or "limit" in error_msg.lower():
            state['besoin_calculs'] = False
            state['reponse_finale'] = """Limite d'utilisation temporairement atteinte.

Le service d'analyse est temporairement saturé. 
Veuillez réessayer dans quelques minutes.

Les données restent accessibles en mode consultation."""

        else:
            state['besoin_calculs'] = False
            state['reponse_finale'] = f"""Erreur technique lors de l'analyse.

Détails: {error_msg[:150]}...

Veuillez reformuler votre question ou réessayer plus tard.
Les données sont disponibles mais l'analyse automatique a échoué."""

    # [Le reste des méthodes restent identiques]
    def _extract_user_info(self, state: ChatbotState) -> tuple:
        """Extrait les informations utilisateur du state"""
        try:
            session_id = state.get('session_id', '')
            username = state.get('username')
            email = state.get('email')

            if username and email:
                return username, email

            user_role = state.get('user_role', '')

            if session_id:
                if 'admin' in session_id or user_role == 'admin':
                    return 'admin_user', 'admin@amdie.ma'
                elif 'employee' in session_id or user_role == 'employee':
                    return 'employee_user', 'employee@amdie.ma'
                else:
                    return 'public_user', 'public@amdie.ma'

            return None, None

        except Exception as e:
            self.chatbot._log_error(f"Erreur extraction info utilisateur: {e}", state)
            return None, None

    def _preparer_contexte_avec_metadata(self, state: ChatbotState) -> str:
        """Prépare un contexte enrichi avec toutes les métadonnées"""

        contexte = "DONNÉES DISPONIBLES POUR L'ANALYSE:\n\n"

        tableaux_a_analyser = state.get('tableaux_pour_upload', [])
        dataframes_a_analyser = state.get('dataframes', [])

        for i, (tableau, df) in enumerate(zip(tableaux_a_analyser, dataframes_a_analyser)):
            titre = tableau.get('titre_contextuel', f'Tableau {i}')
            source = tableau.get('fichier_source', 'N/A')
            feuille = tableau.get('nom_feuille', 'N/A')

            df_attrs = getattr(df, 'attrs', {})

            contexte += f"""DATAFRAME df{i}: "{titre}"
   Source: {source} -> Feuille "{feuille}" 
   Contenu: {df_attrs.get('description', 'Données statistiques')}
   Structure: {len(df)} lignes × {len(df.columns)} colonnes

"""

        contexte += "APERÇU DES DONNÉES:\n"
        for i, df in enumerate(dataframes_a_analyser[:3]):
            if not df.empty:
                contexte += f"   df{i} (premiers éléments): {', '.join(str(col) for col in df.columns[:3])}{'...' if len(df.columns) > 3 else ''}\n"

        return contexte

    def _creer_dataframes_valides(self, tableaux_charges: List[Dict], state: ChatbotState) -> List[pd.DataFrame]:
        """Crée des DataFrames validés avec métadonnées"""
        dataframes = []

        for i, tableau in enumerate(tableaux_charges):
            try:
                df = self.chatbot.pandas_agent.creer_dataframe_propre(tableau)
                if df is not None and not df.empty:
                    df.attrs.update({
                        'titre': tableau.get('titre_contextuel', f'Tableau {i}'),
                        'source': tableau.get('fichier_source', 'N/A'),
                        'feuille': tableau.get('nom_feuille', 'N/A'),
                        'description': tableau.get('description', 'Données statistiques'),
                        'nb_lignes': len(df),
                        'nb_colonnes': len(df.columns)
                    })

                    dataframes.append(df)
                    self.chatbot._log(f"DataFrame {i} créé: {df.shape}", state)
                else:
                    self.chatbot._log(f"DataFrame {i} vide", state)
            except Exception as e:
                self.chatbot._log_error(f"Création DataFrame {i}: {str(e)}", state)

        return dataframes

    def _creer_csvs_pour_gemini(self, dataframes: List[pd.DataFrame], state: ChatbotState) -> List[str]:
        """Crée des fichiers CSV temporaires pour chaque DataFrame"""

        fichiers_csv = []

        try:
            for i, df in enumerate(dataframes):
                if df is not None and not df.empty:
                    nom_fichier = f'df{i}_analysis.csv'
                    df.to_csv(nom_fichier, index=False, encoding='utf-8')
                    fichiers_csv.append(nom_fichier)
                    self.chatbot._log(f"CSV créé: {nom_fichier} {df.shape}", state)
                else:
                    self.chatbot._log(f"DataFrame {i} vide ignoré", state)

        except Exception as e:
            self.chatbot._log_error(f"Erreur création CSV: {str(e)}", state)
            return []

        return fichiers_csv

    def _upload_fichier_to_gemini(self, fichiers_csv: List[str], state: ChatbotState):
        API_KEY = os.getenv("GEMINI_API_KEY")
        client = genai.Client(api_key=API_KEY)

        fichiers_gemini = []
        for fichier_csv in fichiers_csv:
            try:
                fichier_uploade = client.files.upload(file=fichier_csv)
                fichiers_gemini.append(fichier_uploade)
                self.chatbot._log(f"Fichier uploadé: {fichier_csv}", state)
            except Exception as e:
                self.chatbot._log_error(f"Erreur upload {fichier_csv}: {str(e)}", state)
                raise e

        self._nettoyer_csvs_temporaires(fichiers_csv, state)
        return fichiers_gemini, client

    def _nettoyer_fichiers_gemini(self, fichiers_gemini: List, client, state: ChatbotState):
        """Supprime les fichiers uploadés chez Gemini"""

        for fichier in fichiers_gemini:
            try:
                client.files.delete(name=fichier.name)
                self.chatbot._log(f"Fichier Gemini supprimé: {fichier.name}", state)
            except Exception as e:
                self.chatbot._log_error(f"Erreur suppression Gemini {fichier.name}: {str(e)}", state)

    def _nettoyer_csvs_temporaires(self, fichiers_csv: List[str], state: ChatbotState):
        """Supprime les fichiers CSV temporaires"""

        for fichier in fichiers_csv:
            try:
                if os.path.exists(fichier):
                    os.remove(fichier)
                    self.chatbot._log(f"CSV local supprimé: {fichier}", state)
            except Exception as e:
                self.chatbot._log_error(f"Erreur suppression {fichier}: {str(e)}", state)
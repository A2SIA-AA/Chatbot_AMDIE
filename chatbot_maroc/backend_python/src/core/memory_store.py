import sqlite3
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class ConversationMemoryStore:
    """
    Classe pour gérer le stockage des conversations en utilisant SQLite.

    Cette classe fournit des fonctionnalités pour enregistrer, récupérer et analyser
    les conversations des utilisateurs. Elle inclut également des méthodes pour nettoyer
    les conversations anciennes et formater les données pour des besoins spécifiques,
    comme le contexte des agents d'intelligence artificielle.

    :ivar db_path: Chemin vers la base de données SQLite utilisée pour stocker les conversations.
    :type db_path: str
    """

    def __init__(self, db_path: str = "conversations.db"):
        """
        Initialise le store SQLite

        Args:
            db_path: Chemin vers la base de données SQLite
        """
        self.db_path = db_path
        self._init_database()
        logger.info(f" ConversationMemoryStore initialisé: {os.path.abspath(db_path)}")

    def _init_database(self):
        """
        Initialise la base de données pour gérer les conversations et configure les tables nécessaires.

        Cette méthode crée une table `conversations` si elle n'existe pas, ainsi que deux index pour améliorer
        les performances des requêtes fréquemment utilisées. La table `conversations` stocke des informations
        liées aux utilisateurs, y compris leur identifiant, leur email, leurs questions, les réponses qui leur
        sont fournies, les horodatages de ces interactions, ainsi que des informations de session.

        :raises Exception: Si une erreur se produit lors de l'initialisation de la base de données.
        """
        try:
            with self._get_connection() as conn:
                conn.execute("""
                             CREATE TABLE IF NOT EXISTS conversations
                             (
                                 id
                                 INTEGER
                                 PRIMARY
                                 KEY
                                 AUTOINCREMENT,
                                 username
                                 TEXT
                                 NOT
                                 NULL,
                                 email
                                 TEXT
                                 NOT
                                 NULL,
                                 question
                                 TEXT
                                 NOT
                                 NULL,
                                 reponse
                                 TEXT
                                 NOT
                                 NULL,
                                 timestamp
                                 DATETIME
                                 NOT
                                 NULL,
                                 session_id
                                 TEXT,
                                 created_at
                                 DATETIME
                                 DEFAULT
                                 CURRENT_TIMESTAMP
                             )
                             """)

                # Index pour optimiser les requêtes fréquentes
                conn.execute("""
                             CREATE INDEX IF NOT EXISTS idx_user_timestamp
                                 ON conversations(username, email, timestamp DESC)
                             """)

                conn.execute("""
                             CREATE INDEX IF NOT EXISTS idx_session
                                 ON conversations(session_id)
                             """)

                conn.commit()
                logger.info(" Base de données conversations initialisée")

        except Exception as e:
            logger.error(f" Erreur initialisation DB: {e}")
            raise

    @contextmanager
    def _get_connection(self):
        """
        Fournit un gestionnaire de contexte pour obtenir une connexion à une base de
        données SQLite, avec gestion automatisée des transactions et nettoyage en
        cas d'erreur.

        Lorsque le gestionnaire de contexte est utilisé, il établit une connexion avec la
        base de données, permet son utilisation à l'intérieur du bloc de code, et se charge
        de fermer la connexion une fois que le bloc de code est terminé ou en cas
        d'exception.

        :raises Exception: Si une erreur survient pendant l'utilisation de la connexion.
        :return: Un objet connexion SQLite avec `row_factory` configuré pour permettre
                 l'accès aux colonnes par nom.
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            conn.row_factory = sqlite3.Row  # Pour accéder aux colonnes par nom
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            raise e
        finally:
            if conn:
                conn.close()

    def save_conversation(self, username: str, email: str, question: str,
                          reponse: str, session_id: str = None) -> bool:
        """
        Enregistre une conversation dans la base de données. La fonction enregistre
        les informations fournies, telles que le nom d'utilisateur, l'adresse email,
        la question posée, la réponse donnée ainsi qu'un éventuel identifiant de
        session. Le timestamp est automatiquement ajouté lors de l'insertion.

        :param username: Le nom d'utilisateur qui a posé la question
        :type username: str
        :param email: L'adresse email de l'utilisateur
        :type email: str
        :param question: La question posée par l'utilisateur
        :type question: str
        :param reponse: La réponse donnée à l'utilisateur
        :type reponse: str
        :param session_id: L'identifiant de session associé, optionnel
        :type session_id: str, optional
        :return: Retourne True si la conversation a été enregistrée avec succès,
                 False en cas d'échec
        :rtype: bool
        """
        try:
            with self._get_connection() as conn:
                conn.execute("""
                             INSERT INTO conversations
                                 (username, email, question, reponse, timestamp, session_id)
                             VALUES (?, ?, ?, ?, ?, ?)
                             """, (
                                 username,
                                 email,
                                 question,
                                 reponse,
                                 datetime.now(),
                                 session_id
                             ))
                conn.commit()

            logger.info(f" Conversation sauvegardée: {username} ({session_id})")
            return True

        except Exception as e:
            logger.error(f" Erreur sauvegarde conversation: {e}")
            return False

    def get_user_history_24h(self, username: str, email: str, limit: int = 20) -> List[Dict]:
        """
        Récupère l'historique des conversations de l'utilisateur spécifié au cours des
        dernières 24 heures. Les conversations sont triées par ordre décroissant de
        timestamp.

        L'historique est limité par un nombre spécifié.

        :param username: Le nom d'utilisateur de l'utilisateur pour lequel récupérer
            l'historique des conversations.
        :param email: L'adresse email associée à l'utilisateur.
        :param limit: (optionnel) Le nombre maximum de conversations à récupérer. La
            valeur par défaut est 20.
        :return: Une liste de dictionnaires contenant les informations des conversations
            récupérées. Chaque dictionnaire inclut les clés suivantes : 'question',
            'reponse', 'timestamp', et 'session_id'.
        """
        try:
            cutoff_time = datetime.now() - timedelta(hours=24)

            with self._get_connection() as conn:
                cursor = conn.execute("""
                                      SELECT question, reponse, timestamp, session_id
                                      FROM conversations
                                      WHERE username = ?
                                        AND email = ?
                                        AND timestamp >= ?
                                      ORDER BY timestamp DESC
                                          LIMIT ?
                                      """, (username, email, cutoff_time, limit))

                conversations = []
                for row in cursor.fetchall():
                    conversations.append({
                        'question': row['question'],
                        'reponse': row['reponse'],
                        'timestamp': row['timestamp'],
                        'session_id': row['session_id']
                    })

            logger.info(f" Historique récupéré: {len(conversations)} conversations pour {username}")
            return conversations

        except Exception as e:
            logger.error(f" Erreur récupération historique: {e}")
            return []

    def format_history_for_context(self, username: str, email: str, max_conversations: int = 5) -> str:
        """
        Formate l'historique des conversations pour un contexte spécifique en affichant les détails des
        conversations d'un utilisateur au cours des dernières 24 heures.

        :param username: Le nom d'utilisateur pour lequel extraire l'historique des conversations.
        :type username: str
        :param email: L'email de l'utilisateur correspondant au nom d'utilisateur donné.
        :type email: str
        :param max_conversations: Le nombre maximum de conversations à inclure dans le contexte.
            Par défaut, 5.
        :type max_conversations: int
        :return: Une chaîne de caractères formatée contenant l'historique des conversations, ou
            un message indiquant l'absence d'historique.
        :rtype: str
        """
        history = self.get_user_history_24h(username, email, max_conversations)

        if not history:
            return "HISTORIQUE: Aucune conversation précédente dans les 24h.\n"

        context = f"HISTORIQUE DES CONVERSATIONS (24h) - Utilisateur: {username}\n"
        context += "=" * 60 + "\n"

        for i, conv in enumerate(history, 1):
            timestamp = conv['timestamp']
            if isinstance(timestamp, str):
                # Parse si c'est une string
                try:
                    timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                except:
                    timestamp = "N/A"

            context += f"\n[CONVERSATION {i}] - {timestamp}\n"
            context += f"Q: {conv['question']}\n"
            context += f"R: {conv['reponse'][:200]}{'...' if len(conv['reponse']) > 200 else ''}\n"
            context += "-" * 40 + "\n"

        context += f"\nTotal: {len(history)} conversation(s) récente(s)\n"
        context += "=" * 60 + "\n\n"

        return context

    def get_conversation_stats(self, username: str, email: str) -> Dict:
        """
        Récupère les statistiques liées aux conversations d'un utilisateur, y compris le total des conversations,
        le nombre de conversations dans les dernières 24 heures et les détails de la dernière conversation.

        :param username: Le nom d'utilisateur pour lequel rechercher les statistiques
        :type username: str
        :param email: L'adresse email de l'utilisateur pour lequel rechercher les statistiques
        :type email: str
        :return: Un dictionnaire contenant les statistiques suivantes :
                 - 'total_conversations': nombre total de conversations
                 - 'conversations_24h': nombre de conversations dans les 24 dernières heures
                 - 'last_conversation': détails de la dernière conversation incluant 'timestamp' et 'question'
        :rtype: Dict
        :raises Exception: En cas d'erreur lors de l'exécution des requêtes ou de la connexion à la base de données
        """
        try:
            with self._get_connection() as conn:
                # Total conversations
                cursor = conn.execute("""
                                      SELECT COUNT(*) as total
                                      FROM conversations
                                      WHERE username = ?
                                        AND email = ?
                                      """, (username, email))
                total = cursor.fetchone()['total']

                # Conversations 24h
                cutoff_time = datetime.now() - timedelta(hours=24)
                cursor = conn.execute("""
                                      SELECT COUNT(*) as recent
                                      FROM conversations
                                      WHERE username = ?
                                        AND email = ?
                                        AND timestamp >= ?
                                      """, (username, email, cutoff_time))
                recent = cursor.fetchone()['recent']

                # Dernière conversation
                cursor = conn.execute("""
                                      SELECT timestamp, question
                                      FROM conversations
                                      WHERE username = ? AND email = ?
                                      ORDER BY timestamp DESC LIMIT 1
                                      """, (username, email))
                last_row = cursor.fetchone()
                last_conversation = {
                    'timestamp': last_row['timestamp'] if last_row else None,
                    'question': last_row['question'] if last_row else None
                } if last_row else None

            return {
                'total_conversations': total,
                'conversations_24h': recent,
                'last_conversation': last_conversation
            }

        except Exception as e:
            logger.error(f" Erreur statistiques: {e}")
            return {'total_conversations': 0, 'conversations_24h': 0, 'last_conversation': None}

    def cleanup_old_conversations(self, days_to_keep: int = 30) -> int:
        """
        Supprime les anciennes conversations de la base de données qui ont une date
        antérieure à un nombre de jours spécifié (days_to_keep). Cette méthode effectue
        un nettoyage des données en supprimant les enregistrements obsolètes d'après
        la date limite calculée.

        :param days_to_keep: Nombre de jours avant lesquels les conversations
            doivent être supprimées (par défaut 30).
        :type days_to_keep: int
        :return: Le nombre de conversations supprimées.
        :rtype: int
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)

            with self._get_connection() as conn:
                cursor = conn.execute("""
                                      DELETE
                                      FROM conversations
                                      WHERE timestamp < ?
                                      """, (cutoff_date,))
                deleted_count = cursor.rowcount
                conn.commit()

            logger.info(f" Nettoyage: {deleted_count} conversations supprimées (> {days_to_keep} jours)")
            return deleted_count

        except Exception as e:
            logger.error(f" Erreur nettoyage: {e}")
            return 0

    def get_all_users(self) -> List[Tuple[str, str]]:
        """
        Récupère tous les utilisateurs distincts avec leurs noms d'utilisateur et leurs
        adresses e-mail à partir de la base de données. Les utilisateurs sont renvoyés
        dans un ordre alphabétique basé sur leurs noms d'utilisateur.

        :return: Une liste de tuples contenant les noms d'utilisateur et adresses e-mail
                 de tous les utilisateurs distincts dans la base de données. Si une erreur
                 se produit, retourne une liste vide.
        :rtype: List[Tuple[str, str]]
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("""
                                      SELECT DISTINCT username, email
                                      FROM conversations
                                      ORDER BY username
                                      """)
                return [(row['username'], row['email']) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f" Erreur liste utilisateurs: {e}")
            return []

    def delete_user_conversations(self, username: str, email: str) -> int:
        """
        Supprime les conversations associées à un utilisateur spécifique.

        Cette méthode permet de supprimer toutes les conversations d'un utilisateur donné
        en fonction de son nom d'utilisateur (username) et de son adresse e-mail.

        :param username: Nom d'utilisateur de l'individu dont les conversations doivent
            être supprimées.
        :type username: str
        :param email: Adresse e-mail de l'utilisateur dont les conversations sont à
            supprimer.
        :type email: str
        :return: Le nombre total de conversations supprimées avec succès pour cet
            utilisateur. Retourne `0` en cas d'échec ou si aucune conversation n'a été
            supprimée.
        :rtype: int
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("""
                                      DELETE
                                      FROM conversations
                                      WHERE username = ?
                                        AND email = ?
                                      """, (username, email))
                deleted_count = cursor.rowcount
                conn.commit()

            logger.info(f" {deleted_count} conversations supprimées pour {username}")
            return deleted_count

        except Exception as e:
            logger.error(f" Erreur suppression utilisateur: {e}")
            return 0

    def export_user_conversations(self, username: str, email: str) -> List[Dict]:
        """
        Exporte les conversations d'un utilisateur à partir de la base de données en fonction de son
        nom d'utilisateur et de son email. Les conversations sont triées par ordre décroissant de leur
        horodatage.

        Cette méthode effectue une requête SQL pour récupérer les conversations correspondantes dans la
        base de données, puis les formate sous forme de liste de dictionnaires, où chaque dictionnaire
        représente une conversation.

        :param username: Le nom d'utilisateur pour lequel les conversations doivent être exportées.
        :param email: L'adresse e-mail associée à l'utilisateur pour l'extraction des conversations.
        :return: Une liste de dictionnaires représentant les conversations de l'utilisateur, ou une
                 liste vide en cas d'erreur.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("""
                                      SELECT *
                                      FROM conversations
                                      WHERE username = ?
                                        AND email = ?
                                      ORDER BY timestamp DESC
                                      """, (username, email))

                conversations = []
                for row in cursor.fetchall():
                    conversations.append({
                        'id': row['id'],
                        'username': row['username'],
                        'email': row['email'],
                        'question': row['question'],
                        'reponse': row['reponse'],
                        'timestamp': row['timestamp'],
                        'session_id': row['session_id'],
                        'created_at': row['created_at']
                    })

            return conversations

        except Exception as e:
            logger.error(f" Erreur export: {e}")
            return []

    def check_database_health(self) -> Dict:
        """
        Vérifie l'état de santé de la base de données et retourne des statistiques détaillées sur son utilisation. Cette
        fonction évalue la taille de la base, le nombre total de conversations stockées, les utilisateurs uniques,
        ainsi que le nombre de conversations enregistrées durant les dernières 24 heures.

        :return: Un dictionnaire contenant des informations sur la santé de la base de données, y compris
            le chemin absolu de la base, sa taille en octets et mégaoctets, le nombre total de conversations
            enregistrées, le total d'utilisateurs uniques et le nombre de conversations dans les dernières 24 heures.
            Si une erreur survient lors du diagnostic, elle inclut l'erreur et marque l'état de la base comme
            « error ».
        :rtype: Dict
        """
        try:
            with self._get_connection() as conn:
                # Taille de la base
                cursor = conn.execute("SELECT COUNT(*) as total FROM conversations")
                total_conversations = cursor.fetchone()['total']

                # Utilisateurs uniques
                cursor = conn.execute("SELECT COUNT(DISTINCT username, email) as users FROM conversations")
                total_users = cursor.fetchone()['users']

                # Conversations récentes (24h)
                cutoff_time = datetime.now() - timedelta(hours=24)
                cursor = conn.execute("SELECT COUNT(*) as recent FROM conversations WHERE timestamp >= ?",
                                      (cutoff_time,))
                recent_conversations = cursor.fetchone()['recent']

                # Taille du fichier
                file_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0

            return {
                'database_path': os.path.abspath(self.db_path),
                'file_size_bytes': file_size,
                'file_size_mb': round(file_size / 1024 / 1024, 2),
                'total_conversations': total_conversations,
                'total_users': total_users,
                'conversations_24h': recent_conversations,
                'status': 'healthy'
            }

        except Exception as e:
            logger.error(f" Erreur vérification santé DB: {e}")
            return {
                'database_path': self.db_path,
                'status': 'error',
                'error': str(e)
            }


# Instance globale du memory store
conversation_memory = ConversationMemoryStore()


# Fonctions utilitaires pour compatibilité
def save_conversation(username: str, email: str, question: str, reponse: str, session_id: str = None) -> bool:
    """
    Sauvegarde une conversation dans la mémoire persistante. Cette fonction permet
    de stocker les informations pertinentes d'une conversation pour un usage
    ultérieur. Les informations sauvegardées incluent le nom d'utilisateur, l'email,
    la question posée, la réponse et un identifiant de session facultatif.

    :param username: Le nom d'utilisateur qui a participé à la conversation.
    :type username: str
    :param email: L'adresse email associée à l'utilisateur.
    :type email: str
    :param question: La question posée par l'utilisateur pendant la conversation.
    :type question: str
    :param reponse: La réponse apportée à la question de l'utilisateur.
    :type reponse: str
    :param session_id: L'identifiant unique de la session de conversation
        (facultatif, peut être None si non fourni).
    :type session_id: str, optionnel
    :return: Retourne True si la conversation a été sauvegardée avec succès,
        False sinon.
    :rtype: bool
    """
    return conversation_memory.save_conversation(username, email, question, reponse, session_id)


def get_user_context(username: str, email: str) -> str:
    """
    Récupère le contexte utilisateur pour formater l'historique de la conversation.

    Cette fonction utilise la mémoire de conversation pour retourner un contexte
    formaté basé sur l'historique et les informations utilisateur fournies.

    :param username: Le nom d'utilisateur utilisé pour le contexte.
    :type username: str
    :param email: L'adresse e-mail associée à l'utilisateur.
    :type email: str
    :return: Une chaîne formatée représentant le contexte utilisateur.
    :rtype: str
    """
    return conversation_memory.format_history_for_context(username, email)


def get_user_stats(username: str, email: str) -> Dict:
    """
    Récupère les statistiques de conversation d'un utilisateur donné.

    Cette fonction interagit avec une mémoire de conversation pour obtenir
    des statistiques spécifiques à un utilisateur identifiable par son nom
    d'utilisateur et son adresse e-mail.

    :param username: Nom d'utilisateur pour identifier l'utilisateur cible.
    :type username: str
    :param email: Adresse e-mail associée à l'utilisateur.
    :type email: str
    :return: Un dictionnaire contenant les statistiques de conversation
        associées à l'utilisateur.
    :rtype: Dict
    """
    return conversation_memory.get_conversation_stats(username, email)
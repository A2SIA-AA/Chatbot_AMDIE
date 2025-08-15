import sqlite3
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class ConversationMemoryStore:
    """
    Système de mémoire persistante avec SQLite pour l'historique des conversations
    Keycloak par utilisateur (username + email)
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
        """Crée la table conversations si elle n'existe pas"""
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
        """Context manager pour les connexions SQLite"""
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
        Sauvegarde une conversation complète

        Args:
            username: Nom d'utilisateur Keycloak 
            email: Email utilisateur
            question: Question posée
            reponse: Réponse de l'IA
            session_id: ID de session (optionnel)

        Returns:
            bool: True si sauvegarde réussie
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
        Récupère l'historique des 24 dernières heures pour un utilisateur

        Args:
            username: Nom d'utilisateur
            email: Email utilisateur  
            limit: Nombre maximum de conversations à retourner

        Returns:
            List[Dict]: Liste des conversations [{question, reponse, timestamp, session_id}]
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
        Formate l'historique pour le contexte des agents IA

        Args:
            username: Nom d'utilisateur
            email: Email utilisateur
            max_conversations: Nombre max de conversations à inclure

        Returns:
            str: Historique formaté pour le prompt IA
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
        Statistiques des conversations pour un utilisateur

        Returns:
            Dict: {total_conversations, conversations_24h, last_conversation}
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
        Nettoie les conversations anciennes

        Args:
            days_to_keep: Nombre de jours à conserver

        Returns:
            int: Nombre de conversations supprimées
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
        Liste tous les utilisateurs ayant des conversations

        Returns:
            List[Tuple[str, str]]: Liste des (username, email)
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
        Supprime toutes les conversations d'un utilisateur

        Returns:
            int: Nombre de conversations supprimées
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
        Exporte toutes les conversations d'un utilisateur

        Returns:
            List[Dict]: Toutes les conversations de l'utilisateur
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
        Vérifie l'état de santé de la base de données

        Returns:
            Dict: Informations sur l'état de la DB
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
    """Fonction helper pour sauvegarder une conversation"""
    return conversation_memory.save_conversation(username, email, question, reponse, session_id)


def get_user_context(username: str, email: str) -> str:
    """Fonction helper pour récupérer le contexte utilisateur"""
    return conversation_memory.format_history_for_context(username, email)


def get_user_stats(username: str, email: str) -> Dict:
    """Fonction helper pour les statistiques utilisateur"""
    return conversation_memory.get_conversation_stats(username, email)
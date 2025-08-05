import time
import asyncio
from typing import Dict, List, Optional
from models import MessageResponse


# ========================================
# CLASSE PRINCIPALE DE STOCKAGE
# ========================================
class MessageStore:
    """Gère le stockage des messages en mémoire"""

    def __init__(self):
        # Stockage principal : {session_id: [liste_messages]}
        self.sessions: Dict[str, List[MessageResponse]] = {}

        # Métadonnées par session : {session_id: {infos}}
        self.session_metadata: Dict[str, Dict] = {}

    async def add_message(self, session_id: str, message_data: dict) -> None:
        """
        Ajoute un message à une session

        Args:
            session_id: ID de la session (ex: "session_123_abc")
            message_data: Dictionnaire avec type, content, metadata
        """
        # Créer la session si elle n'existe pas
        if session_id not in self.sessions:
            self.sessions[session_id] = []
            self.session_metadata[session_id] = {
                'start_time': time.time(),  # Quand la session a commencé
                'last_activity': time.time(),  # Dernière activité
                'message_count': 0,  # Nombre de messages
                'status': 'active',  # active, completed, error
                'architecture': 'separated'  # Marquer comme architecture séparée
            }

        # Créer l'objet message avec timestamp
        message = MessageResponse(
            type=message_data['type'],
            content=message_data['content'],
            timestamp=time.time(),  # Timestamp automatique
            metadata=message_data.get('metadata', {})
        )

        # Ajouter à la session
        self.sessions[session_id].append(message)

        # Mettre à jour les métadonnées
        metadata = self.session_metadata[session_id]
        metadata['last_activity'] = time.time()
        metadata['message_count'] += 1

        # Changer le statut selon le type de message
        if message_data['type'] == 'final':
            metadata['status'] = 'completed'
        elif message_data['type'] == 'error':
            metadata['status'] = 'error'

        # Programmer le nettoyage automatique (2h)
        asyncio.create_task(self._cleanup_session_later(session_id, 7200))

    async def get_messages(self, session_id: str) -> List[MessageResponse]:
        """
        Récupère TOUS les messages d'une session

        Args:
            session_id: ID de la session

        Returns:
            Liste de tous les messages (peut être vide)
        """
        return self.sessions.get(session_id, [])

    async def get_new_messages(self, session_id: str, since: float) -> List[MessageResponse]:
        """
        Récupère seulement les nouveaux messages depuis un timestamp

        Args:
            session_id: ID de la session
            since: Timestamp depuis lequel récupérer (ex: 1640000000.5)

        Returns:
            Liste des messages plus récents que 'since'
        """
        all_messages = self.sessions.get(session_id, [])
        return [msg for msg in all_messages if msg.timestamp > since]

    async def clear_session(self, session_id: str) -> bool:
        """
        Supprime complètement une session et ses messages

        Args:
            session_id: ID de la session à supprimer

        Returns:
            True si suppression réussie, False si session n'existait pas
        """
        session_existed = session_id in self.sessions

        # Supprimer de partout
        if session_id in self.sessions:
            del self.sessions[session_id]
        if session_id in self.session_metadata:
            del self.session_metadata[session_id]

        return session_existed

    async def get_session_info(self, session_id: str) -> Optional[dict]:
        """
        Récupère les métadonnées d'une session (pour debugging)

        Args:
            session_id: ID de la session

        Returns:
            Dictionnaire avec start_time, message_count, status, etc.
        """
        return self.session_metadata.get(session_id)

    async def get_all_sessions(self) -> List[str]:
        """
        Liste toutes les sessions actives (pour debugging)

        Returns:
            Liste des IDs de session
        """
        return list(self.sessions.keys())

    async def get_stats(self) -> dict:
        """
        Statistiques globales du message store

        Returns:
            Dictionnaire avec statistiques
        """
        active_sessions = sum(1 for meta in self.session_metadata.values()
                              if meta.get('status') == 'active')
        total_messages = sum(len(msgs) for msgs in self.sessions.values())

        return {
            'total_sessions': len(self.sessions),
            'active_sessions': active_sessions,
            'total_messages': total_messages,
            'architecture': 'separated',
            'uptime': time.time()
        }

    async def _cleanup_session_later(self, session_id: str, delay: int):
        """
        Nettoie automatiquement une session après un délai

        Args:
            session_id: Session à nettoyer
            delay: Délai en secondes (ex: 7200 = 2h)
        """
        await asyncio.sleep(delay)
        if session_id in self.sessions:
            await self.clear_session(session_id)
            print(f" Session {session_id} auto-supprimée après {delay}s")


# ========================================
# INSTANCE GLOBALE (SINGLETON)
# ========================================
# Une seule instance partagée par toute l'API
message_store = MessageStore()
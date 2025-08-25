# message_store.py - VERSION AVEC STOCKAGE PARTAGÉ
import asyncio
import time
import json
import os
import fcntl
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum


class MessageType(Enum):
    PROGRESS = "progress"
    FINAL = "final"
    ERROR = "error"
    AGENT_RESULT = "agent_result"


@dataclass
class Message:
    type: str
    content: str
    timestamp: float
    metadata: Dict[str, Any]


class MessageStore:
    """
    Message Store avec stockage partagé sur fichier
    Permet aux différentes instances (FastAPI et MCP) de partager les données
    """

    def __init__(self, storage_file: str = "/tmp/chatbot_sessions.json"):
        self.storage_file = storage_file
        self.session_metadata: Dict[str, Dict[str, Any]] = {}

        # Créer le fichier s'il n'existe pas
        if not os.path.exists(self.storage_file):
            self._write_storage({})

        print(f"[MessageStore] Utilise stockage partagé: {self.storage_file}")

    def _read_storage(self) -> Dict[str, List[Dict]]:
        """Lit le stockage partagé avec verrouillage"""
        try:
            with open(self.storage_file, 'r') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)  # Verrouillage lecture
                content = f.read().strip()
                if not content:
                    return {}
                return json.loads(content)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
        except Exception as e:
            print(f"[MessageStore] Erreur lecture: {e}")
            return {}

    def _write_storage(self, data: Dict[str, List[Dict]]) -> bool:
        """Écrit le stockage partagé avec verrouillage"""
        try:
            # Écrire dans un fichier temporaire puis renommer (atomique)
            temp_file = f"{self.storage_file}.tmp"
            with open(temp_file, 'w') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # Verrouillage exclusif
                json.dump(data, f, ensure_ascii=False, indent=2)

            # Renommer atomiquement
            os.rename(temp_file, self.storage_file)
            return True
        except Exception as e:
            print(f"[MessageStore] Erreur écriture: {e}")
            return False

    async def add_message(self, session_id: str, message: Dict[str, Any]) -> None:
        """Ajoute un message à une session dans le stockage partagé"""
        print(f"[MessageStore] add_message session={session_id} type={message.get('type')}")

        current_time = time.time()

        # Préparer le message avec timestamp
        message_data = {
            'type': message['type'],
            'content': message['content'],
            'timestamp': current_time,
            'metadata': message.get('metadata', {})
        }

        # Lire le stockage actuel
        storage = self._read_storage()

        # Ajouter le message
        if session_id not in storage:
            storage[session_id] = []

        storage[session_id].append(message_data)

        # Sauvegarder
        success = self._write_storage(storage)

        if success:
            print(f"[MessageStore] Message ajouté à {session_id}")

            # Mettre à jour les métadonnées de session
            if session_id not in self.session_metadata:
                self.session_metadata[session_id] = {
                    'start_time': current_time,
                    'message_count': 0,
                    'status': 'active',
                    'architecture': 'separated'
                }

            self.session_metadata[session_id]['last_activity'] = current_time
            self.session_metadata[session_id]['message_count'] = len(storage[session_id])
        else:
            print(f"[MessageStore]  Erreur sauvegarde message pour {session_id}")

    async def get_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """Récupère tous les messages d'une session en format dictionnaire"""
        storage = self._read_storage()

        if session_id not in storage:
            print(f"[MessageStore] Session {session_id} non trouvée")
            return []

        messages = []
        for msg_data in storage[session_id]:
            # Retourner directement le dictionnaire au lieu d'un objet Message
            message_dict = {
                'type': msg_data['type'],
                'content': msg_data['content'],
                'timestamp': msg_data['timestamp'],
                'metadata': msg_data.get('metadata', {})
            }
            messages.append(message_dict)

        print(f"[MessageStore] Récupéré {len(messages)} messages pour {session_id}")
        return messages

    async def get_new_messages(self, session_id: str, since_timestamp: float) -> List[Dict[str, Any]]:
        """Récupère les nouveaux messages depuis un timestamp en format dictionnaire"""
        all_messages = await self.get_messages(session_id)
        new_messages = [msg for msg in all_messages if msg['timestamp'] > since_timestamp]
        print(f"[MessageStore] {len(new_messages)} nouveaux messages depuis {since_timestamp}")
        return new_messages

    async def get_all_sessions(self) -> List[str]:
        """Récupère la liste de toutes les sessions actives"""
        storage = self._read_storage()
        sessions = list(storage.keys())
        print(f"[MessageStore] {len(sessions)} sessions actives: {sessions}")
        return sessions

    async def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Récupère les informations d'une session"""
        storage = self._read_storage()

        if session_id not in storage:
            return None

        # Calculer les stats depuis le stockage
        messages = storage[session_id]

        if not messages:
            return None

        start_time = min(msg['timestamp'] for msg in messages)
        last_activity = max(msg['timestamp'] for msg in messages)

        return {
            'start_time': start_time,
            'last_activity': last_activity,
            'message_count': len(messages),
            'status': 'active',
            'architecture': 'separated'
        }

    async def clear_session(self, session_id: str) -> bool:
        """Supprime une session et ses messages"""
        storage = self._read_storage()

        if session_id in storage:
            del storage[session_id]
            success = self._write_storage(storage)

            # Nettoyer les métadonnées locales
            if session_id in self.session_metadata:
                del self.session_metadata[session_id]

            print(f"[MessageStore] Session {session_id} supprimée: {success}")
            return success

        return True  # Session déjà supprimée

    async def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques globales"""
        storage = self._read_storage()

        total_sessions = len(storage)
        total_messages = sum(len(messages) for messages in storage.values())

        return {
            'total_sessions': total_sessions,
            'total_messages': total_messages,
            'active_sessions': list(storage.keys()),
            'storage_file': self.storage_file
        }


# Instance partagée globale
message_store = MessageStore()

sessions = message_store.session_metadata


# Test de fonctionnement
async def test_shared_storage():
    """Test pour vérifier que le stockage partagé fonctionne"""
    print("=== TEST STOCKAGE PARTAGÉ ===")

    # Créer deux instances (simule FastAPI et MCP)
    store1 = MessageStore("/tmp/test_shared.json")  # Simule MCP
    store2 = MessageStore("/tmp/test_shared.json")  # Simule FastAPI

    session_id = "test_shared_session"

    # Instance 1 ajoute un message
    await store1.add_message(session_id, {
        'type': 'progress',
        'content': 'Message depuis instance 1',
        'metadata': {'source': 'store1'}
    })

    # Instance 2 lit les messages
    messages = await store2.get_messages(session_id)

    print(f"Instance 1 ajoute message...")
    print(f"Instance 2 lit {len(messages)} messages:")
    for msg in messages:
        print(f"  - {msg.type}: {msg.content}")

    if len(messages) > 0:
        print(" STOCKAGE PARTAGÉ FONCTIONNE!")
    else:
        print(" Stockage partagé échoué")

    # Nettoyer
    await store1.clear_session(session_id)

    # Supprimer le fichier de test
    try:
        os.remove("/tmp/test_shared.json")
    except:
        pass


if __name__ == "__main__":
    asyncio.run(test_shared_storage())

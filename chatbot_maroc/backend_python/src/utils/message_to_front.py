import sys
import requests
import time

sys.path[:0] = ['../../']
from chatbot_wrapper import send_log


def _send_to_frontend(session_id, message, log_level='INFO'):
    """Version avec gestion d'auth si nécessaire"""
    try:
        url = "http://localhost:8000/api/v1/messages"

        payload = {
            'sessionId': session_id,
            'type': 'agent_result',  # Type spécial pour les messages d'agents
            'content': message,
            'metadata': {
                'timestamp': time.time(),
                'source': 'agent_progression',
                'log_level': log_level,
                'agent_name': 'internal_agent'
            }
        }

        # Essayer sans auth d'abord (route publique pour les messages)
        response = requests.post(url, json=payload, timeout=2)

        if response.status_code == 200:
            return True
        else:
            print(f"[FRONTEND] Erreur {response.status_code} pour {session_id}")
            return False

    except Exception as e:
        print(f"[FRONTEND] Erreur: {e}")
        return False
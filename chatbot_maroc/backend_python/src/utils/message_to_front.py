import sys
import requests
import time

sys.path[:0] = ['../../']
from chatbot_wrapper import send_log


def _send_to_frontend(session_id, message, log_level='INFO'):
    """
    Envoie un message à l'interface frontend via une requête HTTP POST. Cette fonction
    est utilisée pour transmettre des résultats ou des statuts provenant d'un agent
    à une interface utilisateur ou à un autre système de gestion.

    L'opération tente d'envoyer le message sans authentification préalable, étant donné
    que cette route est spécifiquement publique pour ce type de messages. En cas de succès,
    la fonction retourne un booléen `True`. En cas d'échec, elle retourne `False`.

    :param session_id: Identifiant unique de la session pour laquelle la donnée est envoyée.
    :type session_id: str
    :param message: Le message à transmettre à l'interface frontend.
    :type message: str
    :param log_level: Le niveau de log associé au message. Par exemple 'INFO', 'DEBUG' ou 'ERROR'.
                      Ce paramètre est facultatif et sa valeur par défaut est 'INFO'.
    :type log_level: str
    :return: Retourne `True` si le message a été envoyé avec succès, sinon `False`.
    :rtype: bool
    """
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

        # Essayer sans auth (route publique pour les messages)
        response = requests.post(url, json=payload, timeout=2)

        if response.status_code == 200:
            return True
        else:
            print(f"[FRONTEND] Erreur {response.status_code} pour {session_id}")
            return False

    except Exception as e:
        print(f"[FRONTEND] Erreur: {e}")
        return False
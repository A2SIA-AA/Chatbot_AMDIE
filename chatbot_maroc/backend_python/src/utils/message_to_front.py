def _send_to_frontend(session_id: str, message: str, log_level: str = "INFO"):
    """
    Envoie un message vers le frontend via FastAPI

    Args:
        session_id: ID de session (peut être None)
        message: Message à envoyer
        log_level: Niveau de log (INFO, SUCCESS, WARNING, ERROR, etc.)
    """
    if not session_id:
        return  # Pas de session, pas d'envoi

    try:
        # Import dynamique pour éviter les erreurs circulaires
        from chatbot_wrapper import send_log
        send_log(session_id, message, log_level)
    except ImportError:
        # Si la fonction n'est pas disponible, pas grave
        pass
    except Exception as e:
        # Log local en cas d'erreur d'envoi
        print(f" Erreur envoi frontend: {e}")
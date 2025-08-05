import logging
import logging.handlers
from pathlib import Path
from datetime import datetime
import json


class JsonFormatter(logging.Formatter):
    """Formatter JSON pour structured logging"""

    def format(self, record):
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }

        # Ajouter exception si présente
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)

        return json.dumps(log_entry, ensure_ascii=False)


def setup_logging(settings) -> logging.Logger:
    """Configure le système de logging avancé"""

    # Créer le dossier de logs
    log_dir = Path(settings.log_dir)
    log_dir.mkdir(exist_ok=True)

    # Logger principal
    logger = logging.getLogger("chatbot_maroc")
    logger.setLevel(getattr(logging, settings.log_level.upper()))

    # Éviter la duplication des handlers
    if logger.handlers:
        return logger

    # 1. Handler pour fichier principal (JSON structured)
    main_handler = logging.handlers.RotatingFileHandler(
        log_dir / "chatbot.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    main_handler.setFormatter(JsonFormatter())
    logger.addHandler(main_handler)

    # 2. Handler pour erreurs séparées
    error_handler = logging.handlers.RotatingFileHandler(
        log_dir / "errors.log",
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=3
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(JsonFormatter())
    logger.addHandler(error_handler)

    # 3. Handler console (pour développement)
    if settings.debug:
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

    return logger


class PerformanceLogger:
    """Logger pour métriques de performance"""

    def __init__(self, settings):
        self.settings = settings
        self.metrics_logger = logging.getLogger("chatbot_maroc.metrics")

        # Handler spécifique pour métriques
        metrics_handler = logging.handlers.RotatingFileHandler(
            Path(settings.log_dir) / "metrics.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=3
        )
        metrics_handler.setFormatter(JsonFormatter())
        if not self.metrics_logger.handlers:
            self.metrics_logger.addHandler(metrics_handler)

    def log_request_metrics(self, question: str, duration: float, success: bool, error: str = None):
        """Log métriques d'une requête"""
        metrics = {
            'type': 'request',
            'question_length': len(question),
            'duration_seconds': duration,
            'success': success,
            'error': error
        }
        self.metrics_logger.info(f"Request metrics: {json.dumps(metrics)}")
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv()

class ChatbotSettings(BaseSettings):
    """Configuration du chatbot avec validation Pydantic"""

    # API Keys
    gemini_api_key: str = Field(os.getenv("GEMINI_API_KEY"), description="Clé API Gemini")

    # Paths
    rag_db_path: str = Field(default="./chroma_db", description="Chemin vers ChromaDB")
    log_dir: str = Field(default="./logs", description="Dossier des logs")
    data_dir: str = Field(default="./data", description="Dossier des données")

    # RAG Settings
    embedding_model: str = Field(default="sentence-transformers/all-MiniLM-L6-v2")

    debug: bool = Field(default=False, description="Mode debug")

    # Logging
    log_level: str = Field(default="INFO", description="Niveau de log")



# Instance globale
_settings: Optional[ChatbotSettings] = None


def get_settings() -> ChatbotSettings:
    """Singleton pour récupérer les settings"""
    global _settings
    if _settings is None:
        _settings = ChatbotSettings(gemini_api_key=os.getenv("GEMINI_API_KEY"))
    return _settings
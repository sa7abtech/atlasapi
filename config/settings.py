"""
ATLAS Configuration Settings
Loads environment variables and provides configuration management
"""

import os
from typing import List
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Settings:
    """Application settings loaded from environment variables"""

    # Supabase Configuration
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
    SUPABASE_SERVICE_KEY: str = os.getenv("SUPABASE_SERVICE_KEY", "")

    # OpenAI Configuration
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_EMBEDDING_MODEL: str = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-ada-002")
    OPENAI_CHAT_MODEL_SIMPLE: str = os.getenv("OPENAI_CHAT_MODEL_SIMPLE", "gpt-3.5-turbo")
    OPENAI_CHAT_MODEL_COMPLEX: str = os.getenv("OPENAI_CHAT_MODEL_COMPLEX", "gpt-4")

    # Claude Configuration (optional - uses Claude for chat if set)
    CLAUDE_API_KEY: str = os.getenv("CLAUDE_API_KEY", "")
    CLAUDE_MODEL_SIMPLE: str = os.getenv("CLAUDE_MODEL_SIMPLE", "claude-3-5-haiku-20241022")
    CLAUDE_MODEL_COMPLEX: str = os.getenv("CLAUDE_MODEL_COMPLEX", "claude-3-5-sonnet-20241022")

    # Telegram Configuration
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")

    # Application Configuration
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    PORT: int = int(os.getenv("PORT", "8000"))
    API_URL: str = os.getenv("API_URL", "http://localhost:8000")
    MAX_CONTEXT_TOKENS: int = int(os.getenv("MAX_CONTEXT_TOKENS", "2000"))
    CACHE_EXPIRY_HOURS: int = int(os.getenv("CACHE_EXPIRY_HOURS", "24"))
    MAX_CONVERSATION_HISTORY: int = int(os.getenv("MAX_CONVERSATION_HISTORY", "5"))
    TOP_K_KNOWLEDGE_CHUNKS: int = int(os.getenv("TOP_K_KNOWLEDGE_CHUNKS", "3"))
    MAX_USER_MEMORY_FACTS: int = int(os.getenv("MAX_USER_MEMORY_FACTS", "10"))

    # Token Thresholds
    SIMPLE_QUERY_TOKEN_THRESHOLD: int = int(os.getenv("SIMPLE_QUERY_TOKEN_THRESHOLD", "100"))
    COMPLEX_QUERY_TOKEN_THRESHOLD: int = int(os.getenv("COMPLEX_QUERY_TOKEN_THRESHOLD", "300"))

    # Language Support
    DEFAULT_LANGUAGE: str = os.getenv("DEFAULT_LANGUAGE", "en")
    SUPPORTED_LANGUAGES: List[str] = os.getenv("SUPPORTED_LANGUAGES", "en,ar,fr").split(",")

    # Rate Limiting
    RATE_LIMIT_PER_USER: int = int(os.getenv("RATE_LIMIT_PER_USER", "30"))

    # Performance Tuning
    EMBEDDING_BATCH_SIZE: int = int(os.getenv("EMBEDDING_BATCH_SIZE", "50"))
    VECTOR_SEARCH_LISTS: int = int(os.getenv("VECTOR_SEARCH_LISTS", "100"))
    SIMILARITY_THRESHOLD: float = float(os.getenv("SIMILARITY_THRESHOLD", "0.7"))

    # Morocco-specific Configuration
    TIMEZONE: str = os.getenv("TIMEZONE", "Africa/Casablanca")
    BUSINESS_HOURS_START: int = int(os.getenv("BUSINESS_HOURS_START", "9"))
    BUSINESS_HOURS_END: int = int(os.getenv("BUSINESS_HOURS_END", "18"))

    # Batch Learning Configuration
    BATCH_LEARNING_ENABLED: bool = os.getenv("BATCH_LEARNING_ENABLED", "true").lower() == "true"
    BATCH_LEARNING_TIME: str = os.getenv("BATCH_LEARNING_TIME", "02:00")  # HH:MM format
    BATCH_LEARNING_LOOKBACK_DAYS: int = int(os.getenv("BATCH_LEARNING_LOOKBACK_DAYS", "1"))
    BATCH_LEARNING_MAX_CONVERSATIONS: int = int(os.getenv("BATCH_LEARNING_MAX_CONVERSATIONS", "20"))

    @classmethod
    def validate(cls) -> bool:
        """Validate that all required settings are present"""
        required_settings = [
            "SUPABASE_URL",
            "SUPABASE_KEY",
            "OPENAI_API_KEY",
            "TELEGRAM_BOT_TOKEN",
        ]

        missing = []
        for setting in required_settings:
            if not getattr(cls, setting):
                missing.append(setting)

        if missing:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing)}\n"
                "Please check your .env file and ensure all required variables are set."
            )

        return True

    @classmethod
    def is_production(cls) -> bool:
        """Check if running in production environment"""
        return cls.ENVIRONMENT.lower() == "production"

    @classmethod
    def is_development(cls) -> bool:
        """Check if running in development environment"""
        return cls.ENVIRONMENT.lower() == "development"


# Create a singleton instance
settings = Settings()


# Logging configuration
def get_log_config():
    """Get logging configuration dictionary"""
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "[%(asctime)s] %(levelname)s in %(module)s: %(message)s",
            },
            "detailed": {
                "format": "[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": settings.LOG_LEVEL,
                "formatter": "default",
                "stream": "ext://sys.stdout",
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": settings.LOG_LEVEL,
                "formatter": "detailed",
                "filename": "atlas.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
            },
        },
        "root": {
            "level": settings.LOG_LEVEL,
            "handlers": ["console", "file"],
        },
        "loggers": {
            "atlas": {
                "level": settings.LOG_LEVEL,
                "handlers": ["console", "file"],
                "propagate": False,
            },
        },
    }

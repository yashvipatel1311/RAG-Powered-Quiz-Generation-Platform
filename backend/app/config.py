"""
Academix AI — Application Configuration

Loads all settings from environment variables (.env file).
See .env.example for the full list of required variables.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # --- Supabase ---
    # TODO: Set these in your .env file (see .env.example)
    SUPABASE_URL: str
    SUPABASE_KEY: str  # anon/public key
    SUPABASE_SERVICE_KEY: str  # service_role key (server-side only)
    SUPABASE_JWT_SECRET: str

    # --- Groq API ---
    # TODO: Set your Groq API key in .env
    GROQ_API_KEY: str
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    # --- Embedding Model ---
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION: int = 384

    # --- Application ---
    APP_NAME: str = "Academix AI"
    APP_ENV: str = "development"
    DEBUG: bool = True
    FRONTEND_URL: str = "http://localhost:5173"
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000

    # --- Chunking ---
    CHUNK_SIZE: int = 400  # tokens per chunk
    CHUNK_OVERLAP: int = 50  # overlap tokens between chunks

    # --- RAG ---
    RETRIEVAL_TOP_K: int = 10
    RETRIEVAL_THRESHOLD: float = 0.5

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance — loaded once, reused everywhere."""
    return Settings()

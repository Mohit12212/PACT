"""Central configuration, read from environment variables."""
import os
from pathlib import Path
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)
except ImportError:
    # Environment variables still work when python-dotenv is not installed.
    pass


@dataclass(frozen=True)
class Settings:
    secret_key: str = os.getenv("SECRET_KEY", "dev-secret-change-me-please-32bytes!")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./pact.db")
    token_minutes: int = int(os.getenv("TOKEN_MINUTES", "720"))
    admin_email: str = os.getenv("ADMIN_EMAIL", "admin@partnerhub.dev")
    admin_password: str = os.getenv("ADMIN_PASSWORD", "Admin@12345")
    llm_base_url: str = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "")
    llm_embed_model: str = os.getenv("LLM_EMBED_MODEL", "")
    seed_demo: bool = os.getenv("SEED_DEMO", "1") == "1"


settings = Settings()

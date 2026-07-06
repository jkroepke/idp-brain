"""Typed application settings for idp-brain."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    database_url: str = (
        "postgresql+psycopg://idp_brain:idp_brain@localhost:55432/idp_brain"
    )
    log_level: str = "INFO"
    config_dir: Path = Path("config")
    cache_dir: Path = Path(".idp-brain-cache")
    embedding_provider: str = "mock"
    external_model_calls_enabled: bool = False

    model_config = SettingsConfigDict(
        env_prefix="IDP_BRAIN_",
        env_file=".env",
        extra="ignore",
    )


@lru_cache
def load_settings() -> Settings:
    """Load application settings once for reuse by CLI and services."""

    return Settings()

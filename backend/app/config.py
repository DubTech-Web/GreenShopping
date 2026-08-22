"""Application configuration, loaded from environment / .env (Spec §25, §30).

No secret is hardcoded. `JWT_SECRET` must be set in production; the development default is
clearly marked and only used when the env var is absent.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # SQLite lives in a single file next to the backend package (no DB server — Spec §3).
    database_url: str = "sqlite:///./greenshopping.db"

    # Auth. Override JWT_SECRET in every real deployment.
    jwt_secret: str = "dev-only-insecure-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 12

    # CORS: the Vite dev server origins. Kept explicit, not "*", so credentials stay safe.
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Catalog pagination defaults (Spec §7, §17).
    default_page_size: int = 20
    max_page_size: int = 100


@lru_cache
def get_settings() -> Settings:
    """Cached so the .env file is parsed once per process, not per request (Spec §16)."""
    return Settings()

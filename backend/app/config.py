"""Application configuration, loaded from environment / .env (Spec §25, §30; Phase-2 §33).

No secret is hardcoded. `JWT_SECRET` must be set in production; the development default is
clearly marked and only used when the env var is absent. External integrations (Resend email,
Paystack payments, PostgreSQL) are all env-driven and degrade to a safe local/dev mode when
their keys are absent, so the app runs and tests pass without any secrets (Spec Phase-2 §5, §33).
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Environment. "production" tightens behaviour (CORS, error detail, no dev code echo).
    app_env: str = "development"

    # Database. SQLite (single file, no server) for local dev; a managed PostgreSQL
    # `DATABASE_URL` in production (Spec Phase-2 §16). Both use the same SQLAlchemy models.
    database_url: str = "sqlite:///./greenshopping.db"

    # Auth. Override JWT_SECRET in every real deployment.
    jwt_secret: str = "dev-only-insecure-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 12

    # CORS: dev origins are the Vite server; production adds FRONTEND_URL. Never "*" with
    # credentials (Spec §25, Phase-2 §37). See `allowed_origins`.
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    frontend_url: str = ""  # deployed Vercel origin, e.g. https://greenshopping.vercel.app
    backend_url: str = ""   # deployed Render origin, used for Paystack callback URLs

    # Catalog pagination defaults (Spec §7, §17).
    default_page_size: int = 20
    max_page_size: int = 100

    # ---- Email verification & notifications (SMTP / Resend) — Spec Phase-2 §1, §2, §5 ----
    resend_api_key: str = ""     # empty -> dev mode or SMTP mode
    resend_from_email: str = "GreenShopping <onboarding@resend.dev>"
    verification_code_ttl_minutes: int = 10
    verification_resend_cooldown_seconds: int = 60
    verification_max_attempts: int = 5

    # SMTP fallback / standard email provider (e.g. Gmail SMTP with App Password)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False

    # ---- Paystack payments — Spec Phase-2 §9–§12 ----
    paystack_secret_key: str = ""  # empty -> simulation mode (no real charge); tests run offline
    paystack_public_key: str = ""
    # The demo charge is ALWAYS this fixed amount, in kobo (₦100 = 10000 kobo). The backend is
    # authoritative — never derived from the cart total, never trusted from the frontend (§10, §12).
    payment_amount_kobo: int = 10_000

    @property
    def is_production(self) -> bool:
        return self.app_env.strip().lower() == "production"

    @property
    def allowed_origins(self) -> list[str]:
        """Final CORS allow-list: configured dev origins + the deployed frontend if set."""
        origins = [origin.strip().rstrip("/") for origin in self.cors_origins
                   if origin.strip().startswith(("http://", "https://"))]
        frontend = self.frontend_url.strip()
        if frontend.startswith(("http://", "https://")) and frontend.rstrip("/") not in origins:
            origins.append(frontend.rstrip("/"))
        return origins

    @property
    def smtp_enabled(self) -> bool:
        return bool(self.smtp_host and self.smtp_user and self.smtp_password)

    @property
    def resend_enabled(self) -> bool:
        return bool(self.resend_api_key)

    @property
    def email_delivery_enabled(self) -> bool:
        return self.smtp_enabled or self.resend_enabled

    @property
    def paystack_enabled(self) -> bool:
        return bool(self.paystack_secret_key)


@lru_cache
def get_settings() -> Settings:
    """Cached so the .env file is parsed once per process, not per request (Spec §16)."""
    return Settings()

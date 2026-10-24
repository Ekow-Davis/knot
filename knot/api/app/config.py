from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration comes from environment variables (or api/.env in development)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: str = "development"  # "production" on Railway

    # Railway gives postgresql://...; we rewrite it to the asyncpg driver below.
    database_url: str = "postgresql+asyncpg://knot:knot@localhost:5432/knot"

    # 32+ random bytes, used for HMAC of email codes, invites and verified-email tickets.
    secret_key: str = "dev-only-change-me"
    # base64-encoded 32-byte AES key for the question bank. Generated once, never committed.
    bank_key: str = ""

    owner_email: str = ""

    resend_api_key: str = ""
    mail_from: str = "no-reply <no-reply@forgottenguardian.com>"

    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_subject: str = "mailto:no-reply@forgottenguardian.com"

    app_origin: str = "http://localhost:5173"

    # Where the built PWA lives inside the container (see Dockerfile).
    static_dir: str = "../web/dist"

    # Tunables
    code_ttl_minutes: int = 10
    code_max_attempts: int = 5
    code_resend_seconds: int = 60
    session_ttl_days: int = 90
    invite_ttl_days: int = 7
    round_ttl_hours: int = 24

    @field_validator("database_url")
    @classmethod
    def _asyncpg_driver(cls, v: str) -> str:
        if v.startswith("postgres://"):
            v = "postgresql://" + v[len("postgres://"):]
        if v.startswith("postgresql://"):
            v = "postgresql+asyncpg://" + v[len("postgresql://"):]
        return v

    @field_validator("owner_email")
    @classmethod
    def _lower(cls, v: str) -> str:
        return v.strip().lower()

    @property
    def is_production(self) -> bool:
        return self.env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()

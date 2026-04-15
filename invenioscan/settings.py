import logging
import secrets
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INVSCAN_", env_file=".env", extra="ignore")

    app_name: str = "Shelfscan"
    api_prefix: str = "/api/v1"

    # Database
    database_url: str = "sqlite+aiosqlite:///./invenioscan.db"

    # JWT
    jwt_secret_key: str | None = None
    jwt_algorithm: str = "HS256"
    jwt_access_token_exp_minutes: int = 60

    # Bootstrap admin (auto-created on first startup)
    # If bootstrap_admin_password is not set, a random password is generated and printed to stdout.
    bootstrap_admin_username: str = "admin"
    bootstrap_admin_password: str | None = None
    bootstrap_admin_email: str = "admin@localhost"

    @model_validator(mode="after")
    def _fill_jwt_secret(self) -> "Settings":
        if self.jwt_secret_key is None:
            self.jwt_secret_key = secrets.token_hex(32)
            logger.warning(
                "INVSCAN_JWT_SECRET_KEY is not set — using an ephemeral secret. "
                "All sessions will be invalidated on restart. "
                "Set INVSCAN_JWT_SECRET_KEY to a stable 32+ character value in production."
            )
        elif self.jwt_secret_key.lower() in ("change-me", "secret", "changeme", "password"):
            raise ValueError("jwt_secret_key must not be a well-known placeholder value")
        elif len(self.jwt_secret_key) < 32:
            raise ValueError("jwt_secret_key must be at least 32 characters long")
        return self

    # Registration
    registration_expiry_days: int = 7

    # Uploads
    public_base_url: str | None = None
    upload_dir: Path = Path("uploads")

    # Scanner sub-path (where the Expo web app is served)
    scanner_url: str = "/scan"

    # Security
    cookie_secure: bool = True  # Set to False only in local dev/test (HTTP)

    # Frontend development
    cors_allowed_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:8081",
            "http://127.0.0.1:8081",
        ]
    )

    # QR
    qr_payload_version: int = 1
    qr_box_size: int = 8
    qr_border: int = 4

    # ISBN lookup (Open Library)
    isbn_lookup_enabled: bool = True
    isbn_lookup_timeout_seconds: float = 5.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
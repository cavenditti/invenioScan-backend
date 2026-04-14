from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INVSCAN_", env_file=".env", extra="ignore")

    app_name: str = "Shelfscan"
    api_prefix: str = "/api/v1"

    # Database
    database_url: str = "sqlite+aiosqlite:///./invenioscan.db"

    # JWT
    jwt_secret_key: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    jwt_access_token_exp_minutes: int = 60

    # Bootstrap admin (auto-created on first startup)
    # If bootstrap_admin_password is not set, a random password is generated and printed to stdout.
    bootstrap_admin_username: str = "admin"
    bootstrap_admin_password: str | None = None
    bootstrap_admin_email: str = "admin@localhost"

    @field_validator("jwt_secret_key")
    @classmethod
    def _require_strong_secret(cls, v: str) -> str:
        if v.lower() in ("change-me", "secret", "changeme", "password"):
            raise ValueError("jwt_secret_key must not be a well-known placeholder value")
        return v

    # Registration
    registration_expiry_days: int = 7

    # Uploads
    public_base_url: str | None = None
    upload_dir: Path = Path("uploads")

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
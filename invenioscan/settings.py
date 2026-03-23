from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INVSCAN_", env_file=".env", extra="ignore")

    app_name: str = "InvenioScan"
    api_prefix: str = "/api/v1"

    # Database
    database_url: str = "sqlite+aiosqlite:///./invenioscan.db"

    # JWT
    jwt_secret_key: str = Field(default="change-me", min_length=8)
    jwt_algorithm: str = "HS256"
    jwt_access_token_exp_minutes: int = 60

    # Bootstrap admin (auto-created on first startup)
    bootstrap_admin_username: str = "admin"
    bootstrap_admin_password: str = "admin"
    bootstrap_admin_email: str = "admin@localhost"

    # Registration
    registration_expiry_days: int = 7

    # Uploads
    public_base_url: str | None = None
    upload_dir: Path = Path("uploads")

    # QR
    qr_payload_version: int = 1
    qr_box_size: int = 8
    qr_border: int = 4


@lru_cache
def get_settings() -> Settings:
    return Settings()
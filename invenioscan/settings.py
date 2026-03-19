from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INVSCAN_", env_file=".env", extra="ignore")

    app_name: str = "InvenioScan API"
    api_prefix: str = "/api/v1"
    jwt_secret_key: str = Field(default="change-me", min_length=8)
    jwt_algorithm: str = "HS256"
    jwt_access_token_exp_minutes: int = 60
    bootstrap_username: str = "operator"
    bootstrap_password: str = "operator"
    invenio_base_url: str | None = None
    invenio_api_token: str | None = None
    qr_payload_version: int = 1
    qr_box_size: int = 8
    qr_border: int = 4


@lru_cache
def get_settings() -> Settings:
    return Settings()
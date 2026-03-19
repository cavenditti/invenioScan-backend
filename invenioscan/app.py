from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from invenioscan.api import build_api_router
from invenioscan.settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name)
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=upload_dir), name="uploads")
    app.include_router(build_api_router(), prefix=settings.api_prefix)
    return app


app = create_app()
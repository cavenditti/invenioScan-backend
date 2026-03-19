from fastapi import FastAPI

from invenioscan.api import build_api_router
from invenioscan.settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name)
    app.include_router(build_api_router(), prefix=settings.api_prefix)
    return app


app = create_app()
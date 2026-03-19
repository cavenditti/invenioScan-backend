from fastapi import APIRouter

from invenioscan.api.routes_auth import router as auth_router
from invenioscan.api.routes_health import router as health_router
from invenioscan.api.routes_ingest import router as ingest_router
from invenioscan.api.routes_qr import router as qr_router


def build_api_router() -> APIRouter:
    router = APIRouter()
    router.include_router(health_router)
    router.include_router(auth_router)
    router.include_router(ingest_router)
    router.include_router(qr_router)
    return router
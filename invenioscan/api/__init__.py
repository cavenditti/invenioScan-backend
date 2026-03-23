from fastapi import APIRouter

from invenioscan.api.routes_admin import router as admin_router
from invenioscan.api.routes_auth import router as auth_router
from invenioscan.api.routes_books import router as books_router
from invenioscan.api.routes_copies import router as copies_router
from invenioscan.api.routes_health import router as health_router
from invenioscan.api.routes_ingest import router as ingest_router
from invenioscan.api.routes_qr import router as qr_router
from invenioscan.api.routes_shelves import router as shelves_router


def build_api_router() -> APIRouter:
    router = APIRouter()
    router.include_router(health_router)
    router.include_router(auth_router)
    router.include_router(admin_router)
    router.include_router(books_router)
    router.include_router(shelves_router)
    router.include_router(copies_router)
    router.include_router(ingest_router)
    router.include_router(qr_router)
    return router
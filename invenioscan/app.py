from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from invenioscan.api import build_api_router
from invenioscan.auth import hash_password
import invenioscan.database as db_module
from invenioscan.database import create_db_and_tables
from invenioscan.models import User, UserStatus
from invenioscan.settings import get_settings

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


async def _ensure_bootstrap_admin() -> None:
    """Create the bootstrap admin user if no admin exists yet."""
    settings = get_settings()
    async with AsyncSession(db_module.engine) as session:
        result = await session.exec(select(User).where(User.is_admin == True))
        if result.first():
            return
        admin = User(
            username=settings.bootstrap_admin_username,
            email=settings.bootstrap_admin_email,
            hashed_password=hash_password(settings.bootstrap_admin_password),
            is_admin=True,
            is_active=True,
            status=UserStatus.APPROVED,
        )
        session.add(admin)
        await session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_db_and_tables()
    await _ensure_bootstrap_admin()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(title=settings.app_name, lifespan=lifespan)

    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    application.mount("/uploads", StaticFiles(directory=upload_dir), name="uploads")

    # Serve static assets (CSS/JS) if they exist
    static_dir = Path(__file__).parent / "static"
    if static_dir.is_dir():
        application.mount("/static", StaticFiles(directory=static_dir), name="static")

    # API routes
    application.include_router(build_api_router(), prefix=settings.api_prefix)

    # Web UI routes (must be after API)
    from invenioscan.web import router as web_router
    application.include_router(web_router)

    return application


app = create_app()
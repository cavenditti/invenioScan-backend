from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from invenioscan.auth import create_access_token, hash_password, verify_password
from invenioscan.database import get_session
from invenioscan.dependencies import get_current_user
from invenioscan.email import notify_admin_new_registration
from invenioscan.models import User, UserStatus
from invenioscan.schemas import RegisterRequest, TokenResponse, UserPublic
from invenioscan.settings import Settings, get_settings

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    existing = await session.exec(
        select(User).where((User.username == payload.username) | (User.email == payload.email))
    )
    if existing.first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username or email already taken")
    user = User(
        username=payload.username,
        email=payload.email,
        hashed_password=hash_password(payload.password),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    await notify_admin_new_registration(settings, user.username, user.email)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TokenResponse:
    result = await session.exec(select(User).where(User.username == form.username))
    user = result.first()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # Auto-deny expired pending registrations
    if user.status == UserStatus.PENDING:
        created = user.created_at if user.created_at.tzinfo else user.created_at.replace(tzinfo=UTC)
        expiry = created + timedelta(days=settings.registration_expiry_days)
        if datetime.now(UTC) > expiry:
            user.status = UserStatus.DENIED
            user.status_changed_at = datetime.now(UTC)
            session.add(user)
            await session.commit()

    if user.status != UserStatus.APPROVED:
        detail = "Account pending approval" if user.status == UserStatus.PENDING else "Account denied"
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    token, expires_in = create_access_token(user.id, user.username, user.is_admin, settings)
    return TokenResponse(access_token=token, expires_in=expires_in)


@router.get("/me", response_model=UserPublic)
async def read_current_user(user: Annotated[User, Depends(get_current_user)]) -> User:
    return user
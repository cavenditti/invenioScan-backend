from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from invenioscan.database import get_session
from invenioscan.dependencies import require_admin
from invenioscan.models import User, UserStatus
from invenioscan.schemas import UserPublic

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[UserPublic])
async def list_users(
    _admin: Annotated[User, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
    user_status: UserStatus | None = Query(default=None, alias="status"),
) -> list[User]:
    stmt = select(User)
    if user_status:
        stmt = stmt.where(User.status == user_status)
    stmt = stmt.order_by(User.created_at.desc())
    result = await session.exec(stmt)
    return list(result.all())


@router.post("/users/{user_id}/approve", response_model=UserPublic)
async def approve_user(
    user_id: int,
    admin: Annotated[User, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.status = UserStatus.APPROVED
    user.status_changed_at = datetime.now(UTC)
    user.approved_by_id = admin.id
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@router.post("/users/{user_id}/deny", response_model=UserPublic)
async def deny_user(
    user_id: int,
    _admin: Annotated[User, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.status = UserStatus.DENIED
    user.status_changed_at = datetime.now(UTC)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from invenioscan.database import get_session
from invenioscan.dependencies import get_current_user
from invenioscan.models import Book, BookCopy, User
from invenioscan.schemas import CopyCreate, CopyPublic, CopyUpdate

router = APIRouter(tags=["copies"])


@router.get("/books/{book_id}/copies", response_model=list[CopyPublic])
async def list_copies(
    book_id: int,
    _user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[BookCopy]:
    book = await session.get(Book, book_id)
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    result = await session.exec(select(BookCopy).where(BookCopy.book_id == book_id))
    return list(result.all())


@router.post("/books/{book_id}/copies", response_model=CopyPublic, status_code=status.HTTP_201_CREATED)
async def create_copy(
    book_id: int,
    payload: CopyCreate,
    _user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> BookCopy:
    book = await session.get(Book, book_id)
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    copy = BookCopy(book_id=book_id, **payload.model_dump())
    session.add(copy)
    await session.commit()
    await session.refresh(copy)
    return copy


@router.put("/copies/{copy_id}", response_model=CopyPublic)
async def update_copy(
    copy_id: int,
    payload: CopyUpdate,
    _user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> BookCopy:
    copy = await session.get(BookCopy, copy_id)
    if not copy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Copy not found")
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(copy, key, value)
    copy.updated_at = datetime.now(UTC)
    session.add(copy)
    await session.commit()
    await session.refresh(copy)
    return copy


@router.delete("/copies/{copy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_copy(
    copy_id: int,
    _user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    copy = await session.get(BookCopy, copy_id)
    if not copy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Copy not found")
    await session.delete(copy)
    await session.commit()

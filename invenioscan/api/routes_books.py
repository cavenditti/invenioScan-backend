from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from invenioscan.database import get_session
from invenioscan.dependencies import get_current_user, require_admin
from invenioscan.models import Book, BookCopy, User
from invenioscan.schemas import BookCreate, BookPublic, BookUpdate, BookWithCopies, CopyPublic

router = APIRouter(prefix="/books", tags=["books"])


@router.get("", response_model=list[BookPublic])
async def list_books(
    _user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    q: str | None = Query(default=None, description="Search title, author, or ISBN"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
) -> list[Book]:
    stmt = select(Book)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            (Book.title.ilike(like)) | (Book.author.ilike(like)) | (Book.isbn.ilike(like))
        )
    stmt = stmt.order_by(Book.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
    result = await session.exec(stmt)
    return list(result.all())


@router.get("/{book_id}", response_model=BookWithCopies)
async def get_book(
    book_id: int,
    _user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    book = await session.get(Book, book_id)
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    # Load copies
    result = await session.exec(select(BookCopy).where(BookCopy.book_id == book_id))
    copies = list(result.all())
    return {**book.model_dump(), "copies": [c.model_dump() for c in copies]}


@router.post("", response_model=BookPublic, status_code=status.HTTP_201_CREATED)
async def create_book(
    payload: BookCreate,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Book:
    book = Book(**payload.model_dump(), created_by_id=user.id)
    session.add(book)
    await session.commit()
    await session.refresh(book)
    return book


@router.put("/{book_id}", response_model=BookPublic)
async def update_book(
    book_id: int,
    payload: BookUpdate,
    _user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Book:
    book = await session.get(Book, book_id)
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(book, key, value)
    book.updated_at = datetime.now(UTC)
    session.add(book)
    await session.commit()
    await session.refresh(book)
    return book


@router.delete("/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_book(
    book_id: int,
    _admin: Annotated[User, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    book = await session.get(Book, book_id)
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    # Delete associated copies first
    result = await session.exec(select(BookCopy).where(BookCopy.book_id == book_id))
    for copy in result.all():
        await session.delete(copy)
    await session.delete(book)
    await session.commit()

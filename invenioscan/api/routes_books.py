from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import delete, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from invenioscan.database import get_session
from invenioscan.dependencies import get_current_user, require_admin
from invenioscan.isbn_lookup import lookup_isbn
from invenioscan.models import Book, BookCopy, User
from invenioscan.schemas import BookCreate, BookPublic, BookUpdate, BookWithCopies, CopyPublic, EnrichResponse
from invenioscan.settings import Settings, get_settings

router = APIRouter(prefix="/books", tags=["books"])


@router.get("", response_model=list[BookPublic])
async def list_books(
    _user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    q: str | None = Query(default=None, description="Search title, author, or ISBN"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=100),
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


@router.post("/{book_id}/enrich", response_model=EnrichResponse)
async def enrich_book(
    book_id: int,
    _user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> EnrichResponse:
    book = await session.get(Book, book_id)
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    if not book.isbn:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Book has no ISBN — cannot look up metadata.",
        )

    lookup = await lookup_isbn(book.isbn, settings)
    if not lookup:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ISBN lookup returned no results. The external service may be unavailable.",
        )

    fields_updated: list[str] = []
    for field, key in [
        ("title", "title"),
        ("author", "author"),
        ("publication_year", "publication_year"),
        ("cover_image_url", "cover_image_url"),
    ]:
        value = lookup.get(key)
        if value is not None:
            setattr(book, field, value)
            fields_updated.append(field)

    # Merge extra metadata
    extra = dict(book.extra) if book.extra else {}
    for key in ("publishers", "subjects", "identifiers", "number_of_pages", "publish_date_raw"):
        if lookup.get(key) is not None:
            extra[key] = lookup[key]
    if extra:
        book.extra = extra
        if "extra" not in fields_updated:
            fields_updated.append("extra")

    book.updated_at = datetime.now(UTC)
    session.add(book)
    await session.commit()
    await session.refresh(book)

    return EnrichResponse(
        status="enriched",
        book_id=book.id,
        title=book.title,
        author=book.author,
        cover_image_url=book.cover_image_url,
        fields_updated=fields_updated,
    )


@router.delete("/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_book(
    book_id: int,
    _admin: Annotated[User, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    book = await session.get(Book, book_id)
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    # Bulk-delete associated copies in a single statement
    await session.exec(delete(BookCopy).where(BookCopy.book_id == book_id))
    await session.delete(book)
    await session.commit()

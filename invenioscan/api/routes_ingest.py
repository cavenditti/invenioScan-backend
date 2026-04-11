from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from invenioscan.database import get_session
from invenioscan.dependencies import get_current_user
from invenioscan.isbn_lookup import lookup_isbn
from invenioscan.models import Book, BookCopy, Shelf, User
from invenioscan.schemas import IngestRequest, IngestResponse, ShelfPosition, SourceType
from invenioscan.settings import Settings, get_settings
from invenioscan.uploads import persist_upload

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("", response_model=IngestResponse, status_code=status.HTTP_201_CREATED)
async def ingest(
    payload: IngestRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> IngestResponse:
    return await _perform_ingest(payload, user, session, settings)


@router.post("/upload", response_model=IngestResponse, status_code=status.HTTP_201_CREATED)
async def upload_ingest(
    request: Request,
    shelf_id: Annotated[str, Form()],
    row: Annotated[str, Form()],
    position: Annotated[int, Form()],
    height: Annotated[int, Form()],
    title: Annotated[str | None, Form()] = None,
    author: Annotated[str | None, Form()] = None,
    publication_year: Annotated[int | None, Form()] = None,
    document_type: Annotated[str | None, Form()] = None,
    language: Annotated[str | None, Form()] = None,
    notes: Annotated[str | None, Form()] = None,
    image: UploadFile = File(...),
    user: Annotated[User, Depends(get_current_user)] = None,
    session: Annotated[AsyncSession, Depends(get_session)] = None,
    settings: Annotated[Settings, Depends(get_settings)] = None,
) -> IngestResponse:
    _, public_url = await persist_upload(image, settings, request)
    payload = IngestRequest(
        shelf=ShelfPosition(shelf_id=shelf_id, row=row, position=position, height=height),
        source_type=SourceType.IMAGE_REFERENCE,
        image_reference=public_url,
        title=title or "Untitled (image scan)",
        author=author,
        publication_year=publication_year,
        document_type=document_type,
        language=language,
        notes=notes,
    )
    return await _perform_ingest(payload, user, session, settings)


async def _perform_ingest(
    payload: IngestRequest,
    user: User,
    session: AsyncSession,
    settings: Settings,
) -> IngestResponse:
    # Find or create shelf
    result = await session.exec(select(Shelf).where(Shelf.shelf_id == payload.shelf.shelf_id))
    shelf = result.first()
    if not shelf:
        shelf = Shelf(shelf_id=payload.shelf.shelf_id)
        session.add(shelf)
        await session.flush()

    # Find existing book by ISBN or create new
    book = None
    enriched = False
    if payload.isbn:
        result = await session.exec(select(Book).where(Book.isbn == payload.isbn))
        book = result.first()

    if not book:
        # Attempt Open Library lookup for ISBN ingests
        lookup = None
        if payload.isbn:
            lookup = await lookup_isbn(payload.isbn, settings)

        extra = {}
        if lookup:
            enriched = True
            # Store all lookup data in extra
            for key in ("publishers", "subjects", "identifiers", "number_of_pages", "publish_date_raw"):
                if lookup.get(key) is not None:
                    extra[key] = lookup[key]

        book = Book(
            title=payload.title or (lookup and lookup.get("title")) or payload.isbn or "Untitled",
            author=payload.author or (lookup and lookup.get("author")),
            isbn=payload.isbn,
            publication_year=payload.publication_year or (lookup and lookup.get("publication_year")),
            document_type=payload.document_type or "BOOK",
            language=payload.language,
            cover_image_url=(
                payload.image_reference if payload.source_type == SourceType.IMAGE_REFERENCE
                else (lookup and lookup.get("cover_image_url"))
            ),
            extra=extra or None,
            notes=payload.notes,
            created_by_id=user.id,
        )
        session.add(book)
        await session.flush()

    # Create copy at shelf position
    copy = BookCopy(
        book_id=book.id,
        shelf_id=shelf.id,
        row=payload.shelf.row,
        position=payload.shelf.position,
        height=payload.shelf.height,
    )
    session.add(copy)
    await session.commit()
    await session.refresh(copy)
    await session.refresh(book)

    return IngestResponse(
        status="created",
        book_id=book.id,
        copy_id=copy.id,
        scan_id=str(copy.scan_id),
        title=book.title,
        author=book.author,
        cover_image_url=book.cover_image_url,
        enriched=enriched,
    )
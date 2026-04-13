from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ── Auth ──────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    username: str = Field(min_length=2, max_length=80)
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=6)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    is_admin: bool
    status: str
    created_at: datetime | None = None


# ── Shelf ─────────────────────────────────────────────────

class ShelfPosition(BaseModel):
    shelf_id: str = Field(min_length=1)
    row: str = Field(min_length=1)
    position: int = Field(ge=1)
    height: int = Field(ge=1)


class ShelfCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    shelf_id: str = Field(min_length=1, max_length=40)
    row: str = Field(min_length=1, max_length=10)
    position: int = Field(ge=1)
    height: int = Field(ge=1)
    label: str | None = None


class ShelfUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    row: str | None = Field(default=None, min_length=1, max_length=10)
    position: int | None = Field(default=None, ge=1)
    height: int | None = Field(default=None, ge=1)
    label: str | None = None


class ShelfPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    shelf_id: str
    row: str
    position: int
    height: int
    label: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


# ── Book ──────────────────────────────────────────────────

class BookCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=500)
    author: str | None = None
    isbn: str | None = None
    publication_year: int | None = None
    document_type: str = "BOOK"
    language: str | None = None
    cover_image_url: str | None = None
    extra: dict | None = None
    notes: str | None = None


class BookUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str | None = None
    author: str | None = None
    isbn: str | None = None
    publication_year: int | None = None
    document_type: str | None = None
    language: str | None = None
    cover_image_url: str | None = None
    extra: dict | None = None
    notes: str | None = None


class BookPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    author: str | None = None
    isbn: str | None = None
    publication_year: int | None = None
    document_type: str
    language: str | None = None
    cover_image_url: str | None = None
    extra: dict | None = None
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    created_by_id: int | None = None


# ── BookCopy ──────────────────────────────────────────────

class CopyCreate(BaseModel):
    shelf_id: int
    notes: str | None = None


class CopyUpdate(BaseModel):
    shelf_id: int | None = None
    notes: str | None = None


class CopyPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    book_id: int
    shelf_id: int
    scan_id: UUID | None = None
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class BookWithCopies(BookPublic):
    copies: list[CopyPublic] = []


# ── Ingest (mobile scanning) ─────────────────────────────

class SourceType(str, Enum):
    ISBN = "isbn"
    IMAGE_REFERENCE = "image_reference"


class IngestRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    shelf: ShelfPosition
    source_type: SourceType
    isbn: str | None = None
    image_reference: str | None = None
    title: str | None = None
    author: str | None = None
    publication_year: int | None = None
    document_type: str | None = None
    language: str | None = None
    notes: str | None = None

    def model_post_init(self, __context: object) -> None:
        if self.source_type == SourceType.ISBN:
            if not self.isbn:
                raise ValueError("isbn is required when source_type is isbn")
            if self.image_reference:
                raise ValueError("image_reference must not be provided for isbn ingest")
        if self.source_type == SourceType.IMAGE_REFERENCE:
            if not self.image_reference:
                raise ValueError("image_reference is required when source_type is image_reference")
            if self.isbn:
                raise ValueError("isbn must not be provided for image_reference ingest")


class IngestResponse(BaseModel):
    status: str
    book_id: int
    copy_id: int
    scan_id: str
    title: str | None = None
    author: str | None = None
    cover_image_url: str | None = None
    enriched: bool = False


# ── Enrich ────────────────────────────────────────────────

class EnrichResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: str
    book_id: int
    title: str | None = None
    author: str | None = None
    cover_image_url: str | None = None
    fields_updated: list[str] = []


# ── QR ────────────────────────────────────────────────────

class ShelfQRCodeRequest(BaseModel):
    shelf_id: str = Field(min_length=1)
    row: str = Field(min_length=1)
    position: int = Field(ge=1)
    height: int = Field(ge=1)


class ShelfQRCodePayload(BaseModel):
    payload: str


class ShelfQRCodeSheetRequest(BaseModel):
    rows: list[str] = Field(min_length=1)
    positions: list[int] = Field(min_length=1)
    heights: list[int] = Field(min_length=1)


# ── Pagination ────────────────────────────────────────────

class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    per_page: int
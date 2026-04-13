from datetime import UTC, datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlmodel import Field, JSON, Column, Relationship, SQLModel


class UserStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True, max_length=80)
    email: str = Field(index=True, unique=True, max_length=254)
    hashed_password: str
    is_active: bool = Field(default=True)
    is_admin: bool = Field(default=False)
    status: UserStatus = Field(default=UserStatus.PENDING)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    status_changed_at: datetime | None = Field(default=None)
    approved_by_id: int | None = Field(default=None, foreign_key="user.id")

    books: list["Book"] = Relationship(back_populates="creator")


class Shelf(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    shelf_id: str = Field(index=True, max_length=40)
    label: str | None = Field(default=None, max_length=200)
    row: str = Field(max_length=10)
    position: int
    height: int
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    copies: list["BookCopy"] = Relationship(back_populates="shelf")


class Book(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str = Field(max_length=500)
    author: str | None = Field(default=None, max_length=500)
    isbn: str | None = Field(default=None, index=True, max_length=20)
    publication_year: int | None = Field(default=None)
    document_type: str = Field(default="BOOK", max_length=40)
    language: str | None = Field(default=None, max_length=10)
    cover_image_url: str | None = Field(default=None, max_length=1000)
    extra: dict | None = Field(default=None, sa_column=Column(JSON))
    notes: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    created_by_id: int | None = Field(default=None, foreign_key="user.id")

    creator: User | None = Relationship(back_populates="books")
    copies: list["BookCopy"] = Relationship(back_populates="book")


class BookCopy(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    book_id: int = Field(foreign_key="book.id", index=True)
    shelf_id: int = Field(foreign_key="shelf.id", index=True)
    scan_id: UUID = Field(default_factory=uuid4)
    notes: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    book: Book = Relationship(back_populates="copies")
    shelf: Shelf = Relationship(back_populates="copies")

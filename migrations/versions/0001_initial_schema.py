"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # User
    op.create_table(
        "user",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("username", sqlmodel.sql.sqltypes.AutoString(length=80), nullable=False),
        sa.Column("email", sqlmodel.sql.sqltypes.AutoString(length=254), nullable=False),
        sa.Column("hashed_password", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("1")),
        sa.Column("is_admin", sa.Boolean, nullable=False, server_default=sa.text("0")),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("status_changed_at", sa.DateTime, nullable=True),
        sa.Column("approved_by_id", sa.Integer, sa.ForeignKey("user.id"), nullable=True),
    )
    op.create_index("ix_user_username", "user", ["username"], unique=True)
    op.create_index("ix_user_email", "user", ["email"], unique=True)

    # Shelf
    op.create_table(
        "shelf",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("shelf_id", sqlmodel.sql.sqltypes.AutoString(length=40), nullable=False),
        sa.Column("label", sqlmodel.sql.sqltypes.AutoString(length=200), nullable=True),
        sa.Column("row", sqlmodel.sql.sqltypes.AutoString(length=10), nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("height", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint("shelf_id", name="uq_shelf_shelf_id"),
        sa.UniqueConstraint("row", "position", "height", name="uq_shelf_row_position_height"),
    )

    # Book
    op.create_table(
        "book",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("title", sqlmodel.sql.sqltypes.AutoString(length=500), nullable=False),
        sa.Column("author", sqlmodel.sql.sqltypes.AutoString(length=500), nullable=True),
        sa.Column("isbn", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=True),
        sa.Column("publication_year", sa.Integer, nullable=True),
        sa.Column("document_type", sqlmodel.sql.sqltypes.AutoString(length=40), nullable=False, server_default="BOOK"),
        sa.Column("language", sqlmodel.sql.sqltypes.AutoString(length=10), nullable=True),
        sa.Column("cover_image_url", sqlmodel.sql.sqltypes.AutoString(length=1000), nullable=True),
        sa.Column("extra", sa.JSON, nullable=True),
        sa.Column("notes", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.Column("created_by_id", sa.Integer, sa.ForeignKey("user.id"), nullable=True),
    )
    op.create_index("ix_book_isbn", "book", ["isbn"])

    # BookCopy
    op.create_table(
        "bookcopy",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("book_id", sa.Integer, sa.ForeignKey("book.id", ondelete="CASCADE"), nullable=False),
        sa.Column("shelf_id", sa.Integer, sa.ForeignKey("shelf.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("scan_id", sa.Uuid, nullable=False),
        sa.Column("notes", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_bookcopy_book_id", "bookcopy", ["book_id"])
    op.create_index("ix_bookcopy_shelf_id", "bookcopy", ["shelf_id"])


def downgrade() -> None:
    op.drop_table("bookcopy")
    op.drop_table("book")
    op.drop_table("shelf")
    op.drop_table("user")

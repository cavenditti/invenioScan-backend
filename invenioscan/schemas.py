from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SourceType(str, Enum):
    ISBN = "isbn"
    IMAGE_REFERENCE = "image_reference"


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class CurrentUserResponse(BaseModel):
    username: str


class ShelfPosition(BaseModel):
    shelf_id: str = Field(min_length=1)
    row: str = Field(min_length=1)
    position: int = Field(ge=1)
    height: int = Field(ge=1)


class IngestRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    shelf: ShelfPosition
    source_type: SourceType
    isbn: str | None = None
    image_reference: str | None = None
    title: str | None = None
    author: str | None = None

    @model_validator(mode="after")
    def validate_source_fields(self) -> "IngestRequest":
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
        return self


class PreparedMetadata(BaseModel):
    scan_id: str
    title: str | None = None
    author: str | None = None
    isbn: str | None = None
    image_reference: str | None = None
    source_type: SourceType
    shelf: ShelfPosition
    remote_document_pid: str | None = None
    remote_item_pid: str | None = None
    remote_eitem_pid: str | None = None
    identifiers: list[dict[str, str]]
    notes: list[str]


class IngestResponse(BaseModel):
    status: str
    submitted_by: str
    payload: PreparedMetadata


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
    height: int = Field(ge=1)
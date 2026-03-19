from __future__ import annotations

from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

from fastapi import Request, UploadFile

from invenioscan.settings import Settings


CONTENT_TYPE_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


async def persist_upload(upload: UploadFile, settings: Settings, request: Request) -> tuple[Path, str]:
    upload_root = settings.upload_dir
    upload_root.mkdir(parents=True, exist_ok=True)

    suffix = _resolve_suffix(upload)
    filename = f"{uuid4().hex}{suffix}"
    destination = upload_root / filename
    content = await upload.read()
    destination.write_bytes(content)
    await upload.close()

    relative_path = quote(filename)
    public_base = (settings.public_base_url or str(request.base_url)).rstrip("/")
    public_url = f"{public_base}/uploads/{relative_path}"
    return destination, public_url


def _resolve_suffix(upload: UploadFile) -> str:
    if upload.filename:
        suffix = Path(upload.filename).suffix.lower()
        if suffix:
            return suffix
    return CONTENT_TYPE_EXTENSIONS.get(upload.content_type or "", ".jpg")
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from invenioscan.dependencies import get_current_user
from invenioscan.models import User
from invenioscan.settings import Settings, get_settings

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.get("/{filename:path}", response_class=FileResponse)
async def serve_upload(
    filename: str,
    _user: Annotated[User, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> FileResponse:
    # Prevent path traversal attacks
    upload_dir = Path(settings.upload_dir).resolve()
    target = (upload_dir / filename).resolve()
    if not str(target).startswith(str(upload_dir)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid path")
    if not target.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    return FileResponse(target)

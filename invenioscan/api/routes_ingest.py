from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status

from invenioscan.adapters.base import InvenioAdapter, InvenioAdapterError
from invenioscan.dependencies import get_current_user, get_invenio_adapter
from invenioscan.schemas import CurrentUserResponse, IngestRequest, IngestResponse, ShelfPosition, SourceType
from invenioscan.settings import Settings, get_settings
from invenioscan.uploads import persist_upload

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("", response_model=IngestResponse, status_code=status.HTTP_202_ACCEPTED)
async def ingest(
    payload: IngestRequest,
    user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    adapter: Annotated[InvenioAdapter, Depends(get_invenio_adapter)],
) -> IngestResponse:
    return await _submit_ingest(payload, user, adapter)


@router.post("/upload", response_model=IngestResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_ingest(
    request: Request,
    shelf_id: Annotated[str, Form()],
    row: Annotated[str, Form()],
    position: Annotated[int, Form()],
    height: Annotated[int, Form()],
    title: Annotated[str | None, Form()] = None,
    author: Annotated[str | None, Form()] = None,
    image: UploadFile = File(...),
    user: Annotated[CurrentUserResponse, Depends(get_current_user)] = None,
    adapter: Annotated[InvenioAdapter, Depends(get_invenio_adapter)] = None,
    settings: Annotated[Settings, Depends(get_settings)] = None,
) -> IngestResponse:
    _, public_url = await persist_upload(image, settings, request)
    payload = IngestRequest(
        shelf=ShelfPosition(shelf_id=shelf_id, row=row, position=position, height=height),
        source_type=SourceType.IMAGE_REFERENCE,
        image_reference=public_url,
        title=title,
        author=author,
    )
    return await _submit_ingest(payload, user, adapter)


async def _submit_ingest(
    payload: IngestRequest,
    user: CurrentUserResponse,
    adapter: InvenioAdapter,
) -> IngestResponse:
    try:
        prepared = await adapter.submit_ingest(payload, user.username)
    except InvenioAdapterError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return IngestResponse(status="accepted", submitted_by=user.username, payload=prepared)
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from invenioscan.adapters.base import InvenioAdapter, InvenioAdapterError
from invenioscan.dependencies import get_current_user, get_invenio_adapter
from invenioscan.schemas import CurrentUserResponse, IngestRequest, IngestResponse

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("", response_model=IngestResponse, status_code=status.HTTP_202_ACCEPTED)
async def ingest(
    payload: IngestRequest,
    user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    adapter: Annotated[InvenioAdapter, Depends(get_invenio_adapter)],
) -> IngestResponse:
    try:
        prepared = await adapter.submit_ingest(payload, user.username)
    except InvenioAdapterError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return IngestResponse(status="accepted", submitted_by=user.username, payload=prepared)
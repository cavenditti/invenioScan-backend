from typing import Annotated

from fastapi import APIRouter, Depends, status

from invenioscan.adapters.base import InvenioAdapter
from invenioscan.dependencies import get_current_user, get_invenio_adapter
from invenioscan.schemas import CurrentUserResponse, IngestRequest, IngestResponse

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("", response_model=IngestResponse, status_code=status.HTTP_202_ACCEPTED)
async def ingest(
    payload: IngestRequest,
    user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    adapter: Annotated[InvenioAdapter, Depends(get_invenio_adapter)],
) -> IngestResponse:
    prepared = await adapter.submit_ingest(payload, user.username)
    return IngestResponse(status="accepted", submitted_by=user.username, payload=prepared)
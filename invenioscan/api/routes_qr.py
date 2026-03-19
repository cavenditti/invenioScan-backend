from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from invenioscan.qr import build_shelf_payload, generate_qr_png
from invenioscan.schemas import ShelfPosition, ShelfQRCodePayload, ShelfQRCodeRequest
from invenioscan.settings import Settings, get_settings

router = APIRouter(prefix="/qr", tags=["qr"])


@router.post("/shelf", response_model=ShelfQRCodePayload)
async def create_shelf_payload(
    payload: ShelfQRCodeRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> ShelfQRCodePayload:
    shelf = ShelfPosition(**payload.model_dump())
    return ShelfQRCodePayload(payload=build_shelf_payload(shelf, settings))


@router.get("/shelf.png")
async def create_shelf_png(
    shelf_id: str,
    row: str,
    position: int,
    height: int,
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    shelf = ShelfPosition(shelf_id=shelf_id, row=row, position=position, height=height)
    payload = build_shelf_payload(shelf, settings)
    image = generate_qr_png(payload, settings)
    return Response(content=image, media_type="image/png")
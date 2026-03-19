from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse, Response

from invenioscan.qr import build_shelf_label, build_shelf_payload, generate_qr_png, render_printable_qr_sheet
from invenioscan.schemas import ShelfPosition, ShelfQRCodePayload, ShelfQRCodeRequest, ShelfQRCodeSheetRequest
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


@router.post("/sheet", response_class=HTMLResponse)
async def create_shelf_sheet(
    payload: ShelfQRCodeSheetRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> HTMLResponse:
    labels: list[tuple[ShelfPosition, str]] = []
    for row in payload.rows:
        for position in payload.positions:
            shelf_id = build_shelf_label(row, position, payload.height)
            labels.append(
                (
                    ShelfPosition(
                        shelf_id=shelf_id,
                        row=row,
                        position=position,
                        height=payload.height,
                    ),
                    shelf_id,
                )
            )

    html = render_printable_qr_sheet(labels, settings)
    return HTMLResponse(content=html)
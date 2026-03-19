from io import BytesIO
from urllib.parse import urlencode

import qrcode

from invenioscan.schemas import ShelfPosition
from invenioscan.settings import Settings


def build_shelf_payload(shelf: ShelfPosition, settings: Settings) -> str:
    query = urlencode(
        {
            "v": settings.qr_payload_version,
            "row": shelf.row,
            "position": shelf.position,
            "height": shelf.height,
        }
    )
    return f"invscan://shelf/{shelf.shelf_id}?{query}"


def generate_qr_png(payload: str, settings: Settings) -> bytes:
    qr_code = qrcode.QRCode(box_size=settings.qr_box_size, border=settings.qr_border)
    qr_code.add_data(payload)
    qr_code.make(fit=True)
    image = qr_code.make_image(fill_color="black", back_color="white")

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
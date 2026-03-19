from html import escape
from io import BytesIO
from urllib.parse import urlencode

import qrcode
from qrcode.image.svg import SvgPathImage

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


def build_shelf_label(row: str, position: int, height: int) -> str:
    return f"{row}{position}-{height}"


def generate_qr_png(payload: str, settings: Settings) -> bytes:
    qr_code = qrcode.QRCode(box_size=settings.qr_box_size, border=settings.qr_border)
    qr_code.add_data(payload)
    qr_code.make(fit=True)
    image = qr_code.make_image(fill_color="black", back_color="white")

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def generate_qr_svg(payload: str, settings: Settings) -> str:
    qr_code = qrcode.QRCode(box_size=settings.qr_box_size, border=settings.qr_border)
    qr_code.add_data(payload)
    qr_code.make(fit=True)
    image = qr_code.make_image(image_factory=SvgPathImage)

    buffer = BytesIO()
    image.save(buffer)
    return buffer.getvalue().decode("utf-8")


def render_printable_qr_sheet(labels: list[tuple[ShelfPosition, str]], settings: Settings) -> str:
    cards = []
    for shelf, text_label in labels:
        payload = build_shelf_payload(shelf, settings)
        svg = generate_qr_svg(payload, settings)
        cards.append(
            "".join(
                [
                    '<article class="label-card">',
                    f'<div class="qr-box">{svg}</div>',
                    f'<div class="label-text">{escape(text_label)}</div>',
                    "</article>",
                ]
            )
        )

    return "".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            "<title>InvenioScan QR Sheet</title>",
            "<style>",
            "@page { size: A4 portrait; margin: 10mm; }",
            "body { font-family: Helvetica, Arial, sans-serif; margin: 0; color: #111; }",
            ".sheet { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8mm; }",
            ".label-card { border: 0.3mm solid #bbb; border-radius: 2mm; padding: 3mm; break-inside: avoid; text-align: center; }",
            ".qr-box svg { width: 100%; height: auto; }",
            ".label-text { margin-top: 2mm; font-size: 10pt; font-weight: 700; letter-spacing: 0.04em; }",
            "</style>",
            "</head>",
            "<body>",
            f'<main class="sheet">{"".join(cards)}</main>',
            "</body>",
            "</html>",
        ]
    )
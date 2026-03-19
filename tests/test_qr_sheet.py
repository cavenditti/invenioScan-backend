from invenioscan.qr import build_shelf_label, render_printable_qr_sheet
from invenioscan.schemas import ShelfPosition
from invenioscan.settings import Settings


def test_build_shelf_label() -> None:
    assert build_shelf_label("A", 1, 3) == "A1-3"


def test_render_printable_qr_sheet_contains_expected_labels() -> None:
    settings = Settings()
    labels = [
        (ShelfPosition(shelf_id="A1-3", row="A", position=1, height=3), "A1-3"),
        (ShelfPosition(shelf_id="A2-3", row="A", position=2, height=3), "A2-3"),
    ]

    html = render_printable_qr_sheet(labels, settings)

    assert "A1-3" in html
    assert "A2-3" in html
    assert "<svg" in html
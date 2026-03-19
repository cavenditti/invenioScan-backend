import json

import httpx
import pytest

from invenioscan.adapters.invenio_ils import InvenioILSAdapter
from invenioscan.schemas import IngestRequest, ShelfPosition, SourceType
from invenioscan.settings import Settings


def build_settings() -> Settings:
    return Settings(
        invenio_base_url="https://ils.example.org",
        invenio_api_token="secret-token",
        invenio_default_internal_location_pid="ilocid-1",
    )


@pytest.mark.asyncio
async def test_submit_ingest_creates_document_and_item_for_isbn() -> None:
    captured: list[tuple[str, dict]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        json_payload = json.loads(request.content.decode())
        captured.append((request.url.path, json_payload))
        if request.url.path == "/api/documents":
            return httpx.Response(201, json={"id": "docid-1", "metadata": {"pid": "docid-1"}})
        if request.url.path == "/api/items":
            return httpx.Response(201, json={"id": "itemid-1", "metadata": {"pid": "itemid-1"}})
        raise AssertionError(f"Unexpected path {request.url.path}")

    adapter = InvenioILSAdapter(build_settings())
    transport = httpx.MockTransport(handler)
    adapter._build_client = lambda: httpx.AsyncClient(  # type: ignore[method-assign]
        transport=transport,
        base_url="https://ils.example.org",
        headers={"Authorization": "Bearer secret-token", "Content-Type": "application/json"},
    )

    payload = IngestRequest(
        shelf=ShelfPosition(shelf_id="shelf-1", row="A", position=4, height=3),
        source_type=SourceType.ISBN,
        isbn="9780000000002",
        title="My Book",
        author="A. Writer",
    )

    result = await adapter.submit_ingest(payload, "operator")

    assert result.remote_document_pid == "docid-1"
    assert result.remote_item_pid == "itemid-1"
    assert result.remote_eitem_pid is None
    assert captured[0][0] == "/api/documents"
    assert captured[1][0] == "/api/items"
    assert captured[0][1]["title"] == "My Book"
    assert captured[0][1]["authors"] == [{"full_name": "A. Writer"}]
    assert captured[1][1]["internal_location_pid"] == "ilocid-1"
    assert captured[1][1]["shelf"] == "shelf-1|row=A|position=4|height=3"


@pytest.mark.asyncio
async def test_submit_ingest_creates_document_and_eitem_for_public_image_reference() -> None:
    captured: list[tuple[str, dict]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        json_payload = json.loads(request.content.decode())
        captured.append((request.url.path, json_payload))
        if request.url.path == "/api/documents":
            return httpx.Response(201, json={"id": "docid-2", "metadata": {"pid": "docid-2"}})
        if request.url.path == "/api/eitems":
            return httpx.Response(201, json={"id": "eitemid-2", "metadata": {"pid": "eitemid-2"}})
        raise AssertionError(f"Unexpected path {request.url.path}")

    adapter = InvenioILSAdapter(build_settings())
    transport = httpx.MockTransport(handler)
    adapter._build_client = lambda: httpx.AsyncClient(  # type: ignore[method-assign]
        transport=transport,
        base_url="https://ils.example.org",
        headers={"Authorization": "Bearer secret-token", "Content-Type": "application/json"},
    )

    payload = IngestRequest(
        shelf=ShelfPosition(shelf_id="shelf-9", row="C", position=7, height=1),
        source_type=SourceType.IMAGE_REFERENCE,
        image_reference="https://cdn.example.org/scan.jpg",
    )

    result = await adapter.submit_ingest(payload, "operator")

    assert result.remote_document_pid == "docid-2"
    assert result.remote_item_pid is None
    assert result.remote_eitem_pid == "eitemid-2"
    assert captured[0][1]["document_type"] == "MULTIMEDIA"
    assert captured[1][1]["eitem_type"] == "VIDEO"
    assert captured[1][1]["urls"][0]["value"] == "https://cdn.example.org/scan.jpg"
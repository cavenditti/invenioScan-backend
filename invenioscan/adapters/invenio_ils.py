from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import urlparse
from uuid import uuid4

import httpx

from invenioscan.adapters.base import InvenioAdapter, InvenioAdapterError
from invenioscan.schemas import IngestRequest, PreparedMetadata
from invenioscan.settings import Settings


class InvenioILSAdapter(InvenioAdapter):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def submit_ingest(self, request: IngestRequest, submitted_by: str) -> PreparedMetadata:
        self._ensure_configuration()

        scan_id = str(uuid4())
        notes = self._build_response_notes(request, submitted_by, scan_id)
        identifiers = self._build_response_identifiers(request)

        async with self._build_client() as client:
            document_payload = self._build_document_payload(request, submitted_by, scan_id)
            document_response = await self._post_json(client, "/api/documents", document_payload)
            remote_document_pid = self._extract_pid(document_response)

            remote_item_pid: str | None = None
            if request.source_type.value == "isbn" and self.settings.invenio_default_internal_location_pid:
                item_payload = self._build_item_payload(request, submitted_by, scan_id, remote_document_pid)
                item_response = await self._post_json(client, "/api/items", item_payload)
                remote_item_pid = self._extract_pid(item_response)

            remote_eitem_pid: str | None = None
            if request.source_type.value == "image_reference":
                eitem_payload = self._build_eitem_payload(request, submitted_by, scan_id, remote_document_pid)
                eitem_response = await self._post_json(client, "/api/eitems", eitem_payload)
                remote_eitem_pid = self._extract_pid(eitem_response)

        return PreparedMetadata(
            scan_id=scan_id,
            title=self._resolve_title(request, scan_id),
            author=self._resolve_author(request),
            isbn=request.isbn,
            image_reference=request.image_reference,
            source_type=request.source_type,
            shelf=request.shelf,
            remote_document_pid=remote_document_pid,
            remote_item_pid=remote_item_pid,
            remote_eitem_pid=remote_eitem_pid,
            identifiers=identifiers,
            notes=notes,
        )

    def _ensure_configuration(self) -> None:
        if not self.settings.invenio_base_url:
            raise InvenioAdapterError("INVSCAN_INVENIO_BASE_URL is not configured", status_code=500)
        if not self.settings.invenio_api_token:
            raise InvenioAdapterError("INVSCAN_INVENIO_API_TOKEN is not configured", status_code=500)

    def _build_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.settings.invenio_base_url.rstrip("/"),
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self.settings.invenio_api_token}",
                "Content-Type": "application/json",
            },
            timeout=self.settings.invenio_timeout_seconds,
        )

    async def _post_json(self, client: httpx.AsyncClient, endpoint: str, payload: dict) -> dict:
        try:
            response = await client.post(endpoint, json=payload)
        except httpx.HTTPError as exc:
            raise InvenioAdapterError(f"InvenioILS request failed for {endpoint}: {exc}") from exc

        if response.is_error:
            details = self._parse_json_response(response)
            message = self._extract_error_message(details) or response.text or response.reason_phrase
            raise InvenioAdapterError(
                f"InvenioILS rejected {endpoint}: {message}",
                status_code=502,
                details=details if isinstance(details, dict) else None,
            )

        data = self._parse_json_response(response)
        if not isinstance(data, dict):
            raise InvenioAdapterError(f"InvenioILS returned an invalid response for {endpoint}")
        return data

    def _parse_json_response(self, response: httpx.Response) -> dict | list | str | None:
        try:
            return response.json()
        except ValueError:
            return response.text

    def _extract_error_message(self, details: dict | list | str | None) -> str | None:
        if isinstance(details, dict):
            for key in ("message", "detail", "description", "errors"):
                value = details.get(key)
                if value:
                    return str(value)
        if isinstance(details, str) and details.strip():
            return details.strip()
        return None

    def _extract_pid(self, data: dict) -> str:
        metadata = data.get("metadata", {}) if isinstance(data.get("metadata"), dict) else {}
        pid = metadata.get("pid") or data.get("id")
        if not pid:
            raise InvenioAdapterError("InvenioILS response did not include a record PID")
        return str(pid)

    def _build_document_payload(self, request: IngestRequest, submitted_by: str, scan_id: str) -> dict:
        title = self._resolve_title(request, scan_id)
        author = self._resolve_author(request)
        document_type = self._resolve_document_type(request)
        payload = {
            "title": title,
            "authors": [{"full_name": author}],
            "publication_year": str(datetime.now(UTC).year),
            "document_type": document_type,
            "languages": [self.settings.invenio_default_language],
            "source": "INVSCAN",
            "keywords": self._build_document_keywords(request, scan_id),
            "internal_notes": self._build_document_internal_notes(request, submitted_by, scan_id),
        }

        identifiers = []
        if request.isbn:
            identifiers.append({"scheme": "ISBN", "value": request.isbn})
            payload["cover_metadata"] = {"isbn": request.isbn}
        if identifiers:
            payload["identifiers"] = identifiers

        return payload

    def _build_item_payload(
        self,
        request: IngestRequest,
        submitted_by: str,
        scan_id: str,
        document_pid: str,
    ) -> dict:
        if not self.settings.invenio_default_internal_location_pid:
            raise InvenioAdapterError("INVSCAN_INVENIO_DEFAULT_INTERNAL_LOCATION_PID is required for item creation")

        payload = {
            "document_pid": document_pid,
            "internal_location_pid": self.settings.invenio_default_internal_location_pid,
            "status": self.settings.invenio_default_item_status,
            "circulation_restriction": self.settings.invenio_default_item_circulation_restriction,
            "medium": self.settings.invenio_default_item_medium,
            "shelf": self._format_shelf_string(request),
            "description": self._resolve_title(request, scan_id),
            "internal_notes": self._build_item_internal_notes(request, submitted_by, scan_id),
        }
        if request.isbn:
            payload["isbns"] = [{"value": request.isbn, "description": "InvenioScan import"}]
        return payload

    def _build_eitem_payload(
        self,
        request: IngestRequest,
        submitted_by: str,
        scan_id: str,
        document_pid: str,
    ) -> dict:
        payload = {
            "document_pid": document_pid,
            "eitem_type": self.settings.invenio_default_eitem_type,
            "source": "INVSCAN",
            "description": self._resolve_title(request, scan_id),
            "internal_notes": self._build_eitem_internal_notes(request, submitted_by, scan_id),
            "open_access": self._is_public_url(request.image_reference),
        }

        if request.image_reference and self._is_public_url(request.image_reference):
            payload["urls"] = [
                {
                    "value": request.image_reference,
                    "description": "InvenioScan captured image reference",
                    "login_required": False,
                }
            ]

        return payload

    def _build_document_keywords(self, request: IngestRequest, scan_id: str) -> list[dict[str, str]]:
        return [
            {"source": "invscan", "value": f"scan_id:{scan_id}"},
            {"source": "invscan", "value": f"source_type:{request.source_type.value}"},
            {"source": "invscan", "value": f"shelf_id:{request.shelf.shelf_id}"},
            {"source": "invscan", "value": f"row:{request.shelf.row}"},
            {"source": "invscan", "value": f"position:{request.shelf.position}"},
            {"source": "invscan", "value": f"height:{request.shelf.height}"},
        ]

    def _build_document_internal_notes(
        self,
        request: IngestRequest,
        submitted_by: str,
        scan_id: str,
    ) -> list[dict[str, str]]:
        values = [
            f"scan_id={scan_id}",
            f"submitted_by={submitted_by}",
            f"source_type={request.source_type.value}",
            f"shelf_id={request.shelf.shelf_id}",
            f"row={request.shelf.row}",
            f"position={request.shelf.position}",
            f"height={request.shelf.height}",
        ]
        if request.image_reference:
            values.append(f"image_reference={request.image_reference}")
        return [{"field": "invscan", "user": submitted_by, "value": value} for value in values]

    def _build_item_internal_notes(self, request: IngestRequest, submitted_by: str, scan_id: str) -> str:
        return (
            f"InvenioScan scan_id={scan_id}; submitted_by={submitted_by}; "
            f"shelf_id={request.shelf.shelf_id}; row={request.shelf.row}; "
            f"position={request.shelf.position}; height={request.shelf.height}"
        )

    def _build_eitem_internal_notes(self, request: IngestRequest, submitted_by: str, scan_id: str) -> str:
        base = (
            f"InvenioScan image scan_id={scan_id}; submitted_by={submitted_by}; "
            f"shelf_id={request.shelf.shelf_id}; row={request.shelf.row}; "
            f"position={request.shelf.position}; height={request.shelf.height}"
        )
        if request.image_reference and not self._is_public_url(request.image_reference):
            return f"{base}; image_reference={request.image_reference}"
        return base

    def _build_response_notes(self, request: IngestRequest, submitted_by: str, scan_id: str) -> list[str]:
        notes = [
            f"scan_id:{scan_id}",
            f"submitted_by:{submitted_by}",
            f"source_type:{request.source_type.value}",
            f"shelf_id:{request.shelf.shelf_id}",
            f"shelf_row:{request.shelf.row}",
            f"shelf_position:{request.shelf.position}",
            f"shelf_height:{request.shelf.height}",
        ]
        if request.image_reference:
            notes.append(f"image_reference:{request.image_reference}")
        return notes

    def _build_response_identifiers(self, request: IngestRequest) -> list[dict[str, str]]:
        identifiers = []
        if request.isbn:
            identifiers.append({"scheme": "ISBN", "value": request.isbn})
        return identifiers

    def _resolve_title(self, request: IngestRequest, scan_id: str) -> str:
        if request.title:
            return request.title
        if request.isbn:
            return f"ISBN {request.isbn}"
        return f"Uncatalogued scan {scan_id[:8]}"

    def _resolve_author(self, request: IngestRequest) -> str:
        return request.author or "Unknown"

    def _resolve_document_type(self, request: IngestRequest) -> str:
        if request.source_type.value == "image_reference":
            return self.settings.invenio_default_image_document_type
        return self.settings.invenio_default_book_document_type

    def _format_shelf_string(self, request: IngestRequest) -> str:
        return (
            f"{request.shelf.shelf_id}|row={request.shelf.row}|"
            f"position={request.shelf.position}|height={request.shelf.height}"
        )

    def _is_public_url(self, value: str | None) -> bool:
        if not value:
            return False
        parsed = urlparse(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
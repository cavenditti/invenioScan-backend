from invenioscan.adapters.base import InvenioAdapter
from invenioscan.schemas import IngestRequest, PreparedMetadata
from invenioscan.settings import Settings


class InvenioILSAdapter(InvenioAdapter):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def submit_ingest(self, request: IngestRequest, submitted_by: str) -> PreparedMetadata:
        notes = [
            f"submitted_by:{submitted_by}",
            f"shelf_row:{request.shelf.row}",
            f"shelf_position:{request.shelf.position}",
            f"shelf_height:{request.shelf.height}",
        ]
        identifiers = [
            {"scheme": "INVSCAN_SHELF_ID", "value": request.shelf.shelf_id},
            {"scheme": "INVSCAN_SOURCE_TYPE", "value": request.source_type.value},
        ]

        return PreparedMetadata(
            title=request.title,
            author=request.author,
            isbn=request.isbn,
            image_reference=request.image_reference,
            source_type=request.source_type,
            shelf=request.shelf,
            identifiers=identifiers,
            notes=notes,
        )
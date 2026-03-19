from abc import ABC, abstractmethod

from invenioscan.schemas import IngestRequest, PreparedMetadata


class InvenioAdapterError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 502, details: dict | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.details = details or {}


class InvenioAdapter(ABC):
    @abstractmethod
    async def submit_ingest(self, request: IngestRequest, submitted_by: str) -> PreparedMetadata:
        raise NotImplementedError
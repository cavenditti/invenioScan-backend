from abc import ABC, abstractmethod

from invenioscan.schemas import IngestRequest, PreparedMetadata


class InvenioAdapter(ABC):
    @abstractmethod
    async def submit_ingest(self, request: IngestRequest, submitted_by: str) -> PreparedMetadata:
        raise NotImplementedError
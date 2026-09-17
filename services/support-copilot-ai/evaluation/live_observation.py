from app.config import Settings
from app.knowledge import KnowledgeRetriever, RetrievalRequest
from app.models import RetrievalHit


class ObservedKnowledgeRetriever(KnowledgeRetriever):
    """Retain live evidence independently of a later local fallback response."""

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self._live_hits: dict[str, tuple[RetrievalHit, ...]] = {}

    async def search(self, request: RetrievalRequest) -> list[RetrievalHit]:
        hits = await super().search(request)
        if request.live:
            self._live_hits[request.ticket.id] = tuple(hits)
        return hits

    def take_live_hits(self, ticket_id: str) -> tuple[RetrievalHit, ...] | None:
        return self._live_hits.pop(ticket_id, None)

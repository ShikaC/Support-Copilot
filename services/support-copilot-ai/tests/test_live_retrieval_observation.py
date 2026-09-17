import pytest

from app.config import Settings
from app.knowledge import KnowledgeRetriever, RetrievalRequest
from app.models import BUNDLED_KNOWLEDGE_ACCESS, RetrievalHit, TicketInput


@pytest.mark.anyio
async def test_local_fallback_does_not_overwrite_observed_live_retrieval(monkeypatch) -> None:
    from evaluation.live_observation import ObservedKnowledgeRetriever

    # Given a live retrieval with no evidence followed by local fallback evidence.
    settings = Settings(ai_mode="mock", _env_file=None)
    retriever = ObservedKnowledgeRetriever(settings)
    request = RetrievalRequest(ticket=TicketInput(id="observed", subject="重复扣款", description="账单"),
                               query="重复扣款 账单", top_n=10, top_k=3, live=True,
                               knowledge_access=BUNDLED_KNOWLEDGE_ACCESS)
    original_search = KnowledgeRetriever.search

    async def search(self: KnowledgeRetriever, value: RetrievalRequest) -> list[RetrievalHit]:
        return [] if value.live else await original_search(self, value)

    monkeypatch.setattr(KnowledgeRetriever, "search", search)
    # When both paths execute for the same ticket.
    await retriever.search(request)
    local = RetrievalRequest(ticket=request.ticket, query=request.query, top_n=10, top_k=3,
                             live=False, knowledge_access=request.knowledge_access)
    assert await retriever.search(local)
    # Then an observed empty live result is distinct from an unobserved result.
    assert retriever.take_live_hits("observed") == ()
    assert retriever.take_live_hits("observed") is None

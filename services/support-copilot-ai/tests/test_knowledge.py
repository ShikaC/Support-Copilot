import pytest

from app.config import Settings
from app.knowledge import KnowledgeRetriever
from app.models import Priority, TicketInput


@pytest.mark.asyncio
async def test_exact_error_code_ranks_matching_chunk_first() -> None:
    retriever = KnowledgeRetriever(Settings(ai_mode="mock"))
    ticket = TicketInput(
        id="ticket-sync",
        subject="客户端提示 SYNC-2047",
        description="Windows 客户端无法同步",
        currentCategory="TECHNICAL",
        currentPriority=Priority.MEDIUM,
    )

    hits = await retriever.search(
        ticket,
        "Windows 客户端 SYNC-2047 同步失败",
        top_n=10,
        top_k=3,
        live=False,
    )

    assert hits[0].chunk_id == "chunk-sync-2047"
    assert hits[0].retrieval_method == "HYBRID_DEMO"

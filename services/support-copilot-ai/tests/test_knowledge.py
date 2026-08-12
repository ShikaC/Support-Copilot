import pytest

from app.config import Settings
from app.knowledge import KnowledgeRetriever
from app.models import Priority, TicketInput


@pytest.mark.asyncio
async def test_exact_error_code_ranks_matching_chunk_first() -> None:
    # 这条测试只验证一个查询是否命中；整体 Hit Rate 需要汇总一组评估案例。
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


@pytest.mark.asyncio
async def test_top_n_controls_local_candidate_pool_before_category_ranking() -> None:
    retriever = KnowledgeRetriever(Settings(ai_mode="mock"))
    ticket = TicketInput(
        id="ticket-privacy-export",
        subject="导出员工数据",
        description="需要处理员工数据导出申请。",
        currentCategory="PRIVACY",
        currentPriority=Priority.HIGH,
    )

    narrow_hits = await retriever.search(
        ticket,
        "数据导出任务",
        top_n=1,
        top_k=1,
        live=False,
    )
    wider_hits = await retriever.search(
        ticket,
        "数据导出任务",
        top_n=2,
        top_k=1,
        live=False,
    )

    assert narrow_hits[0].chunk_id == "chunk-export-04"
    assert wider_hits[0].chunk_id == "chunk-privacy-05"
    assert wider_hits[0].initial_rank == 2
    assert wider_hits[0].rerank_position == 1


@pytest.mark.asyncio
async def test_uncovered_category_does_not_use_unrelated_knowledge_as_evidence() -> None:
    retriever = KnowledgeRetriever(Settings(ai_mode="mock"))
    ticket = TicketInput(
        id="ticket-recovery-unknown",
        subject="很久以前删除的空间能否恢复",
        description="没有项目编号，也不确定删除日期和备份保留范围。",
        currentCategory="DATA_RECOVERY",
        currentPriority=Priority.MEDIUM,
    )

    hits = await retriever.search(
        ticket,
        "很久以前删除的空间能否恢复 没有项目编号，也不确定删除日期和备份保留范围。",
        top_n=10,
        top_k=3,
        live=False,
    )

    assert hits == []

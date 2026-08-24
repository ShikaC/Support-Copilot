import json
from pathlib import Path

import pytest
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import InMemoryVectorStore

from app.config import Settings
from app.knowledge import KnowledgeRetriever
from app.knowledge_source import KnowledgeSourceInvalidError, load_knowledge_chunks
from app.models import Priority, TicketInput


class DeterministicTestEmbeddings(Embeddings):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0]


@pytest.fixture
def external_knowledge_path(tmp_path: Path) -> Path:
    knowledge_path = tmp_path / "authorized-knowledge.json"
    knowledge_path.write_text(
        json.dumps(
            [
                {
                    "chunk_id": "external-login-runbook",
                    "document_id": "external-identity-guide",
                    "document_title": "Identity support runbook",
                    "section": "Error ACME-LOGIN-42",
                    "content": "Escalate ACME-LOGIN-42 with the tenant identifier.",
                    "source_uri": "https://support.example.test/identity/login-42",
                    "categories": ["ACCOUNT_ACCESS"],
                    "keywords": ["ACME-LOGIN-42", "tenant identifier"],
                    "document_version": "2026.08",
                    "status": "PUBLISHED",
                    "updated_at": "2026-08-24",
                }
            ]
        ),
        encoding="utf-8",
    )
    return knowledge_path


@pytest.mark.asyncio
async def test_configured_knowledge_file_drives_retrieval(
    external_knowledge_path: Path,
) -> None:
    # Given: an authorized knowledge file outside the repository's demo data path.
    retriever = KnowledgeRetriever(
        Settings(ai_mode="mock", knowledge_path=external_knowledge_path)
    )
    ticket = TicketInput(
        id="ticket-external-knowledge",
        subject="ACME-LOGIN-42",
        description="The tenant cannot sign in.",
        currentCategory="ACCOUNT_ACCESS",
        currentPriority=Priority.HIGH,
    )

    # When: retrieval runs against the configured source.
    hits = await retriever.search(
        ticket,
        "ACME-LOGIN-42 tenant identifier",
        top_n=10,
        top_k=3,
        live=False,
    )

    # Then: repository demo chunks are not used.
    assert retriever.chunk_count == 1
    assert [hit.chunk_id for hit in hits] == ["external-login-runbook"]


@pytest.mark.asyncio
async def test_external_knowledge_reaches_vector_retrieval(
    external_knowledge_path: Path,
) -> None:
    # Given: the configured external chunk is indexed by a real in-memory vector store.
    retriever = KnowledgeRetriever(
        Settings(ai_mode="mock", knowledge_path=external_knowledge_path)
    )
    retriever._vector_store = InMemoryVectorStore.from_documents(
        [retriever._as_document(chunk) for chunk in retriever._chunks],
        DeterministicTestEmbeddings(),
    )
    ticket = TicketInput(
        id="ticket-external-vector",
        subject="ACME-LOGIN-42",
        description="The tenant cannot sign in.",
        currentCategory="ACCOUNT_ACCESS",
        currentPriority=Priority.HIGH,
    )

    # When: the live retrieval branch executes without a paid API call.
    hits = await retriever.search(
        ticket,
        "ACME-LOGIN-42 tenant identifier",
        top_n=10,
        top_k=3,
        live=True,
    )

    # Then: vector retrieval returns evidence from the external source.
    assert [hit.chunk_id for hit in hits] == ["external-login-runbook"]
    assert hits[0].retrieval_method == "VECTOR"


def test_duplicate_chunk_ids_are_rejected(tmp_path: Path) -> None:
    # Given: an external source with two records that claim the same stable ID.
    knowledge_path = tmp_path / "duplicate-knowledge.json"
    chunk = {
        "chunk_id": "duplicate-id",
        "document_id": "external-guide",
        "document_title": "External guide",
        "section": "Login",
        "content": "Escalate the login incident.",
        "source_uri": "https://support.example.test/login",
        "categories": ["ACCOUNT_ACCESS"],
        "keywords": ["login"],
        "document_version": "2026.08",
        "status": "PUBLISHED",
        "updated_at": "2026-08-24",
    }
    knowledge_path.write_text(json.dumps([chunk, chunk]), encoding="utf-8")

    # When / Then: the trust boundary rejects ambiguous evidence identifiers.
    with pytest.raises(
        KnowledgeSourceInvalidError,
        match="Knowledge source is invalid",
    ) as exc_info:
        KnowledgeRetriever(Settings(ai_mode="mock", knowledge_path=knowledge_path))
    assert exc_info.value.__cause__ is None


def test_missing_provenance_uses_typed_source_error(
    external_knowledge_path: Path,
    tmp_path: Path,
) -> None:
    # Given: a valid corpus configured with a provenance file that does not exist.
    missing_provenance = tmp_path / "missing.provenance.json"

    # When / Then: startup exposes the stable source error boundary.
    with pytest.raises(KnowledgeSourceInvalidError) as exc_info:
        load_knowledge_chunks(external_knowledge_path, missing_provenance)
    assert exc_info.value.path == missing_provenance
    assert exc_info.value.__cause__ is None
    exc_info.value.__traceback__ = None


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

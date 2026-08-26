from datetime import date
from pathlib import Path

import pytest

from app.config import Settings
from app.embedding_artifact import EmbeddingArtifactStore
from app.knowledge import KnowledgeRetriever
from app.knowledge_source import KnowledgeChunk, KnowledgeSourceInvalidError, load_knowledge_chunks, load_knowledge_corpus
from app.models import Priority, SupportScope, TicketInput
from tests.knowledge_access_support import retrieval_request, write_test_corpus


@pytest.fixture
def external_knowledge_path(tmp_path: Path) -> Path:
    knowledge_path = tmp_path / "authorized-knowledge.json"
    write_test_corpus(
        knowledge_path,
        (
            KnowledgeChunk(
                chunk_id="external-login-runbook",
                document_id="external-identity-guide",
                document_title="Identity support runbook",
                section="Error ACME-LOGIN-42",
                content="Escalate ACME-LOGIN-42 with the tenant identifier.",
                source_uri="https://support.example.test/identity/login-42",
                categories=("ACCOUNT_ACCESS",),
                keywords=("ACME-LOGIN-42", "tenant identifier"),
                allowed_scopes=(SupportScope.ACCOUNT,),
                document_version="2026.08",
                status="PUBLISHED",
                updated_at=date(2026, 8, 24),
            ),
        ),
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
        retrieval_request(retriever, ticket, "ACME-LOGIN-42 tenant identifier")
    )

    # Then: repository demo chunks are not used.
    assert retriever.chunk_count == 1
    assert [hit.chunk_id for hit in hits] == ["external-login-runbook"]


@pytest.mark.asyncio
async def test_external_knowledge_reaches_vector_retrieval(
    external_knowledge_path: Path,
    tmp_path: Path,
) -> None:
    # Given: the configured external chunk is indexed by a persisted matrix.
    settings = Settings(
        ai_mode="mock", knowledge_path=external_knowledge_path,
        openai_embedding_model="test-model", embedding_artifact_root=tmp_path / "artifacts",
        embedding_vector_dimension=2,
    )
    retriever = KnowledgeRetriever(settings)

    class AsyncDeterministicProvider:
        async def embed_documents(self, texts: list[str]) -> list[list[float]]:
            return [[1.0, 0.0] for _ in texts]

        async def embed_query(self, _text: str) -> list[float]:
            return [1.0, 0.0]

    provider = AsyncDeterministicProvider()
    store = EmbeddingArtifactStore(settings, load_knowledge_corpus(external_knowledge_path))
    manifest = await store.build(provider)
    store.activate(manifest.artifact_id)
    retriever._live_index._provider = provider
    ticket = TicketInput(
        id="ticket-external-vector",
        subject="ACME-LOGIN-42",
        description="The tenant cannot sign in.",
        currentCategory="ACCOUNT_ACCESS",
        currentPriority=Priority.HIGH,
    )

    # When: the live retrieval branch executes without a paid API call.
    hits = await retriever.search(
        retrieval_request(
            retriever,
            ticket,
            "ACME-LOGIN-42 tenant identifier",
            live=True,
            scopes=(SupportScope.ACCOUNT,),
        )
    )

    # Then: vector retrieval returns evidence from the external source.
    assert [hit.chunk_id for hit in hits] == ["external-login-runbook"]
    assert hits[0].retrieval_method == "VECTOR"


@pytest.mark.asyncio
async def test_live_vector_index_uses_independent_embedding_base_url(
    external_knowledge_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: chat and embedding providers use different compatible endpoints.
    captured: dict[str, str | int | None] = {}

    class CapturingEmbeddings:
        def __init__(
            self,
            *,
            api_key: str | None,
            base_url: str | None,
            model: str | None,
            max_retries: int,
            request_timeout: float,
        ) -> None:
            del model, request_timeout
            captured["base_url"] = base_url
            captured["api_key"] = api_key
            captured["max_retries"] = max_retries

        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            return [[1.0, 0.0] for _ in texts]

        def embed_query(self, text: str) -> list[float]:
            return [1.0, 0.0]

    monkeypatch.setattr("app.embedding_provider.OpenAIEmbeddings", CapturingEmbeddings)
    retriever = KnowledgeRetriever(
        Settings(
            ai_mode="live",
            openai_api_key="chat-provider-key",
            openai_embedding_api_key="embedding-provider-key",
            openai_base_url="https://chat.example.test/v1",
            openai_embedding_base_url="https://embedding.example.test/v1",
            openai_max_retries=1,
            knowledge_path=external_knowledge_path,
        )
    )

    # When: the live vector index initializes its embedding store.
    retriever._live_index._get_provider()

    # Then: the embedding client receives the independent endpoint.
    assert captured["base_url"] == "https://embedding.example.test/v1"
    assert captured["api_key"] == "embedding-provider-key"
    assert captured["max_retries"] == 0


@pytest.mark.asyncio
async def test_live_retrieval_rejects_vector_matches_below_minimum_score(
    external_knowledge_path: Path,
    tmp_path: Path,
) -> None:
    # Given: a vector store returns a zero-similarity match for an unrelated query.
    settings = Settings(
            ai_mode="mock", knowledge_path=external_knowledge_path,
            live_retrieval_min_score=0.35,
            openai_embedding_model="test-model", embedding_artifact_root=tmp_path / "artifacts",
            embedding_vector_dimension=2,
    )
    retriever = KnowledgeRetriever(settings)

    class AsyncQueryAwareProvider:
        async def embed_documents(self, texts: list[str]) -> list[list[float]]:
            return [[1.0, 0.0] for _ in texts]

        async def embed_query(self, text: str) -> list[float]:
            return [1.0, 0.0] if "known" in text else [0.0, 1.0]

    provider = AsyncQueryAwareProvider()
    store = EmbeddingArtifactStore(settings, load_knowledge_corpus(external_knowledge_path))
    manifest = await store.build(provider)
    store.activate(manifest.artifact_id)
    retriever._live_index._provider = provider
    ticket = TicketInput(
        id="ticket-low-vector-score",
        subject="Unrelated support question",
        description="The user asks about an unsupported workflow.",
        currentCategory="ACCOUNT_ACCESS",
        currentPriority=Priority.MEDIUM,
    )

    # When: live retrieval evaluates the unrelated query.
    hits = await retriever.search(
        retrieval_request(
            retriever,
            ticket,
            "unrelated workflow",
            live=True,
            scopes=(SupportScope.ACCOUNT,),
        )
    )

    # Then: a low-confidence match is not exposed as evidence.
    assert hits == []


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
        retrieval_request(
        retriever,
        ticket,
        "数据导出任务",
        top_n=1,
        top_k=1,
        scopes=(SupportScope.PRIVACY, SupportScope.TECHNICAL),
        ),
    )
    wider_hits = await retriever.search(
        retrieval_request(
        retriever,
        ticket,
        "数据导出任务",
        top_n=2,
        top_k=1,
        scopes=(SupportScope.PRIVACY, SupportScope.TECHNICAL),
        ),
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
        retrieval_request(
            retriever,
            ticket,
            "很久以前删除的空间能否恢复 没有项目编号，也不确定删除日期和备份保留范围。",
        )
    )

    assert hits == []


@pytest.mark.asyncio
async def test_local_retrieval_rejects_generic_query_below_minimum_score() -> None:
    # Given: a generic product question shares weak character bigrams with the corpus.
    retriever = KnowledgeRetriever(Settings(ai_mode="mock"))
    ticket = TicketInput(
        id="ticket-generic-settings",
        subject="通知设置咨询",
        description="想确认是否支持自定义提醒时间，但没有具体产品模块和处理流程。",
        currentCategory="UNCLASSIFIED",
        currentPriority=Priority.MEDIUM,
    )

    # When: local retrieval evaluates the unsupported question.
    hits = await retriever.search(
        retrieval_request(
            retriever,
            ticket,
            "通知设置咨询 想确认是否支持自定义提醒时间，但没有具体产品模块和处理流程。",
        )
    )

    # Then: weak lexical overlap is not exposed as evidence.
    assert hits == []

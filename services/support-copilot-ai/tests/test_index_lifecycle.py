import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.embedding_artifact import EmbeddingArtifactStore
from app.knowledge import KnowledgeRetriever
from app.embedding_artifact import EmbeddingArtifactError
from app.knowledge_source import load_knowledge_corpus
from tests.knowledge_access_support import (
    CapturingEmbeddings,
    retrieval_request,
    write_canary_corpus,
)
from app.models import TicketInput


class AsyncFakeProvider:
    def __init__(
        self,
        document_vectors: list[list[float]],
        query_vector: list[float],
    ) -> None:
        self.document_vectors = document_vectors
        self.query_vector = query_vector
        self.document_calls = 0
        self.query_calls = 0

    async def embed_documents(self, _texts: list[str]) -> list[list[float]]:
        self.document_calls += 1
        return self.document_vectors

    async def embed_query(self, _text: str) -> list[float]:
        self.query_calls += 1
        return self.query_vector


def _live_settings(knowledge_path: Path, artifact_root: Path) -> Settings:
    return Settings(
        ai_mode="live",
        knowledge_path=knowledge_path,
        openai_api_key="synthetic-test-key",
        openai_chat_model="synthetic-chat-model",
        openai_embedding_model="synthetic-embedding-model",
        embedding_artifact_root=artifact_root,
        embedding_vector_dimension=2,
        embedding_artifact_build_policy="build-if-missing",
        _env_file=None,
    )


@pytest.mark.asyncio
async def test_second_live_process_loads_documents_without_reembedding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    knowledge_path = tmp_path / "knowledge.json"
    write_canary_corpus(knowledge_path)
    settings = _live_settings(knowledge_path, tmp_path / "artifacts")
    embeddings = CapturingEmbeddings()
    monkeypatch.setattr(
        "app.embedding_provider.OpenAIEmbeddings",
        lambda **_kwargs: embeddings,
    )
    ticket = TicketInput(
        id="ticket-lifecycle",
        subject="Duplicate charge",
        description="COLLIDING_CANARY duplicate charge",
        currentCategory="BILLING",
    )

    first = KnowledgeRetriever(settings)
    first_hits = await first.search(
        retrieval_request(
            first,
            ticket,
            "COLLIDING_CANARY duplicate charge",
            live=True,
            scopes=("BILLING",),
        )
    )
    first_document_calls = len(embeddings.documents)
    first_query_calls = len(embeddings.queries)

    second = KnowledgeRetriever(settings)
    second_hits = await second.search(
        retrieval_request(
            second,
            ticket,
            "COLLIDING_CANARY duplicate charge",
            live=True,
            scopes=("BILLING",),
        )
    )

    assert [hit.chunk_id for hit in second_hits] == [
        hit.chunk_id for hit in first_hits
    ]
    assert first_document_calls == 2
    assert first_query_calls == 1
    assert len(embeddings.documents) == first_document_calls
    assert len(embeddings.queries) == first_query_calls + 1


@pytest.mark.asyncio
async def test_activation_and_rollback_restore_ranking_without_reembedding(
    tmp_path: Path,
) -> None:
    knowledge_path = tmp_path / "knowledge.json"
    write_canary_corpus(knowledge_path)
    settings = _live_settings(knowledge_path, tmp_path / "artifacts").model_copy(
        update={"embedding_artifact_build_policy": "require-active"}
    )
    store = EmbeddingArtifactStore(settings, load_knowledge_corpus(knowledge_path))
    next_knowledge_path = tmp_path / "next-knowledge.json"
    payload = json.loads(knowledge_path.read_text(encoding="utf-8"))
    payload["release_version"] = 2
    next_knowledge_path.write_text(json.dumps(payload), encoding="utf-8")
    next_settings = _live_settings(
        next_knowledge_path,
        tmp_path / "artifacts",
    ).model_copy(update={"embedding_artifact_build_policy": "require-active"})
    next_store = EmbeddingArtifactStore(
        next_settings,
        load_knowledge_corpus(next_knowledge_path),
    )
    first_provider = AsyncFakeProvider([[1.0, 0.0], [0.0, 1.0]], [1.0, 0.0])
    second_provider = AsyncFakeProvider([[0.0, 1.0], [1.0, 0.0]], [1.0, 0.0])
    first = await store.build(first_provider)
    second = await next_store.build(second_provider)
    ticket = TicketInput(
        id="ticket-rollback",
        subject="Support request",
        description="investigation",
        currentCategory="UNCLASSIFIED",
    )

    store.activate(first.artifact_id)
    first_retriever = KnowledgeRetriever(settings)
    first_retriever._live_index._provider = first_provider
    first_hits = await first_retriever.search(
        retrieval_request(first_retriever, ticket, "query", live=True)
    )
    next_store.activate(second.artifact_id)
    second_retriever = KnowledgeRetriever(next_settings)
    second_retriever._live_index._provider = second_provider
    second_hits = await second_retriever.search(
        retrieval_request(second_retriever, ticket, "query", live=True)
    )
    store.rollback()
    recovered_retriever = KnowledgeRetriever(settings)
    recovered_retriever._live_index._provider = first_provider
    recovered_hits = await recovered_retriever.search(
        retrieval_request(recovered_retriever, ticket, "query", live=True)
    )

    assert [hit.chunk_id for hit in first_hits] == ["billing-canary"]
    assert [hit.chunk_id for hit in second_hits] == ["privacy-forbidden-canary"]
    assert [hit.chunk_id for hit in recovered_hits] == ["billing-canary"]
    assert first_provider.document_calls == 1
    assert second_provider.document_calls == 1
    assert first_provider.query_calls == 2
    assert second_provider.query_calls == 1


@pytest.mark.asyncio
async def test_corrupt_active_artifact_degrades_readiness_but_not_liveness(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import main

    knowledge_path = tmp_path / "knowledge.json"
    write_canary_corpus(knowledge_path)
    settings = _live_settings(knowledge_path, tmp_path / "artifacts").model_copy(
        update={"embedding_artifact_build_policy": "require-active"}
    )
    store = EmbeddingArtifactStore(settings, load_knowledge_corpus(knowledge_path))
    provider = AsyncFakeProvider([[1.0, 0.0], [0.0, 1.0]], [1.0, 0.0])
    manifest = await store.build(provider)
    store.activate(manifest.artifact_id)
    (tmp_path / "artifacts" / manifest.artifact_id / "matrix.npy").write_bytes(
        b"corrupt"
    )
    retriever = KnowledgeRetriever(settings)
    monkeypatch.setattr(main, "retriever", retriever)
    ticket = TicketInput(
        id="ticket-corrupt",
        subject="Duplicate charge",
        description="duplicate charge",
        currentCategory="BILLING",
    )

    with pytest.raises(EmbeddingArtifactError, match="artifact-corrupt"):
        await retriever.search(
            retrieval_request(
                retriever,
                ticket,
                "duplicate charge",
                live=True,
                scopes=("BILLING",),
            )
        )

    client = TestClient(main.app)
    ready = client.get("/health/ready")
    assert client.get("/health/live").status_code == 200
    assert ready.status_code == 503
    assert ready.json()["dependencies"]["index"] == "degraded"
    assert ready.json()["indexReason"] == "artifact-corrupt"
    assert provider.query_calls == 0

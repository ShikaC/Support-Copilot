from datetime import date
from pathlib import Path

import pytest

from app.config import Settings
from app.embedding_artifact import EmbeddingArtifactStore
from app.knowledge import KnowledgeRetriever
from app.knowledge_source import KnowledgeChunk, load_knowledge_corpus
from app.models import Priority, SupportScope, TicketInput
from tests.knowledge_access_support import retrieval_request, write_test_corpus


class CapturingTestEmbeddings:
    def __init__(self) -> None:
        self.document_inputs: list[str] = []
        self.query_inputs: list[str] = []

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.document_inputs.extend(texts)
        return [[1.0, 0.0] for _ in texts]

    async def embed_query(self, text: str) -> list[float]:
        self.query_inputs.append(text)
        return [1.0, 0.0]


@pytest.mark.asyncio
async def test_live_embedding_requests_redact_sensitive_data(
    tmp_path: Path,
) -> None:
    # Given: sensitive values appear in both authorized knowledge and the query.
    sensitive_values = (
        "alice@example.com",
        "13800138000",
        "11010519491231002X",
        "4111 1111 1111 1111",
    )
    invalid_card_like_order = "1234 5678 9012 3456"
    knowledge_path = tmp_path / "sensitive-knowledge.json"
    write_test_corpus(
        knowledge_path,
        (
            KnowledgeChunk(
                chunk_id="sensitive-login-runbook",
                document_id="sensitive-identity-guide",
                document_title="Identity support runbook",
                section="Escalation contacts",
                content=" ".join((*sensitive_values, invalid_card_like_order)),
                source_uri="https://support.example.test/identity/sensitive",
                categories=("ACCOUNT_ACCESS",),
                keywords=("login",),
                allowed_scopes=(SupportScope.ACCOUNT,),
                document_version="2026.08",
                status="PUBLISHED",
                updated_at=date(2026, 8, 24),
            ),
        ),
    )
    settings = Settings(
        ai_mode="mock",
        knowledge_path=knowledge_path,
        openai_embedding_model="test-model",
        embedding_artifact_root=tmp_path / "artifacts",
    )
    retriever = KnowledgeRetriever(settings)
    embeddings = CapturingTestEmbeddings()
    store = EmbeddingArtifactStore(settings, load_knowledge_corpus(knowledge_path))
    manifest = await store.build(embeddings)
    store.activate(manifest.artifact_id)
    retriever._live_index._provider = embeddings
    ticket = TicketInput(
        id="ticket-sensitive-vector",
        subject="Enterprise login incident",
        description="Escalation requested.",
        currentCategory="ACCOUNT_ACCESS",
        currentPriority=Priority.HIGH,
    )

    # When: the live vector branch sends documents and a query to its embedding client.
    await retriever.search(
        retrieval_request(
            retriever,
            ticket,
            " ".join((*sensitive_values, invalid_card_like_order)),
            live=True,
            scopes=(SupportScope.ACCOUNT,),
        )
    )

    # Then: external embedding inputs contain markers, never the sensitive values.
    outbound_text = "\n".join((*embeddings.document_inputs, *embeddings.query_inputs))
    assert all(value not in outbound_text for value in sensitive_values)
    assert all(
        marker in outbound_text
        for marker in (
            "[REDACTED_EMAIL]",
            "[REDACTED_PHONE]",
            "[REDACTED_CN_ID]",
            "[REDACTED_PAYMENT_CARD]",
        )
    )
    assert invalid_card_like_order in outbound_text

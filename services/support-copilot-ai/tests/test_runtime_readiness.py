from typing import Never

from fastapi.testclient import TestClient
from openai import OpenAIError
import pytest

from app import main as main_module
from app.analysis_runner import AnalysisRunner
from app.config import Settings
from app.errors import StructuredGenerationApiError
from app.knowledge import KnowledgeRetriever
from app.live_vector_index import RetrievalWindow
from app.models import (
    BUNDLED_KNOWLEDGE_ACCESS,
    AnalyzeRequest,
    ModelDraft,
    RetrievalHit,
    SupportScope,
    TicketInput,
)
from app.openai_provider import OpenAIProvider
from app.workflow import AnalysisWorkflow


TRACE_ID = "trace_runtime_readiness"
INTERNAL_TOKEN = "synthetic-test-internal-service-token"


def live_settings() -> Settings:
    return Settings(
        ai_mode="live",
        openai_api_key="test-key",
        openai_chat_model="test-chat-model",
        openai_embedding_model="test-embedding-model",
        internal_service_token=INTERNAL_TOKEN,
    )


def analyze_payload() -> dict[str, str | dict[str, str | int]]:
    return {
        "traceId": TRACE_ID,
        "knowledgeAccess": BUNDLED_KNOWLEDGE_ACCESS.model_dump(
            by_alias=True, mode="json"
        ),
        "ticket": {
            "id": "ticket-runtime-readiness",
            "subject": "Enterprise SSO login failure",
            "description": "Members cannot enter the workspace.",
            "currentCategory": "ACCOUNT_ACCESS",
            "currentPriority": "HIGH",
        },
        "options": {
            "topN": 10,
            "topK": 3,
            "promptVersion": "ticket-analysis-v1",
        },
    }


def one_retrieval_hit() -> list[RetrievalHit]:
    return [
        RetrievalHit(
            chunkId="account-evidence",
            documentId="account-guide",
            documentTitle="Account access runbook",
            section="SSO login",
            content="Check the identity provider callback and domain configuration.",
            sourceUri="knowledge://account-guide",
            retrievalMethod="VECTOR",
            initialRank=1,
            initialScore=0.9,
            rerankPosition=1,
            rerankScore=0.9,
            usedAsEvidence=True,
        )
    ]


def successful_draft() -> ModelDraft:
    return ModelDraft(
        evidence_sufficient=True,
        intent="Restore enterprise account access",
        category="ACCOUNT_ACCESS",
        priority="HIGH",
        sentiment="NEGATIVE",
        confidence=0.91,
        reason_summary="The evidence covers enterprise SSO troubleshooting.",
        reply_content="Please verify the identity provider callback configuration.",
        warnings=[],
        citation_indexes=[1],
    )


@pytest.mark.asyncio
async def test_embedding_failure_degrades_readiness_until_live_processing_recovers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: a valid live workflow whose embedding dependency fails on real retrieval.
    settings = live_settings()
    retriever = KnowledgeRetriever(settings)
    workflow = AnalysisWorkflow(settings, retriever)
    runner = AnalysisRunner(settings, workflow)
    provider = workflow._provider
    assert isinstance(provider, OpenAIProvider)

    async def unavailable_embeddings(
        ticket: TicketInput,
        query: str,
        window: RetrievalWindow,
        allowed_scopes: tuple[SupportScope, ...],
    ) -> Never:
        raise OpenAIError("synthetic embedding outage")

    async def available_embeddings(
        ticket: TicketInput,
        query: str,
        window: RetrievalWindow,
        allowed_scopes: tuple[SupportScope, ...],
    ) -> list[RetrievalHit]:
        return one_retrieval_hit()

    async def available_generation(
        request: AnalyzeRequest,
        evidence: list[RetrievalHit],
    ) -> tuple[ModelDraft, int, int]:
        return successful_draft(), 12, 8

    monkeypatch.setattr(retriever._live_index, "search", unavailable_embeddings)
    monkeypatch.setattr(provider, "analyze", available_generation)
    monkeypatch.setattr(main_module, "settings", settings)
    monkeypatch.setattr(main_module, "retriever", retriever)
    monkeypatch.setattr(main_module, "runner", runner)
    client = TestClient(
        main_module.app,
        headers={
            "X-Internal-Service-Token": INTERNAL_TOKEN,
            "X-Trace-Id": TRACE_ID,
        },
    )

    # When: processing observes the embedding failure and returns its established fallback.
    degraded_analysis = client.post("/analyze", json=analyze_payload())

    # Then: readiness is degraded without affecting process liveness.
    assert degraded_analysis.status_code == 200
    assert degraded_analysis.json()["fallbackReason"] == "embedding_api_error"
    assert client.get("/health/live").status_code == 200
    degraded_ready = client.get("/health/ready")
    assert degraded_ready.status_code == 503
    assert degraded_ready.json()["dependencies"] == {
        "provider": "degraded",
        "index": "degraded",
    }

    # When: the same real workflow completes retrieval and generation successfully.
    monkeypatch.setattr(retriever._live_index, "search", available_embeddings)
    recovered_analysis = client.post("/analyze", json=analyze_payload())

    # Then: controlled success recovers readiness and liveness remains independent.
    assert recovered_analysis.status_code == 200
    assert recovered_analysis.json()["mode"] == "live"
    assert client.get("/health/live").status_code == 200
    recovered_ready = client.get("/health/ready")
    assert recovered_ready.status_code == 200
    assert recovered_ready.json()["dependencies"] == {
        "provider": "up",
        "index": "up",
    }


@pytest.mark.asyncio
async def test_generation_failure_preserves_index_until_generation_recovers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: live retrieval succeeds before structured generation fails.
    settings = live_settings()
    retriever = KnowledgeRetriever(settings)
    workflow = AnalysisWorkflow(settings, retriever)
    runner = AnalysisRunner(settings, workflow)
    provider = workflow._provider
    assert isinstance(provider, OpenAIProvider)

    async def available_embeddings(
        ticket: TicketInput,
        query: str,
        window: RetrievalWindow,
        allowed_scopes: tuple[SupportScope, ...],
    ) -> list[RetrievalHit]:
        return one_retrieval_hit()

    async def unavailable_generation(
        request: AnalyzeRequest,
        evidence: list[RetrievalHit],
    ) -> Never:
        raise StructuredGenerationApiError

    async def available_generation(
        request: AnalyzeRequest,
        evidence: list[RetrievalHit],
    ) -> tuple[ModelDraft, int, int]:
        return successful_draft(), 12, 8

    monkeypatch.setattr(retriever._live_index, "search", available_embeddings)
    monkeypatch.setattr(provider, "analyze", unavailable_generation)
    monkeypatch.setattr(main_module, "settings", settings)
    monkeypatch.setattr(main_module, "retriever", retriever)
    monkeypatch.setattr(main_module, "runner", runner)
    client = TestClient(
        main_module.app,
        headers={
            "X-Internal-Service-Token": INTERNAL_TOKEN,
            "X-Trace-Id": TRACE_ID,
        },
    )

    # When: processing reaches the typed generation failure.
    degraded_analysis = client.post("/analyze", json=analyze_payload())

    # Then: only provider readiness degrades and liveness remains up.
    assert degraded_analysis.status_code == 200
    assert degraded_analysis.json()["fallbackReason"] == (
        "structured_generation_api_error"
    )
    assert client.get("/health/live").status_code == 200
    degraded_ready = client.get("/health/ready")
    assert degraded_ready.status_code == 503
    assert degraded_ready.json()["dependencies"] == {
        "provider": "degraded",
        "index": "up",
    }

    # When: the same workflow later completes structured generation.
    monkeypatch.setattr(provider, "analyze", available_generation)
    recovered_analysis = client.post("/analyze", json=analyze_payload())

    # Then: generation success deterministically recovers provider readiness.
    assert recovered_analysis.status_code == 200
    assert recovered_analysis.json()["mode"] == "live"
    assert client.get("/health/ready").status_code == 200

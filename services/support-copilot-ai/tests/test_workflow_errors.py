import logging
from typing import Never

from _pytest.logging import LogCaptureFixture
import httpx
import pytest
from openai import APITimeoutError, OpenAIError

from app.config import Settings
from app.errors import (
    ExternalAiServiceError,
    InvalidModelResponseError,
    ModelResponseFailureKind,
    StructuredGenerationResponseTimeoutError,
)
from app.knowledge import KnowledgeRetriever, RetrievalRequest
from app.live_vector_index import RetrievalWindow
from app.models import (
    BUNDLED_KNOWLEDGE_ACCESS,
    AnalyzeRequest,
    RetrievalHit,
    SupportScope,
    TicketInput,
)
from app.openai_provider import OpenAIProvider
from app.workflow import AnalysisWorkflow


class SimulatedProgrammingError(RuntimeError):
    pass


def live_settings() -> Settings:
    return Settings(
        ai_mode="live",
        openai_api_key="test-key",
        openai_chat_model="test-chat-model",
        openai_embedding_model="test-embedding-model",
        openai_max_retries=0,
    )


def analyze_request() -> AnalyzeRequest:
    return AnalyzeRequest(
        traceId="trace_workflow_error",
        knowledgeAccess=BUNDLED_KNOWLEDGE_ACCESS,
        ticket=TicketInput(
            id="ticket-error-test",
            subject="企业账号无法登录",
            description="管理员和成员都无法进入工作区。",
            currentCategory="ACCOUNT_ACCESS",
        ),
    )


async def no_retrieval_hits(_request: RetrievalRequest) -> list[RetrievalHit]:
    return []


def one_retrieval_hit() -> list[RetrievalHit]:
    return [
        RetrievalHit(
            chunkId="account-evidence",
            documentId="account-guide",
            documentTitle="账号访问排查手册",
            section="SSO 登录循环",
            content="请检查身份提供商回调和域名配置。",
            sourceUri="knowledge://account-guide",
            retrievalMethod="HYBRID_DEMO",
            initialRank=1,
            initialScore=0.9,
            rerankPosition=1,
            rerankScore=0.9,
            usedAsEvidence=True,
        )
    ]


@pytest.mark.asyncio
async def test_recoverable_ai_error_returns_fallback(
    monkeypatch: pytest.MonkeyPatch,
    caplog: LogCaptureFixture,
) -> None:
    # Given: structured generation reaches a recoverable response timeout.
    settings = live_settings()
    retriever = KnowledgeRetriever(settings)
    workflow = AnalysisWorkflow(settings, retriever)

    async def unavailable_provider(
        provider: OpenAIProvider,
        request: AnalyzeRequest,
        evidence: list[RetrievalHit],
    ) -> Never:
        assert request.options.prompt_version == "ticket-analysis-v1"
        raise StructuredGenerationResponseTimeoutError

    async def one_hit_search(_request: RetrievalRequest) -> list[RetrievalHit]:
        return one_retrieval_hit()

    monkeypatch.setattr(retriever, "search", one_hit_search)
    monkeypatch.setattr(OpenAIProvider, "analyze", unavailable_provider)
    caplog.set_level(logging.WARNING, logger="app.workflow")

    # When: the workflow handles the named external failure.
    result = await workflow.run(analyze_request())

    # Then: fallback is explicit and the log preserves the named failure type.
    assert result.status == "FALLBACK"
    assert result.mode == "fallback"
    assert result.fallback_reason == "structured_generation_response_timeout"
    assert result.decision.escalation_required is True
    external_failure = next(
        record
        for record in caplog.records
        if record.message == "analysis.external_failure"
    )
    assert getattr(external_failure, "trace_id") == "trace_workflow_error"
    assert getattr(external_failure, "error_type") == (
        "StructuredGenerationResponseTimeoutError"
    )
    fallback = next(
        record for record in caplog.records if record.message == "analysis.fallback"
    )
    assert getattr(fallback, "trace_id") == "trace_workflow_error"
    assert getattr(fallback, "mode") == "fallback"
    assert getattr(fallback, "status") == "FALLBACK"
    assert getattr(fallback, "hit_count") == 1
    assert getattr(fallback, "reason") == "structured_generation_response_timeout"


@pytest.mark.asyncio
async def test_invalid_model_response_logs_safe_failure_kind(
    monkeypatch: pytest.MonkeyPatch,
    caplog: LogCaptureFixture,
) -> None:
    settings = live_settings()
    retriever = KnowledgeRetriever(settings)
    workflow = AnalysisWorkflow(settings, retriever)
    sensitive_marker = "TASK10_SENSITIVE_MARKER_DO_NOT_LOG"

    async def invalid_provider(
        provider: OpenAIProvider,
        request: AnalyzeRequest,
        evidence: list[RetrievalHit],
    ) -> Never:
        try:
            raise RuntimeError(sensitive_marker)
        except RuntimeError as cause:
            raise InvalidModelResponseError(ModelResponseFailureKind.REFUSAL) from cause

    async def one_hit_search(_request: RetrievalRequest) -> list[RetrievalHit]:
        return one_retrieval_hit()

    monkeypatch.setattr(retriever, "search", one_hit_search)
    monkeypatch.setattr(OpenAIProvider, "analyze", invalid_provider)
    caplog.set_level(logging.WARNING, logger="app.workflow")

    result = await workflow.run(analyze_request())

    external_failure = next(
        record
        for record in caplog.records
        if record.message == "analysis.external_failure"
    )
    assert result.fallback_reason == "invalid_model_response"
    assert getattr(external_failure, "protocol") == settings.openai_chat_protocol
    assert getattr(external_failure, "model_response_failure_kind") == "refusal"
    assert sensitive_marker not in caplog.text


@pytest.mark.asyncio
async def test_programming_error_is_not_hidden_as_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = live_settings()
    retriever = KnowledgeRetriever(settings)
    workflow = AnalysisWorkflow(settings, retriever)

    async def broken_provider(
        provider: OpenAIProvider,
        request: AnalyzeRequest,
        evidence: list[RetrievalHit],
    ) -> Never:
        raise SimulatedProgrammingError("simulated programming defect")

    async def one_hit_search(_request: RetrievalRequest) -> list[RetrievalHit]:
        return one_retrieval_hit()

    monkeypatch.setattr(retriever, "search", one_hit_search)
    monkeypatch.setattr(OpenAIProvider, "analyze", broken_provider)

    with pytest.raises(RuntimeError, match="simulated programming defect"):
        await workflow.run(analyze_request())


@pytest.mark.asyncio
async def test_live_model_is_not_called_without_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = live_settings()
    retriever = KnowledgeRetriever(settings)
    workflow = AnalysisWorkflow(settings, retriever)
    called = False

    async def broken_provider(
        provider: OpenAIProvider,
        request: AnalyzeRequest,
        evidence: list[RetrievalHit],
    ) -> Never:
        nonlocal called
        called = True
        raise AssertionError("model must not receive an empty evidence set")

    monkeypatch.setattr(retriever, "search", no_retrieval_hits)
    monkeypatch.setattr(OpenAIProvider, "analyze", broken_provider)

    result = await workflow.run(analyze_request())

    assert called is False
    assert result.mode == "fallback"
    assert result.status == "FALLBACK"
    assert result.fallback_reason == "insufficient_evidence"


@pytest.mark.asyncio
async def test_live_retrieval_converts_openai_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = live_settings()
    retriever = KnowledgeRetriever(settings)

    async def unavailable_embeddings(
        ticket: TicketInput,
        query: str,
        window: RetrievalWindow,
        allowed_scopes: tuple[SupportScope, ...],
    ) -> Never:
        raise OpenAIError("embedding service unavailable")

    monkeypatch.setattr(retriever._live_index, "search", unavailable_embeddings)

    with pytest.raises(ExternalAiServiceError, match="embedding"):
        from tests.knowledge_access_support import retrieval_request

        await retriever.search(
            retrieval_request(
                retriever,
                analyze_request().ticket,
                "企业账号无法登录",
                live=True,
            )
        )


@pytest.mark.asyncio
async def test_embedding_timeout_preserves_response_timeout_kind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: the embedding endpoint accepts a request but exceeds its response timeout.
    settings = live_settings()
    retriever = KnowledgeRetriever(settings)

    async def time_out_embeddings(
        ticket: TicketInput,
        query: str,
        window: RetrievalWindow,
        allowed_scopes: tuple[SupportScope, ...],
    ) -> Never:
        try:
            raise httpx.ReadTimeout("embedding response timed out")
        except httpx.ReadTimeout as exc:
            raise APITimeoutError(request=httpx.Request("POST", "https://example.test")) from exc

    monkeypatch.setattr(retriever._live_index, "search", time_out_embeddings)

    # When: the retrieval boundary converts the SDK timeout.
    with pytest.raises(ExternalAiServiceError) as error:
        from tests.knowledge_access_support import retrieval_request

        await retriever.search(
            retrieval_request(
                retriever,
                analyze_request().ticket,
                "企业账号无法登录",
                live=True,
            )
        )

    # Then: operators can identify both the embedding stage and timeout kind.
    assert error.value.operation == "embedding"
    assert error.value.failure_kind == "response_timeout"

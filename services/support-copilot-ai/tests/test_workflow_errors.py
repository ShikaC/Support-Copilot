import logging
from typing import Never

from _pytest.logging import LogCaptureFixture
import httpx
import pytest
from openai import APITimeoutError, OpenAIError

from app.config import Settings
from app.errors import (
    ExternalAiServiceError,
    StructuredGenerationResponseTimeoutError,
)
from app.knowledge import KnowledgeRetriever
from app.live_vector_index import RetrievalWindow
from app.models import (
    AnalyzeRequest,
    ModelDraft,
    PromptVersion,
    RetrievalHit,
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


def test_provider_disables_sdk_retries_for_legacy_bounded_setting() -> None:
    settings = live_settings().model_copy(update={"openai_max_retries": 1})

    provider = OpenAIProvider(settings)

    assert provider._client.max_retries == 0


def analyze_request() -> AnalyzeRequest:
    return AnalyzeRequest(
        traceId="trace_workflow_error",
        ticket=TicketInput(
            id="ticket-error-test",
            subject="企业账号无法登录",
            description="管理员和成员都无法进入工作区。",
            currentCategory="ACCOUNT_ACCESS",
        ),
    )


async def no_retrieval_hits(
    ticket: TicketInput,
    query: str,
    top_n: int,
    top_k: int,
    live: bool,
) -> list[RetrievalHit]:
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
        ticket: TicketInput,
        evidence: list[RetrievalHit],
        prompt_version: PromptVersion,
    ) -> Never:
        assert prompt_version == "ticket-analysis-v1"
        raise StructuredGenerationResponseTimeoutError

    async def one_hit_search(*args: object, **kwargs: object) -> list[RetrievalHit]:
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
    assert any(
        "error_type=StructuredGenerationResponseTimeoutError" in record.message
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_programming_error_is_not_hidden_as_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = live_settings()
    retriever = KnowledgeRetriever(settings)
    workflow = AnalysisWorkflow(settings, retriever)

    async def broken_provider(
        provider: OpenAIProvider,
        ticket: TicketInput,
        evidence: list[RetrievalHit],
        prompt_version: PromptVersion,
    ) -> Never:
        raise SimulatedProgrammingError("simulated programming defect")

    async def one_hit_search(*args: object, **kwargs: object) -> list[RetrievalHit]:
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
        ticket: TicketInput,
        evidence: list[RetrievalHit],
        prompt_version: PromptVersion,
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
    ) -> Never:
        raise OpenAIError("embedding service unavailable")

    monkeypatch.setattr(retriever._live_index, "search", unavailable_embeddings)

    with pytest.raises(ExternalAiServiceError, match="embedding"):
        await retriever.search(
            analyze_request().ticket,
            "企业账号无法登录",
            top_n=10,
            top_k=3,
            live=True,
        )


@pytest.mark.asyncio
async def test_provider_converts_openai_error(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = live_settings()
    provider = OpenAIProvider(settings)

    async def unavailable_model(
        **kwargs: str | type[ModelDraft] | None,
    ) -> Never:
        raise OpenAIError("model service unavailable")

    monkeypatch.setattr(provider._client.responses, "parse", unavailable_model)

    with pytest.raises(ExternalAiServiceError, match="structured_generation"):
        await provider.analyze(
            analyze_request().ticket,
            [],
            "ticket-analysis-v1",
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
    ) -> Never:
        try:
            raise httpx.ReadTimeout("embedding response timed out")
        except httpx.ReadTimeout as exc:
            raise APITimeoutError(request=httpx.Request("POST", "https://example.test")) from exc

    monkeypatch.setattr(retriever._live_index, "search", time_out_embeddings)

    # When: the retrieval boundary converts the SDK timeout.
    with pytest.raises(ExternalAiServiceError) as error:
        await retriever.search(
            analyze_request().ticket,
            "企业账号无法登录",
            top_n=10,
            top_k=3,
            live=True,
        )

    # Then: operators can identify both the embedding stage and timeout kind.
    assert error.value.operation == "embedding"
    assert error.value.failure_kind == "response_timeout"


@pytest.mark.asyncio
async def test_generation_timeout_preserves_connection_timeout_kind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: the structured-generation client cannot establish its connection in time.
    provider = OpenAIProvider(live_settings())

    async def time_out_connection(
        **kwargs: str | bool | type[ModelDraft] | None,
    ) -> Never:
        try:
            raise httpx.ConnectTimeout("generation connection timed out")
        except httpx.ConnectTimeout as exc:
            raise APITimeoutError(request=httpx.Request("POST", "https://example.test")) from exc

    monkeypatch.setattr(provider._client.responses, "parse", time_out_connection)

    # When: the model boundary converts the SDK timeout.
    with pytest.raises(ExternalAiServiceError) as error:
        await provider.analyze(
            analyze_request().ticket,
            [],
            "ticket-analysis-v1",
        )

    # Then: operators can identify generation and connection setup as the cause.
    assert error.value.operation == "structured_generation"
    assert error.value.failure_kind == "connection_timeout"


@pytest.mark.asyncio
async def test_provider_redacts_sensitive_data_before_sdk_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: sensitive values occur across the ticket and retrieved evidence.
    sensitive_values = (
        "alice@example.com",
        "13800138000",
        "11010519491231002X",
        "4111 1111 1111 1111",
    )
    invalid_card_like_order = "1234 5678 9012 3456"
    provider = OpenAIProvider(live_settings())
    ticket = TicketInput(
        id="ticket-sensitive-model",
        subject=f"Contact {sensitive_values[0]} or {sensitive_values[1]}",
        description=(
            f"Identity {sensitive_values[2]}, card {sensitive_values[3]}, "
            f"order {invalid_card_like_order}."
        ),
        currentCategory="ACCOUNT_ACCESS",
    )
    evidence = [
        RetrievalHit(
            chunkId="sensitive-evidence",
            documentId="identity-guide",
            documentTitle="Escalation guide",
            section="Sensitive example",
            content=" ".join(sensitive_values),
            sourceUri="https://support.example.test/sensitive",
            retrievalMethod="VECTOR",
            initialRank=1,
            initialScore=0.9,
            rerankPosition=1,
            rerankScore=0.9,
            usedAsEvidence=True,
        )
    ]
    captured_inputs: list[str] = []
    captured_store_values: list[bool | None] = []

    async def capture_model_request(
        **kwargs: str | bool | type[ModelDraft] | None,
    ) -> Never:
        model_input = kwargs.get("input")
        assert isinstance(model_input, str)
        captured_inputs.append(model_input)
        store = kwargs.get("store")
        assert store is None or isinstance(store, bool)
        captured_store_values.append(store)
        raise OpenAIError("stop after capturing the request")

    monkeypatch.setattr(provider._client.responses, "parse", capture_model_request)

    # When: the provider reaches the external SDK boundary.
    with pytest.raises(ExternalAiServiceError, match="structured_generation"):
        await provider.analyze(ticket, evidence, "ticket-analysis-v1")

    # Then: the request is non-persistent and contains only redaction markers.
    outbound_text = captured_inputs[0]
    assert captured_store_values == [False]
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

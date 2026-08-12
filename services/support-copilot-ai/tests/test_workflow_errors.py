from typing import Never

import pytest
from openai import OpenAIError

from app.config import Settings
from app.errors import ExternalAiServiceError
from app.knowledge import KnowledgeRetriever
from app.models import (
    AnalyzeRequest,
    ModelDraft,
    PromptVersion,
    RetrievalHit,
    TicketInput,
)
from app.openai_provider import OpenAIProvider
from app.workflow import AnalysisWorkflow


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


@pytest.mark.asyncio
async def test_recoverable_ai_error_returns_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
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
        raise ExternalAiServiceError(operation="structured analysis")

    monkeypatch.setattr(retriever, "search", no_retrieval_hits)
    monkeypatch.setattr(OpenAIProvider, "analyze", unavailable_provider)

    result = await workflow.run(analyze_request())

    assert result.status == "FALLBACK"
    assert result.mode == "fallback"
    assert result.decision.escalation_required is True


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
        raise RuntimeError("simulated programming defect")

    monkeypatch.setattr(retriever, "search", no_retrieval_hits)
    monkeypatch.setattr(OpenAIProvider, "analyze", broken_provider)

    with pytest.raises(RuntimeError, match="simulated programming defect"):
        await workflow.run(analyze_request())


@pytest.mark.asyncio
async def test_live_retrieval_converts_openai_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = live_settings()
    retriever = KnowledgeRetriever(settings)

    async def unavailable_embeddings(
        ticket: TicketInput,
        query: str,
        top_n: int,
        top_k: int,
    ) -> Never:
        raise OpenAIError("embedding service unavailable")

    monkeypatch.setattr(retriever, "_vector_search", unavailable_embeddings)

    with pytest.raises(ExternalAiServiceError, match="knowledge retrieval"):
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

    with pytest.raises(ExternalAiServiceError, match="structured analysis"):
        await provider.analyze(
            analyze_request().ticket,
            [],
            "ticket-analysis-v1",
        )

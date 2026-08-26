from typing import Never

import httpx
from openai import APITimeoutError, OpenAIError
import pytest

from app.config import Settings
from app.errors import ExternalAiServiceError
from app.models import (
    BUNDLED_KNOWLEDGE_ACCESS,
    AnalyzeRequest,
    ModelDraft,
    RetrievalHit,
    TicketInput,
)
from app.openai_provider import OpenAIProvider


def live_settings() -> Settings:
    return Settings(
        ai_mode="live",
        openai_api_key="test-key",
        openai_chat_model="test-chat-model",
        openai_embedding_model="test-embedding-model",
        openai_max_retries=0,
    )


def analyze_request(ticket: TicketInput | None = None) -> AnalyzeRequest:
    return AnalyzeRequest(
        traceId="trace_provider_error",
        knowledgeAccess=BUNDLED_KNOWLEDGE_ACCESS,
        ticket=ticket
        or TicketInput(
            id="ticket-provider-test",
            subject="Enterprise login failure",
            description="Members cannot enter the workspace.",
            currentCategory="ACCOUNT_ACCESS",
        ),
    )


def test_provider_disables_sdk_retries_for_legacy_bounded_setting() -> None:
    settings = live_settings().model_copy(update={"openai_max_retries": 1})

    provider = OpenAIProvider(settings)

    assert provider._client.max_retries == 0


@pytest.mark.asyncio
async def test_provider_converts_openai_error(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = OpenAIProvider(live_settings())

    async def unavailable_model(
        **_kwargs: str | type[ModelDraft] | None,
    ) -> Never:
        raise OpenAIError("model service unavailable")

    monkeypatch.setattr(provider._client.responses, "parse", unavailable_model)

    with pytest.raises(ExternalAiServiceError, match="structured_generation"):
        await provider.analyze(analyze_request(), [])


@pytest.mark.asyncio
async def test_generation_timeout_preserves_connection_timeout_kind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = OpenAIProvider(live_settings())

    async def time_out_connection(
        **_kwargs: str | bool | type[ModelDraft] | None,
    ) -> Never:
        try:
            raise httpx.ConnectTimeout("generation connection timed out")
        except httpx.ConnectTimeout as exc:
            raise APITimeoutError(
                request=httpx.Request("POST", "https://example.test")
            ) from exc

    monkeypatch.setattr(provider._client.responses, "parse", time_out_connection)

    with pytest.raises(ExternalAiServiceError) as error:
        await provider.analyze(analyze_request(), [])

    assert error.value.operation == "structured_generation"
    assert error.value.failure_kind == "connection_timeout"


@pytest.mark.asyncio
async def test_provider_redacts_sensitive_data_before_sdk_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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

    with pytest.raises(ExternalAiServiceError, match="structured_generation"):
        await provider.analyze(analyze_request(ticket), evidence)

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

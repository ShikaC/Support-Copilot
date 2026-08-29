import json
from collections.abc import Callable

import httpx
from openai import AsyncOpenAI
import pytest

from app.config import Settings
from app.errors import ExternalAiServiceError, InvalidModelResponseError
from app.openai_provider import OpenAIProvider
from tests.test_openai_provider_protocols import (
    DRAFT_PAYLOAD,
    JsonValue,
    _chat_payload,
    _evidence,
    _request,
)


class SyntheticProgrammerError(RuntimeError):
    pass


def _provider(
    handler: Callable[[httpx.Request], httpx.Response],
) -> tuple[OpenAIProvider, httpx.AsyncClient]:
    settings = Settings(
        ai_mode="live",
        openai_api_key="synthetic-wire-key",
        openai_base_url="https://provider.example.test/v1",
        openai_chat_model="synthetic-chat-model",
        openai_embedding_model="synthetic-embedding-model",
        openai_chat_protocol="chat_completions",
        _env_file=None,
    )
    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAIProvider(settings)
    provider._client = AsyncOpenAI(
        api_key="synthetic-wire-key",
        base_url=settings.openai_base_url,
        max_retries=0,
        timeout=settings.openai_timeout_seconds,
        http_client=http_client,
    )
    return provider, http_client


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        _chat_payload(content=""),
        _chat_payload(content=None),
        _chat_payload(content=None, refusal="I cannot provide that response."),
        _chat_payload(content='{"intent":'),
        {**_chat_payload(content=json.dumps(DRAFT_PAYLOAD)), "choices": []},
        _chat_payload(content=json.dumps({**DRAFT_PAYLOAD, "unexpected": "field"})),
    ],
    ids=("empty", "unparsed", "refusal", "malformed-json", "no-choice", "extra-field"),
)
async def test_chat_completions_invalid_structured_output_fails_closed(
    payload: dict[str, JsonValue],
) -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=payload)

    provider, http_client = _provider(respond)
    try:
        with pytest.raises(InvalidModelResponseError):
            await provider.analyze(_request(), _evidence())
    finally:
        await http_client.aclose()

    assert len(requests) == 1
    assert requests[0].url.path == "/v1/chat/completions"


@pytest.mark.asyncio
async def test_chat_completions_does_not_swallow_programmer_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = OpenAIProvider(
        Settings(
            ai_mode="live",
            openai_api_key="synthetic-wire-key",
            openai_chat_model="synthetic-chat-model",
            openai_embedding_model="synthetic-embedding-model",
            openai_chat_protocol="chat_completions",
            _env_file=None,
        )
    )

    async def fail_programming(**_kwargs) -> None:
        raise SyntheticProgrammerError

    monkeypatch.setattr(provider._client.chat.completions, "parse", fail_programming)

    with pytest.raises(SyntheticProgrammerError):
        await provider.analyze(_request(), _evidence())


@pytest.mark.asyncio
async def test_chat_completions_maps_api_errors_without_retry() -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(503, json={"error": {"message": "unavailable"}})

    provider, http_client = _provider(respond)
    try:
        with pytest.raises(ExternalAiServiceError, match="structured_generation"):
            await provider.analyze(_request(), _evidence())
    finally:
        await http_client.aclose()

    assert len(requests) == 1
    assert requests[0].url.path == "/v1/chat/completions"


@pytest.mark.asyncio
async def test_chat_completions_preserves_connection_timeout_mapping() -> None:
    requests: list[httpx.Request] = []

    def time_out(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        raise httpx.ConnectTimeout("synthetic connection timeout", request=request)

    provider, http_client = _provider(time_out)
    try:
        with pytest.raises(ExternalAiServiceError) as error:
            await provider.analyze(_request(), _evidence())
    finally:
        await http_client.aclose()

    assert len(requests) == 1
    assert requests[0].url.path == "/v1/chat/completions"
    assert error.value.operation == "structured_generation"
    assert error.value.failure_kind == "connection_timeout"

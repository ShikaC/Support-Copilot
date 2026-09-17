import json
from collections.abc import Callable
from typing import Literal, TypeAlias

import httpx
import pytest
from openai import AsyncOpenAI

from app.config import Settings
from app.errors import InvalidModelResponseError, ModelResponseFailureKind
from app.models import (
    BUNDLED_KNOWLEDGE_ACCESS,
    AnalyzeRequest,
    ModelDraft,
    RetrievalHit,
    TicketInput,
)
from app.openai_provider import OpenAIProvider

JsonValue: TypeAlias = (
    str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]
)

DRAFT_PAYLOAD: dict[str, JsonValue] = {
    "intent": "account_access_recovery",
    "category": "ACCOUNT_ACCESS",
    "priority": "HIGH",
    "sentiment": "NEGATIVE",
    "confidence": 0.91,
    "reason_summary": "The identity guide matches the reported sign-in failure.",
    "reply_content": "Please follow the identity recovery steps.",
    "warnings": [],
    "citation_indexes": [1],
    "evidence_sufficient": True,
}


def _settings(
    protocol: Literal["responses", "chat_completions"] = "responses",
) -> Settings:
    return Settings(
        ai_mode="live",
        openai_api_key="synthetic-wire-key",
        openai_base_url="https://provider.example.test/v1",
        openai_chat_model="synthetic-chat-model",
        openai_embedding_model="synthetic-embedding-model",
        openai_chat_protocol=protocol,
        _env_file=None,
    )


def _request() -> AnalyzeRequest:
    return AnalyzeRequest(
        traceId="trace_protocol_wire",
        knowledgeAccess=BUNDLED_KNOWLEDGE_ACCESS,
        ticket=TicketInput(
            id="ticket-protocol-wire",
            subject="Sign-in failure for alice@example.com",
            description="Call 13800138000 after checking identity recovery.",
            currentCategory="ACCOUNT_ACCESS",
        ),
    )


def _evidence() -> list[RetrievalHit]:
    return [
        RetrievalHit(
            chunkId="identity-recovery",
            documentId="identity-guide",
            documentTitle="Identity guide",
            section="Recovery",
            content="Contact alice@example.com only through the approved workflow.",
            sourceUri="https://support.example.test/identity",
            retrievalMethod="VECTOR",
            initialRank=1,
            initialScore=0.9,
            rerankPosition=1,
            rerankScore=0.9,
            usedAsEvidence=True,
        )
    ]


def _responses_payload() -> dict[str, JsonValue]:
    return {
        "id": "resp_wire_001",
        "object": "response",
        "created_at": 1_788_000_000,
        "status": "completed",
        "error": None,
        "incomplete_details": None,
        "instructions": None,
        "model": "synthetic-chat-model",
        "output": [
            {
                "id": "msg_wire_001",
                "type": "message",
                "status": "completed",
                "role": "assistant",
                "content": [
                    {
                        "type": "output_text",
                        "annotations": [],
                        "logprobs": [],
                        "text": json.dumps(DRAFT_PAYLOAD),
                    }
                ],
            }
        ],
        "parallel_tool_calls": True,
        "tool_choice": "auto",
        "tools": [],
        "temperature": 1.0,
        "top_p": 1.0,
        "truncation": "disabled",
        "usage": {
            "input_tokens": 37,
            "input_tokens_details": {"cached_tokens": 0},
            "output_tokens": 19,
            "output_tokens_details": {"reasoning_tokens": 0},
            "total_tokens": 56,
        },
    }


def _chat_payload(
    *,
    content: str | None = None,
    refusal: str | None = None,
) -> dict[str, JsonValue]:
    return {
        "id": "chatcmpl_wire_001",
        "object": "chat.completion",
        "created": 1_788_000_000,
        "model": "synthetic-chat-model",
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "logprobs": None,
                "message": {
                    "role": "assistant",
                    "content": content,
                    "refusal": refusal,
                },
            }
        ],
        "usage": {
            "prompt_tokens": 41,
            "completion_tokens": 23,
            "total_tokens": 64,
        },
    }


def _wire_provider(
    settings: Settings,
    handler: Callable[[httpx.Request], httpx.Response],
) -> tuple[OpenAIProvider, httpx.AsyncClient]:
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
async def test_responses_protocol_wire_contract_is_preserved() -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=_responses_payload())

    provider, http_client = _wire_provider(_settings(), respond)
    try:
        draft, input_tokens, output_tokens = await provider.analyze(_request(), _evidence())
    finally:
        await http_client.aclose()

    assert len(requests) == 1
    assert requests[0].url.path == "/v1/responses"
    body = json.loads(requests[0].content)
    assert body["store"] is False
    assert body["text"]["format"]["type"] == "json_schema"
    assert body["text"]["format"]["strict"] is True
    assert body["text"]["format"]["schema"]["additionalProperties"] is False
    assert "alice@example.com" not in body["input"]
    assert "13800138000" not in body["input"]
    assert "[REDACTED_EMAIL]" in body["input"]
    assert "[REDACTED_PHONE]" in body["input"]
    assert draft == ModelDraft.model_validate(DRAFT_PAYLOAD)
    assert (input_tokens, output_tokens) == (37, 19)


@pytest.mark.asyncio
async def test_responses_parsed_none_is_classified_without_retry() -> None:
    requests: list[httpx.Request] = []
    payload = _responses_payload()
    payload["output"] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=payload)

    provider, http_client = _wire_provider(_settings(), respond)
    try:
        with pytest.raises(InvalidModelResponseError) as error:
            await provider.analyze(_request(), _evidence())
    finally:
        await http_client.aclose()

    assert error.value.model_response_failure_kind is ModelResponseFailureKind.PARSED_NONE
    assert len(requests) == 1
    assert requests[0].url.path == "/v1/responses"


@pytest.mark.asyncio
async def test_chat_completions_protocol_wire_contract() -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=_chat_payload(content=json.dumps(DRAFT_PAYLOAD)))

    provider, http_client = _wire_provider(_settings("chat_completions"), respond)
    try:
        draft, input_tokens, output_tokens = await provider.analyze(_request(), _evidence())
    finally:
        await http_client.aclose()

    assert len(requests) == 1
    assert requests[0].url.path == "/v1/chat/completions"
    assert all(request.url.path != "/v1/responses" for request in requests)
    body = json.loads(requests[0].content)
    assert body["store"] is False
    assert [message["role"] for message in body["messages"]] == ["system", "user"]
    assert body["messages"][0]["content"]
    user_content = body["messages"][1]["content"]
    assert "alice@example.com" not in user_content
    assert "13800138000" not in user_content
    assert "[REDACTED_EMAIL]" in user_content
    assert "[REDACTED_PHONE]" in user_content
    response_format = body["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["strict"] is True
    schema = response_format["json_schema"]["schema"]
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(DRAFT_PAYLOAD)
    assert draft == ModelDraft.model_validate(DRAFT_PAYLOAD)
    assert (input_tokens, output_tokens) == (41, 23)

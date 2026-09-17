import json

import httpx
import pytest
from openai import AsyncOpenAI

from app.config import Settings
from app.embedding_provider import OpenAIEmbeddingProvider


@pytest.mark.asyncio
@pytest.mark.parametrize("query", [False, True])
async def test_embedding_wire_preserves_original_chinese_text(query: bool) -> None:
    # Given a compatible provider whose tokenizer is not OpenAI's tokenizer.
    texts = ["企业 SSO 登录循环，检查身份提供商与域名配置。"]
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={
            "data": [{"index": 0, "embedding": [1.0, 0.0], "object": "embedding"}],
            "model": "Qwen/Qwen3-Embedding-8B", "object": "list",
            "usage": {"prompt_tokens": 12, "total_tokens": 12},
        })

    async with (
        httpx.AsyncClient(transport=httpx.MockTransport(respond)) as transport,
        AsyncOpenAI(api_key="test-key", base_url="https://example.test/v1", http_client=transport) as client,
    ):
        provider = OpenAIEmbeddingProvider(Settings(
            openai_embedding_model="Qwen/Qwen3-Embedding-8B",
            openai_embedding_api_key="test-key", _env_file=None,
        ))
        provider._client.async_client = client.embeddings
        # When the real LangChain adapter serializes documents or a query.
        if query:
            await provider.embed_query(texts[0])
        else:
            await provider.embed_documents(texts)

    # Then the remote provider receives source text, never foreign token IDs.
    assert len(requests) == 1
    assert json.loads(requests[0].content)["input"] == texts

from typing import Protocol

from langchain_openai import OpenAIEmbeddings

from app.config import Settings


class EmbeddingProvider(Protocol):
    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    async def embed_query(self, text: str) -> list[float]: ...


class OpenAIEmbeddingProvider:
    def __init__(self, settings: Settings) -> None:
        self._client = OpenAIEmbeddings(
            api_key=settings.embedding_api_key,
            base_url=settings.embedding_base_url,
            model=settings.openai_embedding_model,
            max_retries=0,
            request_timeout=settings.openai_timeout_seconds,
        )

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return await self._client.aembed_documents(texts)

    async def embed_query(self, text: str) -> list[float]:
        return await self._client.aembed_query(text)

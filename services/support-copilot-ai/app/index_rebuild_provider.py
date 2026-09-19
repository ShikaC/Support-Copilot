"""Bounded embedding batches with durable progress and task-owned SDK lifetime."""

from collections.abc import AsyncGenerator, Callable
from contextlib import AbstractAsyncContextManager, AsyncExitStack, asynccontextmanager
from datetime import datetime, timezone
from typing import Final

import numpy as np
from openai import AsyncOpenAI

from app.config import Settings
from app.embedding_artifact import EmbeddingArtifactError
from app.embedding_provider import EmbeddingProvider
from app.index_rebuild_models import FailureCode, RebuildError, RebuildStatus
from app.index_rebuild_storage import RebuildStorage

BATCH_SIZE: Final = 32
ProviderFactory = Callable[[Settings], AbstractAsyncContextManager[EmbeddingProvider]]


class _SDKEmbeddingProvider:
    def __init__(self, client: AsyncOpenAI, model: str) -> None:
        self.client: AsyncOpenAI = client
        self.model: str = model

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        response = await self.client.embeddings.create(
            model=self.model,
            input=texts,
            encoding_format="float",
        )
        rows = sorted(response.data, key=lambda item: item.index)
        if [item.index for item in rows] != list(range(len(texts))):
            raise EmbeddingArtifactError("provider-row-order-mismatch")
        return [item.embedding for item in rows]

    async def embed_query(self, text: str) -> list[float]:
        raise EmbeddingArtifactError("rebuild-query-unsupported")


@asynccontextmanager
async def managed_embedding_provider(
    settings: Settings,
) -> AsyncGenerator[EmbeddingProvider, None]:
    model = settings.openai_embedding_model
    if model is None:
        raise RebuildError(
            409, "REBUILD_CONFIGURATION_INCOMPLETE", "Embedding model is required."
        )
    async with AsyncOpenAI(
        api_key=settings.embedding_api_key,
        base_url=settings.embedding_base_url,
        timeout=settings.openai_timeout_seconds,
        max_retries=0,
    ) as client:
        yield _SDKEmbeddingProvider(client, model)


class RebuildProgress:
    """A single worker mutates its snapshot only after the durable write succeeds."""

    def __init__(self, storage: RebuildStorage, status: RebuildStatus) -> None:
        self.storage: RebuildStorage = storage
        self.status: RebuildStatus = status

    def save(self, status: RebuildStatus) -> None:
        self.storage.save(status)
        self.status = status

    def attempted(self) -> None:
        if self.status.embedding_calls >= self.status.max_embedding_calls:
            raise EmbeddingArtifactError("embedding-call-budget-exhausted")
        self.save(
            self.status.model_copy(
                update={
                    "embedding_calls": self.status.embedding_calls + 1,
                    "updated_at": datetime.now(timezone.utc),
                }
            )
        )

    def completed(self, count: int) -> None:
        self.save(
            self.status.model_copy(
                update={
                    "completed_chunks": self.status.completed_chunks + count,
                    "updated_at": datetime.now(timezone.utc),
                }
            )
        )

    def finish(
        self, artifact_id: str | None, failure_code: FailureCode | None = None
    ) -> None:
        now = datetime.now(timezone.utc)
        self.save(
            self.status.model_copy(
                update={
                    "status": "FAILED" if failure_code else "SUCCEEDED",
                    "failure_code": failure_code,
                    "artifact_id": artifact_id,
                    "completed_chunks": self.status.completed_chunks
                    if failure_code
                    else self.status.total_chunks,
                    "updated_at": now,
                    "finished_at": now,
                    "elapsed_seconds": max(
                        0.0, (now - self.status.started_at).total_seconds()
                    ),
                }
            )
        )


class BatchedRebuildProvider:
    def __init__(
        self, settings: Settings, progress: RebuildProgress, factory: ProviderFactory
    ) -> None:
        self.settings: Settings = settings
        self.progress: RebuildProgress = progress
        self.factory: ProviderFactory = factory

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        async with AsyncExitStack() as resources:
            provider: EmbeddingProvider | None = None
            for offset in range(0, len(texts), BATCH_SIZE):
                batch = texts[offset : offset + BATCH_SIZE]
                self.progress.attempted()
                if provider is None:
                    provider = await resources.enter_async_context(
                        self.factory(self.settings)
                    )
                received = await provider.embed_documents(batch)
                try:
                    with np.errstate(over="ignore", invalid="ignore"):
                        matrix = np.asarray(received, dtype=np.float32)
                except (ValueError, TypeError):
                    raise EmbeddingArtifactError("provider-shape-mismatch") from None
                if matrix.shape != (
                    len(batch),
                    self.settings.embedding_vector_dimension,
                ):
                    raise EmbeddingArtifactError("provider-shape-mismatch")
                if not np.isfinite(matrix).all():
                    raise EmbeddingArtifactError("provider-non-finite-vector")
                self.progress.completed(len(batch))
                vectors.extend(received)
        return vectors

    async def embed_query(self, text: str) -> list[float]:
        raise EmbeddingArtifactError("rebuild-query-unsupported")

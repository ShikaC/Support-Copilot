from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Event

from app.config import Settings
from app.embedding_provider import EmbeddingProvider
from app.index_rebuild_models import RebuildRequest
from app.knowledge_source import load_knowledge_corpus
from tests.knowledge_access_support import write_canary_corpus, write_test_corpus


def rebuild_inputs(root: Path, count: int = 2) -> tuple[Settings, RebuildRequest]:
    path = root / "corpus.json"
    write_canary_corpus(path)
    base = load_knowledge_corpus(path).chunks[0]
    write_test_corpus(
        path,
        tuple(
            base.model_copy(
                update={
                    "chunk_id": f"chunk-{index}",
                    "content": f"Synthetic content {index}",
                }
            )
            for index in range(count)
        ),
    )
    settings = Settings(
        _env_file=None,
        knowledge_path=path,
        embedding_artifact_root=root / "artifacts",
        openai_embedding_api_key="synthetic-key",
        openai_embedding_model="test-model",
        embedding_vector_dimension=2,
    )
    request = RebuildRequest(
        maxEmbeddingCalls=(count + 31) // 32,
        expectedCorpusChecksum=load_knowledge_corpus(path).corpus_checksum,
    )
    return settings, request


class ControlledProvider:
    """Synthetic external provider records calls and optionally blocks a chosen batch."""

    def __init__(self) -> None:
        self.batches: list[list[str]] = []
        self.created = 0
        self.closed = 0
        self.block_call = 0
        self.entered = Event()
        self.release = Event()
        self.failure: Exception | None = None
        self.vector = [1.0, 0.0]

    @asynccontextmanager
    async def factory(self, settings: Settings) -> AsyncIterator[EmbeddingProvider]:
        self.created += 1
        try:
            yield self
        finally:
            self.closed += 1

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.batches.append(texts)
        if len(self.batches) == self.block_call:
            self.entered.set()
            if not self.release.wait(10):
                raise AssertionError("Test did not release the controlled provider")
        if self.failure is not None:
            raise self.failure
        return [list(self.vector) for _ in texts]

    async def embed_query(self, text: str) -> list[float]:
        raise AssertionError("Rebuild must not embed queries")

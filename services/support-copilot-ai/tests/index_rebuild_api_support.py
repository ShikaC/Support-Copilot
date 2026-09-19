from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Event

import anyio
import pytest

import app.main as main_module
from app.config import Settings
from app.embedding_provider import EmbeddingProvider
from app.index_rebuild import IndexRebuildManager
from app.knowledge import KnowledgeRetriever
from tests.knowledge_access_support import write_canary_corpus
from tests.test_embedding_artifact_store import (
    artifact_settings,
    artifact_store,
)


class InjectedProviderFailure(RuntimeError):
    def __str__(self) -> str:
        return "private-provider-token /private/customer/path"


class ControlledProvider:
    """Hold a build at its external boundary so HTTP responsiveness is observable."""

    def __init__(self, *, fail: bool = False) -> None:
        self.entered = Event()
        self.release = Event()
        self.fail = fail
        self.calls = 0

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        self.entered.set()
        if not self.release.wait(timeout=10):
            raise TimeoutError("test provider was not released")
        if self.fail:
            raise InjectedProviderFailure
        return [[1.0, 0.0] for _ in texts]

    async def embed_query(self, text: str) -> list[float]:
        raise AssertionError("a build must not issue query embeddings")


def configure_rebuild(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, provider: ControlledProvider
) -> Settings:
    corpus_path = tmp_path / "corpus.json"
    write_canary_corpus(corpus_path)
    settings = artifact_settings(corpus_path, tmp_path / "artifacts")
    old_store = artifact_store(settings)
    active_provider = ControlledProvider()
    active_provider.release.set()
    old_manifest = anyio.run(old_store.build, active_provider)
    old_store.activate(old_manifest.artifact_id)
    settings = settings.model_copy(update={
        "knowledge_index_mutation_enabled": True,
        "openai_embedding_api_key": "synthetic-rebuild-test-only",
        "embedding_chunking_version": "new-test-chunking",
    })

    @asynccontextmanager
    async def factory(_settings: Settings) -> AsyncIterator[EmbeddingProvider]:
        yield provider

    def manager_factory(config: Settings) -> IndexRebuildManager:
        return IndexRebuildManager(config, provider_factory=factory)

    monkeypatch.setattr(main_module, "settings", settings)
    monkeypatch.setattr(main_module, "retriever", KnowledgeRetriever(settings))
    monkeypatch.setattr(main_module, "IndexRebuildManager", manager_factory)
    return settings

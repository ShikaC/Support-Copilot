from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import anyio
import pytest

from app.config import Settings
from app import index_rebuild
from app.embedding_provider import EmbeddingProvider
from tests.knowledge_access_support import write_canary_corpus
from tests.index_rebuild_support import ControlledProvider, rebuild_inputs


@pytest.mark.asyncio
async def test_success_survives_restart_without_activating_index(
    tmp_path: Path,
) -> None:
    # Given a configured corpus and an isolated synthetic embedding provider.
    path = tmp_path / "corpus.json"
    checksum = write_canary_corpus(path)
    settings = Settings(
        _env_file=None,
        knowledge_path=path,
        embedding_artifact_root=tmp_path / "artifacts",
        openai_embedding_api_key="synthetic-key",
        openai_embedding_model="test-model",
        embedding_vector_dimension=2,
    )

    class Provider:
        async def embed_documents(self, texts: list[str]) -> list[list[float]]:
            return [[1.0, 0.0] for _ in texts]

        async def embed_query(self, text: str) -> list[float]:
            raise AssertionError("Rebuild must not embed queries")

    @asynccontextmanager
    async def factory(config: Settings) -> AsyncIterator[EmbeddingProvider]:
        yield Provider()

    manager = index_rebuild.IndexRebuildManager(settings, factory)
    request = index_rebuild.RebuildRequest(
        maxEmbeddingCalls=1,
        expectedCorpusChecksum=checksum,
    )
    # When the task group drains and a new manager reads the durable result.
    async with anyio.create_task_group() as tasks:
        started = await manager.start(request, "test-trace", tasks)
    result = await index_rebuild.IndexRebuildManager(settings, factory).get(
        started.task_id
    )
    # Then the completed artifact exists without any activation side effect.
    assert started.status == "RUNNING"
    assert result.status == "SUCCEEDED"
    assert result.completed_chunks == result.total_chunks == 2
    assert result.embedding_calls == 1
    assert result.artifact_id is not None
    assert (
        settings.embedding_artifact_root / result.artifact_id / "manifest.json"
    ).is_file()
    assert not (settings.embedding_artifact_root / "active.json").exists()


@pytest.mark.asyncio
async def test_progress_is_durable_and_other_managers_reject_duplicate(
    tmp_path: Path,
) -> None:
    # Given three batches with the second held at the external boundary.
    settings, request = rebuild_inputs(tmp_path, 65)
    provider = ControlledProvider()
    provider.block_call = 2
    manager = index_rebuild.IndexRebuildManager(settings, provider.factory)
    observer = index_rebuild.IndexRebuildManager(settings, provider.factory)
    async with anyio.create_task_group() as tasks:
        started = await manager.start(request, "trace-progress", tasks)
        try:
            assert await anyio.to_thread.run_sync(provider.entered.wait, 5)
            # When a different manager observes progress and tries another rebuild.
            progress = await observer.get(started.task_id)
            with pytest.raises(index_rebuild.RebuildError) as duplicate:
                await observer.start(request, "trace-duplicate", tasks)
            # Then completed chunks exclude the in-flight batch, but attempts include it.
            assert progress.status == "RUNNING"
            assert progress.completed_chunks == 32
            assert progress.embedding_calls == 2
            assert duplicate.value.status_code == 409
        finally:
            provider.release.set()
    complete = await observer.get(started.task_id)
    assert complete.completed_chunks == 65
    assert [len(batch) for batch in provider.batches] == [32, 32, 1]
    assert provider.created == provider.closed == 1


@pytest.mark.asyncio
async def test_existing_artifact_reuses_without_creating_provider(
    tmp_path: Path,
) -> None:
    # Given an already built and validated candidate artifact.
    settings, request = rebuild_inputs(tmp_path)
    provider = ControlledProvider()
    manager = index_rebuild.IndexRebuildManager(settings, provider.factory)
    async with anyio.create_task_group() as tasks:
        original = await manager.start(request, "trace-original", tasks)
    original_status = await manager.get(original.task_id)
    # When a new explicit task rebuilds identical content.
    async with anyio.create_task_group() as tasks:
        reused = await manager.start(request, "trace-reused", tasks)
    result = await manager.get(reused.task_id)
    # Then no new external provider or embedding call is created.
    assert result.status == "SUCCEEDED"
    assert result.artifact_id == original_status.artifact_id
    assert result.embedding_calls == 0
    assert provider.created == 1


@pytest.mark.asyncio
async def test_unknown_provider_failure_is_retained_and_sanitized(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    # Given an unknown bug in the task provider, containing deliberately sensitive text.
    settings, request = rebuild_inputs(tmp_path)
    provider = ControlledProvider()
    provider.failure = RuntimeError("private-token /private/path user-message")
    manager = index_rebuild.IndexRebuildManager(settings, provider.factory)
    original_corpus = settings.knowledge_path.read_bytes()
    # When the worker handles the bug at its task boundary.
    async with anyio.create_task_group() as tasks:
        started = await manager.start(request, "trace-unknown", tasks)
    result = await index_rebuild.IndexRebuildManager(settings).get(started.task_id)
    # Then failure survives restart, retains candidate evidence, and never becomes fallback.
    assert result.status == "FAILED"
    assert result.failure_code == "REBUILD_INTERNAL_ERROR"
    assert result.completed_chunks == 0 and result.embedding_calls == 1
    assert (manager.storage.directory(result.task_id) / "candidate").is_dir()
    assert provider.closed == 1
    assert "private-token" not in result.model_dump_json() + caplog.text
    assert any(
        getattr(record, "error_type", None) == "RuntimeError"
        for record in caplog.records
    )
    assert settings.knowledge_path.read_bytes() == original_corpus
    assert not (settings.embedding_artifact_root / "active.json").exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("vector", [[float("nan"), 0.0], [float("inf"), 0.0], [1.0]])
async def test_invalid_vectors_never_advance_completed_progress(
    tmp_path: Path, vector: list[float]
) -> None:
    # Given invalid external embedding data.
    settings, request = rebuild_inputs(tmp_path)
    provider = ControlledProvider()
    provider.vector = vector
    manager = index_rebuild.IndexRebuildManager(settings, provider.factory)
    # When the rebuild receives the malformed batch.
    async with anyio.create_task_group() as tasks:
        started = await manager.start(request, "trace-invalid", tasks)
    result = await manager.get(started.task_id)
    # Then failed shape/finite validation does not count chunks as complete.
    assert result.status == "FAILED"
    assert result.failure_code == "ARTIFACT_BUILD_FAILED"
    assert result.completed_chunks == 0
    assert result.embedding_calls == 1
    assert result.artifact_id is None

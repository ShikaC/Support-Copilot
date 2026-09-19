from pathlib import Path

import anyio
import pytest

from app.index_rebuild import IndexRebuildManager
from app.index_rebuild_models import RebuildError, RebuildStatus
from tests.index_rebuild_support import ControlledProvider, rebuild_inputs


@pytest.mark.asyncio
@pytest.mark.parametrize("reason", ["checksum", "budget", "config", "corpus"])
async def test_preflight_rejection_never_constructs_provider(
    tmp_path: Path, reason: str
) -> None:
    # Given an explicitly unauthorized or unavailable rebuild input.
    settings, request = rebuild_inputs(tmp_path, 33)
    if reason == "checksum":
        request = request.model_copy(update={"expected_corpus_checksum": "0" * 64})
    elif reason == "budget":
        request = request.model_copy(update={"max_embedding_calls": 1})
    elif reason == "config":
        settings.embedding_vector_dimension = None
    else:
        settings.knowledge_path.write_text("invalid-json", encoding="utf-8")
    provider = ControlledProvider()
    manager = IndexRebuildManager(settings, provider.factory)
    # When task admission checks the actual configured corpus and budget.
    async with anyio.create_task_group() as tasks:
        with pytest.raises(RebuildError):
            await manager.start(request, "trace-rejected", tasks)
    # Then no external client or paid request exists.
    assert provider.created == 0
    assert not list(
        settings.embedding_artifact_root.glob(".rebuild-tasks/*/status.json")
    )


@pytest.mark.asyncio
async def test_semantically_corrupt_persisted_success_is_unavailable(
    tmp_path: Path,
) -> None:
    # Given valid saved JSON altered to falsely claim success without an artifact.
    settings, request = rebuild_inputs(tmp_path)
    provider = ControlledProvider()
    manager = IndexRebuildManager(settings, provider.factory)
    async with anyio.create_task_group() as tasks:
        started = await manager.start(request, "trace-corrupt", tasks)
    result = await manager.get(started.task_id)
    corrupt = result.model_copy(update={"artifact_id": None, "completed_chunks": 0})
    manager.storage.save(corrupt)
    # When a fresh manager parses persisted status at the filesystem boundary.
    with pytest.raises(RebuildError) as failure:
        await IndexRebuildManager(settings).get(started.task_id)
    # Then it reports unavailable evidence instead of accepting a false success.
    assert failure.value.status_code == 503


@pytest.mark.asyncio
async def test_unowned_running_task_recovers_without_resuming_provider(
    tmp_path: Path,
) -> None:
    # Given durable admission whose process no longer owns the lock.
    settings, request = rebuild_inputs(tmp_path)
    provider = ControlledProvider()
    manager = IndexRebuildManager(settings, provider.factory)
    prepared = manager._prepare(request, "trace-interrupted")
    with prepared.ownership:
        task_id = prepared.progress.status.task_id
    # When another manager reads the interrupted task.
    result = await IndexRebuildManager(settings, provider.factory).get(task_id)
    # Then recovery records failure and never automatically resumes paid work.
    assert result.status == "FAILED"
    assert result.failure_code == "REBUILD_INTERRUPTED"
    assert result.embedding_calls == 0
    assert provider.created == 0


@pytest.mark.asyncio
async def test_closed_task_group_marks_failure_and_releases_ownership(
    tmp_path: Path,
) -> None:
    # Given an unavailable lifespan task group.
    settings, request = rebuild_inputs(tmp_path)
    provider = ControlledProvider()
    manager = IndexRebuildManager(settings, provider.factory)
    async with anyio.create_task_group() as closed_tasks:
        pass
    # When admission cannot schedule its worker.
    with pytest.raises(RebuildError) as failure:
        await manager.start(request, "trace-start-failed", closed_tasks)
    # Then it persists failure without a provider, and the next task can own the lock.
    assert failure.value.code == "REBUILD_START_FAILED"
    saved = list(manager.storage.root.glob("*/status.json"))
    status = RebuildStatus.model_validate_json(saved[0].read_bytes())
    assert status.failure_code == "REBUILD_START_FAILED"
    assert provider.created == 0
    async with anyio.create_task_group() as tasks:
        following = await manager.start(request, "trace-following", tasks)
    assert (await manager.get(following.task_id)).status == "SUCCEEDED"


@pytest.mark.asyncio
async def test_cancelled_task_group_holds_lock_until_worker_finishes(
    tmp_path: Path,
) -> None:
    # Given an admitted worker blocked inside its external call.
    settings, request = rebuild_inputs(tmp_path)
    provider = ControlledProvider()
    provider.block_call = 1
    manager = IndexRebuildManager(settings, provider.factory)
    async with anyio.create_task_group() as tasks:
        started = await manager.start(request, "trace-cancel", tasks)
        assert await anyio.to_thread.run_sync(provider.entered.wait, 5)
        # When the lifespan group is cancelled before the thread finishes.
        tasks.cancel_scope.cancel()
        with anyio.CancelScope(shield=True):
            try:
                with pytest.raises(RebuildError) as duplicate:
                    await IndexRebuildManager(settings).start(
                        request, "trace-overlap", tasks
                    )
                assert duplicate.value.code == "REBUILD_ALREADY_RUNNING"
            finally:
                provider.release.set()
    # Then cancellation drains the actual work and retains its terminal evidence.
    assert (await manager.get(started.task_id)).status == "SUCCEEDED"
    assert provider.created == provider.closed == 1


@pytest.mark.asyncio
async def test_attempt_write_failure_stops_before_next_paid_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given a storage fault when reserving the second external request.
    settings, request = rebuild_inputs(tmp_path, 65)
    provider = ControlledProvider()
    manager = IndexRebuildManager(settings, provider.factory)
    original_save = manager.storage.save

    def fail_second_attempt(status: RebuildStatus) -> None:
        if status.embedding_calls == 2:
            raise manager.storage.unavailable()
        original_save(status)

    monkeypatch.setattr(manager.storage, "save", fail_second_attempt)
    # When the first batch completes and the next attempt cannot be made durable.
    async with anyio.create_task_group() as tasks:
        started = await manager.start(request, "trace-disk-failure", tasks)
    result = await manager.get(started.task_id)
    # Then only one real call happened and its validated progress remains visible.
    assert result.status == "FAILED"
    assert result.failure_code == "REBUILD_STORAGE_UNAVAILABLE"
    assert result.completed_chunks == 32
    assert result.embedding_calls == len(provider.batches) == 1
    assert provider.closed == 1

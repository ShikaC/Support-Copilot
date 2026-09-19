import errno
import shutil
from pathlib import Path

import pytest

from app.embedding_artifact import EmbeddingArtifactError
from tests.knowledge_access_support import write_canary_corpus
from tests.test_embedding_artifact_store import (
    FakeEmbeddingProvider,
    artifact_settings,
    artifact_store,
)


class UnavailableEmbeddingProvider(FakeEmbeddingProvider):
    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.document_calls += 1
        raise TimeoutError("injected-provider-timeout")


@pytest.mark.asyncio
async def test_provider_failure_retains_candidate_and_active_artifact(
    tmp_path: Path,
) -> None:
    # Given an active index and a task-owned location for a different build.
    knowledge_path = tmp_path / "knowledge.json"
    write_canary_corpus(knowledge_path)
    root = tmp_path / "artifacts"
    active_store = artifact_store(artifact_settings(knowledge_path, root))
    active = await active_store.build(
        FakeEmbeddingProvider([[1.0, 0.0], [0.0, 1.0]])
    )
    active_store.activate(active.artifact_id)
    pointer_before = (root / "active.json").read_bytes()
    corpus_before = knowledge_path.read_bytes()
    build_store = artifact_store(
        artifact_settings(knowledge_path, root, chunking_version="next-version")
    )
    task_directory = tmp_path / "task"
    task_directory.mkdir()
    candidate_directory = task_directory / "candidate"
    provider = UnavailableEmbeddingProvider([])

    # When the provider fails, the original error must still reach the caller.
    with pytest.raises(TimeoutError, match="injected-provider-timeout"):
        await build_store.build(provider, candidate_directory=candidate_directory)

    # Then the task keeps its evidence location without publishing or switching.
    assert provider.document_calls == 1
    assert candidate_directory.is_dir()
    assert (root / "active.json").read_bytes() == pointer_before
    assert knowledge_path.read_bytes() == corpus_before
    assert active_store.load_active().manifest.artifact_id == active.artifact_id


@pytest.mark.asyncio
async def test_success_publishes_valid_artifact_without_changing_active(
    tmp_path: Path,
) -> None:
    # Given an active index and a separate task-owned build location.
    knowledge_path = tmp_path / "knowledge.json"
    write_canary_corpus(knowledge_path)
    root = tmp_path / "artifacts"
    active_store = artifact_store(artifact_settings(knowledge_path, root))
    active = await active_store.build(
        FakeEmbeddingProvider([[1.0, 0.0], [0.0, 1.0]])
    )
    active_store.activate(active.artifact_id)
    pointer_before = (root / "active.json").read_bytes()
    build_store = artifact_store(
        artifact_settings(knowledge_path, root, chunking_version="next-version")
    )
    task_directory = tmp_path / "task"
    task_directory.mkdir()
    candidate_directory = task_directory / "candidate"
    provider = FakeEmbeddingProvider([[0.0, 1.0], [1.0, 0.0]])

    # When the build succeeds, it publishes under the validated content identity.
    manifest = await build_store.build(provider, candidate_directory=candidate_directory)

    # Then the complete artifact is loadable and activation remains independent.
    assert manifest.artifact_id != active.artifact_id
    assert build_store.load(manifest.artifact_id).matrix.tolist() == provider.vectors
    assert not candidate_directory.exists()
    assert task_directory.is_dir()
    assert (root / "active.json").read_bytes() == pointer_before
    assert active_store.load_active().manifest.artifact_id == active.artifact_id


@pytest.mark.asyncio
@pytest.mark.parametrize("retain_evidence", [False, True])
async def test_disk_failure_retains_partial_files_only_when_requested(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    retain_evidence: bool,
) -> None:
    # Given a disk failure after the matrix and part of the metadata were written.
    knowledge_path = tmp_path / "knowledge.json"
    write_canary_corpus(knowledge_path)
    root = tmp_path / "artifacts"
    store = artifact_store(artifact_settings(knowledge_path, root))
    candidate_directory = tmp_path / "candidate" if retain_evidence else None

    def fail_write(path: Path, content: bytes) -> None:
        path.write_bytes(content[:5])
        raise OSError(errno.ENOSPC, "injected-disk-full")

    monkeypatch.setattr(store, "_write_bytes", fail_write)

    # When publishing fails, the disk error remains visible to the task wrapper.
    with pytest.raises(OSError, match="injected-disk-full"):
        await store.build(
            FakeEmbeddingProvider([[1.0, 0.0], [0.0, 1.0]]),
            candidate_directory=candidate_directory,
        )

    # Then opt-in evidence survives; ordinary callers retain their cleanup contract.
    if candidate_directory is not None:
        assert (candidate_directory / "matrix.npy").is_file()
        assert len((candidate_directory / "metadata.json").read_bytes()) == 5
    assert list(root.iterdir()) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("corrupt_target", [False, True])
async def test_existing_target_is_validated_before_provider_or_candidate_creation(
    tmp_path: Path,
    corrupt_target: bool,
) -> None:
    # Given an already-published identity, optionally damaged after publication.
    knowledge_path = tmp_path / "knowledge.json"
    write_canary_corpus(knowledge_path)
    root = tmp_path / "artifacts"
    store = artifact_store(artifact_settings(knowledge_path, root))
    manifest = await store.build(FakeEmbeddingProvider([[1.0, 0.0], [0.0, 1.0]]))
    if corrupt_target:
        (root / manifest.artifact_id / "matrix.npy").write_bytes(b"corrupt")
    provider = UnavailableEmbeddingProvider([])
    candidate_directory = tmp_path / "candidate"

    # When rebuilding the same identity, no embedding work is necessary.
    if corrupt_target:
        with pytest.raises(EmbeddingArtifactError, match="artifact-corrupt"):
            await store.build(provider, candidate_directory=candidate_directory)
    else:
        assert await store.build(provider, candidate_directory=candidate_directory) == manifest

    # Then reuse fails closed for corruption and never spends provider calls.
    assert provider.document_calls == 0
    assert not candidate_directory.exists()


@pytest.mark.asyncio
async def test_existing_candidate_is_not_reused_or_cleaned(
    tmp_path: Path,
) -> None:
    # Given an earlier task's retained directory, containing failure evidence.
    knowledge_path = tmp_path / "knowledge.json"
    write_canary_corpus(knowledge_path)
    store = artifact_store(artifact_settings(knowledge_path, tmp_path / "artifacts"))
    candidate_directory = tmp_path / "candidate"
    candidate_directory.mkdir()
    evidence = candidate_directory / "evidence"
    evidence.write_bytes(b"prior failure")
    provider = UnavailableEmbeddingProvider([])

    # When a caller incorrectly reuses that location, creation fails before work.
    with pytest.raises(FileExistsError):
        await store.build(provider, candidate_directory=candidate_directory)

    # Then the earlier evidence survives and no provider call is made.
    assert evidence.read_bytes() == b"prior failure"
    assert provider.document_calls == 0


@pytest.mark.asyncio
async def test_losing_publication_race_retains_owned_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given another process publishing the same artifact just before our rename.
    knowledge_path = tmp_path / "knowledge.json"
    write_canary_corpus(knowledge_path)
    root = tmp_path / "artifacts"
    store = artifact_store(artifact_settings(knowledge_path, root))
    candidate_directory = tmp_path / "candidate"

    def publish_competitor(source: Path, destination: Path) -> None:
        shutil.copytree(source, destination)
        raise FileExistsError(errno.EEXIST, "injected-publication-race")

    monkeypatch.setattr("app.embedding_artifact.os.replace", publish_competitor)

    # When our atomic publication loses the race, the existing target is verified.
    manifest = await store.build(
        FakeEmbeddingProvider([[1.0, 0.0], [0.0, 1.0]]),
        candidate_directory=candidate_directory,
    )

    # Then neither the winner nor the caller-owned candidate is cleaned up.
    assert store.load(manifest.artifact_id).manifest == manifest
    assert sorted(path.name for path in candidate_directory.iterdir()) == [
        "manifest.json", "matrix.npy", "metadata.json"
    ]

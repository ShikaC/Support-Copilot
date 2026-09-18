from pathlib import Path
from threading import get_ident

import anyio
import pytest
from fastapi.testclient import TestClient

from app import main as main_module
from app.embedding_artifact import EmbeddingArtifactStore, LoadedEmbeddingArtifact
from app.knowledge import KnowledgeRetriever
from app.live_vector_index import LiveVectorIndex
from tests.knowledge_access_support import write_canary_corpus
from tests.test_index_versions import AUTH_HEADERS, FakeEmbeddingProvider, artifact_settings, artifact_store


@pytest.mark.parametrize("pointer_content", [None, "not-json"])
def test_reload_never_builds_or_activates_when_pointer_is_unusable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pointer_content: str | None
) -> None:
    # Given build-if-missing is enabled, but reload has no usable active pointer.
    corpus_path = tmp_path / "corpus.json"
    write_canary_corpus(corpus_path)
    root = tmp_path / "artifacts"
    root.mkdir()
    settings = artifact_settings(corpus_path, root)
    settings.embedding_artifact_build_policy = "build-if-missing"
    retriever = KnowledgeRetriever(settings)
    before = retriever.corpus_metadata
    pointer = root / settings.embedding_artifact_pointer
    if pointer_content is not None:
        pointer.write_text(pointer_content, encoding="utf-8")
    provider_calls: list[str] = []

    def provider(index: LiveVectorIndex) -> FakeEmbeddingProvider:
        provider_calls.append("provider-created")
        return FakeEmbeddingProvider([[1.0, 0.0], [0.0, 1.0]])

    monkeypatch.setattr(LiveVectorIndex, "_get_provider", provider)
    monkeypatch.setattr(main_module, "retriever", retriever)
    monkeypatch.setattr(main_module.settings, "knowledge_index_mutation_enabled", True)

    # When the authenticated operator requests only a reload.
    with TestClient(main_module.app, headers=AUTH_HEADERS) as client:
        response = client.post("/knowledge/index/reload")

    # Then no provider is created, no artifact or pointer is written, and state is preserved.
    assert provider_calls == []
    assert response.status_code == 409
    assert response.json()["code"] == "INDEX_VERSION_UNUSABLE"
    assert retriever.corpus_metadata == before
    assert sorted(p.name for p in root.iterdir()) == (
        [] if pointer_content is None else [pointer.name]
    )
    if pointer_content is not None:
        assert pointer.read_text(encoding="utf-8") == pointer_content


def test_reload_loads_artifacts_outside_the_event_loop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given a real on-disk artifact whose load thread is observable.
    corpus_path = tmp_path / "corpus.json"
    write_canary_corpus(corpus_path)
    settings = artifact_settings(corpus_path, tmp_path / "artifacts")
    store = artifact_store(settings)
    manifest = anyio.run(store.build, FakeEmbeddingProvider([[1.0, 0.0], [0.0, 1.0]]))
    store.activate(manifest.artifact_id)
    retriever = KnowledgeRetriever(settings)
    threads: list[int] = []
    original = EmbeddingArtifactStore.load_active

    def observed_load(current: EmbeddingArtifactStore) -> LoadedEmbeddingArtifact:
        threads.append(get_ident())
        return original(current)

    monkeypatch.setattr(EmbeddingArtifactStore, "load_active", observed_load)

    # When reload validates the matrix and its checksums.
    async def scenario() -> None:
        event_loop_thread = get_ident()
        await retriever.reload_index()
        # Then disk and matrix work cannot block the event-loop thread.
        assert threads
        assert event_loop_thread not in threads

    anyio.run(scenario)


@pytest.mark.parametrize("corruption", ["missing", "encoding", "json"])
def test_unreadable_corpus_reload_is_a_safe_conflict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, corruption: str
) -> None:
    # Given a valid running snapshot but an unreadable replacement corpus.
    corpus_path = tmp_path / "private-corpus-location.json"
    write_canary_corpus(corpus_path)
    retriever = KnowledgeRetriever(artifact_settings(corpus_path, tmp_path / "artifacts"))
    before = retriever.corpus_metadata
    match corruption:
        case "missing":
            corpus_path.unlink()
        case "encoding":
            corpus_path.write_bytes(b"\xff")
        case "json":
            corpus_path.write_text("not-json", encoding="utf-8")
    monkeypatch.setattr(main_module, "retriever", retriever)
    monkeypatch.setattr(main_module.settings, "knowledge_index_mutation_enabled", True)

    # When attempting the authenticated reload.
    with TestClient(main_module.app, headers=AUTH_HEADERS) as client:
        response = client.post("/knowledge/index/reload")

    # Then the operator gets a named conflict, no local path, and the old state remains usable.
    assert response.status_code == 409
    assert response.json()["code"] == "INDEX_CORPUS_UNRELOADABLE"
    assert str(corpus_path) not in response.text
    assert retriever.corpus_metadata == before


def test_overlapping_reloads_cannot_restore_an_older_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from anyio import wait_all_tasks_blocked
    from tests.test_index_versions import build_two_corpora

    # Given two prepared corpora and a delayed first reload of the old one.
    root = tmp_path / "artifacts"
    old_id, new_id, old_path, new_path = build_two_corpora(root, tmp_path)
    settings = artifact_settings(old_path, root)
    old_store = artifact_store(settings)
    old_store.activate(old_id)
    retriever = KnowledgeRetriever(settings)
    new_corpus_bytes = new_path.read_bytes()
    new_store = artifact_store(artifact_settings(new_path, root))
    original_reload = LiveVectorIndex.reload

    async def scenario() -> None:
        first_loaded = anyio.Event()
        release_first = anyio.Event()
        second_started = anyio.Event()
        first = True

        async def delayed_reload(index: LiveVectorIndex) -> LoadedEmbeddingArtifact:
            nonlocal first
            artifact = await original_reload(index)
            if first:
                first = False
                first_loaded.set()
                await release_first.wait()
            return artifact

        async def second_reload() -> None:
            second_started.set()
            await retriever.reload_index()

        monkeypatch.setattr(LiveVectorIndex, "reload", delayed_reload)
        # When a later reload requests the new corpus while the first is finishing.
        async with anyio.create_task_group() as tasks:
            tasks.start_soon(retriever.reload_index)
            await first_loaded.wait()
            old_path.write_bytes(new_corpus_bytes)
            new_store.activate(new_id)
            tasks.start_soon(second_reload)
            await second_started.wait()
            await wait_all_tasks_blocked()
            release_first.set()

        # Then request completion order cannot silently roll back the newer state.
        loaded = await retriever._live_index._get_artifact()
        assert loaded.manifest.artifact_id == new_id
        assert retriever.corpus_metadata.corpus_checksum == loaded.manifest.corpus_checksum

    anyio.run(scenario)

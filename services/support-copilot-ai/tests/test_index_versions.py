from pathlib import Path

import anyio
import json
import pytest
from fastapi.testclient import TestClient

from app import main as main_module
from app.config import Settings
from app.embedding_artifact import EmbeddingArtifactError, EmbeddingArtifactStore
from app.knowledge import KnowledgeRetriever
from app.knowledge_source import load_knowledge_corpus
from tests.knowledge_access_support import write_canary_corpus

AUTH_HEADERS = {"X-Internal-Service-Token": "synthetic-test-internal-service-token"}


class FakeEmbeddingProvider:
    def __init__(self, vectors: list[list[float]]) -> None:
        self.vectors = vectors

    async def embed_documents(self, _texts: list[str]) -> list[list[float]]:
        return self.vectors

    async def embed_query(self, _text: str) -> list[float]:
        return self.vectors[0]


def artifact_settings(
    knowledge_path: Path,
    root: Path,
    *,
    chunking_version: str = "knowledge-corpus-v2",
) -> Settings:
    return Settings(
        ai_mode="mock",
        knowledge_path=knowledge_path,
        embedding_artifact_root=root,
        openai_embedding_model="fake-model",
        embedding_vector_dimension=2,
        embedding_chunking_version=chunking_version,
        _env_file=None,
    )


def artifact_store(settings: Settings) -> EmbeddingArtifactStore:
    return EmbeddingArtifactStore(settings, load_knowledge_corpus(settings.knowledge_path))


def build_two_slicings(corpus_path: Path, root: Path) -> tuple[str, str]:
    """Build two artifacts from one corpus，代表两种切片方案（不同 chunking_version）。

    这里刻意用不同切片：它正是用户想切换的场景，也是当前架构下无法热切换的场景。
    """

    async def build() -> tuple[str, str]:
        vectors = [[1.0, 0.0], [0.0, 1.0]]
        first = artifact_store(artifact_settings(corpus_path, root, chunking_version="corpus-2000-1600"))
        first_manifest = await first.build(FakeEmbeddingProvider(vectors))
        _ = first.activate(first_manifest.artifact_id)
        second = artifact_store(artifact_settings(corpus_path, root, chunking_version="corpus-1000-800"))
        second_manifest = await second.build(FakeEmbeddingProvider(vectors))
        _ = second.activate(second_manifest.artifact_id)
        return first_manifest.artifact_id, second_manifest.artifact_id

    return anyio.run(build)


def test_list_artifacts_on_an_empty_root_reports_no_versions(tmp_path: Path) -> None:
    # Given a store whose root has never been built into.
    corpus_path = tmp_path / "corpus.json"
    write_canary_corpus(corpus_path)
    # When listing versions.
    inventory = artifact_store(artifact_settings(corpus_path, tmp_path / "root")).list_artifacts()
    # Then the inventory is empty instead of raising.
    assert inventory.artifacts == ()
    assert inventory.active_artifact_id is None
    assert inventory.previous_artifact_id is None
    assert inventory.unreadable == ()


def test_list_artifacts_marks_active_and_previous(tmp_path: Path) -> None:
    # Given two artifacts where the second one is active.
    corpus_path = tmp_path / "corpus.json"
    write_canary_corpus(corpus_path)
    root = tmp_path / "root"
    first_id, second_id = build_two_slicings(corpus_path, root)
    store = artifact_store(artifact_settings(corpus_path, root, chunking_version="corpus-1000-800"))

    # When listing versions.
    inventory = store.list_artifacts()

    # Then both appear with their roles and their own slicing identity.
    assert inventory.active_artifact_id == second_id
    assert inventory.previous_artifact_id == first_id
    assert [item.artifact_id for item in inventory.artifacts] == sorted([first_id, second_id])
    by_id = {item.artifact_id: item for item in inventory.artifacts}
    assert by_id[second_id].active is True
    assert by_id[first_id].active is False
    assert by_id[first_id].previous is True
    assert by_id[first_id].chunking_version == "corpus-2000-1600"
    assert by_id[second_id].chunking_version == "corpus-1000-800"
    assert by_id[first_id].row_count == 2
    assert by_id[first_id].document_count == 2
    assert by_id[first_id].modified_at.endswith("+00:00")


def test_list_artifacts_reports_unreadable_directories_without_failing(tmp_path: Path) -> None:
    # Given a root containing a directory without a manifest and one with a broken manifest.
    corpus_path = tmp_path / "corpus.json"
    write_canary_corpus(corpus_path)
    root = tmp_path / "root"
    root.mkdir()
    (root / ("a" * 64)).mkdir()
    (root / ("b" * 64)).mkdir()
    (root / ("b" * 64) / "manifest.json").write_text("{not json", encoding="utf-8")
    (root / "not-an-artifact").mkdir()

    # When listing versions.
    inventory = artifact_store(artifact_settings(corpus_path, root)).list_artifacts()

    # Then broken entries are reported and unrelated directories are not invented as versions.
    assert inventory.artifacts == ()
    assert set(inventory.unreadable) == {"a" * 64, "b" * 64}


def build_two_corpora(root: Path, tmp_path: Path) -> tuple[str, str, Path, Path]:
    """Build two artifacts from two *different* corpora，代表真正的换切片。

    换切片必然换语料，所以这里必须有第二份语料：只有这种组合才是真正的切换，
    也才是必须被拒绝（除非语料也一起换）的那种。
    """
    coarse_corpus = tmp_path / "corpus-coarse.json"
    write_canary_corpus(coarse_corpus)
    fine_corpus = tmp_path / "corpus-fine.json"
    payload = json.loads(coarse_corpus.read_text(encoding="utf-8"))
    # 更细的切片会把一段内容切成更多块：改掉 chunk 内容并重算校验和。
    payload["chunks"][0]["content"] = "COLLIDING_CANARY duplicate charge investigation (fine slice)"
    payload["corpus_checksum"] = checksum_of(payload["chunks"])
    fine_corpus.write_text(json.dumps(payload), encoding="utf-8")

    async def build() -> tuple[str, str]:
        vectors = [[1.0, 0.0], [0.0, 1.0]]
        first = artifact_store(artifact_settings(coarse_corpus, root))
        first_manifest = await first.build(FakeEmbeddingProvider(vectors))
        _ = first.activate(first_manifest.artifact_id)
        second = artifact_store(artifact_settings(fine_corpus, root))
        second_manifest = await second.build(FakeEmbeddingProvider(vectors))
        _ = second.activate(second_manifest.artifact_id)
        return first_manifest.artifact_id, second_manifest.artifact_id

    return (*anyio.run(build), coarse_corpus, fine_corpus)


def checksum_of(chunks: list[dict[str, object]]) -> str:
    import hashlib

    canonical = json.dumps(chunks, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(canonical).hexdigest()


def test_a_second_slicing_is_reported_and_can_be_activated_when_the_corpus_is_the_same(tmp_path: Path) -> None:
    """同一份语料、只是切片标签不同时，标签不再阻止切换。"""
    # Given a process configured for one slicing label while another artifact is active.
    corpus_path = tmp_path / "corpus.json"
    write_canary_corpus(corpus_path)
    root = tmp_path / "root"
    first_id, second_id = build_two_slicings(corpus_path, root)
    store = artifact_store(artifact_settings(corpus_path, root, chunking_version="corpus-2000-1600"))

    # When activating the artifact that carries a different slicing label.
    pointer = store.activate(second_id)

    # Then it is accepted: corpus checksum and per-row chunk alignment are what protect truth.
    assert pointer.active_artifact_id == second_id
    assert pointer.previous_artifact_id == first_id
    assert store.load_active().manifest.chunking_version == "corpus-1000-800"


def test_a_different_corpus_is_still_refused(tmp_path: Path) -> None:
    """真正的换切片（换语料）仍然被拒绝：这才是安全边界。"""
    # Given two artifacts built from two different corpora.
    root = tmp_path / "root"
    coarse_id, fine_id, coarse_corpus, _fine_corpus = build_two_corpora(root, tmp_path)
    store = artifact_store(artifact_settings(coarse_corpus, root))
    assert coarse_id != fine_id

    # When the process (still on the coarse corpus) tries to activate the fine one.
    with pytest.raises(EmbeddingArtifactError) as failure:
        _ = store.activate(fine_id)

    # Then it is refused as incompatible and the pointer does not move.
    assert failure.value.reason == "artifact-incompatible"
    assert store.list_artifacts().active_artifact_id == fine_id


def test_activating_the_already_active_artifact_is_a_no_op(tmp_path: Path) -> None:
    # Given a process already configured for the active artifact.
    corpus_path = tmp_path / "corpus.json"
    write_canary_corpus(corpus_path)
    root = tmp_path / "root"
    _coarse_id, fine_id = build_two_slicings(corpus_path, root)
    store = artifact_store(artifact_settings(corpus_path, root, chunking_version="corpus-1000-800"))

    # When activating the id that is already active.
    pointer = store.activate(fine_id)

    # Then the pointer is returned unchanged.
    assert pointer.active_artifact_id == fine_id


def test_rollback_moves_between_slicings_of_the_same_corpus(tmp_path: Path) -> None:
    # Given two artifacts of one corpus and a process configured for the newer label.
    corpus_path = tmp_path / "corpus.json"
    write_canary_corpus(corpus_path)
    root = tmp_path / "root"
    coarse_id, fine_id = build_two_slicings(corpus_path, root)
    store = artifact_store(artifact_settings(corpus_path, root, chunking_version="corpus-1000-800"))

    # When rolling back.
    pointer = store.rollback()

    # Then the earlier artifact becomes active again.
    assert pointer.active_artifact_id == coarse_id
    assert pointer.previous_artifact_id == fine_id
    assert store.load_active().manifest.artifact_id == coarse_id


def test_reload_rereads_the_active_pointer_instead_of_reusing_the_cache(tmp_path: Path) -> None:
    # Given a retriever that already loaded an artifact.
    corpus_path = tmp_path / "corpus.json"
    write_canary_corpus(corpus_path)
    root = tmp_path / "root"
    _coarse_id, fine_id = build_two_slicings(corpus_path, root)
    settings = artifact_settings(corpus_path, root, chunking_version="corpus-1000-800")
    retriever = KnowledgeRetriever(settings)

    async def scenario() -> tuple[str, str]:
        loaded = await retriever._live_index._get_artifact()
        # 把指针指向一个不存在的 artifact，用来证明 reload 真的重读了指针而不是复用缓存。
        (root / settings.embedding_artifact_pointer).write_text(
            '{"schema_version":1,"active_artifact_id":"' + "d" * 64 + '","previous_artifact_id":null}',
            encoding="utf-8",
        )
        with pytest.raises(EmbeddingArtifactError):
            await retriever.reload_index()
        return loaded.manifest.artifact_id, ""

    loaded_before, _ = anyio.run(scenario)
    assert loaded_before == fine_id


def test_index_versions_endpoint_requires_the_internal_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given a running app whose retriever points at a test artifact root.
    corpus_path = tmp_path / "corpus.json"
    write_canary_corpus(corpus_path)
    monkeypatch.setattr(
        main_module,
        "retriever",
        KnowledgeRetriever(artifact_settings(corpus_path, tmp_path / "root")),
    )
    client = TestClient(main_module.app)

    # When calling the endpoint without credentials.
    response = client.get("/knowledge/index/versions")

    # Then it is rejected before any index state is read.
    assert response.status_code == 401


def test_index_versions_endpoint_lists_versions_and_corpus_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given two built slicings where the finer one is active.
    corpus_path = tmp_path / "corpus.json"
    write_canary_corpus(corpus_path)
    root = tmp_path / "root"
    coarse_id, fine_id = build_two_slicings(corpus_path, root)
    retriever = KnowledgeRetriever(artifact_settings(corpus_path, root, chunking_version="corpus-1000-800"))
    monkeypatch.setattr(main_module, "retriever", retriever)
    client = TestClient(main_module.app, headers=AUTH_HEADERS)

    # When listing versions.
    response = client.get("/knowledge/index/versions")

    # Then every version and the loaded corpus identity are reported.
    assert response.status_code == 200
    body = response.json()
    assert body["activeArtifactId"] == fine_id
    assert body["previousArtifactId"] == coarse_id
    assert {item["artifactId"] for item in body["versions"]} == {coarse_id, fine_id}
    assert {item["chunkingVersion"] for item in body["versions"]} == {"corpus-2000-1600", "corpus-1000-800"}
    assert body["corpus"]["releaseId"] == retriever.corpus_metadata.release_id
    assert body["corpus"]["chunkCount"] == retriever.corpus_metadata.chunk_count
    assert body["unreadable"] == []


def test_index_mutation_endpoints_are_absent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """写端点被有意移除：当前架构下热切换必然失败，留着只会误导。"""
    # Given a running app.
    corpus_path = tmp_path / "corpus.json"
    write_canary_corpus(corpus_path)
    monkeypatch.setattr(
        main_module,
        "retriever",
        KnowledgeRetriever(artifact_settings(corpus_path, tmp_path / "root")),
    )
    client = TestClient(main_module.app, headers=AUTH_HEADERS)

    # When calling the removed mutation routes.
    activate = client.post("/knowledge/index/versions/activate", json={"artifactId": "a" * 64})
    rollback = client.post("/knowledge/index/rollback")

    # Then they are not part of the API at all.
    assert activate.status_code == 404
    assert rollback.status_code == 404


def write_corpus_variant(path: Path, content: str) -> str:
    """改写语料正文并重算校验和，模拟“换成另一种切片的语料”。"""
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["chunks"][0]["content"] = content
    payload["corpus_checksum"] = checksum_of(payload["chunks"])
    path.write_text(json.dumps(payload), encoding="utf-8")
    return payload["corpus_checksum"]


def test_reload_swaps_corpus_and_index_without_a_restart(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given a process running on corpus A with the matching index.
    corpus_path = tmp_path / "corpus.json"
    write_canary_corpus(corpus_path)
    root = tmp_path / "root"
    settings = artifact_settings(corpus_path, root)
    store = artifact_store(settings)
    first_manifest = anyio.run(store.build, FakeEmbeddingProvider([[1.0, 0.0], [0.0, 1.0]]))
    _ = store.activate(first_manifest.artifact_id)
    retriever = KnowledgeRetriever(settings)
    monkeypatch.setattr(main_module, "retriever", retriever)
    monkeypatch.setattr(main_module.settings, "knowledge_index_mutation_enabled", True)
    client = TestClient(main_module.app, headers=AUTH_HEADERS)
    before = retriever.corpus_metadata
    assert client.post("/knowledge/index/reload").status_code == 200

    # When the corpus on disk is replaced by a finer slicing and its index is built.
    second_checksum = write_corpus_variant(corpus_path, "COLLIDING_CANARY finer slicing of the same document")
    second_store = artifact_store(artifact_settings(corpus_path, root))
    second_manifest = anyio.run(second_store.build, FakeEmbeddingProvider([[1.0, 0.0], [0.0, 1.0]]))
    _ = second_store.activate(second_manifest.artifact_id)
    assert second_manifest.artifact_id != first_manifest.artifact_id
    response = client.post("/knowledge/index/reload")

    # Then the running process serves the new corpus and the new index, with no restart.
    assert response.status_code == 200
    body = response.json()
    assert body["corpus"]["corpusChecksum"] == second_checksum
    assert body["corpus"]["corpusChecksum"] != before.corpus_checksum
    assert body["activeArtifactId"] == second_manifest.artifact_id
    assert retriever.artifact_store.load_active().manifest.artifact_id == second_manifest.artifact_id
    assert retriever.chunk_count == 2


def test_reload_keeps_the_old_state_when_half_of_the_swap_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """只换语料、不换索引时必须失败，而且旧快照必须原封不动。"""
    # Given a process running on corpus A with index A active.
    corpus_path = tmp_path / "corpus.json"
    write_canary_corpus(corpus_path)
    root = tmp_path / "root"
    settings = artifact_settings(corpus_path, root)
    store = artifact_store(settings)
    first_manifest = anyio.run(store.build, FakeEmbeddingProvider([[1.0, 0.0], [0.0, 1.0]]))
    _ = store.activate(first_manifest.artifact_id)
    retriever = KnowledgeRetriever(settings)
    monkeypatch.setattr(main_module, "retriever", retriever)
    monkeypatch.setattr(main_module.settings, "knowledge_index_mutation_enabled", True)
    client = TestClient(main_module.app, headers=AUTH_HEADERS)
    before = retriever.corpus_metadata

    # When only the corpus changes while index A stays active.
    _ = write_corpus_variant(corpus_path, "COLLIDING_CANARY a half-finished swap")
    response = client.post("/knowledge/index/reload")

    # Then it refuses and the process keeps serving the corpus it validated at startup.
    assert response.status_code == 409
    assert response.json()["code"] == "INDEX_VERSION_UNUSABLE"
    assert retriever.corpus_metadata == before
    assert retriever.artifact_store.load_active().manifest.artifact_id == first_manifest.artifact_id


def test_reload_is_refused_while_mutation_is_disabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given an app that has not enabled index mutation.
    corpus_path = tmp_path / "corpus.json"
    write_canary_corpus(corpus_path)
    monkeypatch.setattr(main_module, "retriever", KnowledgeRetriever(artifact_settings(corpus_path, tmp_path / "root")))
    monkeypatch.setattr(main_module.settings, "knowledge_index_mutation_enabled", False)
    client = TestClient(main_module.app, headers=AUTH_HEADERS)

    # When calling reload.
    response = client.post("/knowledge/index/reload")

    # Then it is refused before anything is read from disk.
    assert response.status_code == 403
    assert response.json()["code"] == "INDEX_MUTATION_DISABLED"


def test_reload_requires_the_internal_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given an app with mutation enabled.
    corpus_path = tmp_path / "corpus.json"
    write_canary_corpus(corpus_path)
    monkeypatch.setattr(main_module, "retriever", KnowledgeRetriever(artifact_settings(corpus_path, tmp_path / "root")))
    monkeypatch.setattr(main_module.settings, "knowledge_index_mutation_enabled", True)
    client = TestClient(main_module.app)

    # When calling reload without credentials.
    # Then authentication wins over the feature flag.
    assert client.post("/knowledge/index/reload").status_code == 401


def test_search_uses_the_reloaded_corpus(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """端到端：重载之后，检索命中的内容真的来自新语料。"""
    from app.models import Priority, SupportScope, TicketInput
    from tests.knowledge_access_support import retrieval_request

    corpus_path = tmp_path / "corpus.json"
    write_canary_corpus(corpus_path)
    root = tmp_path / "root"
    settings = artifact_settings(corpus_path, root)
    store = artifact_store(settings)
    manifest = anyio.run(store.build, FakeEmbeddingProvider([[1.0, 0.0], [0.0, 1.0]]))
    _ = store.activate(manifest.artifact_id)
    retriever = KnowledgeRetriever(settings)
    ticket = TicketInput(id="ticket-reload-1", subject="duplicate charge",
        description="duplicate charge investigation", current_category="BILLING")
    scopes = (SupportScope.BILLING,)
    before = anyio.run(
        retriever.search, retrieval_request(retriever, ticket, "duplicate charge investigation", scopes=scopes))
    assert "COLLIDING_CANARY" in before[0].content

    # When the corpus is replaced and reloaded.
    _ = write_corpus_variant(corpus_path, "COLLIDING_CANARY resliced duplicate charge investigation text")
    second_store = artifact_store(artifact_settings(corpus_path, root))
    second_manifest = anyio.run(second_store.build, FakeEmbeddingProvider([[1.0, 0.0], [0.0, 1.0]]))
    _ = second_store.activate(second_manifest.artifact_id)
    anyio.run(retriever.reload_index)

    # Then the next search reads the new corpus while in-flight callers keep older snapshots.
    after = anyio.run(
        retriever.search, retrieval_request(retriever, ticket, "duplicate charge investigation", scopes=scopes))
    assert "resliced" in after[0].content
    assert after[0].chunk_id == before[0].chunk_id

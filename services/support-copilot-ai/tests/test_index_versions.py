from pathlib import Path

import anyio
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


def test_a_second_slicing_is_reported_but_not_activatable(tmp_path: Path) -> None:
    """这是本轮的核心发现：列得出来，但切不过去。"""
    # Given a process configured for the finer slicing while the coarser artifact is active.
    corpus_path = tmp_path / "corpus.json"
    write_canary_corpus(corpus_path)
    root = tmp_path / "root"
    coarse_id, fine_id = build_two_slicings(corpus_path, root)
    store = artifact_store(artifact_settings(corpus_path, root, chunking_version="corpus-2000-1600"))

    # When asking the running configuration to activate the finer artifact.
    with pytest.raises(EmbeddingArtifactError) as failure:
        _ = store.activate(fine_id)

    # Then it is refused as incompatible instead of silently mixing slicings.
    assert failure.value.reason == "artifact-incompatible"
    assert store.list_artifacts().active_artifact_id == fine_id
    assert coarse_id != fine_id


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


def test_rollback_cannot_cross_slicings_either(tmp_path: Path) -> None:
    # Given a process configured for the finer slicing, with the coarser one remembered.
    corpus_path = tmp_path / "corpus.json"
    write_canary_corpus(corpus_path)
    root = tmp_path / "root"
    coarse_id, _fine_id = build_two_slicings(corpus_path, root)
    store = artifact_store(artifact_settings(corpus_path, root, chunking_version="corpus-1000-800"))

    # When rolling back to the remembered artifact.
    with pytest.raises(EmbeddingArtifactError) as failure:
        _ = store.rollback()

    # Then rollback is refused for the same compatibility reason.
    assert failure.value.reason == "artifact-incompatible"
    assert store.list_artifacts().previous_artifact_id == coarse_id


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

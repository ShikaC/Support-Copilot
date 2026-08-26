import json
from pathlib import Path

import anyio
import numpy as np
import pytest

from app.config import Settings
from app.embedding_artifact import EmbeddingArtifactError, EmbeddingArtifactStore
from app.knowledge_source import load_knowledge_corpus
from tests.knowledge_access_support import write_canary_corpus, write_test_corpus


class FakeEmbeddingProvider:
    def __init__(self, vectors: list[list[float]]) -> None:
        self.vectors = vectors
        self.document_calls = 0
        self.query_calls = 0

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.document_calls += 1
        return self.vectors

    async def embed_query(self, _text: str) -> list[float]:
        self.query_calls += 1
        return self.vectors[0]


def artifact_settings(
    knowledge_path: Path,
    root: Path,
    *,
    model: str = "fake-model",
    dimension: int | None = 2,
) -> Settings:
    return Settings(
        ai_mode="mock",
        knowledge_path=knowledge_path,
        embedding_artifact_root=root,
        openai_embedding_model=model,
        openai_embedding_base_url="https://user:secret@example.test/v1?key=secret",
        embedding_vector_dimension=dimension,
        _env_file=None,
    )


def artifact_store(settings: Settings) -> EmbeddingArtifactStore:
    return EmbeddingArtifactStore(
        settings,
        load_knowledge_corpus(settings.knowledge_path),
    )


@pytest.mark.asyncio
async def test_identity_reuses_unchanged_build_and_changes_with_release(
    tmp_path: Path,
) -> None:
    first_knowledge = tmp_path / "first.json"
    write_canary_corpus(first_knowledge)
    first_store = artifact_store(artifact_settings(first_knowledge, tmp_path / "root"))
    first_provider = FakeEmbeddingProvider([[1.0, 0.0], [0.0, 1.0]])

    first = await first_store.build(first_provider)
    repeated = await first_store.build(first_provider)

    second_knowledge = tmp_path / "second.json"
    payload = json.loads(first_knowledge.read_text(encoding="utf-8"))
    payload["release_version"] = 2
    second_knowledge.write_text(json.dumps(payload), encoding="utf-8")
    second_store = artifact_store(
        artifact_settings(second_knowledge, tmp_path / "root")
    )
    second = await second_store.build(
        FakeEmbeddingProvider([[1.0, 0.0], [0.0, 1.0]])
    )

    assert repeated.artifact_id == first.artifact_id
    assert second.artifact_id != first.artifact_id
    assert sorted(path.name for path in (tmp_path / "root").iterdir()) == sorted(
        [first.artifact_id, second.artifact_id]
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("filename", ["matrix.npy", "metadata.json", "manifest.json"])
async def test_corrupt_artifact_is_rejected_without_pointer_change(
    tmp_path: Path,
    filename: str,
) -> None:
    knowledge_path = tmp_path / "knowledge.json"
    write_canary_corpus(knowledge_path)
    store = artifact_store(artifact_settings(knowledge_path, tmp_path / "root"))
    active = await store.build(
        FakeEmbeddingProvider([[1.0, 0.0], [0.0, 1.0]])
    )
    candidate = await store.build(
        FakeEmbeddingProvider([[0.0, 1.0], [1.0, 0.0]])
    )
    store.activate(active.artifact_id)
    pointer_path = tmp_path / "root" / "active.json"
    pointer_before = pointer_path.read_bytes()
    candidate_path = tmp_path / "root" / candidate.artifact_id
    (candidate_path / filename).write_bytes(b"corrupt")

    with pytest.raises(EmbeddingArtifactError):
        store.activate(candidate.artifact_id)

    assert pointer_path.read_bytes() == pointer_before
    assert store.load_active().manifest.artifact_id == active.artifact_id


@pytest.mark.asyncio
async def test_activation_and_rollback_switch_only_verified_artifacts(
    tmp_path: Path,
) -> None:
    knowledge_path = tmp_path / "knowledge.json"
    write_canary_corpus(knowledge_path)
    store = artifact_store(artifact_settings(knowledge_path, tmp_path / "root"))
    first = await store.build(FakeEmbeddingProvider([[1.0, 0.0], [0.0, 1.0]]))
    second = await store.build(FakeEmbeddingProvider([[0.0, 1.0], [1.0, 0.0]]))

    initial = store.activate(first.artifact_id)
    switched = store.activate(second.artifact_id)
    repeated = store.activate(second.artifact_id)
    rolled_back = store.rollback()

    assert initial.active_artifact_id == first.artifact_id
    assert switched.active_artifact_id == second.artifact_id
    assert switched.previous_artifact_id == first.artifact_id
    assert repeated == switched
    assert rolled_back.active_artifact_id == first.artifact_id
    assert store.load_active().manifest.artifact_id == first.artifact_id


@pytest.mark.asyncio
async def test_provider_shape_dimension_and_finiteness_are_rejected(
    tmp_path: Path,
) -> None:
    knowledge_path = tmp_path / "knowledge.json"
    write_canary_corpus(knowledge_path)
    store = artifact_store(artifact_settings(knowledge_path, tmp_path / "root"))

    with pytest.raises(EmbeddingArtifactError, match="provider-shape-mismatch"):
        await store.build(FakeEmbeddingProvider([[1.0, 0.0]]))
    with pytest.raises(EmbeddingArtifactError, match="provider-dimension-mismatch"):
        await store.build(FakeEmbeddingProvider([[1.0], [1.0]]))
    with pytest.raises(EmbeddingArtifactError, match="provider-non-finite-vector"):
        await store.build(FakeEmbeddingProvider([[np.nan, 0.0], [0.0, 1.0]]))
    assert not (tmp_path / "root").exists()


@pytest.mark.asyncio
async def test_concurrent_builds_converge_on_one_complete_artifact(
    tmp_path: Path,
) -> None:
    knowledge_path = tmp_path / "knowledge.json"
    write_canary_corpus(knowledge_path)
    store = artifact_store(artifact_settings(knowledge_path, tmp_path / "root"))
    artifact_ids: list[str] = []

    async def build() -> None:
        manifest = await store.build(
            FakeEmbeddingProvider([[1.0, 0.0], [0.0, 1.0]])
        )
        artifact_ids.append(manifest.artifact_id)

    async with anyio.create_task_group() as tasks:
        tasks.start_soon(build)
        tasks.start_soon(build)

    visible = [path for path in (tmp_path / "root").iterdir() if not path.name.startswith(".")]
    assert len(set(artifact_ids)) == 1
    assert len(visible) == 1
    assert store.load(artifact_ids[0]).manifest.artifact_id == artifact_ids[0]


@pytest.mark.asyncio
async def test_concurrent_activation_always_leaves_a_complete_pointer(
    tmp_path: Path,
) -> None:
    knowledge_path = tmp_path / "knowledge.json"
    write_canary_corpus(knowledge_path)
    store = artifact_store(artifact_settings(knowledge_path, tmp_path / "root"))
    first = await store.build(FakeEmbeddingProvider([[1.0, 0.0], [0.0, 1.0]]))
    second = await store.build(FakeEmbeddingProvider([[0.0, 1.0], [1.0, 0.0]]))

    async with anyio.create_task_group() as tasks:
        tasks.start_soon(anyio.to_thread.run_sync, store.activate, first.artifact_id)
        tasks.start_soon(anyio.to_thread.run_sync, store.activate, second.artifact_id)

    active = store.load_active().manifest.artifact_id
    pointer = json.loads((tmp_path / "root" / "active.json").read_text())
    assert active in {first.artifact_id, second.artifact_id}
    assert pointer["active_artifact_id"] == active


@pytest.mark.asyncio
async def test_manifest_and_errors_exclude_text_and_secrets(tmp_path: Path) -> None:
    knowledge_path = tmp_path / "knowledge.json"
    write_canary_corpus(knowledge_path)
    store = artifact_store(artifact_settings(knowledge_path, tmp_path / "root"))
    manifest = await store.build(
        FakeEmbeddingProvider([[1.0, 0.0], [0.0, 1.0]])
    )
    artifact_path = tmp_path / "root" / manifest.artifact_id
    observable = "\n".join(
        [
            (artifact_path / "manifest.json").read_text(encoding="utf-8"),
            (artifact_path / "metadata.json").read_text(encoding="utf-8"),
        ]
    )

    assert "COLLIDING_CANARY" not in observable
    assert "FORBIDDEN_CANARY" not in observable
    assert "secret" not in observable
    assert "user@" not in observable
    assert manifest.provider_identity == "https://example.test/v1"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"model": "other-model"}, "artifact-incompatible"),
        ({"dimension": 3}, "artifact-dimension-mismatch"),
    ],
)
async def test_model_and_dimension_mismatches_are_rejected(
    tmp_path: Path,
    change: dict[str, str | int],
    reason: str,
) -> None:
    knowledge_path = tmp_path / "knowledge.json"
    write_canary_corpus(knowledge_path)
    root = tmp_path / "root"
    store = artifact_store(artifact_settings(knowledge_path, root))
    manifest = await store.build(
        FakeEmbeddingProvider([[1.0, 0.0], [0.0, 1.0]])
    )
    mismatched = artifact_store(
        artifact_settings(
            knowledge_path,
            root,
            model=str(change.get("model", "fake-model")),
            dimension=int(change.get("dimension", 2)),
        )
    )

    with pytest.raises(EmbeddingArtifactError, match=reason):
        mismatched.load(manifest.artifact_id)


@pytest.mark.asyncio
async def test_checksum_and_chunk_order_mismatch_is_rejected(tmp_path: Path) -> None:
    knowledge_path = tmp_path / "knowledge.json"
    write_canary_corpus(knowledge_path)
    root = tmp_path / "root"
    store = artifact_store(artifact_settings(knowledge_path, root))
    manifest = await store.build(
        FakeEmbeddingProvider([[1.0, 0.0], [0.0, 1.0]])
    )
    corpus = load_knowledge_corpus(knowledge_path)
    reordered_path = tmp_path / "reordered.json"
    write_test_corpus(reordered_path, tuple(reversed(corpus.chunks)))
    reordered = artifact_store(artifact_settings(reordered_path, root))

    with pytest.raises(EmbeddingArtifactError, match="artifact-incompatible"):
        reordered.load(manifest.artifact_id)

import json
from hashlib import sha256
from pathlib import Path

import pytest

from app.embedding_artifact import EmbeddingArtifactError
from app.embedding_artifact_identity import canonical_bytes
from tests.knowledge_access_support import write_canary_corpus
from tests.test_embedding_artifact_store import (
    FakeEmbeddingProvider,
    artifact_settings,
    artifact_store,
)


@pytest.mark.asyncio
async def test_missing_input_format_cannot_load_or_replace_active_pointer(tmp_path: Path) -> None:
    # Given a legacy artifact with no tokenizer/input-format declaration.
    knowledge = tmp_path / "knowledge.json"
    write_canary_corpus(knowledge)
    root = tmp_path / "artifacts"
    store = artifact_store(artifact_settings(knowledge, root))
    manifest = await store.build(FakeEmbeddingProvider([[1.0, 0.0], [0.0, 1.0]]))
    store.activate(manifest.artifact_id)
    pointer_before = (root / "active.json").read_bytes()
    path = root / manifest.artifact_id / "manifest.json"
    payload = json.loads(path.read_text())
    payload.pop("input_format", None)
    path.write_text(json.dumps(payload))

    # When trying to reuse an artifact built before raw-text embedding.
    with pytest.raises(EmbeddingArtifactError, match="artifact-input-format-incompatible"):
        store.load_active()
    with pytest.raises(EmbeddingArtifactError, match="artifact-input-format-incompatible"):
        store.activate(manifest.artifact_id)

    # Then the incompatible pointer is never silently replaced.
    assert (root / "active.json").read_bytes() == pointer_before


@pytest.mark.asyncio
async def test_raw_text_identity_rebuilds_beside_legacy_artifact(tmp_path: Path) -> None:
    # Given the legacy identity with the same model, corpus, chunks and dimension.
    knowledge = tmp_path / "knowledge.json"
    write_canary_corpus(knowledge)
    root = tmp_path / "artifacts"
    store = artifact_store(artifact_settings(knowledge, root))
    provider = FakeEmbeddingProvider([[1.0, 0.0], [0.0, 1.0]])
    manifest = await store.build(provider)
    metadata = (root / manifest.artifact_id / "metadata.json").read_bytes()
    legacy_identity = {
        "schema_version": 1, "release_id": manifest.release_id,
        "release_version": manifest.release_version, "corpus_checksum": manifest.corpus_checksum,
        "provider_identity": manifest.provider_identity, "embedding_model": manifest.embedding_model,
        "vector_dimension": manifest.vector_dimension, "chunking_version": manifest.chunking_version,
        "metadata_sha256": sha256(metadata).hexdigest(),
        "documents_sha256": sha256(canonical_bytes([item.model_dump(mode="json") for item in manifest.documents])).hexdigest(),
    }
    legacy_id = sha256(canonical_bytes(legacy_identity)).hexdigest()
    legacy_path = root / legacy_id
    (root / manifest.artifact_id).rename(legacy_path)
    old_payload = json.loads((legacy_path / "manifest.json").read_text())
    old_payload.pop("input_format", None)
    old_payload["artifact_id"] = legacy_id
    (legacy_path / "manifest.json").write_text(json.dumps(old_payload))

    # When rebuilding with the new input protocol.
    rebuilt = await store.build(provider)

    # Then identity differs, embeddings are recomputed and legacy bytes remain.
    assert rebuilt.artifact_id != legacy_id
    assert rebuilt.model_dump()["input_format"] == "raw-text-v1"
    assert provider.document_calls == 2
    assert legacy_path.exists()

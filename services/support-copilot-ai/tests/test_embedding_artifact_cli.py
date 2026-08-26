from pathlib import Path
import subprocess
import sys

import pytest

from app.embedding_artifact import EmbeddingArtifactStore
from tests.knowledge_access_support import write_canary_corpus
from tests.test_embedding_artifact_store import (
    FakeEmbeddingProvider,
    artifact_settings,
    artifact_store,
)


@pytest.mark.asyncio
async def test_cli_verify_corruption_is_nonzero_and_redacted(tmp_path: Path) -> None:
    knowledge_path = tmp_path / "knowledge.json"
    write_canary_corpus(knowledge_path)
    root = tmp_path / "root"
    store: EmbeddingArtifactStore = artifact_store(
        artifact_settings(knowledge_path, root)
    )
    manifest = await store.build(
        FakeEmbeddingProvider([[1.0, 0.0], [0.0, 1.0]])
    )
    (root / manifest.artifact_id / "matrix.npy").write_bytes(b"corrupt")

    result = subprocess.run(
        (
            sys.executable,
            "-m",
            "scripts.manage_embedding_artifacts",
            "verify",
            "--artifact-id",
            manifest.artifact_id,
            "--knowledge",
            str(knowledge_path),
            "--artifact-root",
            str(root),
            "--model",
            "fake-model",
            "--base-url",
            "https://example.test/v1",
            "--dimension",
            "2",
        ),
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 1
    assert "embedding-artifact-error: artifact-corrupt" in result.stderr
    assert "COLLIDING_CANARY" not in result.stderr
    assert "secret" not in result.stderr

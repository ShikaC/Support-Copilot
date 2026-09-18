import json
from types import SimpleNamespace

import anyio
import numpy as np
import pytest

from app.embedding_artifact import EmbeddingArtifactError, EmbeddingArtifactStore
from app.embedding_artifact_identity import file_checksum
from app.knowledge_source import load_knowledge_corpus
from evaluation import gold_rank, hybrid_retrieval, retrieval_only
from tests.knowledge_access_support import write_test_corpus
from tests.test_retrieval_only import harness  # noqa: F401


@pytest.fixture
def evidence(harness: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    write_test_corpus(harness.corpus_path, tuple(
        chunk.model_copy(update={"source_uri": f"kb://fixture#{chunk.chunk_id}"})
        for chunk in harness.corpus.chunks
    ))
    harness.corpus = load_knowledge_corpus(harness.corpus_path)
    harness.store = EmbeddingArtifactStore(harness.settings, harness.corpus)
    manifest = anyio.run(harness.store.build, harness.provider)
    harness.store.activate(manifest.artifact_id)
    harness.artifact = harness.store.load_active()
    monkeypatch.setattr(retrieval_only, "Settings", lambda **kwargs: harness.settings)
    monkeypatch.setattr(retrieval_only, "OpenAIEmbeddingProvider", lambda _: harness.provider)
    (harness.tmp_path / "inputs.json").write_text(json.dumps([
        {"id": "case-1", "input": {"subject": "S", "description": "D"}},
    ]))
    (harness.tmp_path / "cases.json").write_text(json.dumps([
        {"id": "case-1", "source": {"document_id": "chunk-a"}},
    ]))
    args = retrieval_only.parse_args([
        "--root", str(harness.tmp_path), "--inputs", "inputs.json",
        "--corpus", "corpus.json", "--artifact-root", "artifacts",
        "--output", "out", "--execute",
    ])
    anyio.run(retrieval_only.run, args)
    return harness


@pytest.mark.parametrize("tool", ["gold", "hybrid"])
@pytest.mark.parametrize("drift", ["corpus", "model", "matrix", "metadata", "vectors"])
def test_offline_cli_rejects_mixed_retrieval_evidence(
    evidence: SimpleNamespace, tool: str, drift: str,
) -> None:
    # Given: one component no longer belongs to the recorded retrieval run.
    root = evidence.tmp_path
    if drift == "corpus":
        payload = json.loads(evidence.corpus_path.read_text())
        payload["chunks"].reverse()
        evidence.corpus_path.write_text(json.dumps(payload))
    elif drift == "model":
        file = root / "out/retrieval-plan.json"
        payload = json.loads(file.read_text())
        payload["embeddingModel"] = "different-same-dimension-model"
        file.write_text(json.dumps(payload))
    elif drift == "matrix":
        file = root / "artifacts" / evidence.artifact.manifest.artifact_id / "matrix.npy"
        np.save(file, np.zeros_like(evidence.artifact.matrix))
    elif drift == "metadata":
        file = root / "artifacts" / evidence.artifact.manifest.artifact_id / "metadata.json"
        payload = json.loads(file.read_text())
        payload.reverse()
        file.write_text(json.dumps(payload))
    else:
        (root / "out/query-vectors.json").write_text(json.dumps({"case-1": [0., 1., 0.]}))
    args = [
        "--root", str(root), "--vectors", "out/query-vectors.json",
        "--cases", "cases.json", "--corpus", "corpus.json",
        "--artifact-root", "artifacts", "--json", "report.json",
    ]
    # When: a diagnostic CLI tries to combine the inconsistent files.
    with pytest.raises((ValueError, EmbeddingArtifactError)):
        if tool == "gold":
            gold_rank.main(args)
        else:
            hybrid_retrieval.main([*args, "--plan", "out/retrieval-plan.json"])
    # Then: no report legitimizes the mismatched evidence.
    assert not (root / "report.json").exists()


@pytest.mark.parametrize("tool", ["gold", "hybrid"])
def test_offline_cli_uses_recorded_artifact_after_active_pointer_moves(
    evidence: SimpleNamespace, tool: str,
) -> None:
    # A later activation must not change the matrix used for an earlier run.
    (evidence.tmp_path / "artifacts/active.json").write_text(json.dumps({
        "schema_version": 1, "active_artifact_id": "0" * 64,
    }))
    args = [
        "--root", str(evidence.tmp_path), "--vectors", "out/query-vectors.json",
        "--cases", "cases.json", "--corpus", "corpus.json",
        "--artifact-root", "artifacts", "--json", "report.json",
    ]
    before = evidence.provider.query_calls
    if tool == "gold":
        assert gold_rank.main(args) == 0
    else:
        assert hybrid_retrieval.main([*args, "--plan", "out/retrieval-plan.json"]) == 0
    report = json.loads((evidence.tmp_path / "report.json").read_text())
    assert report["artifactId"] == evidence.artifact.manifest.artifact_id
    assert report["casesSha256"] == file_checksum(evidence.tmp_path / "cases.json")
    assert report["measuredCases"] == 1
    assert evidence.provider.query_calls == before


@pytest.mark.parametrize("tool", ["gold", "hybrid"])
def test_offline_cli_does_not_retroactively_certify_legacy_vectors(
    evidence: SimpleNamespace, tool: str,
) -> None:
    manifest_file = evidence.tmp_path / "out/retrieval-only-manifest.json"
    manifest = json.loads(manifest_file.read_text())
    manifest.pop("queryVectorsSha256")
    manifest.pop("retrievalPlanSha256")
    manifest_file.write_text(json.dumps(manifest))
    args = [
        "--root", str(evidence.tmp_path), "--vectors", "out/query-vectors.json",
        "--cases", "cases.json", "--corpus", "corpus.json",
        "--artifact-root", "artifacts", "--json", "report.json",
    ]
    with pytest.raises(ValueError, match="legacy cache"):
        if tool == "gold":
            gold_rank.main(args)
        else:
            hybrid_retrieval.main([*args, "--plan", "out/retrieval-plan.json"])
    assert not (evidence.tmp_path / "report.json").exists()


@pytest.mark.parametrize("vectors", [
    {"different-case": [1.0, 0.0, 0.0]},
    {"case-1": [1.0, 0.0]},
    {"case-1": [float("nan"), 0.0, 0.0]},
])
def test_offline_loader_rejects_invalid_vectors_even_with_matching_hash(
    evidence: SimpleNamespace, vectors: dict[str, list[float]],
) -> None:
    vector_file = evidence.tmp_path / "out/query-vectors.json"
    vector_file.write_text(json.dumps(vectors))
    manifest_file = evidence.tmp_path / "out/retrieval-only-manifest.json"
    manifest = json.loads(manifest_file.read_text())
    manifest["queryVectorsSha256"] = file_checksum(vector_file)
    manifest_file.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        gold_rank.main([
            "--root", str(evidence.tmp_path), "--vectors", "out/query-vectors.json",
            "--cases", "cases.json", "--corpus", "corpus.json",
            "--artifact-root", "artifacts", "--json", "report.json",
        ])
    assert not (evidence.tmp_path / "report.json").exists()


def test_offline_loader_rejects_same_dimension_embedding_model_mismatch(
    evidence: SimpleNamespace,
) -> None:
    # Even internally consistent execution hashes cannot make a model compatible.
    plan_file = evidence.tmp_path / "out/retrieval-plan.json"
    plan = json.loads(plan_file.read_text())
    plan["embeddingModel"] = "another-model-with-three-dimensions"
    plan_file.write_text(json.dumps(plan))
    manifest_file = evidence.tmp_path / "out/retrieval-only-manifest.json"
    manifest = json.loads(manifest_file.read_text())
    manifest["retrievalPlanSha256"] = file_checksum(plan_file)
    manifest_file.write_text(json.dumps(manifest))
    with pytest.raises(EmbeddingArtifactError, match="artifact-incompatible"):
        gold_rank.main([
            "--root", str(evidence.tmp_path), "--vectors", "out/query-vectors.json",
            "--cases", "cases.json", "--corpus", "corpus.json",
            "--artifact-root", "artifacts", "--json", "report.json",
        ])
    assert not (evidence.tmp_path / "report.json").exists()

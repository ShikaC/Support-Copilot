"""Select an actual successful corpus task without switching the active corpus."""

import json
from hashlib import sha256
from pathlib import Path
from typing import Literal, assert_never
from uuid import uuid4

import app.main as main
import pytest
from fastapi.testclient import TestClient

from tests.index_rebuild_api_support import ControlledProvider, configure_rebuild
from tests.test_corpus_build_api import HEADERS


def generate_candidate(
    directory: Path, client: TestClient, text: str = "A😀BCDE"
) -> tuple[str, str]:
    source = directory / "documents.json"
    source.write_text(
        json.dumps(
            {
                "doc_data": {
                    "dmv": {
                        "sample": {
                            "doc_id": "sample",
                            "title": "Candidate",
                            "doc_text": text,
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    response = client.post(
        "/knowledge/corpus/build",
        json={
            "expectedSourceChecksum": sha256(source.read_bytes()).hexdigest(),
            "window": 4,
            "stride": 3,
        },
    )
    assert response.status_code == 202
    return response.json()["taskId"], response.headers["Location"]


def test_candidate_build_uses_verified_snapshot_and_records_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = ControlledProvider()
    config = configure_rebuild(tmp_path, monkeypatch, provider)
    config.knowledge_corpus_mutation_enabled = True
    config.knowledge_corpus_source_path = tmp_path / "documents.json"
    config.knowledge_corpus_build_root = tmp_path / "corpus-builds"
    with TestClient(main.app, headers=HEADERS) as client:
        source_id, source_location = generate_candidate(tmp_path, client)
    with TestClient(main.app, headers=HEADERS) as client:
        generated = client.get(source_location).json()
    assert generated["status"] == "SUCCEEDED"
    candidate = (
        config.knowledge_corpus_build_root / source_id / "result" / "corpus.json"
    )
    original = json.loads(candidate.read_bytes())
    active_before = config.knowledge_path.read_bytes()
    pointer = config.embedding_artifact_root / "active.json"
    pointer_before = pointer.read_bytes()
    try:
        with TestClient(main.app, headers=HEADERS) as client:
            accepted = client.post(
                "/knowledge/index/rebuild",
                json={
                    "corpusBuildTaskId": source_id,
                    "expectedCorpusChecksum": generated["result"]["corpusChecksum"],
                    "maxEmbeddingCalls": 1,
                },
            )
            assert accepted.status_code == 202, accepted.text
            assert provider.entered.wait(5)
            candidate.write_text("changed after admission")
            provider.release.set()
        with TestClient(main.app, headers=HEADERS) as client:
            finished = client.get(accepted.headers["Location"]).json()
        assert finished["status"] == "SUCCEEDED"
        assert finished["corpusBuildTaskId"] == source_id
        assert finished["corpusChecksum"] == original["corpus_checksum"]
        assert finished["embeddingCalls"] == provider.calls == 1
        artifact = config.embedding_artifact_root / finished["artifactId"]
        manifest = json.loads((artifact / "manifest.json").read_bytes())
        metadata = json.loads((artifact / "metadata.json").read_bytes())
        assert manifest["chunking_version"] == "doc2dial-codepoints-4-3-v1"
        assert manifest["corpus_checksum"] == original["corpus_checksum"]
        assert [row["chunk_id"] for row in metadata] == [
            chunk["chunk_id"] for chunk in original["chunks"]
        ]
        assert config.knowledge_path.read_bytes() == active_before
        assert pointer.read_bytes() == pointer_before
    finally:
        provider.release.set()


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "running",
        "failed",
        "file",
        "checksum",
        "budget",
        "corrupt_status",
        "result_mismatch",
    ],
)
def test_candidate_rejection_never_calls_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fault: Literal[
        "missing",
        "running",
        "failed",
        "file",
        "checksum",
        "budget",
        "corrupt_status",
        "result_mismatch",
    ],
) -> None:
    provider = ControlledProvider()
    provider.release.set()
    config = configure_rebuild(tmp_path, monkeypatch, provider)
    config.knowledge_corpus_mutation_enabled = True
    config.knowledge_corpus_source_path = tmp_path / "documents.json"
    config.knowledge_corpus_build_root = tmp_path / "corpus-builds"
    with TestClient(main.app, headers=HEADERS) as client:
        task_id, location = generate_candidate(tmp_path, client, "x" * 132)
    with TestClient(main.app, headers=HEADERS) as client:
        status = client.get(location).json()
    assert status["status"] == "SUCCEEDED"
    directory = config.knowledge_corpus_build_root / task_id
    checksum = status["result"]["corpusChecksum"]
    budget = 2
    expected_code = 409
    match fault:
        case "missing":
            task_id = str(uuid4())
            expected_code = 404
        case "running":
            status.update(status="RUNNING", result=None, finishedAt=None)
            (directory / "status.json").write_text(json.dumps(status))
        case "failed":
            status.update(
                status="FAILED", result=None, failureCode="CORPUS_PROCESS_FAILED"
            )
            (directory / "status.json").write_text(json.dumps(status))
        case "file":
            with (directory / "result" / "corpus.json").open("a") as stream:
                stream.write(" ")
        case "checksum":
            checksum = "0" * 64
        case "budget":
            budget = 1
            expected_code = 422
        case "corrupt_status":
            (directory / "status.json").write_text('{"status":"SUCCEEDED"}')
            expected_code = 503
        case "result_mismatch":
            status["result"]["corpusChecksum"] = "0" * 64
            (directory / "status.json").write_text(json.dumps(status))
        case unreachable:
            assert_never(unreachable)
    # Reading a prior successful candidate does not require generation to be enabled.
    config.knowledge_corpus_mutation_enabled = False
    with TestClient(main.app, headers=HEADERS) as client:
        rejected = client.post(
            "/knowledge/index/rebuild",
            json={
                "corpusBuildTaskId": task_id,
                "expectedCorpusChecksum": checksum,
                "maxEmbeddingCalls": budget,
            },
        )
    assert rejected.status_code == expected_code, rejected.text
    assert provider.calls == 0
    assert not list(config.embedding_artifact_root.glob(".rebuild-tasks/*/status.json"))
    assert str(tmp_path) not in rejected.text

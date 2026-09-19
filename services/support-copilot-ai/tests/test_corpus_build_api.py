import json
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

import app.main as main
import pytest
from fastapi.testclient import TestClient

HEADERS = {"X-Internal-Service-Token": "synthetic-test-internal-service-token"}
ROUTE = "/knowledge/corpus/build"


def configure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    source = tmp_path / "documents.json"
    source.write_text(
        json.dumps(
            {
                "doc_data": {
                    "dmv": {
                        "sample": {
                            "doc_id": "sample",
                            "title": "Example",
                            "doc_text": "A😀BCDE",
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    config = main.settings.model_copy(
        update={
            "knowledge_corpus_mutation_enabled": True,
            "knowledge_corpus_source_path": source,
            "knowledge_corpus_build_root": tmp_path / "builds",
        }
    )
    monkeypatch.setattr(main, "settings", config)
    return sha256(source.read_bytes()).hexdigest()


def test_corpus_build_runs_node_and_persists_a_validated_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given a document-only source and unchanged active knowledge corpus.
    checksum = configure(tmp_path, monkeypatch)
    monkeypatch.setenv("NODE_OPTIONS", "--private-invalid-option-must-not-reach-child")
    active = main.settings.knowledge_path.read_bytes()
    # When the internal API accepts the build, then a new lifespan polls the result.
    with TestClient(main.app, headers=HEADERS) as client:
        accepted = client.post(
            ROUTE, json={"expectedSourceChecksum": checksum, "window": 4, "stride": 3}
        )
        assert accepted.status_code == 202
        location = accepted.headers["Location"]
    with TestClient(main.app, headers=HEADERS) as client:
        response = client.get(location)
    # Then the real Node process generated the expected corpus without activation or cases.
    status = response.json()
    assert response.status_code == 200
    assert status["status"] == "SUCCEEDED"
    assert status["result"]["chunkCount"] == 2
    result = tmp_path / "builds" / status["taskId"] / "result"
    corpus = json.loads((result / "corpus.json").read_text())
    assert [c["content"] for c in corpus["chunks"]] == ["A😀BC", "CDE"]
    assert not (result / "cases.json").exists()
    assert not (result / "protocol.json").exists()
    assert main.settings.knowledge_path.read_bytes() == active


@pytest.mark.parametrize("method", ["POST", "GET"])
def test_corpus_build_requires_internal_identity(method: str) -> None:
    # Given an unauthenticated caller, even an unknown task must stay protected.
    path = ROUTE if method == "POST" else f"{ROUTE}/{uuid4()}"
    # When making a request with no internal header.
    response = TestClient(main.app).request(method, path, json={})
    # Then authentication precedes parameter or feature validation.
    assert response.status_code == 401


def test_corpus_build_rejects_source_drift_and_arbitrary_options(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given a configured source and valid internal identity.
    checksum = configure(tmp_path, monkeypatch)
    with TestClient(main.app, headers=HEADERS) as client:
        # When the supplied source identity is stale or an arbitrary path is supplied.
        mismatch = client.post(
            ROUTE, json={"expectedSourceChecksum": "0" * 64, "window": 4, "stride": 3}
        )
        extra = client.post(
            ROUTE,
            json={
                "expectedSourceChecksum": checksum,
                "window": 4,
                "stride": 3,
                "source": "/private/source",
                "perDomain": 8,
            },
        )
    # Then neither can create a task or change evaluation inputs.
    assert mismatch.status_code == 409
    assert extra.status_code == 422
    assert not list((tmp_path / "builds").glob("*/status.json"))


@pytest.mark.parametrize(
    "overrides",
    [
        {"window": True},
        {"stride": 5},
        {"window": 0},
        {"window": 8001},
        {"stride": 0},
    ],
)
def test_corpus_build_rejects_invalid_chunking(overrides: dict[str, int]) -> None:
    # Given a valid request shape except for a chunking boundary.
    body = {"expectedSourceChecksum": "a" * 64, "window": 4, "stride": 3, **overrides}
    # When parsing the public request contract.
    response = TestClient(main.app, headers=HEADERS).post(ROUTE, json=body)
    # Then no worker can receive invalid ranges or booleans as integers.
    assert response.status_code == 422


def test_corpus_build_disabled_and_unknown_history(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given disabled mutation with an isolated history root.
    checksum = configure(tmp_path, monkeypatch)
    monkeypatch.setattr(main.settings, "knowledge_corpus_mutation_enabled", False)
    with TestClient(main.app, headers=HEADERS) as client:
        # When writing or reading an unknown task.
        denied = client.post(
            ROUTE, json={"expectedSourceChecksum": checksum, "window": 4, "stride": 3}
        )
        missing = client.get(f"{ROUTE}/{uuid4()}")
    # Then writes fail, while the history route remains available and reports absence.
    assert denied.status_code == 403
    assert missing.status_code == 404
    assert str(tmp_path) not in missing.text


def test_invalid_document_fails_with_retained_candidate_and_safe_code(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given malformed document bytes containing a private canary.
    configure(tmp_path, monkeypatch)
    source = tmp_path / "documents.json"
    source.write_text("private-customer-canary invalid JSON", encoding="utf-8")
    checksum = sha256(source.read_bytes()).hexdigest()
    with TestClient(main.app, headers=HEADERS) as client:
        # When the real Node child rejects the document.
        accepted = client.post(
            ROUTE, json={"expectedSourceChecksum": checksum, "window": 4, "stride": 3}
        )
        assert accepted.status_code == 202
    with TestClient(main.app, headers=HEADERS) as client:
        failed = client.get(accepted.headers["Location"])
    # Then restart retains failure evidence without exposing source text.
    assert failed.json()["status"] == "FAILED"
    assert failed.json()["failureCode"] == "CORPUS_PROCESS_FAILED"
    assert "private-customer-canary" not in failed.text
    task = tmp_path / "builds" / failed.json()["taskId"]
    assert (task / "candidate").is_dir()
    assert not (task / "result").exists()


def test_missing_node_rejects_before_admission(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given a deployment without its configured Node executable.
    checksum = configure(tmp_path, monkeypatch)
    monkeypatch.setattr(
        main.settings, "knowledge_corpus_node_command", str(tmp_path / "absent-node")
    )
    with TestClient(main.app, headers=HEADERS) as client:
        # When accepting a build would be impossible.
        response = client.post(
            ROUTE, json={"expectedSourceChecksum": checksum, "window": 4, "stride": 3}
        )
    # Then fail before making a durable RUNNING record.
    assert response.status_code == 503
    assert not list((tmp_path / "builds").glob("*/status.json"))

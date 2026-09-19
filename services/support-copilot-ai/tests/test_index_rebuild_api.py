from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from tests.index_rebuild_api_support import ControlledProvider, configure_rebuild

AUTH_HEADERS = {"X-Internal-Service-Token": "synthetic-test-internal-service-token"}


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("method", ["GET", "POST"])
def test_rebuild_authentication_precedes_feature_gate(
    monkeypatch: pytest.MonkeyPatch, enabled: bool, method: str
) -> None:
    # Given an app with either feature flag value and no internal credential.
    monkeypatch.setattr(main_module.settings, "knowledge_index_mutation_enabled", enabled)
    path = "/knowledge/index/rebuild"
    if method == "GET":
        path += f"/{uuid4()}"
    client = TestClient(main_module.app)

    # When requesting the protected rebuild surface.
    response = client.request(method, path, json={})

    # Then authentication wins, including over malformed request bodies.
    assert response.status_code == 401
    assert response.json()["code"] == "INTERNAL_SERVICE_AUTHENTICATION_REQUIRED"


def test_rebuild_rejects_disabled_mutation_before_task_creation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given an authenticated caller while index mutation is disabled.
    monkeypatch.setattr(main_module.settings, "knowledge_index_mutation_enabled", False)
    client = TestClient(main_module.app, headers=AUTH_HEADERS)

    # When requesting a bounded rebuild.
    response = client.post(
        "/knowledge/index/rebuild",
        json={"expectedCorpusChecksum": "a" * 64, "maxEmbeddingCalls": 1},
    )

    # Then no task is accepted.
    assert response.status_code == 403
    assert response.json()["code"] == "INDEX_MUTATION_DISABLED"


def test_rebuild_rejects_arbitrary_paths_and_activation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given an authenticated caller with mutation enabled.
    monkeypatch.setattr(main_module.settings, "knowledge_index_mutation_enabled", True)
    client = TestClient(main_module.app, headers=AUTH_HEADERS)

    # When trying to select an arbitrary path or auto-activate a new artifact.
    response = client.post(
        "/knowledge/index/rebuild",
        json={
            "expectedCorpusChecksum": "a" * 64,
            "maxEmbeddingCalls": 1,
            "knowledgePath": "/untrusted/corpus.json",
            "activate": True,
        },
    )

    # Then strict input parsing rejects both extra options.
    assert response.status_code == 422
    assert response.json()["code"] == "REQUEST_VALIDATION_FAILED"


def test_accepted_build_is_pollable_without_blocking_or_activating(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given an active artifact and a provider blocked in a background worker.
    provider = ControlledProvider()
    settings = configure_rebuild(tmp_path, monkeypatch, provider)
    pointer = settings.embedding_artifact_root / "active.json"
    before_pointer = pointer.read_bytes()
    before_corpus = settings.knowledge_path.read_bytes()
    request = {
        "expectedCorpusChecksum": main_module.retriever.corpus_metadata.corpus_checksum,
        "maxEmbeddingCalls": 1,
    }

    # When the server accepts a build and the external batch remains in flight.
    try:
        with TestClient(main_module.app, headers=AUTH_HEADERS) as client:
            accepted = client.post("/knowledge/index/rebuild", json=request)
            assert accepted.status_code == 202
            location = accepted.headers["Location"]
            assert provider.entered.wait(timeout=5)
            running = client.get(location)
            health = client.get("/health/live")
            duplicate = client.post("/knowledge/index/rebuild", json=request)
            settings.knowledge_index_mutation_enabled = False
            read_disabled = client.get(location)
            provider.release.set()

        # Then reads remain available, duplicate work is refused, and restart keeps evidence.
        with TestClient(main_module.app, headers=AUTH_HEADERS) as restarted:
            finished = restarted.get(location)
            versions = restarted.get("/knowledge/index/versions")
        assert running.status_code == 200
        assert running.json()["status"] == "RUNNING"
        assert running.json()["completedChunks"] == 0
        assert health.status_code == 200
        assert duplicate.status_code == 409
        assert read_disabled.status_code == 200
        assert finished.status_code == 200
        assert finished.json()["status"] == "SUCCEEDED"
        assert finished.json()["completedChunks"] == 2
        assert finished.json()["embeddingCalls"] == provider.calls == 1
        assert finished.json()["artifactId"] in {
            item["artifactId"] for item in versions.json()["versions"]
        }
        assert pointer.read_bytes() == before_pointer
        assert settings.knowledge_path.read_bytes() == before_corpus
    finally:
        provider.release.set()


def test_unknown_build_error_remains_failed_and_redacted_after_restart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given a provider that raises an unexpected error containing private details.
    provider = ControlledProvider(fail=True)
    provider.release.set()
    settings = configure_rebuild(tmp_path, monkeypatch, provider)
    before_pointer = (settings.embedding_artifact_root / "active.json").read_bytes()

    # When its accepted task finishes with that error and the app restarts.
    with TestClient(main_module.app, headers=AUTH_HEADERS) as client:
        accepted = client.post("/knowledge/index/rebuild", json={
            "expectedCorpusChecksum": main_module.retriever.corpus_metadata.corpus_checksum,
            "maxEmbeddingCalls": 1,
        })
        assert accepted.status_code == 202
        location = accepted.headers["Location"]
    with TestClient(main_module.app, headers=AUTH_HEADERS) as restarted:
        failed = restarted.get(location)

    # Then it stays a visible failure with retained evidence, never a fallback or success.
    assert failed.status_code == 200
    assert failed.json()["status"] == "FAILED"
    assert failed.json()["artifactId"] is None
    assert failed.json()["completedChunks"] == 0
    assert "private-provider-token" not in failed.text
    assert "/private/customer/path" not in failed.text
    assert list(settings.embedding_artifact_root.glob(".rebuild-tasks/*/candidate"))
    assert (settings.embedding_artifact_root / "active.json").read_bytes() == before_pointer


def test_unknown_task_returns_safe_not_found_after_authentication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given an isolated authenticated service without the requested task.
    configure_rebuild(tmp_path, monkeypatch, ControlledProvider())
    with TestClient(main_module.app, headers=AUTH_HEADERS) as client:
        # When polling an unknown identity.
        response = client.get(f"/knowledge/index/rebuild/{uuid4()}")

    # Then it reports absence without exposing a filesystem path.
    assert response.status_code == 404
    assert str(tmp_path) not in response.text

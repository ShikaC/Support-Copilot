"""Real Uvicorn and SDK requests against a bounded synthetic localhost provider."""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from uuid import uuid4

from tests.test_index_rebuild_http_support import (
    PRIVATE_DETAIL,
    WIRE_KEY,
    embedding_server,
    record_http_response,
    running_api,
    seeded_index,
    terminal_response,
)


def test_rebuild_http_stays_responsive_and_preserves_active_after_success(
    tmp_path: Path, record_property: Callable[[str, str], None],
) -> None:
    # Given an actual HTTP provider held before returning its first embedding response.
    with embedding_server() as provider:
        fixture = seeded_index(tmp_path, provider)
        with running_api(fixture, provider) as client:
            # When a rebuild is accepted while the provider is blocked.
            accepted = client.post("/knowledge/index/rebuild", json={
                "expectedCorpusChecksum": fixture.checksum, "maxEmbeddingCalls": 1,
            })
            assert accepted.status_code == 202, accepted.text
            record_http_response(record_property, "accepted", accepted)
            location = accepted.headers["Location"]
            assert location == f'/knowledge/index/rebuild/{accepted.json()["taskId"]}'
            assert provider.entered.wait(5)

            # Then unrelated requests and polling complete before the provider is released.
            with ThreadPoolExecutor(max_workers=2) as pool:
                health = pool.submit(client.get, "/health/live")
                progress = pool.submit(client.get, location)
                health_response = health.result(timeout=3)
                assert health_response.status_code == 200
                progress_response = progress.result(timeout=3)
                running = progress_response.json()
            record_http_response(record_property, "running", progress_response)
            record_property("responsiveness", json.dumps({
                "healthStatusCode": health_response.status_code,
                "providerBlockedDuringPoll": not provider.release.is_set(),
            }))
            assert running["status"] == "RUNNING"
            assert running["totalChunks"] == 2
            assert running["completedChunks"] == 0
            assert running["embeddingCalls"] == 1
            assert running["estimatedEmbeddingCalls"] == 1
            conflict = client.post("/knowledge/index/rebuild", json={
                "expectedCorpusChecksum": fixture.checksum, "maxEmbeddingCalls": 1,
            })
            assert conflict.status_code == 409
            assert len(provider.calls) == 1
            record_http_response(record_property, "conflict", conflict)
            provider.release.set()
            terminal = terminal_response(client, location)
            completed = terminal.json()
            record_http_response(record_property, "terminal", terminal)
            assert completed["status"] == "SUCCEEDED"
            assert completed["completedChunks"] == completed["totalChunks"] == 2
            assert completed["embeddingCalls"] == 1
            assert completed["artifactId"] != fixture.active_id
            versions = client.get("/knowledge/index/versions").json()
            assert versions["activeArtifactId"] == fixture.active_id
            by_id = {item["artifactId"]: item for item in versions["versions"]}
            assert by_id[completed["artifactId"]]["active"] is False
            assert (fixture.root / "active.json").read_bytes() == fixture.pointer_bytes
            assert fixture.corpus.read_bytes() == fixture.corpus_bytes
            assert provider.calls[0].model == "synthetic-embedding-model"
            assert len(provider.calls[0].input) == 2
            assert provider.authorizations == [f"Bearer {WIRE_KEY}"]
            record_property("completionInvariants", json.dumps({
                "providerCalls": len(provider.calls),
                "activePointerUnchanged": (fixture.root / "active.json").read_bytes() == fixture.pointer_bytes,
                "corpusUnchanged": fixture.corpus.read_bytes() == fixture.corpus_bytes,
                "candidateListed": completed["artifactId"] in by_id,
                "candidateActive": by_id[completed["artifactId"]]["active"],
            }))

        # Then a fresh process can still read the completed task without another provider call.
        with running_api(fixture, provider, enabled=False) as restarted:
            persisted = restarted.get(location)
            assert persisted.status_code == 200
            assert persisted.json() == completed
            assert len(provider.calls) == 1
            record_http_response(record_property, "restarted", persisted)
            record_property("restartInvariants", json.dumps({
                "statusPreserved": persisted.json() == completed,
                "providerCalls": len(provider.calls),
            }))


def test_rebuild_http_provider_failure_is_durable_sanitized_and_never_retried(
    tmp_path: Path, record_property: Callable[[str, str], None],
) -> None:
    # Given a localhost provider returning a synthetic private detail in its HTTP 500 body.
    with embedding_server(failure=True) as provider:
        fixture = seeded_index(tmp_path, provider)
        provider.release.set()
        with running_api(fixture, provider) as client:
            # When the real SDK receives the failure during an accepted task.
            accepted = client.post("/knowledge/index/rebuild", json={
                "expectedCorpusChecksum": fixture.checksum, "maxEmbeddingCalls": 1,
            })
            assert accepted.status_code == 202, accepted.text
            record_http_response(record_property, "accepted", accepted)
            location = accepted.headers["Location"]
            failure = terminal_response(client, location)
            record_http_response(record_property, "terminal", failure)

            # Then failure remains inspectable without exposing the provider body or changing live data.
            body = failure.json()
            assert body["status"] == "FAILED"
            assert body["failureCode"] == "EMBEDDING_PROVIDER_FAILED"
            assert body["completedChunks"] == 0
            assert body["embeddingCalls"] == 1
            assert len(provider.calls) == 1
            assert PRIVATE_DETAIL not in failure.text
            assert WIRE_KEY not in failure.text
            assert (fixture.root / ".rebuild-tasks" / body["taskId"] / "candidate").is_dir()
            assert (fixture.root / "active.json").read_bytes() == fixture.pointer_bytes
            assert fixture.corpus.read_bytes() == fixture.corpus_bytes
            record_property("failureInvariants", json.dumps({
                "providerCalls": len(provider.calls),
                "activePointerUnchanged": (fixture.root / "active.json").read_bytes() == fixture.pointer_bytes,
                "corpusUnchanged": fixture.corpus.read_bytes() == fixture.corpus_bytes,
                "candidateRetained": (fixture.root / ".rebuild-tasks" / body["taskId"] / "candidate").is_dir(),
                "providerDetailAbsentFromResponse": PRIVATE_DETAIL not in failure.text,
                "secretAbsentFromResponse": WIRE_KEY not in failure.text,
            }))

        with running_api(fixture, provider, enabled=False) as restarted:
            persisted = restarted.get(location)
            assert persisted.json() == body
            assert len(provider.calls) == 1
            record_http_response(record_property, "restarted", persisted)
            record_property("restartInvariants", json.dumps({
                "statusPreserved": persisted.json() == body,
                "providerCalls": len(provider.calls),
            }))
        log = (tmp_path / "uvicorn.log").read_text()
        assert PRIVATE_DETAIL not in log
        assert WIRE_KEY not in log
        record_property("logSanitization", json.dumps({
            "providerDetailAbsentFromLog": PRIVATE_DETAIL not in log,
            "secretAbsentFromLog": WIRE_KEY not in log,
        }))


def test_rebuild_http_auth_precedes_disabled_mutation_and_unknown_task_is_missing(
    tmp_path: Path, record_property: Callable[[str, str], None],
) -> None:
    # Given a running service with rebuild mutation disabled.
    with embedding_server() as provider:
        fixture = seeded_index(tmp_path, provider)
        with running_api(fixture, provider, enabled=False) as client:
            # When callers attempt to create or read tasks at the HTTP boundary.
            request = {"expectedCorpusChecksum": fixture.checksum, "maxEmbeddingCalls": 1}
            unauthenticated = client.post("/knowledge/index/rebuild", json=request,
                                          headers={"X-Internal-Service-Token": ""})
            disabled = client.post("/knowledge/index/rebuild", json=request)
            missing = client.get(f"/knowledge/index/rebuild/{uuid4()}")

            # Then authentication wins; valid callers see the explicit feature/missing-task outcomes.
            assert unauthenticated.status_code == 401
            assert disabled.status_code == 403
            assert disabled.json()["code"] == "INDEX_MUTATION_DISABLED"
            assert missing.status_code == 404
            assert provider.calls == []
            record_http_response(record_property, "unauthenticated", unauthenticated)
            record_http_response(record_property, "mutationDisabled", disabled)
            record_http_response(record_property, "unknownTask", missing)
            record_property("providerCalls", json.dumps(len(provider.calls)))

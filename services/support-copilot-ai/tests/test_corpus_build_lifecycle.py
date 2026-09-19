import os
from pathlib import Path
from threading import Event

import app.corpus_build_process as process_module
import app.main as main
import pytest
from app.config import Settings
from app.corpus_build import CorpusBuildManager
from app.corpus_build_models import CorpusBuildResult
from app.corpus_build_process import CorpusBuildInput, build_corpus
from fastapi.testclient import TestClient

from tests.test_corpus_build_api import HEADERS, ROUTE, configure


class InjectedBuilderError(RuntimeError):
    """Unexpected implementation failure used to verify the worker boundary."""


def test_source_snapshot_and_lock_survive_the_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given a real generator paused before receiving its immutable source snapshot.
    checksum = configure(tmp_path, monkeypatch)
    entered, release = Event(), Event()

    def controlled(inputs: CorpusBuildInput) -> CorpusBuildResult:
        entered.set()
        assert release.wait(5)
        return build_corpus(inputs)

    def manager(config: Settings) -> CorpusBuildManager:
        return CorpusBuildManager(config, controlled)

    monkeypatch.setattr(main, "CorpusBuildManager", manager)
    body = {"expectedSourceChecksum": checksum, "window": 4, "stride": 3}
    try:
        with TestClient(main.app, headers=HEADERS) as client:
            # When a disk change and a second manager race an accepted task.
            accepted = client.post(ROUTE, json=body)
            assert accepted.status_code == 202
            assert entered.wait(5)
            running = client.get(accepted.headers["Location"])
            other = CorpusBuildManager(main.settings)
            assert other.storage.acquire() is None
            duplicate = client.post(ROUTE, json=body)
            assert client.get("/health/live").status_code == 200
            (tmp_path / "documents.json").write_text("changed after admission")
            release.set()
        with TestClient(main.app, headers=HEADERS) as client:
            finished = client.get(accepted.headers["Location"])
        # Then the admitted bytes win, with no overlapping build or blocked health endpoint.
        assert duplicate.status_code == 409
        assert running.json()["status"] == "RUNNING"
        assert finished.json()["result"]["sourceChecksum"] == checksum
        assert finished.json()["status"] == "SUCCEEDED"
    finally:
        release.set()


def test_real_node_timeout_kills_and_reaps_the_child(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given a controlled generator that records its PID and never completes.
    checksum = configure(tmp_path, monkeypatch)
    script = tmp_path / "hang.mjs"
    script.write_text(
        "import fs from 'node:fs'; import path from 'node:path';\n"
        "fs.writeFileSync(path.join(process.argv[4], 'pid'), String(process.pid));\n"
        "setInterval(() => {}, 1000);\n"
    )
    monkeypatch.setattr(process_module, "GENERATOR", script)
    monkeypatch.setattr(main.settings, "knowledge_corpus_build_timeout_seconds", 1.0)
    with TestClient(main.app, headers=HEADERS) as client:
        # When the configured deadline expires in the actual subprocess adapter.
        accepted = client.post(
            ROUTE, json={"expectedSourceChecksum": checksum, "window": 4, "stride": 3}
        )
        assert accepted.status_code == 202
    with TestClient(main.app, headers=HEADERS) as client:
        failed = client.get(accepted.headers["Location"])
    # Then failure is durable and the process that held its resources is gone.
    assert failed.json()["failureCode"] == "CORPUS_BUILD_TIMEOUT"
    pid = int(
        (
            tmp_path / "builds" / failed.json()["taskId"] / "candidate" / "pid"
        ).read_text()
    )
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


def test_interrupted_and_corrupt_statuses_are_not_reported_as_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given a durable RUNNING record whose owner was lost before worker execution.
    from app.corpus_build_models import CorpusBuildRequest

    checksum = configure(tmp_path, monkeypatch)
    manager = CorpusBuildManager(main.settings)
    prepared = manager._prepare(
        CorpusBuildRequest(expectedSourceChecksum=checksum, window=4, stride=3),
        "test-recovery",
    )
    prepared.ownership.close()
    task_id = prepared.status.task_id
    with TestClient(main.app, headers=HEADERS) as client:
        # When a new process observes the missing owner, then a corrupted saved status.
        recovered = client.get(f"{ROUTE}/{task_id}")
        (manager.storage.directory(task_id) / "status.json").write_text(
            '{"status":"SUCCEEDED"}'
        )
        corrupt = client.get(f"{ROUTE}/{task_id}")
    # Then interrupted work fails explicitly, and corrupt records fail closed.
    assert recovered.json()["failureCode"] == "CORPUS_BUILD_INTERRUPTED"
    assert corrupt.status_code == 503


def test_unknown_builder_exception_is_redacted_and_retains_failed_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given an unexpected implementation error, rather than an external dependency failure.
    checksum = configure(tmp_path, monkeypatch)

    def broken(_inputs: CorpusBuildInput) -> CorpusBuildResult:
        raise InjectedBuilderError("private-internal-canary")

    def manager(config: Settings) -> CorpusBuildManager:
        return CorpusBuildManager(config, broken)

    monkeypatch.setattr(main, "CorpusBuildManager", manager)
    with TestClient(main.app, headers=HEADERS) as client:
        # When the worker fails unexpectedly.
        accepted = client.post(
            ROUTE, json={"expectedSourceChecksum": checksum, "window": 4, "stride": 3}
        )
    with TestClient(main.app, headers=HEADERS) as client:
        failed = client.get(accepted.headers["Location"])
    # Then no fallback or fabricated result hides the programming failure.
    assert failed.json()["failureCode"] == "CORPUS_INTERNAL_ERROR"
    assert failed.json()["result"] is None
    assert "private-internal-canary" not in failed.text

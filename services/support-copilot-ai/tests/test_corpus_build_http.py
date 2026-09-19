"""Exercise the actual Uvicorn and Node processes without external providers."""

import json
import shutil
import socket
import subprocess
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
from threading import Event
from time import monotonic
from typing import Final

import httpx2

from tests.test_index_rebuild_http_support import terminal_response

SERVICE: Final = Path(__file__).resolve().parents[1]
TOKEN: Final = "synthetic-test-internal-service-token"


@contextmanager
def corpus_api(directory: Path, *, enabled: bool = True) -> Iterator[httpx2.Client]:
    """Own a server with an allowlisted environment and isolated source/history."""
    node = shutil.which("node")
    assert node is not None, "Node is a required corpus test dependency"
    environment = {
        "PYTHONPATH": str(SERVICE),
        "AI_MODE": "mock",
        "SUPPORT_COPILOT_INTERNAL_SERVICE_TOKEN": TOKEN,
        "KNOWLEDGE_PATH": str(SERVICE / "app/data/knowledge.json"),
        "EMBEDDING_ARTIFACT_ROOT": str(directory / "artifacts"),
        "KNOWLEDGE_CORPUS_MUTATION_ENABLED": str(enabled).lower(),
        "KNOWLEDGE_CORPUS_SOURCE_PATH": str(directory / "source.json"),
        "KNOWLEDGE_CORPUS_BUILD_ROOT": str(directory / "builds"),
        "KNOWLEDGE_CORPUS_NODE_COMMAND": node,
    }
    with socket.socket() as listener, (directory / "uvicorn.log").open("a+") as log:
        listener.bind(("127.0.0.1", 0))
        listener.listen(128)
        address = f"http://127.0.0.1:{listener.getsockname()[1]}"
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--fd",
                str(listener.fileno()),
                "--no-access-log",
                "--log-level",
                "warning",
            ],
            cwd=directory,
            env=environment,
            pass_fds=(listener.fileno(),),
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        transport = httpx2.HTTPTransport(
            retries=0,
            trust_env=False,
            limits=httpx2.Limits(
                max_connections=4, max_keepalive_connections=2, keepalive_expiry=5
            ),
            socket_options=[(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)],
        )
        try:
            with httpx2.Client(
                base_url=address,
                transport=transport,
                trust_env=False,
                timeout=httpx2.Timeout(connect=1, read=2, write=2, pool=2),
                headers={"X-Internal-Service-Token": TOKEN},
            ) as client:
                deadline = monotonic() + 20
                while monotonic() < deadline:
                    assert process.poll() is None, (
                        directory / "uvicorn.log"
                    ).read_text()
                    try:
                        if client.get("/health/live").status_code == 200:
                            break
                    except (httpx2.ConnectError, httpx2.ReadTimeout):
                        Event().wait(0.02)
                else:
                    raise AssertionError("Corpus API did not become healthy")
                yield client
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def test_real_http_generation_failure_and_restart(
    tmp_path: Path,
    record_property: Callable[[str, str], None],
) -> None:
    # Given an actual API process with documents only and no provider credentials.
    source = tmp_path / "source.json"
    source.write_text(
        json.dumps(
            {
                "doc_data": {
                    "dmv": {
                        "example": {
                            "doc_id": "example",
                            "title": "Example",
                            "doc_text": "A😀BCDE",
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    active_path = SERVICE / "app/data/knowledge.json"
    active = active_path.read_bytes()
    with corpus_api(tmp_path) as client:
        accepted = client.post(
            "/knowledge/corpus/build",
            json={
                "expectedSourceChecksum": sha256(source.read_bytes()).hexdigest(),
                "window": 4,
                "stride": 3,
            },
        )
        assert accepted.status_code == 202
        location = accepted.headers["Location"]
        succeeded = terminal_response(client, location)
        assert succeeded.json()["status"] == "SUCCEEDED"
        assert succeeded.json()["result"]["chunkCount"] == 2
        record_property(
            "accepted",
            json.dumps(
                {
                    "statusCode": accepted.status_code,
                    "location": location,
                    "body": accepted.json(),
                }
            ),
        )
        record_property("succeeded", succeeded.text)
        # When a second source is malformed, only that candidate fails.
        source.write_text("private-document-canary malformed JSON", encoding="utf-8")
        bad = client.post(
            "/knowledge/corpus/build",
            json={
                "expectedSourceChecksum": sha256(source.read_bytes()).hexdigest(),
                "window": 4,
                "stride": 3,
            },
        )
        assert bad.status_code == 202
        failed_location = bad.headers["Location"]
        failed = terminal_response(client, failed_location)
        assert failed.json()["failureCode"] == "CORPUS_PROCESS_FAILED"
        assert "private-document-canary" not in failed.text
        record_property("failed", failed.text)
    # Then a separate server with writes disabled can still read both terminal records.
    with corpus_api(tmp_path, enabled=False) as restarted:
        read_success = restarted.get(location)
        read_failure = restarted.get(failed_location)
        assert read_success.json() == succeeded.json()
        assert read_failure.json() == failed.json()
        record_property("restartedSuccess", read_success.text)
        record_property("restartedFailure", read_failure.text)
    assert active_path.read_bytes() == active
    assert not (tmp_path / "artifacts").exists()

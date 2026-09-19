"""Owned localhost processes and synthetic wire fixtures for rebuild HTTP tests."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import socket
import subprocess
import sys
from threading import Event, Thread
from time import monotonic
from typing import Final

import anyio
import httpx2
from pydantic import BaseModel, ConfigDict

from app.config import Settings
from app.embedding_artifact import EmbeddingArtifactStore
from app.knowledge_source import load_knowledge_corpus
from tests.knowledge_access_support import write_canary_corpus

SERVICE: Final = Path(__file__).resolve().parents[1]
TOKEN: Final = "synthetic-test-internal-service-token"
WIRE_KEY: Final = "synthetic-wire-only-key"
PRIVATE_DETAIL: Final = "synthetic-upstream-private-diagnostic"
PUBLIC_RESPONSE_FIELDS: Final = frozenset({
    "taskId", "status", "totalChunks", "completedChunks", "estimatedEmbeddingCalls",
    "maxEmbeddingCalls", "embeddingCalls", "artifactId", "corpusChecksum", "traceId",
    "startedAt", "updatedAt", "finishedAt", "elapsedSeconds", "estimatedDurationSeconds",
    "failureCode", "code",
})


def record_http_response(
    record_property: Callable[[str, str], None], name: str, response: httpx2.Response,
) -> None:
    record_property(name, json.dumps({
        "statusCode": response.status_code,
        "body": {key: value for key, value in response.json().items()
                 if key in PUBLIC_RESPONSE_FIELDS},
        "location": response.headers.get("Location"),
    }))


class EmbeddingRequest(BaseModel):
    model_config = ConfigDict(frozen=True)
    model: str
    input: list[str]


@dataclass(slots=True)  # noqa: MUTABLE_OK
class WireProvider:
    """Accumulates actual HTTP requests and controls their completion using events."""

    failure: bool
    entered: Event = field(default_factory=Event)
    release: Event = field(default_factory=Event)
    calls: list[EmbeddingRequest] = field(default_factory=list)
    authorizations: list[str | None] = field(default_factory=list)
    base_url: str = ""


@contextmanager
def embedding_server(*, failure: bool = False) -> Iterator[WireProvider]:
    provider = WireProvider(failure)

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            request = EmbeddingRequest.model_validate_json(
                self.rfile.read(int(self.headers["Content-Length"]))
            )
            provider.calls.append(request)
            provider.authorizations.append(self.headers.get("Authorization"))
            provider.entered.set()
            assert self.path == "/v1/embeddings"
            assert provider.release.wait(20), "Test did not release the provider"
            status = 500 if provider.failure else 200
            body = (
                {"error": {"message": f"{PRIVATE_DETAIL} {WIRE_KEY}", "type": "server_error"}}
                if provider.failure
                else {
                    "object": "list", "model": request.model,
                    "data": [{"object": "embedding", "index": index, "embedding": [1.0, 0.0]}
                             for index in range(len(request.input))],
                    "usage": {"prompt_tokens": len(request.input), "total_tokens": len(request.input)},
                }
            )
            encoded = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, format: str, *args: str) -> None:
            return

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        provider.base_url = f"http://127.0.0.1:{server.server_port}/v1"
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield provider
        finally:
            provider.release.set()
            server.shutdown()
            thread.join(timeout=5)
            assert not thread.is_alive()


class SeedEmbeddings:
    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]

    async def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0]


@dataclass(frozen=True, slots=True)
class IndexFixture:
    directory: Path
    corpus: Path
    root: Path
    checksum: str
    active_id: str
    corpus_bytes: bytes
    pointer_bytes: bytes


def seeded_index(directory: Path, provider: WireProvider) -> IndexFixture:
    corpus = directory / "corpus.json"
    root = directory / "artifacts"
    checksum = write_canary_corpus(corpus)
    settings = Settings(
        ai_mode="mock", knowledge_path=corpus, embedding_artifact_root=root,
        openai_embedding_model="synthetic-embedding-model",
        openai_embedding_base_url=provider.base_url, embedding_vector_dimension=2,
        embedding_chunking_version="prior-slicing", _env_file=None,
    )
    store = EmbeddingArtifactStore(settings, load_knowledge_corpus(corpus))
    manifest = anyio.run(store.build, SeedEmbeddings())
    store.activate(manifest.artifact_id)
    return IndexFixture(directory, corpus, root, checksum, manifest.artifact_id,
                        corpus.read_bytes(), (root / "active.json").read_bytes())


@contextmanager
def running_api(
    fixture: IndexFixture, provider: WireProvider, *, enabled: bool = True,
) -> Iterator[httpx2.Client]:
    """An allowlisted environment plus fresh cwd prevents loading developer credentials."""
    environment = {
        "PYTHONPATH": str(SERVICE), "PYTHONUNBUFFERED": "1", "AI_MODE": "mock",
        "SUPPORT_COPILOT_INTERNAL_SERVICE_TOKEN": TOKEN,
        "KNOWLEDGE_PATH": str(fixture.corpus), "EMBEDDING_ARTIFACT_ROOT": str(fixture.root),
        "OPENAI_EMBEDDING_BASE_URL": provider.base_url,
        "OPENAI_BASE_URL": provider.base_url, "OPENAI_API_KEY": WIRE_KEY,
        "OPENAI_EMBEDDING_API_KEY": WIRE_KEY,
        "OPENAI_EMBEDDING_MODEL": "synthetic-embedding-model",
        "EMBEDDING_VECTOR_DIMENSION": "2", "OPENAI_TIMEOUT_SECONDS": "15",
        "OPENAI_MAX_RETRIES": "0", "EMBEDDING_CHUNKING_VERSION": "rebuilt-slicing",
        "KNOWLEDGE_INDEX_MUTATION_ENABLED": str(enabled).lower(),
    }
    with socket.socket() as listener, (fixture.directory / "uvicorn.log").open("a+") as log:
        listener.bind(("127.0.0.1", 0))
        listener.listen(128)
        address = f"http://127.0.0.1:{listener.getsockname()[1]}"
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--fd", str(listener.fileno()),
             "--no-access-log", "--log-level", "warning"],
            cwd=fixture.directory, env=environment, pass_fds=(listener.fileno(),),
            stdout=log, stderr=subprocess.STDOUT,
        )
        limits = httpx2.Limits(max_connections=8, max_keepalive_connections=4, keepalive_expiry=5)
        transport = httpx2.HTTPTransport(
            retries=0, limits=limits, trust_env=False,
            socket_options=[(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)],
        )
        try:
            with httpx2.Client(
                base_url=address, transport=transport, trust_env=False,
                timeout=httpx2.Timeout(connect=1, read=2, write=2, pool=2),
                headers={"X-Internal-Service-Token": TOKEN},
            ) as client:
                deadline = monotonic() + 20
                while monotonic() < deadline:
                    assert process.poll() is None, (fixture.directory / "uvicorn.log").read_text()
                    try:
                        if client.get("/health/live").status_code == 200:
                            break
                    except (httpx2.ConnectError, httpx2.ReadTimeout):
                        Event().wait(0.02)
                else:
                    raise AssertionError("Uvicorn did not become healthy")
                yield client
        finally:
            provider.release.set()
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def terminal_response(client: httpx2.Client, location: str) -> httpx2.Response:
    deadline = monotonic() + 15
    while monotonic() < deadline:
        response = client.get(location)
        assert response.status_code == 200, response.text
        if response.json()["status"] in {"SUCCEEDED", "FAILED"}:
            return response
        Event().wait(0.02)
    raise AssertionError("Rebuild did not reach a terminal status")

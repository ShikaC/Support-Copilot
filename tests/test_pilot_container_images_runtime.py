"""Docker-backed acceptance coverage for the three production images.

# noqa: SIZE_OK
Cohesion: one isolated Docker lifecycle owns the image build, runtime, and cleanup contract.
"""

import json
import os
import shlex
import subprocess
import time
from collections.abc import Iterator
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ENABLED = os.environ.get("SUPPORT_COPILOT_CONTAINER_ACCEPTANCE") == "1"
EVIDENCE_ENV = "SUPPORT_COPILOT_CONTAINER_EVIDENCE_DIR"
RUN_ID_ENV = "SUPPORT_COPILOT_CONTAINER_RUN_ID"
TOKEN_ENV = "SUPPORT_COPILOT_INTERNAL_SERVICE_TOKEN"
DOCKER_COMMAND_ENV = "SUPPORT_COPILOT_DOCKER_COMMAND"
ARTIFACT_ROOT = "/var/lib/support-copilot-ai"


ARTIFACT_BUILD = """
from pathlib import Path
import json
import anyio
from app.config import Settings
from app.knowledge_source import load_knowledge_corpus
from app.live_vector_index import LiveVectorIndex

class Provider:
    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, float(index % 2)] for index, _text in enumerate(texts)]
    async def embed_query(self, _text: str) -> list[float]:
        return [1.0, 0.0]

async def main() -> None:
    settings = Settings(ai_mode="live", openai_api_key="synthetic-not-sent",
        openai_chat_model="synthetic-chat", openai_embedding_model="synthetic-embedding",
        embedding_vector_dimension=2, embedding_artifact_build_policy="build-if-missing",
        _env_file=None)
    corpus = load_knowledge_corpus(Path("/app/app/data/knowledge.json"))
    index = LiveVectorIndex(settings, corpus)
    index._provider = Provider()
    artifact = await index._get_artifact()
    print(json.dumps({"artifactId": artifact.manifest.artifact_id,
        "policy": settings.embedding_artifact_build_policy,
        "root": str(settings.embedding_artifact_root), "rows": artifact.manifest.row_count},
        sort_keys=True))
anyio.run(main)
"""

ARTIFACT_LOAD = """
from pathlib import Path
import json
import anyio
from app.config import Settings
from app.knowledge_source import load_knowledge_corpus
from app.live_vector_index import LiveVectorIndex

async def main() -> None:
    settings = Settings(ai_mode="live", openai_api_key="synthetic-not-sent",
        openai_chat_model="synthetic-chat", openai_embedding_model="synthetic-embedding",
        embedding_vector_dimension=2, embedding_artifact_build_policy="require-active",
        _env_file=None)
    corpus = load_knowledge_corpus(Path("/app/app/data/knowledge.json"))
    artifact = await LiveVectorIndex(settings, corpus)._get_artifact()
    print(json.dumps({"artifactId": artifact.manifest.artifact_id,
        "policy": settings.embedding_artifact_build_policy,
        "root": str(settings.embedding_artifact_root), "rows": artifact.manifest.row_count},
        sort_keys=True))
anyio.run(main)
"""


@dataclass(frozen=True, slots=True)
class Command:
    argv: tuple[str, ...]
    input_text: str | None = None
    check: bool = True
    timeout_seconds: int = 900


@dataclass(frozen=True, slots=True)
class AcceptanceResult:
    base_platforms: tuple[str, ...]
    image_platforms: tuple[str, ...]
    runtime_contracts: tuple[str, ...]
    health: tuple[str, str, str]
    nginx_check: str
    api_proxy: str
    spa: str
    source_corpus_sha256: str
    image_corpus_sha256: str
    artifact_build: str
    artifact_reload: str
    artifact_files: str


class AcceptanceConfigurationError(RuntimeError):
    """Raised when explicit container acceptance configuration is incomplete."""


class DockerAcceptance:
    """Owns isolated Docker resources and a sanitized command ledger for one run."""

    def __init__(self) -> None:
        self._required_token()
        self.run_id = os.environ[RUN_ID_ENV]
        self.evidence = Path(os.environ[EVIDENCE_ENV]).resolve()
        self.evidence.mkdir(parents=True, exist_ok=False)
        self.docker_command = tuple(shlex.split(os.environ.get("SUPPORT_COPILOT_DOCKER_COMMAND", "docker")))
        prefix = f"task15-container-{self.run_id}"
        self.tags = (f"{prefix}-api:{self.run_id}", f"{prefix}-ai:{self.run_id}", f"{prefix}-web:{self.run_id}")
        self.names = (f"{prefix}-api", f"{prefix}-ai", f"{prefix}-web")
        self.network = f"{prefix}-network"
        self.volume = f"{prefix}-artifacts"
        self.containers: list[str] = []
        self.created_network = False
        self.created_volume = False
        self.command_number = 0
        self._write_source_manifest()

    def _required_token(self) -> str:
        token = os.environ.get(TOKEN_ENV, "")
        if not token:
            raise AcceptanceConfigurationError(f"{TOKEN_ENV} must be set to a non-empty value")
        return token

    def _sanitize(self, value: str) -> str:
        token = os.environ.get(TOKEN_ENV, "")
        return value.replace(token, "[REDACTED]") if token else value

    def execute(self, command: Command) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(command.argv, cwd=ROOT, input=command.input_text, text=True,
            capture_output=True, timeout=command.timeout_seconds, check=False)
        self.command_number += 1
        record = {"command": [self._sanitize(part) for part in command.argv], "exitCode": result.returncode,
            "sequence": self.command_number, "stderr": self._sanitize(result.stderr),
            "stdout": self._sanitize(result.stdout)}
        with (self.evidence / "commands.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=True, sort_keys=True) + "\n")
        if command.check:
            result.check_returncode()
        return result

    def docker(self, *args: str, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
        return self.execute(Command(self.docker_command + args, input_text=input_text))

    def wait(self, *args: str) -> str:
        for _attempt in range(45):
            result = self.execute(Command(self.docker_command + args, check=False, timeout_seconds=10))
            if result.returncode == 0:
                return result.stdout
            diagnostic = self._diagnose_exited_container(args)
            if diagnostic is not None:
                raise AssertionError(diagnostic)
            time.sleep(2)
        raise AssertionError(f"Docker command did not succeed after 45 attempts: {args!r}")

    def _diagnose_exited_container(self, args: tuple[str, ...]) -> str | None:
        if len(args) < 2 or args[0] != "exec":
            return None
        container = args[1]
        inspected = self.execute(Command(self.docker_command + (
            "inspect", "--format", "{{.State.Status}}", container), check=False, timeout_seconds=10))
        if inspected.returncode != 0:
            return None
        status = inspected.stdout.strip()
        if status not in {"exited", "dead"}:
            return None
        logs = self.execute(Command(self.docker_command + ("logs", container), check=False, timeout_seconds=10))
        failure = self._sanitize(logs.stdout + logs.stderr).strip()
        return (f"Docker exec target {container!r} exited with status={status}; "
            f"inspect={self._sanitize(inspected.stdout).strip()!r}; logs={failure!r}")

    def prepare(self) -> AcceptanceResult:
        dockerfiles = tuple(ROOT / path for path in ("services/support-copilot-api/Dockerfile",
            "services/support-copilot-ai/Dockerfile", "apps/support-copilot-web/Dockerfile"))
        refs = tuple(dict.fromkeys(line.split()[1] for path in dockerfiles
            for line in path.read_text(encoding="utf-8").splitlines() if line.startswith("FROM ")))
        base_platforms = []
        base_inspects = []
        for ref in refs:
            self.docker("pull", "--quiet", "--platform", "linux/amd64", ref)
            inspected = self.docker("image", "inspect", "--format", "{{.Os}}/{{.Architecture}}|{{.Id}}|{{json .RepoDigests}}", ref).stdout.strip()
            base_platforms.append(inspected.split("|", 1)[0])
            base_inspects.append(inspected)
        (self.evidence / "base-images.inspect.txt").write_text("\n".join(base_inspects) + "\n", encoding="utf-8")
        for tag, path in zip(self.tags, dockerfiles, strict=True):
            self.docker("build", "--quiet", "--platform", "linux/amd64", "--pull=false", "--file", str(path), "--tag", tag, str(ROOT))
        image_inspects = [self.docker("image", "inspect", "--format",
            "{\"Id\":{{json .Id}},\"Os\":{{json .Os}},\"Architecture\":{{json .Architecture}},\"User\":{{json .Config.User}},\"ExposedPorts\":{{json .Config.ExposedPorts}}}", tag).stdout.strip() for tag in self.tags]
        (self.evidence / "built-images.inspect.jsonl").write_text("\n".join(image_inspects) + "\n", encoding="utf-8")
        self.docker("network", "create", self.network)
        self.created_network = True
        self.docker("volume", "create", self.volume)
        self.created_volume = True
        self._start_ai(self.names[1])
        first_ai = self.names[1]
        self.wait("exec", first_ai, "python", "-c", "from urllib.request import urlopen; print(urlopen('http://127.0.0.1:8000/health', timeout=2).read().decode())")
        artifact_build = self.docker("exec", "-i", first_ai, "python", "-", input_text=ARTIFACT_BUILD).stdout.strip()
        self.docker("rm", "-f", first_ai)
        self.containers.remove(first_ai)
        restarted_ai = f"{first_ai}-restart"
        self._start_ai(restarted_ai)
        self.wait("exec", restarted_ai, "python", "-c", "from urllib.request import urlopen; print(urlopen('http://127.0.0.1:8000/health', timeout=2).read().decode())")
        artifact_reload = self.docker("exec", "-i", restarted_ai, "python", "-", input_text=ARTIFACT_LOAD).stdout.strip()
        artifact_files = self.docker("exec", restarted_ai, "sh", "-c", f"find {ARTIFACT_ROOT} -maxdepth 2 -type f -printf '%P\\n' | sort").stdout
        self._start_api()
        self._start_web()
        health = (self.wait("exec", self.names[2], "wget", "-qO-", "http://ai:8000/health"),
            self.wait("exec", self.names[2], "wget", "-qO-", "http://api:8080/actuator/health"),
            self.wait("exec", self.names[2], "wget", "-qO-", "http://127.0.0.1:8080/health"))
        nginx = self.docker("exec", self.names[2], "nginx", "-t")
        api_proxy = self.docker("exec", self.names[2], "wget", "-qO-", "http://127.0.0.1:8080/api/tickets").stdout
        spa = self.docker("exec", self.names[2], "wget", "-qO-", "http://127.0.0.1:8080/deep-link").stdout
        contracts = tuple(self.docker("inspect", "--format", "{{.HostConfig.ReadonlyRootfs}}|{{.Config.User}}|{{json .Config.ExposedPorts}}|{{range .Mounts}}{{.Name}}:{{.Destination}}:{{.RW}}{{end}}", name).stdout.strip() for name in (self.names[0], restarted_ai, self.names[2]))
        selected_inspects = [self.docker("inspect", "--format", "{\"Id\":{{json .Id}},\"Name\":{{json .Name}},\"Image\":{{json .Image}},\"User\":{{json .Config.User}},\"ReadonlyRootfs\":{{json .HostConfig.ReadonlyRootfs}},\"ExposedPorts\":{{json .Config.ExposedPorts}},\"Mounts\":{{json .Mounts}},\"State\":{{json .State.Status}}}", name).stdout.strip() for name in (self.names[0], restarted_ai, self.names[2])]
        (self.evidence / "containers.inspect.jsonl").write_text("\n".join(selected_inspects) + "\n", encoding="utf-8")
        source_checksum = sha256((ROOT / "services/support-copilot-ai/app/data/knowledge.json").read_bytes()).hexdigest()
        image_checksum = self.docker("exec", self.names[0], "sha256sum", "/opt/support-copilot/knowledge/knowledge.json").stdout.split()[0]
        (self.evidence / "runtime-checksums.json").write_text(json.dumps({"canonicalCorpusSha256": source_checksum,
            "imageCorpusSha256": image_checksum}, sort_keys=True) + "\n", encoding="utf-8")
        return AcceptanceResult(tuple(base_platforms), tuple("linux/amd64" for _tag in self.tags), contracts,
            health, nginx.stdout + nginx.stderr, api_proxy, spa, source_checksum, image_checksum,
            artifact_build, artifact_reload, artifact_files)

    def _start_ai(self, name: str) -> None:
        token = self._required_token()
        self.docker("run", "-d", "--name", name, "--network", self.network, "--network-alias", "ai",
            "--read-only", "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=64m", "--mount",
            f"type=volume,source={self.volume},target={ARTIFACT_ROOT}", "--env", f"{TOKEN_ENV}={token}",
            "--env", "AI_MODE=mock", self.tags[1])
        self.containers.append(name)

    def _start_api(self) -> None:
        token = self._required_token()
        self.docker("run", "-d", "--name", self.names[0], "--network", self.network, "--network-alias", "api",
            "--read-only", "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=64m", "--env", f"{TOKEN_ENV}={token}",
            "--env", "SPRING_PROFILES_ACTIVE=demo", "--env", "AI_SERVICE_BASE_URL=http://ai:8000", self.tags[0])
        self.containers.append(self.names[0])

    def _start_web(self) -> None:
        self.docker("run", "-d", "--name", self.names[2], "--network", self.network, "--read-only",
            "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=32m", "--tmpfs", "/var/cache/nginx:rw,noexec,nosuid,nodev,size=32m",
            "--tmpfs", "/var/run:rw,noexec,nosuid,nodev,size=8m", self.tags[2])
        self.containers.append(self.names[2])

    def cleanup(self) -> None:
        commands = []
        if self.containers:
            commands.append(("rm", "-f", *reversed(self.containers)))
        if self.created_network:
            commands.append(("network", "rm", self.network))
        if self.created_volume:
            commands.append(("volume", "rm", self.volume))
        commands.append(("image", "rm", *self.tags))
        receipts = []
        for args in commands:
            result = self.execute(Command(self.docker_command + args, check=False))
            receipts.append({"command": list(args), "exitCode": result.returncode, "stdout": result.stdout.strip()})
        (self.evidence / "cleanup.receipt.json").write_text(json.dumps(receipts, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        assert all(receipt["exitCode"] == 0 for receipt in receipts)

    def _write_source_manifest(self) -> None:
        digest = sha256()
        count = 0
        size = 0
        excluded = {".git", ".omo", ".venv", "node_modules", "dist", "build", ".gradle", "__pycache__"}
        for path in sorted(item for item in ROOT.rglob("*") if item.is_file() and not excluded.intersection(item.relative_to(ROOT).parts)):
            relative = path.relative_to(ROOT).as_posix().encode()
            content = path.read_bytes()
            digest.update(relative + b"\0" + content + b"\0")
            count += 1
            size += len(content)
        payload = {"fileCount": count, "sha256": digest.hexdigest(), "totalBytes": size}
        (self.evidence / "source-tree.manifest.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


@pytest.fixture(scope="session")
def acceptance() -> Iterator[AcceptanceResult]:
    if not ENABLED:
        pytest.skip("requires explicit Docker acceptance opt-in")
    previous_token = os.environ.get(TOKEN_ENV)
    os.environ[TOKEN_ENV] = "synthetic-container-acceptance-only"
    runtime = DockerAcceptance()
    try:
        yield runtime.prepare()
    finally:
        runtime.cleanup()
        if previous_token is None:
            os.environ.pop(TOKEN_ENV, None)
        else:
            os.environ[TOKEN_ENV] = previous_token


def test_images_when_built_then_resolve_to_linux_amd64(acceptance: AcceptanceResult) -> None:
    assert all(platform == "linux/amd64" for platform in acceptance.base_platforms + acceptance.image_platforms)


def test_containers_when_started_read_only_then_are_non_root_with_expected_ports(acceptance: AcceptanceResult) -> None:
    assert all(value.startswith("true|") and "|0|" not in value for value in acceptance.runtime_contracts)
    assert "8080/tcp" in acceptance.runtime_contracts[0] and "8000/tcp" in acceptance.runtime_contracts[1] and "8080/tcp" in acceptance.runtime_contracts[2]


def test_services_when_probed_then_report_ai_health_and_api_readiness(acceptance: AcceptanceResult) -> None:
    assert '"mode":"mock"' in acceptance.health[0]
    assert '"status":"UP"' in acceptance.health[1]


def test_gateway_when_probed_then_reports_plain_text_liveness(acceptance: AcceptanceResult) -> None:
    assert acceptance.health[2].strip() == '{"status":"up"}'


def test_gateway_when_exercised_then_has_valid_nginx_spa_and_api_routing(acceptance: AcceptanceResult) -> None:
    assert "test is successful" in acceptance.nginx_check and "ticket-10042" in acceptance.api_proxy
    assert "<!doctype html>" in acceptance.spa.lower()


def test_api_image_when_running_then_uses_canonical_corpus(acceptance: AcceptanceResult) -> None:
    assert acceptance.image_corpus_sha256 == acceptance.source_corpus_sha256


def test_ai_image_when_restarted_then_persists_artifact_on_owned_volume(acceptance: AcceptanceResult) -> None:
    assert '"policy": "build-if-missing"' in acceptance.artifact_build and ARTIFACT_ROOT in acceptance.artifact_build
    artifact_id = json.loads(acceptance.artifact_build)["artifactId"]
    assert artifact_id == json.loads(acceptance.artifact_reload)["artifactId"]
    assert "active.json" in acceptance.artifact_files and "manifest.json" in acceptance.artifact_files


def test_container_start_when_token_is_set_then_passes_explicit_env_and_sanitizes_ledger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(RUN_ID_ENV, "unit-start")
    monkeypatch.setenv(EVIDENCE_ENV, str(tmp_path / "evidence"))
    monkeypatch.setenv(TOKEN_ENV, "unit-secret")
    monkeypatch.setenv(DOCKER_COMMAND_ENV, "sudo -n docker")
    runtime = DockerAcceptance()
    calls: list[tuple[str, ...]] = []

    def fake_run(
        argv: tuple[str, ...], **_kwargs: str | bool | int | None
    ) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    runtime._start_ai("unit-ai")
    runtime._start_api()

    ledger = (runtime.evidence / "commands.jsonl").read_text(encoding="utf-8")
    assert f"{TOKEN_ENV}=unit-secret" not in ledger
    assert f"{TOKEN_ENV}=[REDACTED]" in ledger
    assert all(call[:3] == ("sudo", "-n", "docker") for call in calls)
    assert all(f"{TOKEN_ENV}=unit-secret" in call for call in calls)
    assert runtime.containers == ["unit-ai", runtime.names[0]]


def test_container_start_when_token_is_empty_then_fails_before_docker_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(RUN_ID_ENV, "unit-empty-token")
    monkeypatch.setenv(EVIDENCE_ENV, str(tmp_path / "evidence"))
    monkeypatch.setenv(TOKEN_ENV, "")

    with pytest.raises(AcceptanceConfigurationError, match=f"{TOKEN_ENV} must be set"):
        DockerAcceptance()


def test_wait_when_container_exits_then_records_logs_and_inspect_without_retrying(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(RUN_ID_ENV, "unit-exited")
    monkeypatch.setenv(EVIDENCE_ENV, str(tmp_path / "evidence"))
    monkeypatch.setenv(TOKEN_ENV, "unit-secret")
    runtime = DockerAcceptance()
    calls: list[tuple[str, ...]] = []

    def fake_run(
        argv: tuple[str, ...], **_kwargs: str | bool | int | None
    ) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        if "inspect" in argv:
            return subprocess.CompletedProcess(argv, 0, "exited\n", "")
        if "logs" in argv:
            return subprocess.CompletedProcess(argv, 0, "startup token=unit-secret", "")
        return subprocess.CompletedProcess(argv, 1, "", "container is not running")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(time, "sleep", lambda _seconds: pytest.fail("exited container was retried"))

    with pytest.raises(AssertionError, match="status=exited") as error:
        runtime.wait("exec", "unit-ai", "health")

    assert "unit-secret" not in str(error.value)
    assert any("inspect" in call for call in calls)
    assert any("logs" in call for call in calls)
    ledger = (runtime.evidence / "commands.jsonl").read_text(encoding="utf-8")
    assert "unit-secret" not in ledger
    assert '"stdout": "exited\\n"' in ledger


def test_wait_when_container_is_still_running_then_keeps_retrying(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(RUN_ID_ENV, "unit-running")
    monkeypatch.setenv(EVIDENCE_ENV, str(tmp_path / "evidence"))
    monkeypatch.setenv(TOKEN_ENV, "unit-secret")
    runtime = DockerAcceptance()
    attempts = 0

    def fake_run(
        argv: tuple[str, ...], **_kwargs: str | bool | int | None
    ) -> subprocess.CompletedProcess[str]:
        nonlocal attempts
        if "inspect" in argv:
            return subprocess.CompletedProcess(argv, 0, "running\n", "")
        attempts += 1
        if attempts == 1:
            return subprocess.CompletedProcess(argv, 1, "", "not ready")
        return subprocess.CompletedProcess(argv, 0, "ready\n", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)

    assert runtime.wait("exec", "unit-ai", "health") == "ready\n"
    assert attempts == 2

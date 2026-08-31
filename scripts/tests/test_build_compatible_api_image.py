"""Behavioral contract for the compatible API image publication transaction.

# noqa: SIZE_OK - One cohesive CLI contract owns the fake Docker/Git flows and required failure races.
"""

from __future__ import annotations

import hashlib
import json
import os
import select
import signal
import subprocess
from pathlib import Path
from typing import Final

import pytest
from pydantic import TypeAdapter
from typing_extensions import NotRequired, TypedDict


class _Manifest(TypedDict):
    schema_version: int
    revision: str
    image_ref: str
    image_id: str
    source_archive_sha256: str
    packaging_dockerfile_sha256: str
    platform: str
    command_exit: dict[str, int]
    hash_binding: dict[str, str]


class _ImageMetadata(TypedDict):
    id: str
    os: str
    architecture: str
    revision: str
    packaging: str


class _TagObservation(TypedDict):
    manifest: bool
    complete: bool


class _DockerState(TypedDict):
    tags: dict[str, str]
    images: dict[str, _ImageMetadata]
    image_ls_counts: dict[str, int]
    caller_tag_observations: NotRequired[list[_TagObservation]]


ROOT: Final = Path(__file__).resolve().parents[2]
WORKER: Final = ROOT / "scripts" / "build-compatible-api-image.sh"
CALLER_IMAGE: Final = "registry.test:5000/pilot-api:compat"
IMAGE_ID: Final = "sha256:" + "a" * 64
OLD_IMAGE_ID: Final = "sha256:" + "9" * 64
RETARGETED_IMAGE_ID: Final = "sha256:" + "c" * 64
ARCHIVE_PATHS: Final = (
    "services/support-copilot-api",
    "services/support-copilot-ai/app/data/knowledge.json",
)
SOURCE_PROBE: Final = "services/support-copilot-api/settings.gradle.kts"
DOCKER_CALL_ADAPTER: Final = TypeAdapter(list[str])
DOCKER_STATE_ADAPTER: Final = TypeAdapter(_DockerState)
MANIFEST_ADAPTER: Final = TypeAdapter(_Manifest)
PENDING_ADAPTER: Final = TypeAdapter(dict[str, object])


def _ancestor_revision() -> str:
    result = subprocess.run(
        ["git", "rev-list", "--parents", "-n", "1", "HEAD"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    parents = result.stdout.strip().split()[1:]
    if not parents:
        pytest.skip("compatible-image tests require at least one fetched ancestor commit")
    return parents[0]


def _caller_image(tmp_path: Path) -> str:
    namespace = hashlib.sha256(os.fsencode(tmp_path)).hexdigest()[:16]
    return f"registry.test:5000/pilot-api:compat-{namespace}"


def _write_fake_timeout(path: Path) -> None:
    _ = path.write_text(
        "#!/usr/bin/env bash\nprintf '%s\\n' \"$*\" >>\"$FAKE_TIMEOUT_LOG\"\nseconds=\"$1\"\nshift\n[[ $seconds =~ ^[1-9][0-9]*$ ]] || exit 98\nexec \"$@\"\n",
        encoding="utf-8",
    )
    path.chmod(0o755)


def _write_fake_sudo(path: Path) -> None:
    _ = path.write_text(
        "#!/usr/bin/env bash\nprintf '%s\\n' \"$*\" >>\"$FAKE_SUDO_LOG\"\n[[ $1 == -n && $2 == -- ]] || exit 96\nshift 2\nexec \"$@\"\n",
        encoding="utf-8",
    )
    path.chmod(0o755)


def _write_fake_python(path: Path) -> None:
    _ = path.write_text(
        """#!/usr/bin/env python3
import os
import pathlib
import re
import signal
import subprocess
import sys

real_python = os.environ["REAL_PYTHON"]
fault = os.environ.get("FAKE_PYTHON_FAULT")
marker = pathlib.Path(os.environ.get("FAKE_PYTHON_FAULT_MARKER", "/nonexistent"))
arguments = sys.argv[1:]
kill_stage = os.environ.get("FAKE_PYTHON_KILL_STAGE")
if (
    kill_stage == "before_manifest_payload"
    and len(arguments) == 8
    and arguments[0] == "-"
    and pathlib.Path(arguments[1]).name == "manifest.pending"
    and re.fullmatch(r"sha256:[a-f0-9]{64}", arguments[4])
):
    command_substitution_pid = os.getppid()
    builder_pid = int(
        subprocess.check_output(
            ["ps", "-o", "ppid=", "-p", str(command_substitution_pid)],
            text=True,
        ).strip()
    )
    os.closerange(3, 256)
    os.kill(builder_pid, signal.SIGKILL)
    raise SystemExit(0)
if fault is None or marker.exists() or len(arguments) != 10 or arguments[0] != "-":
    os.execv(real_python, [real_python, *arguments])

candidate = arguments[-2]
if pathlib.Path(candidate).is_absolute() and pathlib.Path(candidate).is_file():
    stage = "manifest"
elif re.fullmatch(r"[a-f0-9]{64}", candidate):
    stage = "complete"
else:
    os.execv(real_python, [real_python, *arguments])
if not fault.startswith(stage + "_"):
    os.execv(real_python, [real_python, *arguments])

real_fsync = os.fsync
fsync_calls = 0

def injected_fsync(descriptor):
    global fsync_calls
    real_fsync(descriptor)
    fsync_calls += 1
    if fault == stage + "_after_temp_fsync" and fsync_calls == 1:
        marker.write_text("used", encoding="utf-8")
        raise OSError("injected evidence fsync failure")

real_rename = os.rename

def injected_rename(*rename_args, **rename_kwargs):
    real_rename(*rename_args, **rename_kwargs)
    if fault == stage + "_after_rename":
        marker.write_text("used", encoding="utf-8")
        raise OSError("injected evidence rename failure")

os.fsync = injected_fsync
os.rename = injected_rename
sys.argv = arguments
source = sys.stdin.read()
exec(compile(source, "<stdin>", "exec"), {"__name__": "__main__"})
""",
        encoding="utf-8",
    )
    path.chmod(0o755)


def _write_fake_docker(path: Path) -> None:
    _ = path.write_text(
        """#!/usr/bin/env python3
import json
import os
import pathlib
import signal
import sys

args = sys.argv[1:]
state_path = pathlib.Path(os.environ["FAKE_DOCKER_STATE"])
state = json.loads(state_path.read_text(encoding="utf-8"))
with pathlib.Path(os.environ["FAKE_DOCKER_LOG"]).open("a", encoding="utf-8") as stream:
    stream.write(json.dumps(args) + "\\n")

def save():
    temporary = state_path.with_name(f"{state_path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(state), encoding="utf-8")
    temporary.replace(state_path)

def kill_builder():
    parent_pid = os.getppid()
    os.closerange(3, 256)
    os.kill(parent_pid, signal.SIGKILL)
    raise SystemExit(0)

if args[:2] == ["image", "ls"]:
    image_ref = args[-1]
    counts = state.setdefault("image_ls_counts", {})
    counts[image_ref] = counts.get(image_ref, 0) + 1
    mode = os.environ.get("FAKE_DOCKER_MODE", "success")
    if (
        mode == "hold-first-preflight"
        and image_ref == os.environ["FAKE_CALLER_IMAGE"]
        and counts[image_ref] == 1
    ):
        save()
        with pathlib.Path(os.environ["FAKE_READY_FIFO"]).open("w", encoding="utf-8") as ready:
            ready.write("ready\\n")
        with pathlib.Path(os.environ["FAKE_RELEASE_FIFO"]).open("r", encoding="utf-8") as release:
            release.read(1)
    if (
        mode == "final-caller-collision"
        and image_ref == os.environ["FAKE_CALLER_IMAGE"]
        and counts[image_ref] == 2
    ):
        state["tags"][image_ref] = os.environ["FAKE_OLD_IMAGE_ID"]
    if (
        mode == "build-failure-no-tag-cleanup-query-failure"
        and image_ref.startswith("support-copilot-compatible-api-temp:")
        and counts[image_ref] == 2
    ):
        save()
        raise SystemExit(74)
    save()
    image_id = state["tags"].get(image_ref)
    if image_id:
        print(image_id)
    raise SystemExit(0)

if args and args[0] == "build":
    tag = args[args.index("--tag") + 1]
    context = pathlib.Path(args[-1])
    file_indexes = [index for index, value in enumerate(args) if value == "--file"]
    if len(file_indexes) != 1 or file_indexes[0] + 1 >= len(args):
        raise SystemExit(86)
    dockerfile = pathlib.Path(args[file_indexes[0] + 1])
    if dockerfile != context / "services/support-copilot-api/Dockerfile":
        raise SystemExit(86)
    pathlib.Path(os.environ["FAKE_CONTEXT_RECORD"]).write_text(str(context), encoding="utf-8")
    pathlib.Path(os.environ["FAKE_SOURCE_CAPTURE"]).write_bytes((context / os.environ["FAKE_SOURCE_PROBE"]).read_bytes())
    pathlib.Path(os.environ["FAKE_DOCKERFILE_CAPTURE"]).write_bytes(dockerfile.read_bytes())
    knowledge = context / "services/support-copilot-ai/app/data/knowledge.json"
    if tag == os.environ["FAKE_CALLER_IMAGE"] or (context / ".git").exists() or not knowledge.is_file():
        raise SystemExit(81)
    mode = os.environ.get("FAKE_DOCKER_MODE", "success")
    metadata = {
        "id": os.environ["FAKE_IMAGE_ID"],
        "os": "windows" if mode == "wrong-os" else "linux",
        "architecture": "arm64" if mode == "wrong-arch" else "amd64",
        "revision": os.environ["FAKE_EXPECTED_REVISION"],
        "packaging": "b" * 64 if mode == "label-mismatch" else os.environ["FAKE_EXPECTED_PACKAGING"],
    }
    if mode in {"build-failure-no-tag", "build-failure-no-tag-cleanup-query-failure"}:
        raise SystemExit(37)
    state["images"][metadata["id"]] = metadata
    state["tags"][tag] = metadata["id"]
    save()
    if mode == "replace-evidence":
        evidence = pathlib.Path(os.environ["FAKE_EVIDENCE_PATH"])
        evidence.rename(evidence.with_name(evidence.name + "-owned"))
        evidence.mkdir(mode=0o700)
        (evidence / "sentinel").write_text("replacement", encoding="utf-8")
    if mode == "replace-temp":
        root = context.parent
        root.rename(root.with_name(root.name + "-owned"))
        root.mkdir(mode=0o700)
        (root / "sentinel").write_text("replacement", encoding="utf-8")
    if mode == "inject-evidence-file":
        evidence = pathlib.Path(os.environ["FAKE_EVIDENCE_PATH"])
        (evidence / "sentinel").write_text("injected", encoding="utf-8")
    if mode in {
        "build-failure",
        "replace-evidence",
        "replace-temp",
        "inject-evidence-file",
    }:
        raise SystemExit(37)
    raise SystemExit(0)

if args[:2] == ["image", "inspect"]:
    image_id = state["tags"].get(args[-1], args[-1] if args[-1] in state["images"] else None)
    if image_id is None:
        raise SystemExit(1)
    value = state["images"][image_id]
    print("|".join([value["id"], value["os"], value["architecture"], value["revision"], value["packaging"]]))
    raise SystemExit(0)

if args[:2] == ["image", "tag"]:
    image_id, tag = args[2], args[3]
    if image_id not in state["images"]:
        raise SystemExit(82)
    if tag == os.environ["FAKE_CALLER_IMAGE"]:
        evidence = pathlib.Path(os.environ["FAKE_EVIDENCE_PATH"])
        observation = {
            "manifest": (evidence / "manifest.json").is_file(),
            "complete": (evidence / "COMPLETE").exists(),
        }
        state.setdefault("caller_tag_observations", []).append(observation)
        save()
        if observation != {"manifest": True, "complete": False}:
            raise SystemExit(83)
    mode = os.environ.get("FAKE_DOCKER_MODE")
    if mode == "kill-before-caller-tag" and tag == os.environ["FAKE_CALLER_IMAGE"]:
        kill_builder()
    state["tags"][tag] = image_id
    if mode == "replace-caller-after-tag" and tag == os.environ["FAKE_CALLER_IMAGE"]:
        state["tags"][tag] = os.environ["FAKE_OLD_IMAGE_ID"]
    save()
    if mode == "kill-after-caller-tag" and tag == os.environ["FAKE_CALLER_IMAGE"]:
        kill_builder()
    raise SystemExit(0)

if args[:2] == ["image", "rm"]:
    state["tags"].pop(args[2], None)
    save()
    raise SystemExit(0)

raise SystemExit(97)
""",
        encoding="utf-8",
    )
    path.chmod(0o755)


def _write_unsafe_archive_git(path: Path) -> None:
    _ = path.write_text(
        """#!/usr/bin/env python3
import io
import os
import sys
import tarfile

if "archive" not in sys.argv:
    real_git = os.environ["REAL_GIT"]
    os.execv(real_git, [real_git, *sys.argv[1:]])
with tarfile.open(fileobj=sys.stdout.buffer, mode="w|") as archive:
    payload = b"settings"
    regular = tarfile.TarInfo("services/support-copilot-api/settings.gradle.kts")
    regular.size = len(payload)
    archive.addfile(regular, io.BytesIO(payload))
    unsafe = tarfile.TarInfo("services/support-copilot-api/src-link")
    unsafe.type = tarfile.SYMTYPE
    unsafe.linkname = "/tmp/outside"
    archive.addfile(unsafe)
""",
        encoding="utf-8",
    )
    path.chmod(0o755)


def _prepare_environment(
    tmp_path: Path,
    *,
    revision: str | None = None,
    mode: str = "success",
    preexisting_caller: bool = False,
    git_bin: Path | None = None,
    use_sudo: bool = False,
) -> tuple[str, dict[str, str]]:
    selected_revision = _ancestor_revision() if revision is None else revision
    caller_image = _caller_image(tmp_path)
    resolved = subprocess.check_output(
        ["git", "rev-parse", f"{selected_revision}^{{commit}}"], cwd=ROOT, text=True
    ).strip()
    fake_docker = tmp_path / "docker"
    fake_timeout = tmp_path / "timeout"
    fake_sudo = tmp_path / "sudo"
    fake_python = tmp_path / "python"
    state_path = tmp_path / "docker-state.json"
    _write_fake_docker(fake_docker)
    _write_fake_timeout(fake_timeout)
    _write_fake_sudo(fake_sudo)
    _write_fake_python(fake_python)
    old_metadata = {
        "id": OLD_IMAGE_ID,
        "os": "linux",
        "architecture": "amd64",
        "revision": "old",
        "packaging": "8" * 64,
    }
    state = {
        "tags": {caller_image: OLD_IMAGE_ID} if preexisting_caller else {},
        "images": {OLD_IMAGE_ID: old_metadata},
        "image_ls_counts": {},
    }
    _ = state_path.write_text(json.dumps(state), encoding="utf-8")
    environment = os.environ | {
        "DOCKER_BIN": str(fake_docker),
        "TIMEOUT_BIN": str(fake_timeout),
        "PYTHON_BIN": str(fake_python),
        "REAL_PYTHON": str(ROOT / "services/support-copilot-ai/.venv/bin/python"),
        "FAKE_DOCKER_LOG": str(tmp_path / "docker.log"),
        "FAKE_TIMEOUT_LOG": str(tmp_path / "timeout.log"),
        "FAKE_SUDO_LOG": str(tmp_path / "sudo.log"),
        "FAKE_DOCKER_STATE": str(state_path),
        "FAKE_CONTEXT_RECORD": str(tmp_path / "context-path"),
        "FAKE_SOURCE_CAPTURE": str(tmp_path / "source-capture"),
        "FAKE_DOCKERFILE_CAPTURE": str(tmp_path / "dockerfile-capture"),
        "FAKE_SOURCE_PROBE": SOURCE_PROBE,
        "FAKE_DOCKER_MODE": mode,
        "FAKE_CALLER_IMAGE": caller_image,
        "FAKE_IMAGE_ID": IMAGE_ID,
        "FAKE_OLD_IMAGE_ID": OLD_IMAGE_ID,
        "FAKE_EXPECTED_REVISION": resolved,
        "FAKE_EXPECTED_PACKAGING": hashlib.sha256(
            (ROOT / "services/support-copilot-api/Dockerfile").read_bytes()
        ).hexdigest(),
        "TMPDIR": str(tmp_path),
        "PATH": str(tmp_path) + os.pathsep + os.environ["PATH"],
    }
    if use_sudo:
        environment["DOCKER_USE_SUDO"] = "1"
    if git_bin is not None:
        environment["GIT_BIN"] = str(git_bin)
        environment["REAL_GIT"] = subprocess.check_output(
            ["sh", "-c", "command -v git"], text=True
        ).strip()
    return selected_revision, environment


def _invoke(
    tmp_path: Path,
    revision: str,
    environment: dict[str, str],
    *,
    evidence_name: str = "evidence",
    mode: str | None = None,
    fault: str | None = None,
    kill_stage: str | None = None,
    build_tmpdir: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    evidence = tmp_path / evidence_name
    caller_image = _caller_image(tmp_path)
    invocation_environment = environment | {"FAKE_EVIDENCE_PATH": str(evidence)}
    if mode is not None:
        invocation_environment["FAKE_DOCKER_MODE"] = mode
    if fault is not None:
        fault_marker = tmp_path / f".python-fault-{evidence_name}"
        fault_marker.unlink(missing_ok=True)
        invocation_environment["FAKE_PYTHON_FAULT"] = fault
        invocation_environment["FAKE_PYTHON_FAULT_MARKER"] = str(fault_marker)
    else:
        _ = invocation_environment.pop("FAKE_PYTHON_FAULT", None)
        _ = invocation_environment.pop("FAKE_PYTHON_FAULT_MARKER", None)
    if kill_stage is not None:
        invocation_environment["FAKE_PYTHON_KILL_STAGE"] = kill_stage
    else:
        _ = invocation_environment.pop("FAKE_PYTHON_KILL_STAGE", None)
    if build_tmpdir is not None:
        invocation_environment["TMPDIR"] = str(build_tmpdir)
    return subprocess.run(
        [str(WORKER), "--revision", revision, "--image", caller_image, "--evidence-dir", str(evidence)],
        cwd=ROOT,
        env=invocation_environment,
        text=True,
        capture_output=True,
        check=False,
    )


def _run(
    tmp_path: Path,
    *,
    revision: str | None = None,
    mode: str = "success",
    preexisting_caller: bool = False,
    git_bin: Path | None = None,
    use_sudo: bool = False,
    fault: str | None = None,
) -> subprocess.CompletedProcess[str]:
    selected_revision, environment = _prepare_environment(
        tmp_path,
        revision=revision,
        mode=mode,
        preexisting_caller=preexisting_caller,
        git_bin=git_bin,
        use_sudo=use_sudo,
    )
    return _invoke(tmp_path, selected_revision, environment, mode=mode, fault=fault)


def _docker_calls(tmp_path: Path) -> list[list[str]]:
    log = tmp_path / "docker.log"
    return (
        []
        if not log.exists()
        else [
            DOCKER_CALL_ADAPTER.validate_json(line)
            for line in log.read_text(encoding="utf-8").splitlines()
        ]
    )


def _docker_state(tmp_path: Path) -> _DockerState:
    return DOCKER_STATE_ADAPTER.validate_json(
        (tmp_path / "docker-state.json").read_bytes()
    )


def test_builder_validates_temporary_tag_before_publishing_caller_tag(tmp_path: Path) -> None:
    revision = _ancestor_revision()
    caller_image = _caller_image(tmp_path)
    resolved = subprocess.check_output(["git", "rev-parse", f"{revision}^{{commit}}"], cwd=ROOT, text=True).strip()

    completed = _run(tmp_path, revision=revision)

    assert completed.returncode == 0, completed.stderr
    manifest_bytes = (tmp_path / "evidence/manifest.json").read_bytes()
    manifest = MANIFEST_ADAPTER.validate_json(manifest_bytes)
    archive = subprocess.check_output(
        ["git", "archive", "--format=tar", resolved, "--", *ARCHIVE_PATHS], cwd=ROOT
    )
    expected_source = subprocess.check_output(["git", "show", f"{resolved}:{SOURCE_PROBE}"], cwd=ROOT)
    assert manifest["source_archive_sha256"] == hashlib.sha256(archive).hexdigest()
    assert (tmp_path / "source-capture").read_bytes() == expected_source
    assert (tmp_path / "dockerfile-capture").read_bytes() == (
        ROOT / "services/support-copilot-api/Dockerfile"
    ).read_bytes()
    assert manifest["image_id"] == IMAGE_ID and manifest["platform"] == "linux/amd64"
    assert (tmp_path / "evidence/COMPLETE").read_text(encoding="utf-8") == (
        "manifest_sha256=" + hashlib.sha256(manifest_bytes).hexdigest() + "\n"
    )
    calls = _docker_calls(tmp_path)
    build = next(call for call in calls if call[0] == "build")
    temporary_tag = build[build.index("--tag") + 1]
    context = Path((tmp_path / "context-path").read_text(encoding="utf-8"))
    assert build[build.index("--file") + 1] == str(
        context / "services/support-copilot-api/Dockerfile"
    )
    labels = [build[index + 1] for index, value in enumerate(build[:-1]) if value == "--label"]
    packaging_digest = hashlib.sha256((ROOT / "services/support-copilot-api/Dockerfile").read_bytes()).hexdigest()
    assert temporary_tag.startswith("support-copilot-compatible-api-temp:")
    assert labels == [
        f"org.opencontainers.image.revision={resolved}",
        f"io.support-copilot.packaging-dockerfile-sha256={packaging_digest}",
    ]
    inspect_index = next(index for index, call in enumerate(calls) if call[:2] == ["image", "inspect"])
    tag_index = calls.index(["image", "tag", IMAGE_ID, caller_image])
    remove_index = calls.index(["image", "rm", temporary_tag])
    assert inspect_index < tag_index < remove_index
    assert ["image", "tag", IMAGE_ID, caller_image] in calls
    assert ["image", "rm", temporary_tag] in calls
    docker_state = _docker_state(tmp_path)
    assert "caller_tag_observations" in docker_state
    assert docker_state["caller_tag_observations"] == [
        {"manifest": True, "complete": False}
    ]
    assert docker_state["tags"] == {caller_image: IMAGE_ID}
    assert context.parent.parent == tmp_path
    assert not context.parent.exists()


def test_builder_keeps_docker_bounded_under_noninteractive_sudo(tmp_path: Path) -> None:
    completed = _run(tmp_path, use_sudo=True)

    assert completed.returncode == 0, completed.stderr
    timeout_calls = (tmp_path / "timeout.log").read_text(encoding="utf-8").splitlines()
    sudo_calls = (tmp_path / "sudo.log").read_text(encoding="utf-8").splitlines()
    assert timeout_calls and all(call.startswith("600 sudo -n -- ") for call in timeout_calls)
    assert sudo_calls and all(call.startswith("-n -- ") for call in sudo_calls)


def test_builder_rejects_preexisting_caller_tag_before_build(tmp_path: Path) -> None:
    caller_image = _caller_image(tmp_path)
    completed = _run(tmp_path, preexisting_caller=True)

    assert completed.returncode != 0
    assert "already exists" in completed.stderr
    assert not any(call[0] == "build" for call in _docker_calls(tmp_path))
    assert _docker_state(tmp_path)["tags"] == {caller_image: OLD_IMAGE_ID}
    assert not (tmp_path / "evidence").exists()


@pytest.mark.parametrize("mode", ["label-mismatch", "wrong-os", "wrong-arch"])
def test_builder_validation_failure_never_publishes_caller_tag(tmp_path: Path, mode: str) -> None:
    caller_image = _caller_image(tmp_path)
    completed = _run(tmp_path, mode=mode)

    assert completed.returncode != 0
    calls = _docker_calls(tmp_path)
    assert not any(call[:2] == ["image", "tag"] for call in calls)
    assert caller_image not in _docker_state(tmp_path)["tags"]
    temporary_tag = next(call[call.index("--tag") + 1] for call in calls if call[0] == "build")
    assert ["image", "rm", temporary_tag] in calls
    assert not (tmp_path / "evidence").exists()


def test_builder_rechecks_caller_tag_immediately_before_publication(tmp_path: Path) -> None:
    caller_image = _caller_image(tmp_path)
    completed = _run(tmp_path, mode="final-caller-collision")

    assert completed.returncode != 0
    assert "appeared" in completed.stderr
    calls = _docker_calls(tmp_path)
    assert ["image", "tag", IMAGE_ID, caller_image] not in calls
    assert _docker_state(tmp_path)["tags"][caller_image] == OLD_IMAGE_ID
    assert not (tmp_path / "evidence").exists()


@pytest.mark.parametrize(
    ("fault", "caller_was_published"),
    [
        ("manifest_after_temp_fsync", False),
        ("manifest_after_rename", False),
        ("complete_after_temp_fsync", True),
        ("complete_after_rename", True),
    ],
)
def test_builder_rolls_back_partial_evidence_and_owned_caller_tag(
    tmp_path: Path, fault: str, caller_was_published: bool
) -> None:
    caller_image = _caller_image(tmp_path)
    completed = _run(tmp_path, fault=fault)

    assert completed.returncode != 0
    calls = _docker_calls(tmp_path)
    caller_tag_call = ["image", "tag", IMAGE_ID, caller_image]
    assert (caller_tag_call in calls) is caller_was_published
    if caller_was_published:
        assert ["image", "rm", caller_image] in calls
    assert caller_image not in _docker_state(tmp_path)["tags"]
    assert not (tmp_path / "evidence").exists()


def test_builder_preserves_caller_tag_that_changed_before_rollback(tmp_path: Path) -> None:
    caller_image = _caller_image(tmp_path)
    completed = _run(tmp_path, mode="replace-caller-after-tag")

    assert completed.returncode != 0
    assert "cleanup refused" in completed.stderr
    assert _docker_state(tmp_path)["tags"][caller_image] == OLD_IMAGE_ID
    assert ["image", "rm", caller_image] not in _docker_calls(tmp_path)
    assert not (tmp_path / "evidence").exists()


def test_builder_lock_contends_across_build_tmpdirs_and_allows_retry(
    tmp_path: Path,
) -> None:
    revision, environment = _prepare_environment(tmp_path)
    caller_image = _caller_image(tmp_path)
    first_build_tmp = tmp_path / "first-build-tmp"
    second_build_tmp = tmp_path / "second-build-tmp"
    retry_build_tmp = tmp_path / "retry-build-tmp"
    first_build_tmp.mkdir()
    second_build_tmp.mkdir()
    retry_build_tmp.mkdir()
    ready_fifo = tmp_path / "ready.fifo"
    release_fifo = tmp_path / "release.fifo"
    os.mkfifo(ready_fifo)
    os.mkfifo(release_fifo)
    ready_descriptor = os.open(ready_fifo, os.O_RDONLY | os.O_NONBLOCK)
    first_evidence = tmp_path / "evidence"
    first_environment = environment | {
        "FAKE_DOCKER_MODE": "hold-first-preflight",
        "FAKE_EVIDENCE_PATH": str(first_evidence),
        "FAKE_READY_FIFO": str(ready_fifo),
        "FAKE_RELEASE_FIFO": str(release_fifo),
        "FAKE_PYTHON_FAULT": "manifest_after_rename",
        "FAKE_PYTHON_FAULT_MARKER": str(tmp_path / ".python-fault-concurrent"),
        "TMPDIR": str(first_build_tmp),
    }
    first = subprocess.Popen(
        [
            str(WORKER),
            "--revision",
            revision,
            "--image",
            caller_image,
            "--evidence-dir",
            str(first_evidence),
        ],
        cwd=ROOT,
        env=first_environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        readable, _, _ = select.select([ready_descriptor], [], [], 15)
        assert readable, "first builder never reached its caller-tag preflight"
        assert os.read(ready_descriptor, 64) == b"ready\n"
        calls_while_locked = _docker_calls(tmp_path)

        second = _invoke(
            tmp_path,
            revision,
            environment,
            evidence_name="evidence-second",
            build_tmpdir=second_build_tmp,
        )

        assert second.returncode != 0
        assert "lock is already held" in second.stderr
        assert _docker_calls(tmp_path) == calls_while_locked
        with release_fifo.open("w", encoding="utf-8") as release:
            _ = release.write("x")
        _, first_stderr = first.communicate(timeout=20)
        assert first.returncode != 0, first_stderr
        first_context = Path(
            (tmp_path / "context-path").read_text(encoding="utf-8")
        )
        assert first_context.parent.parent == first_build_tmp
    finally:
        os.close(ready_descriptor)
        if first.poll() is None:
            first.kill()
            _ = first.communicate()

    assert not first_evidence.exists()
    assert caller_image not in _docker_state(tmp_path)["tags"]
    retry = _invoke(
        tmp_path,
        revision,
        environment,
        build_tmpdir=retry_build_tmp,
    )
    assert retry.returncode == 0, retry.stderr
    lock_root = (
        Path("/tmp").resolve()
        / f".support-copilot-compatible-api-locks.{os.getuid()}"
    )
    lock_digest = hashlib.sha256(caller_image.encode()).hexdigest()
    exact_lock = lock_root / f"image-{lock_digest}.lock"
    assert lock_root.is_dir()
    assert exact_lock.is_file()
    assert exact_lock.stat().st_mode & 0o777 == 0o600


def test_builder_failure_is_retryable_with_same_image_and_evidence(tmp_path: Path) -> None:
    revision, environment = _prepare_environment(tmp_path)
    caller_image = _caller_image(tmp_path)

    failed = _invoke(
        tmp_path,
        revision,
        environment,
        fault="complete_after_temp_fsync",
    )
    retried = _invoke(tmp_path, revision, environment)

    assert failed.returncode != 0
    assert retried.returncode == 0, retried.stderr
    assert _docker_state(tmp_path)["tags"][caller_image] == IMAGE_ID
    assert (tmp_path / "evidence/COMPLETE").is_file()


def test_builder_recovers_after_sigkill_after_caller_tag_publication(
    tmp_path: Path,
) -> None:
    revision, environment = _prepare_environment(tmp_path)
    caller_image = _caller_image(tmp_path)

    killed = _invoke(
        tmp_path,
        revision,
        environment,
        mode="kill-after-caller-tag",
    )

    assert killed.returncode == -signal.SIGKILL
    evidence = tmp_path / "evidence"
    assert (evidence / ".pending.json").is_file()
    assert (evidence / "manifest.json").is_file()
    assert not (evidence / "COMPLETE").exists()
    assert _docker_state(tmp_path)["tags"][caller_image] == IMAGE_ID

    retried = _invoke(tmp_path, revision, environment)

    assert retried.returncode == 0, retried.stderr
    assert sorted(path.name for path in evidence.iterdir()) == ["COMPLETE", "manifest.json"]
    assert _docker_state(tmp_path)["tags"][caller_image] == IMAGE_ID
    calls = _docker_calls(tmp_path)
    assert calls.count(["image", "tag", IMAGE_ID, caller_image]) == 1
    assert sum(call[0] == "build" for call in calls) == 1


def test_builder_recovers_after_sigkill_before_caller_tag_publication(
    tmp_path: Path,
) -> None:
    revision, environment = _prepare_environment(tmp_path)
    caller_image = _caller_image(tmp_path)

    killed = _invoke(
        tmp_path,
        revision,
        environment,
        mode="kill-before-caller-tag",
    )

    assert killed.returncode == -signal.SIGKILL
    assert caller_image not in _docker_state(tmp_path)["tags"]
    assert (tmp_path / "evidence/.pending.json").is_file()
    assert not (tmp_path / "evidence/COMPLETE").exists()
    first_calls = _docker_calls(tmp_path)
    first_build = next(call for call in first_calls if call[0] == "build")
    first_temporary_ref = first_build[first_build.index("--tag") + 1]

    retried = _invoke(tmp_path, revision, environment)

    assert retried.returncode == 0, retried.stderr
    assert _docker_state(tmp_path)["tags"][caller_image] == IMAGE_ID
    assert (tmp_path / "evidence/COMPLETE").is_file()
    calls = _docker_calls(tmp_path)
    assert calls.count(["image", "tag", IMAGE_ID, caller_image]) == 2
    assert sum(call[0] == "build" for call in calls) == 2
    assert ["image", "rm", first_temporary_ref] in calls


def test_builder_preserves_retargeted_temp_tag_without_durable_image_id(
    tmp_path: Path,
) -> None:
    revision, environment = _prepare_environment(tmp_path)
    caller_image = _caller_image(tmp_path)

    killed = _invoke(
        tmp_path,
        revision,
        environment,
        kill_stage="before_manifest_payload",
    )

    assert killed.returncode == -signal.SIGKILL
    evidence = tmp_path / "evidence"
    before_evidence = {path.name: path.read_bytes() for path in evidence.iterdir()}
    assert set(before_evidence) == {".pending.json"}
    pending = PENDING_ADAPTER.validate_json(before_evidence[".pending.json"])
    assert "image_id" not in pending
    calls_before_retry = _docker_calls(tmp_path)
    build = next(call for call in calls_before_retry if call[0] == "build")
    temporary_ref = build[build.index("--tag") + 1]
    state = _docker_state(tmp_path)
    built_metadata = state["images"][IMAGE_ID]
    state["images"][RETARGETED_IMAGE_ID] = {
        "id": RETARGETED_IMAGE_ID,
        "os": built_metadata["os"],
        "architecture": built_metadata["architecture"],
        "revision": built_metadata["revision"],
        "packaging": built_metadata["packaging"],
    }
    state["tags"][temporary_ref] = RETARGETED_IMAGE_ID
    _ = (tmp_path / "docker-state.json").write_text(
        json.dumps(state), encoding="utf-8"
    )
    before_retry_state = _docker_state(tmp_path)

    retried = _invoke(tmp_path, revision, environment)

    assert retried.returncode != 0
    assert "recovery refused" in retried.stderr
    assert {path.name: path.read_bytes() for path in evidence.iterdir()} == before_evidence
    retried_state = _docker_state(tmp_path)
    assert retried_state == before_retry_state
    assert retried_state["tags"][temporary_ref] == RETARGETED_IMAGE_ID
    assert caller_image not in retried_state["tags"]
    retry_calls = _docker_calls(tmp_path)[len(calls_before_retry) :]
    assert retry_calls == []


def test_builder_rejects_partial_manifest_before_any_docker_call(
    tmp_path: Path,
) -> None:
    revision, environment = _prepare_environment(tmp_path)

    killed = _invoke(
        tmp_path,
        revision,
        environment,
        kill_stage="before_manifest_payload",
    )

    assert killed.returncode == -signal.SIGKILL
    evidence = tmp_path / "evidence"
    pending = PENDING_ADAPTER.validate_json(
        (evidence / ".pending.json").read_bytes()
    )
    token = pending["token"]
    assert isinstance(token, str)
    partial_manifest = evidence / f".manifest.{token}.tmp"
    _ = partial_manifest.write_bytes(b'{"schema_version":1')
    partial_manifest.chmod(0o600)
    before_evidence = {path.name: path.read_bytes() for path in evidence.iterdir()}
    before_retry_state = _docker_state(tmp_path)
    calls_before_retry = _docker_calls(tmp_path)

    retried = _invoke(tmp_path, revision, environment)

    assert retried.returncode != 0
    assert "recovery refused" in retried.stderr
    assert _docker_calls(tmp_path)[len(calls_before_retry) :] == []
    assert {path.name: path.read_bytes() for path in evidence.iterdir()} == before_evidence
    assert _docker_state(tmp_path) == before_retry_state


def test_builder_refuses_sigkill_recovery_when_caller_tag_changed(
    tmp_path: Path,
) -> None:
    revision, environment = _prepare_environment(tmp_path)
    caller_image = _caller_image(tmp_path)

    killed = _invoke(
        tmp_path,
        revision,
        environment,
        mode="kill-after-caller-tag",
    )
    assert killed.returncode == -signal.SIGKILL
    evidence = tmp_path / "evidence"
    before = {path.name: path.read_bytes() for path in evidence.iterdir()}
    state = _docker_state(tmp_path)
    state["tags"][caller_image] = OLD_IMAGE_ID
    _ = (tmp_path / "docker-state.json").write_text(
        json.dumps(state), encoding="utf-8"
    )

    retried = _invoke(tmp_path, revision, environment)

    assert retried.returncode != 0
    assert "recovery refused" in retried.stderr
    assert _docker_state(tmp_path)["tags"][caller_image] == OLD_IMAGE_ID
    assert {path.name: path.read_bytes() for path in evidence.iterdir()} == before
    assert ["image", "rm", caller_image] not in _docker_calls(tmp_path)


def test_builder_rejects_unsafe_archive_symlink_before_docker(tmp_path: Path) -> None:
    fake_git = tmp_path / "git"
    _write_unsafe_archive_git(fake_git)

    completed = _run(tmp_path, git_bin=fake_git)

    assert completed.returncode != 0
    assert "unsafe archive" in completed.stderr
    assert _docker_calls(tmp_path) == []
    assert not (tmp_path / "evidence").exists()


@pytest.mark.parametrize(
    "mode",
    ["build-failure", "replace-evidence", "replace-temp", "inject-evidence-file"],
)
def test_builder_failure_cleans_only_owned_reservations(tmp_path: Path, mode: str) -> None:
    caller_image = _caller_image(tmp_path)
    completed = _run(tmp_path, mode=mode)

    assert completed.returncode == 37
    calls = _docker_calls(tmp_path)
    temporary_tag = next(call[call.index("--tag") + 1] for call in calls if call[0] == "build")
    assert ["image", "rm", temporary_tag] in calls
    assert caller_image not in _docker_state(tmp_path)["tags"]
    if mode == "replace-evidence":
        assert (tmp_path / "evidence/sentinel").read_text(encoding="utf-8") == "replacement"
        assert (tmp_path / "evidence-owned").is_dir()
    elif mode == "replace-temp":
        context = Path((tmp_path / "context-path").read_text(encoding="utf-8"))
        assert (context.parent / "sentinel").read_text(encoding="utf-8") == "replacement"
        assert context.parent.with_name(context.parent.name + "-owned").is_dir()
    elif mode == "inject-evidence-file":
        assert (tmp_path / "evidence/sentinel").read_text(encoding="utf-8") == "injected"
        assert "unexpected or changed artifacts" in completed.stderr
    else:
        assert not (tmp_path / "evidence").exists()
        context = Path((tmp_path / "context-path").read_text(encoding="utf-8"))
        assert not context.parent.exists()


def test_builder_build_failure_without_temporary_tag_cleans_reservations(tmp_path: Path) -> None:
    # Given: Docker fails before it creates the exact temporary image tag.
    caller_image = _caller_image(tmp_path)

    # When: the compatible image build aborts without a temporary tag.
    completed = _run(tmp_path, mode="build-failure-no-tag")

    # Then: the build exit survives cleanup without mutating the caller tag or leaving owned paths.
    assert completed.returncode == 37
    assert "cleanup failed to remove the exact temporary image tag" not in completed.stderr
    calls = _docker_calls(tmp_path)
    build_index = next(index for index, call in enumerate(calls) if call[0] == "build")
    temporary_tag = calls[build_index][calls[build_index].index("--tag") + 1]
    temporary_inspections = [
        index
        for index, call in enumerate(calls)
        if call[:4] == ["image", "ls", "--quiet", "--no-trunc"]
        and call[-1] == temporary_tag
    ]
    assert len([index for index in temporary_inspections if index > build_index]) == 1
    assert ["image", "rm", temporary_tag] not in calls
    assert caller_image not in _docker_state(tmp_path)["tags"]
    assert temporary_tag not in _docker_state(tmp_path)["tags"]
    assert not (tmp_path / "evidence").exists()
    context = Path((tmp_path / "context-path").read_text(encoding="utf-8"))
    assert not context.parent.exists()


def test_builder_records_temporary_tag_query_failure_during_cleanup(tmp_path: Path) -> None:
    # Given: Docker fails while checking whether the failed build created its exact temporary tag.
    caller_image = _caller_image(tmp_path)

    # When: the compatible image build aborts before it creates the tag.
    completed = _run(tmp_path, mode="build-failure-no-tag-cleanup-query-failure")

    # Then: cleanup failure is reported without replacing the original build exit or mutating tags.
    assert completed.returncode == 37
    assert "cleanup failed to inspect the exact temporary image tag" in completed.stderr
    calls = _docker_calls(tmp_path)
    temporary_tag = next(call[call.index("--tag") + 1] for call in calls if call[0] == "build")
    assert ["image", "rm", temporary_tag] not in calls
    assert caller_image not in _docker_state(tmp_path)["tags"]
    assert temporary_tag not in _docker_state(tmp_path)["tags"]
    assert not (tmp_path / "evidence").exists()
    context = Path((tmp_path / "context-path").read_text(encoding="utf-8"))
    assert not context.parent.exists()


def test_builder_rejects_current_head_without_docker_or_evidence(tmp_path: Path) -> None:
    completed = _run(tmp_path, revision="HEAD")

    assert completed.returncode != 0
    assert "current HEAD" in completed.stderr
    assert _docker_calls(tmp_path) == []
    assert not (tmp_path / "evidence").exists()


@pytest.mark.parametrize("kind", ["stale", "symlink"])
def test_builder_rejects_stale_or_symlinked_evidence_before_docker(tmp_path: Path, kind: str) -> None:
    evidence = tmp_path / "evidence"
    if kind == "stale":
        evidence.mkdir()
    else:
        target = tmp_path / "outside"
        target.mkdir()
        evidence.symlink_to(target, target_is_directory=True)

    completed = _run(tmp_path)

    assert completed.returncode != 0
    assert "evidence directory" in completed.stderr
    assert _docker_calls(tmp_path) == []
    assert evidence.exists() or evidence.is_symlink()


@pytest.mark.parametrize(
    "arguments",
    [
        ("--unknown", "value"),
        ("--revision", "", "--image", CALLER_IMAGE, "--evidence-dir", "output"),
        ("--revision", "../escape", "--image", CALLER_IMAGE, "--evidence-dir", "output"),
    ],
)
def test_builder_rejects_unknown_empty_or_unsafe_arguments_before_mutation(
    tmp_path: Path, arguments: tuple[str, ...]
) -> None:
    completed = subprocess.run(
        [str(WORKER), *arguments],
        cwd=ROOT,
        env=os.environ | {"TMPDIR": str(tmp_path)},
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode != 0
    assert not list(tmp_path.glob("support-copilot-compatible-api.*"))

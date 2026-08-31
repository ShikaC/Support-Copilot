"""Fake-Docker contract coverage for pilot image scanning.

# noqa: SIZE_OK
Cohesion: one stateful Docker fake models scanner lifecycle, evidence, and cleanup ordering.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKER = ROOT / "scripts" / "scan-pilot-images.sh"
PYTHON = ROOT / "services" / "support-copilot-ai" / ".venv" / "bin" / "python"
SCANNER_ID = "sha256:086971aaf400beebd94e8300fd8ea623774419597169156cec56eec5b00dfb1e"
SCANNER_REF = "aquasec/trivy:0.66.0@" + SCANNER_ID
APP_IMAGE_ID = "sha256:" + "1" * 64


def _write_fake_docker(path: Path) -> None:
    path.write_text(
        """#!/usr/bin/env python3
import json
import os
import pathlib
import sys

args = sys.argv[1:]
log = pathlib.Path(os.environ["FAKE_DOCKER_LOG"])
with log.open("a", encoding="utf-8") as stream:
    stream.write(json.dumps(args) + "\\n")

if args[:2] == ["image", "inspect"]:
    ref = args[-1]
    if ref.startswith("aquasec/trivy"):
        if os.environ.get("FAKE_SCAN_MODE") == "scanner-daemon-failure":
            print("Cannot connect to the Docker daemon", file=sys.stderr)
            raise SystemExit(1)
        state = pathlib.Path(os.environ["FAKE_SCANNER_STATE"])
        if not state.exists() or state.read_text(encoding="utf-8") != "present":
            print("Error response from daemon: No such image: " + ref, file=sys.stderr)
            raise SystemExit(1)
        digest = os.environ.get("FAKE_SCANNER_DIGEST", os.environ["FAKE_SCANNER_ID"])
        platform = os.environ.get("FAKE_SCANNER_PLATFORM", "linux/amd64")
        print(os.environ["FAKE_SCANNER_ID"] + " [\\\"aquasec/trivy@" + digest + "\\\"] " + platform)
    else:
        token = "1" if ref.endswith("api:test") else "2"
        image_id = "sha256:" + token * 64
        if os.environ.get("FAKE_SCAN_MODE") == "local-no-digest":
            print(image_id + " null")
        else:
            print(image_id + " [\\\"registry.test/" + ref.split(":")[0] + "@sha256:" + token * 64 + "\\\"]")
    raise SystemExit(0)
if args and args[0] == "pull":
    if args[-1] != os.environ["FAKE_EXPECTED_SCANNER_REF"]:
        print("unexpected scanner reference", file=sys.stderr)
        raise SystemExit(91)
    mode = os.environ.get("FAKE_SCAN_MODE", "clean")
    if mode == "scanner-pull-failure":
        print("pull failed secret=should-not-leak", file=sys.stderr)
        raise SystemExit(1)
    pathlib.Path(os.environ["FAKE_SCANNER_STATE"]).write_text("present", encoding="utf-8")
    raise SystemExit(0)
if args[:2] == ["volume", "create"] or args[:2] == ["volume", "rm"]:
    print(args[-1])
    raise SystemExit(0)
if args[:2] == ["container", "ls"]:
    if os.environ.get("FAKE_SCANNER_REFERENCED") == "1":
        print("referencing-container")
    raise SystemExit(0)
if args[:2] == ["image", "rm"]:
    raise SystemExit(0)
if args and args[0] == "rm":
    raise SystemExit(0)
if args and args[0] == "run":
    if "version" in args:
        print(json.dumps({"Version": "0.66.0", "VulnerabilityDB": {"Version": 2, "UpdatedAt": "2026-08-30T00:00:00Z"}}))
        raise SystemExit(0)
    mount = next(value for index, value in enumerate(args) if args[index - 1] == "-v" and value.endswith(":/reports"))
    output_arg = args[args.index("--output") + 1]
    report = pathlib.Path(mount.removesuffix(":/reports")) / pathlib.Path(output_arg).name
    image_id = args[-1]
    mode = os.environ.get("FAKE_SCAN_MODE", "clean")
    if mode == "operational" or (mode == "partial" and output_arg.endswith("002.json")):
        print("database download failed", file=sys.stderr)
        raise SystemExit(2)
    if mode == "zero-no-report":
        raise SystemExit(0)
    vulnerabilities = []
    if mode == "findings":
        vulnerabilities = [{"Severity": "HIGH", "VulnerabilityID": "CVE-2026-12345", "PkgName": "private-package-inventory"}]
    results = [] if not vulnerabilities else [{"Target": "site-packages", "Class": "lang-pkgs", "Type": "python-pkg", "Vulnerabilities": vulnerabilities}]
    repo_digests = None if mode == "local-no-digest" else ["registry.test/" + ("pilot-api" if image_id.endswith("1" * 64) else "pilot-ai") + "@" + image_id]
    report.write_text(json.dumps({"SchemaVersion": 2, "Metadata": {"ImageID": image_id, "RepoDigests": repo_digests}, "Results": results}), encoding="utf-8")
    raise SystemExit(1 if vulnerabilities else 0)
raise SystemExit(97)
""",
        encoding="utf-8",
    )
    path.chmod(0o755)


def _write_python_probe(path: Path) -> None:
    path.write_text(
        """#!/usr/bin/env python3
import json
import os
import pathlib
import sys

calls = [json.loads(line) for line in pathlib.Path(os.environ["FAKE_DOCKER_LOG"]).read_text().splitlines()]
if not any(call[:2] == ["volume", "rm"] for call in calls):
    print("cache volume still allocated before finalization", file=sys.stderr)
    raise SystemExit(88)
real_python = os.environ["REAL_PYTHON"]
os.execv(real_python, [real_python, *sys.argv[1:]])
""",
        encoding="utf-8",
    )
    path.chmod(0o755)


def _write_fake_timeout(path: Path) -> None:
    path.write_text(
        """#!/usr/bin/env python3
import os
import sys

arguments = sys.argv[1:]
mode = os.environ.get("FAKE_SCAN_MODE")
if mode == "scanner-pull-timeout" and "pull" in arguments:
    print("timed out", file=sys.stderr)
    raise SystemExit(124)
if mode == "cleanup-inspect-timeout" and arguments[2:4] == ["container", "ls"]:
    print("cleanup inspection timed out", file=sys.stderr)
    raise SystemExit(124)
if mode == "cleanup-image-rm-timeout" and arguments[2:4] == ["image", "rm"]:
    print("image removal timed out", file=sys.stderr)
    raise SystemExit(124)
os.execv(arguments[1], arguments[1:])
""",
        encoding="utf-8",
    )
    path.chmod(0o755)


def _run_worker(
    tmp_path: Path,
    *images: str,
    mode: str = "clean",
    scanner_present: bool = True,
    scanner_digest: str = SCANNER_ID,
    scanner_platform: str = "linux/amd64",
    scanner_referenced: bool = False,
    timeout_available: bool = True,
) -> subprocess.CompletedProcess[str]:
    fake_docker = tmp_path / "fake-docker"
    _write_fake_docker(fake_docker)
    scanner_state = tmp_path / "scanner-state"
    if scanner_present:
        scanner_state.write_text("present", encoding="utf-8")
    fake_timeout = tmp_path / "fake-timeout"
    _write_fake_timeout(fake_timeout)
    timeout_bin = fake_timeout if timeout_available else tmp_path / "missing-timeout"
    environment = os.environ | {
        "DOCKER_BIN": str(fake_docker),
        "FAKE_DOCKER_LOG": str(tmp_path / "docker.log"),
        "FAKE_SCANNER_ID": SCANNER_ID,
        "FAKE_SCANNER_STATE": str(scanner_state),
        "FAKE_SCANNER_DIGEST": scanner_digest,
        "FAKE_SCANNER_PLATFORM": scanner_platform,
        "FAKE_EXPECTED_SCANNER_REF": SCANNER_REF,
        "FAKE_SCAN_MODE": mode,
        "FAKE_SCANNER_REFERENCED": "1" if scanner_referenced else "0",
        "PYTHON_BIN": str(PYTHON),
        "TIMEOUT_BIN": str(timeout_bin),
    }
    if mode == "invalid-scan-timeout":
        environment["SCAN_TIMEOUT_SECONDS"] = "0"
    if mode == "invalid-cleanup-timeout":
        environment["CLEANUP_TIMEOUT_SECONDS"] = "unbounded"
    if mode == "require-cache-release":
        python_probe = tmp_path / "python-probe"
        _write_python_probe(python_probe)
        environment["PYTHON_BIN"] = str(python_probe)
        environment["REAL_PYTHON"] = str(PYTHON)
    return subprocess.run(
        [str(WORKER), str(tmp_path / "evidence"), *images],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )


def _docker_calls(tmp_path: Path) -> list[list[str]]:
    return [json.loads(line) for line in (tmp_path / "docker.log").read_text().splitlines()]


def test_worker_preflight_failure_does_not_create_output(tmp_path: Path) -> None:
    # Given: the required timeout executable is unavailable before a scan starts.
    output = tmp_path / "evidence"

    # When: the public worker validates its prerequisites.
    completed = _run_worker(tmp_path, "pilot-api:test", timeout_available=False)

    # Then: it fails without creating evidence or invoking Docker.
    assert completed.returncode == 1
    assert not output.exists()
    assert not (tmp_path / "docker.log").exists()


def test_worker_invalid_scan_timeout_does_not_create_output(tmp_path: Path) -> None:
    # Given: the scan timeout configuration is not a positive integer.
    output = tmp_path / "evidence"

    # When: the public worker validates its timeout budgets.
    completed = _run_worker(tmp_path, "pilot-api:test", mode="invalid-scan-timeout")

    # Then: it fails before creating evidence or invoking Docker.
    assert completed.returncode == 1
    assert not output.exists()
    assert not (tmp_path / "docker.log").exists()


def test_worker_invalid_cleanup_timeout_does_not_create_output(tmp_path: Path) -> None:
    # Given: the cleanup timeout configuration is malformed.
    output = tmp_path / "evidence"

    # When: the public worker validates its timeout budgets.
    completed = _run_worker(tmp_path, "pilot-api:test", mode="invalid-cleanup-timeout")

    # Then: it fails before creating evidence or invoking Docker.
    assert completed.returncode == 1
    assert not output.exists()
    assert not (tmp_path / "docker.log").exists()


def test_worker_completes_clean_multi_image_scan(tmp_path: Path) -> None:
    # Given: two locally inspectable images and a clean scanner result for each.
    output = tmp_path / "evidence"

    # When: the public worker scans both explicit image references.
    completed = _run_worker(tmp_path, "pilot-api:test", "pilot-ai:test")

    # Then: the gate passes and publishes a complete, per-image evidence set.
    assert completed.returncode == 0, completed.stderr
    assert (output / "COMPLETE").is_file()
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert [entry["image_ref"] for entry in manifest["images"]] == [
        "pilot-api:test",
        "pilot-ai:test",
    ]
    assert manifest["scanner"]["vulnerability_db"]["Version"] == 2
    assert json.loads((output / "findings.json").read_bytes())["findings"] == []
    assert sorted(path.name for path in output.glob("report-*.json")) == [
        "report-001.json",
        "report-002.json",
    ]


def test_worker_acquires_absent_pinned_scanner_before_scanning(tmp_path: Path) -> None:
    # Given: no local Trivy image exists before the gate starts.
    output = tmp_path / "evidence"

    # When: the worker scans one built image.
    completed = _run_worker(tmp_path, "pilot-api:test", scanner_present=False)

    # Then: it pulls only the immutable scanner reference and publishes evidence.
    assert completed.returncode == 0, completed.stderr
    calls = _docker_calls(tmp_path)
    pull_index = next(index for index, call in enumerate(calls) if call[0] == "pull")
    scan_index = next(index for index, call in enumerate(calls) if call[0] == "run" and "image" in call)
    assert calls[pull_index][-1] == SCANNER_REF
    assert pull_index < scan_index
    assert (output / "COMPLETE").is_file()


def test_worker_rejects_scanner_digest_mismatch_without_scan(tmp_path: Path) -> None:
    # Given: the local tag resolves to a different immutable digest.
    other_digest = "sha256:" + "2" * 64

    # When: the worker checks scanner identity before scanning.
    completed = _run_worker(tmp_path, "pilot-api:test", scanner_digest=other_digest)

    # Then: it fails closed before the target image or scanner container is used.
    assert completed.returncode == 1
    calls = _docker_calls(tmp_path)
    assert not any(call[0] == "run" for call in calls)
    assert not any(call[:2] == ["image", "inspect"] and call[-1] == "pilot-api:test" for call in calls)


def test_worker_rejects_scanner_platform_mismatch_without_scan(tmp_path: Path) -> None:
    # Given: the immutable scanner image is available only for the wrong platform.

    # When: the worker verifies scanner availability.
    completed = _run_worker(tmp_path, "pilot-api:test", scanner_platform="linux/arm64")

    # Then: it fails before scanning because the intended platform is not resolved.
    assert completed.returncode == 1
    assert not any(call[0] == "run" for call in _docker_calls(tmp_path))


def test_worker_fails_closed_when_scanner_pull_fails(tmp_path: Path) -> None:
    # Given: the required scanner is absent and Docker cannot acquire it.
    output = tmp_path / "evidence"

    # When: the worker attempts the bounded acquisition.
    completed = _run_worker(tmp_path, "pilot-api:test", mode="scanner-pull-failure", scanner_present=False)

    # Then: no scan completion is claimed and no scanner is run.
    assert completed.returncode == 1
    assert not (output / "COMPLETE").exists()
    assert not any(call[0] == "run" for call in _docker_calls(tmp_path))


def test_worker_fails_closed_when_scanner_pull_times_out(tmp_path: Path) -> None:
    # Given: acquiring an absent pinned scanner exceeds the bounded deadline.
    output = tmp_path / "evidence"

    # When: the timeout wrapper returns its operational failure status.
    completed = _run_worker(tmp_path, "pilot-api:test", mode="scanner-pull-timeout", scanner_present=False)

    # Then: the gate fails without publishing completed scan evidence.
    assert completed.returncode == 1
    assert not (output / "COMPLETE").exists()
    assert not any(call[0] == "run" for call in _docker_calls(tmp_path))


def test_worker_does_not_pull_after_scanner_daemon_error(tmp_path: Path) -> None:
    # Given: Docker cannot inspect the scanner because its daemon is unavailable.
    output = tmp_path / "evidence"

    # When: the worker performs the bounded local availability check.
    completed = _run_worker(tmp_path, "pilot-api:test", mode="scanner-daemon-failure")

    # Then: it fails closed without treating the daemon error as an absent image.
    assert completed.returncode == 1
    assert not (output / "COMPLETE").exists()
    calls = _docker_calls(tmp_path)
    assert not any(call[0] == "pull" for call in calls)
    assert not any(call[0] == "run" for call in calls)


def test_worker_preserves_preexisting_scanner_image(tmp_path: Path) -> None:
    # Given: the pinned scanner was present before this invocation.

    # When: a clean image scan completes.
    completed = _run_worker(tmp_path, "pilot-api:test")

    # Then: no scanner pull or image removal is attributed to this gate.
    assert completed.returncode == 0, completed.stderr
    calls = _docker_calls(tmp_path)
    assert not any(call[0] == "pull" for call in calls)
    assert not any(call[:2] == ["image", "rm"] for call in calls)


def test_worker_removes_only_newly_acquired_exact_scanner_image(tmp_path: Path) -> None:
    # Given: this invocation acquires the previously absent pinned scanner.

    # When: the scan completes with no remaining scanner containers.
    completed = _run_worker(tmp_path, "pilot-api:test", scanner_present=False)

    # Then: cleanup removes exactly that acquired immutable reference.
    assert completed.returncode == 0, completed.stderr
    calls = _docker_calls(tmp_path)
    assert ["image", "rm", SCANNER_REF] in calls


def test_worker_refuses_scanner_cleanup_while_referenced(tmp_path: Path) -> None:
    # Given: the gate acquired its scanner but a container still references it.

    # When: scan cleanup reaches the reference safety check.
    completed = _run_worker(tmp_path, "pilot-api:test", scanner_present=False, scanner_referenced=True)

    # Then: cleanup failure blocks the otherwise clean gate without removing the image.
    assert completed.returncode == 1
    calls = _docker_calls(tmp_path)
    assert not any(call[:2] == ["image", "rm"] for call in calls)
    assert "scanner cleanup failed" in (tmp_path / "evidence" / "scanner-001.stderr").read_text(encoding="utf-8")


def test_worker_fails_bounded_cleanup_when_reference_inspect_hangs(tmp_path: Path) -> None:
    # Given: this invocation acquired the scanner and its cleanup reference check hangs.
    output = tmp_path / "evidence"

    # When: the explicit cleanup timeout stops the reference inspection.
    completed = _run_worker(
        tmp_path,
        "pilot-api:test",
        mode="cleanup-inspect-timeout",
        scanner_present=False,
    )

    # Then: scan evidence completes, cleanup fails closed, and no prune is attempted.
    assert completed.returncode == 1
    assert (output / "COMPLETE").is_file()
    cleanup_evidence = (output / "scanner-001.stderr").read_text(encoding="utf-8")
    assert "scanner cleanup timed out: container reference inspection" in cleanup_evidence
    assert not any("prune" in call for call in _docker_calls(tmp_path))


def test_worker_fails_bounded_cleanup_when_image_removal_hangs(tmp_path: Path) -> None:
    # Given: this invocation acquired the scanner and exact image removal hangs.
    output = tmp_path / "evidence"

    # When: the explicit cleanup timeout stops image removal.
    completed = _run_worker(
        tmp_path,
        "pilot-api:test",
        mode="cleanup-image-rm-timeout",
        scanner_present=False,
    )

    # Then: scan evidence completes, cleanup fails closed, and no prune is attempted.
    assert completed.returncode == 1
    assert (output / "COMPLETE").is_file()
    cleanup_evidence = (output / "scanner-001.stderr").read_text(encoding="utf-8")
    assert "scanner cleanup timed out: acquired scanner image removal" in cleanup_evidence
    assert not any("prune" in call for call in _docker_calls(tmp_path))


def test_worker_preserves_blocked_scan_result_when_cleanup_also_fails(tmp_path: Path) -> None:
    # Given: the scanner reports a HIGH finding and its acquired image remains referenced.
    output = tmp_path / "evidence"

    # When: the worker finalizes the policy-blocked scan and attempts cleanup.
    completed = _run_worker(
        tmp_path,
        "pilot-api:test",
        mode="findings",
        scanner_present=False,
        scanner_referenced=True,
    )

    # Then: the finding remains the primary blocked outcome and cleanup is retained as evidence.
    assert completed.returncode == 1
    assert json.loads((output / "summary.json").read_text(encoding="utf-8"))["outcome"] == "blocked"
    assert "scanner cleanup failed" in (output / "scanner-001.stderr").read_text(encoding="utf-8")


def test_worker_never_emits_secret_shaped_fake_docker_diagnostics(tmp_path: Path) -> None:
    # Given: Docker emits secret-shaped text while acquisition fails.

    # When: the public gate exits from its acquisition boundary.
    completed = _run_worker(tmp_path, "pilot-api:test", mode="scanner-pull-failure", scanner_present=False)

    # Then: terminal and retained diagnostics use only stable, non-secret wording.
    rendered = completed.stdout + completed.stderr + (tmp_path / "evidence" / "scanner-acquisition.stderr").read_text(encoding="utf-8")
    assert "secret=" not in rendered.lower()


def test_worker_binds_locally_built_image_without_repo_digest(tmp_path: Path) -> None:
    # Given: a locally built app image has an immutable ID but no registry digest.
    output = tmp_path / "evidence"

    # When: the worker scans that local image by ID.
    completed = _run_worker(tmp_path, "pilot-api:test", mode="local-no-digest")

    # Then: ID binding is sufficient and the absent digest is explicit.
    assert completed.returncode == 0, completed.stderr
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["images"][0]["image_id"] == APP_IMAGE_ID
    assert manifest["images"][0]["repo_digests"] == []


def test_worker_releases_scanner_cache_before_finalization(tmp_path: Path) -> None:
    # Given: finalization requires scanner cache space to have been reclaimed.
    output = tmp_path / "evidence"

    # When: a clean scan reaches the Python evidence boundary.
    completed = _run_worker(
        tmp_path,
        "pilot-api:test",
        mode="require-cache-release",
    )

    # Then: the exact cache is already removed and evidence completes.
    assert completed.returncode == 0, completed.stderr
    assert (output / "COMPLETE").is_file()


def test_worker_blocks_high_findings_with_complete_evidence(tmp_path: Path) -> None:
    # Given: the scanner reports one HIGH CVE for an inspected image.
    output = tmp_path / "evidence"

    # When: the image gate runs under its fixed HIGH/CRITICAL policy.
    completed = _run_worker(tmp_path, "pilot-api:test", mode="findings")

    # Then: policy blocks while complete evidence records only safe finding details.
    assert completed.returncode == 1
    assert (output / "COMPLETE").is_file()
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["outcome"] == "blocked"
    assert summary["images"][0]["high"] == 1
    assert summary["images"][0]["cves"] == ["CVE-2026-12345"]
    finding = json.loads((output / "findings.json").read_bytes())["findings"][0]
    assert finding["ImageRef"] == "pilot-api:test"
    assert finding["ImageID"] == APP_IMAGE_ID


def test_worker_fails_closed_on_scanner_operational_error(tmp_path: Path) -> None:
    # Given: image inspection works but the vulnerability scanner crashes.
    output = tmp_path / "evidence"

    # When: the public worker receives the scanner's operational exit.
    completed = _run_worker(tmp_path, "pilot-api:test", mode="operational")

    # Then: no completion claim is published and the exact cache is removed.
    assert completed.returncode == 1
    assert not (output / "COMPLETE").exists()
    calls = [json.loads(line) for line in (tmp_path / "docker.log").read_text().splitlines()]
    created = next(call[-1] for call in calls if call[:2] == ["volume", "create"])
    assert ["volume", "rm", created] in calls


def test_worker_rejects_zero_exit_without_report(tmp_path: Path) -> None:
    # Given: a misleading scanner exits zero without creating its JSON report.
    output = tmp_path / "evidence"

    # When: the worker attempts to finalize the apparent success.
    completed = _run_worker(tmp_path, "pilot-api:test", mode="zero-no-report")

    # Then: missing machine evidence prevents any completion marker.
    assert completed.returncode == 1
    assert not (output / "COMPLETE").exists()
    assert "report-001.json" in completed.stderr


def test_worker_refuses_stale_output_directory(tmp_path: Path) -> None:
    # Given: an output directory already contains evidence from an earlier run.
    output = tmp_path / "evidence"
    output.mkdir()
    sentinel = output / "keep"
    sentinel.write_text("stale", encoding="utf-8")

    # When: a new scan targets the same path.
    completed = _run_worker(tmp_path, "pilot-api:test")

    # Then: the worker refuses before Docker and preserves the prior bytes.
    assert completed.returncode == 1
    assert sentinel.read_text(encoding="utf-8") == "stale"
    assert not (tmp_path / "docker.log").exists()


def test_worker_refuses_symlink_output(tmp_path: Path) -> None:
    # Given: the requested output is a symlink to a real directory.
    target = tmp_path / "target"
    target.mkdir()
    (tmp_path / "evidence").symlink_to(target, target_is_directory=True)

    # When: the worker is invoked with that path.
    completed = _run_worker(tmp_path, "pilot-api:test")

    # Then: it fails before Docker and writes nothing through the link.
    assert completed.returncode == 1
    assert list(target.iterdir()) == []
    assert not (tmp_path / "docker.log").exists()


def test_worker_stops_multi_image_run_on_partial_failure(tmp_path: Path) -> None:
    # Given: the first image is clean and scanner operation fails on the second.
    output = tmp_path / "evidence"

    # When: three explicit images are submitted as one gate.
    completed = _run_worker(
        tmp_path,
        "pilot-api:test",
        "pilot-ai:test",
        "pilot-web:test",
        mode="partial",
    )

    # Then: partial evidence remains incomplete and the third image is untouched.
    assert completed.returncode == 1
    assert (output / "report-001.json").is_file()
    assert not (output / "COMPLETE").exists()
    calls = [json.loads(line) for line in (tmp_path / "docker.log").read_text().splitlines()]
    assert not any(call[:2] == ["image", "inspect"] and call[-1] == "pilot-web:test" for call in calls)

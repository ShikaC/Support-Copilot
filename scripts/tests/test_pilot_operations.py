"""Fake-Docker contract coverage for authenticated pilot operations.

# noqa: SIZE_OK
Cohesion: shared fake-Docker state models one verifier's resource and failure boundaries.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import stat
import subprocess
from pathlib import Path
from typing import Literal

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PILOT_SCRIPT = REPOSITORY_ROOT / "scripts/verify-pilot-operations.sh"
SHA256_ZERO = "0" * 64


def _write_executable(path: Path, content: str) -> None:
    _ = path.write_text(content, encoding="utf-8")
    _ = path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _jwt(subject: str, role: str, *, audience_as_list: bool = True) -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"none"}').rstrip(b"=").decode()
    audience: str | list[str] = (
        ["support-copilot-api"] if audience_as_list else "support-copilot-api"
    )
    claims = {
        "iss": "http://oidc:8080/default",
        "aud": audience,
        "sub": subject,
        "roles": [role],
    }
    if role == "SUPPORT_AGENT":
        claims["support_scopes"] = ["ACCOUNT"]
    payload = base64.urlsafe_b64encode(
        json.dumps(claims, separators=(",", ":")).encode()
    ).rstrip(b"=").decode()
    return f"{header}.{payload}.signature"


def _write_compatible_build_evidence(
    directory: Path,
    *,
    image_ref: str,
    image_id: str,
    revision: str,
    packaging_sha256: str,
) -> str:
    directory.mkdir()
    manifest = {
        "schema_version": 1,
        "revision": revision,
        "image_ref": image_ref,
        "image_id": image_id,
        "source_archive_sha256": "7" * 64,
        "packaging_dockerfile_sha256": packaging_sha256,
        "platform": "linux/amd64",
        "command_exit": {"git_archive": 0, "docker_build": 0, "docker_inspect": 0},
        "hash_binding": {
            "oci_revision_label": revision,
            "packaging_label": packaging_sha256,
            "source_archive_sha256": "7" * 64,
        },
    }
    manifest_path = directory / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, separators=(",", ":")) + "\n", encoding="utf-8")
    manifest_sha256 = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    (directory / "COMPLETE").write_text(
        f"manifest_sha256={manifest_sha256}\n",
        encoding="utf-8",
    )
    return manifest_sha256


def _run_resource_collision(
    tmp_path: Path,
    *,
    project: str,
    collision_fragment: str,
) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    docker_log = tmp_path / "docker.log"
    _write_executable(fake_bin / "timeout", '#!/usr/bin/env bash\nshift\nexec "$@"\n')
    _write_executable(
        fake_bin / "sha256sum",
        f"#!/usr/bin/env bash\nprintf '%s  %s\\n' '{SHA256_ZERO}' \"$1\"\n",
    )
    _write_executable(
        fake_bin / "docker",
        "\n".join(
            [
                "#!/usr/bin/env bash",
                f"printf '%s\\n' \"$*\" >> {docker_log!s}",
                f"[[ \"$*\" == *{collision_fragment!r}* ]] && printf '%s\\n' 'caller-owned-resource'",
                "exit 0",
                "",
            ]
        ),
    )
    compose_file = tmp_path / "compose.yml"
    compose_file.write_text("services: {}\n", encoding="utf-8")
    evidence_dir = tmp_path / "evidence"
    result = subprocess.run(
        [str(PILOT_SCRIPT), "--compose-file", str(compose_file), "--evidence-dir", str(evidence_dir),
         "--project", project],
        env={**os.environ, "PATH": f"{fake_bin}:/usr/bin:/bin"},
        check=False,
        capture_output=True,
        text=True,
    )
    return result, docker_log, evidence_dir


def test_legacy_verifier_delegates_to_authenticated_pilot_command(
    tmp_path: Path,
) -> None:
    # Given: the legacy entry point and an observable replacement command.
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    legacy = scripts_dir / "verify-mysql-persistence.sh"
    _ = shutil.copy2(REPOSITORY_ROOT / "scripts/verify-mysql-persistence.sh", legacy)
    invocation_log = tmp_path / "invocation.log"
    replacement = scripts_dir / "verify-pilot-operations.sh"
    _write_executable(
        replacement,
        f"#!/usr/bin/env bash\nprintf '%s\\n' \"$*\" > {invocation_log!s}\nexit 37\n",
    )

    # When: a caller uses the preserved command with arguments.
    result = subprocess.run(
        [str(legacy), "--evidence-dir", "/tmp/task-15-evidence"],
        env={**os.environ, "PATH": "/usr/bin:/bin"},
        check=False,
        capture_output=True,
        text=True,
    )

    # Then: delegation is exact and the replacement failure is not hidden.
    assert result.returncode == 37
    assert invocation_log.read_text(encoding="utf-8").strip() == (
        "--evidence-dir /tmp/task-15-evidence"
    )


def test_pilot_verifier_uses_mounted_secret_for_oidc_client_authentication() -> None:
    # Given/When: the real token acquisition function is inspected as an operations contract.
    source = PILOT_SCRIPT.read_text(encoding="utf-8")

    # Then: client credentials use a run-scoped mounted secret and fail before JWT parsing.
    assert 'Path("/run/secrets/internal_service_token").read_text' in source
    assert 'auth=(sys.argv[1], client_secret)' in source
    assert 'data={"grant_type": "client_credentials"}' in source
    assert 'payload["aud"] == "support-copilot-api" or payload["aud"] == ["support-copilot-api"]' in source
    assert 'payload.get("support_scopes", []) == expected_scopes' in source
    assert '"subject":"Enterprise SSO login loop"' in source
    assert "exec -T api timeout 15 bash -ceu" in source
    assert "/dev/tcp/ai/8000" in source
    assert ')" || return 1\n  python3 -c' in source
    assert "--header @-" in source
    assert "Authorization: Bearer $" not in source
    assert "io.support-copilot.run-ownership" in source
    assert "down --volumes" not in source


def test_pilot_verifier_rejects_stale_evidence_before_docker(tmp_path: Path) -> None:
    # Given: a path that already contains evidence from another attempt.
    evidence_dir = tmp_path / "stale"
    evidence_dir.mkdir()

    # When: a new pilot verification targets that path.
    result = subprocess.run(
        [str(PILOT_SCRIPT), "--evidence-dir", str(evidence_dir)],
        env={**os.environ, "PATH": "/usr/bin:/bin"},
        check=False,
        capture_output=True,
        text=True,
    )

    # Then: it fails closed without requiring Docker.
    assert result.returncode != 0
    assert "must not already exist" in result.stderr


def test_pilot_verifier_rejects_primary_resource_collision_without_cleanup(
    tmp_path: Path,
) -> None:
    # Given: a caller-owned container already carries the requested primary project label.
    result, docker_log, evidence_dir = _run_resource_collision(
        tmp_path,
        project="primary-collision",
        collision_fragment="ps -aq --filter label=com.docker.compose.project=primary-collision",
    )

    # When/Then: preflight rejects it without creating verifier state or mutating Docker.
    assert result.returncode != 0
    assert "primary project already owns resources" in result.stderr
    assert not evidence_dir.exists()
    calls = docker_log.read_text(encoding="utf-8")
    assert "primary-collision-restore" not in calls
    assert " compose " not in calls
    assert " down " not in calls
    assert " tag " not in calls
    assert "image rm" not in calls


def test_pilot_verifier_rejects_restore_resource_collision_without_cleanup(
    tmp_path: Path,
) -> None:
    # Given: a caller-owned volume already carries the derived restore project label.
    result, docker_log, evidence_dir = _run_resource_collision(
        tmp_path,
        project="restore-collision",
        collision_fragment="volume ls -q --filter label=com.docker.compose.project=restore-collision-restore",
    )

    # When/Then: both project checks are read-only and restore collision triggers no cleanup.
    assert result.returncode != 0
    assert "restore project already owns resources" in result.stderr
    assert not evidence_dir.exists()
    calls = docker_log.read_text(encoding="utf-8")
    assert "label=com.docker.compose.project=restore-collision" in calls
    assert "label=com.docker.compose.project=restore-collision-restore" in calls
    assert " compose " not in calls
    assert " down " not in calls
    assert " tag " not in calls
    assert "image rm" not in calls


def test_pilot_verifier_preserves_mixed_preflight_resource_results(
    tmp_path: Path,
) -> None:
    # Given: primary preflight observes a container, a failed network query, and no volume.
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    docker_log = tmp_path / "docker.log"
    _write_executable(fake_bin / "timeout", '#!/usr/bin/env bash\nshift\nexec "$@"\n')
    _write_executable(fake_bin / "sha256sum", "#!/usr/bin/env bash\nexit 0\n")
    _write_executable(
        fake_bin / "docker",
        f"""#!/usr/bin/env bash
printf '%s\n' "$*" >> {docker_log!s}
case "$*" in
  'ps -aq --filter label=com.docker.compose.project=mixed-preflight') printf '%s\n' 'existing-container' ;;
  'network ls -q --filter label=com.docker.compose.project=mixed-preflight') printf '%s\n' 'partial-network-output'; exit 72 ;;
  'volume ls -q --filter label=com.docker.compose.project=mixed-preflight') : ;;
esac
""",
    )
    compose_file = tmp_path / "compose.yml"
    _ = compose_file.write_text("services: {}\n", encoding="utf-8")
    evidence_dir = tmp_path / "evidence"

    # When: all three read-only collision queries run through the public CLI.
    result = subprocess.run(
        [
            str(PILOT_SCRIPT),
            "--compose-file",
            str(compose_file),
            "--evidence-dir",
            str(evidence_dir),
            "--project",
            "mixed-preflight",
        ],
        env={**os.environ, "PATH": f"{fake_bin}:/usr/bin:/bin"},
        check=False,
        capture_output=True,
        text=True,
    )

    # Then: failure evidence retains every output/status and no mutation starts.
    assert result.returncode == 2
    receipt_lines = [
        line.removeprefix("resource_inspection=")
        for line in result.stderr.splitlines()
        if line.startswith("resource_inspection=")
    ]
    assert [json.loads(line) for line in receipt_lines] == [
        {
            "phase": "preflight",
            "project": "mixed-preflight",
            "containers": {"inspectExit": 0, "stdout": "existing-container"},
            "networks": {"inspectExit": 72, "stdout": "partial-network-output"},
            "volumes": {"inspectExit": 0, "stdout": ""},
        }
    ]
    calls = docker_log.read_text(encoding="utf-8")
    assert "ps -aq --filter label=com.docker.compose.project=mixed-preflight" in calls
    assert "network ls -q --filter label=com.docker.compose.project=mixed-preflight" in calls
    assert "volume ls -q --filter label=com.docker.compose.project=mixed-preflight" in calls
    for mutation in (" compose ", " down ", " tag ", "image rm"):
        assert mutation not in calls
    assert not evidence_dir.exists()


def test_pilot_verifier_rejects_primary_latest_tag_in_default_build_mode(
    tmp_path: Path,
) -> None:
    # Given: default mode encounters a caller-owned primary API latest tag.
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    docker_log = tmp_path / "docker.log"
    _write_executable(fake_bin / "timeout", '#!/usr/bin/env bash\nshift\nexec "$@"\n')
    _write_executable(fake_bin / "sha256sum", "#!/usr/bin/env bash\nexit 0\n")
    _write_executable(
        fake_bin / "docker",
        "\n".join(
            [
                "#!/usr/bin/env bash",
                f"printf '%s\\n' \"$*\" >> {docker_log!s}",
                f"[[ \"$*\" == *'image ls --quiet --no-trunc tag-collision-api:latest' ]] && printf '%s\\n' \"sha256:{'a' * 64}\"",
                "exit 0",
                "",
            ]
        ),
    )
    compose_file = tmp_path / "compose.yml"
    compose_file.write_text("services: {}\n", encoding="utf-8")
    evidence_dir = tmp_path / "evidence"

    # When: the public command performs ownership preflight.
    result = subprocess.run(
        [str(PILOT_SCRIPT), "--compose-file", str(compose_file), "--evidence-dir", str(evidence_dir),
         "--project", "tag-collision"],
        env={**os.environ, "PATH": f"{fake_bin}:/usr/bin:/bin"},
        check=False,
        capture_output=True,
        text=True,
    )

    # Then: the tag is preserved and no verifier mutation or cleanup occurs.
    assert result.returncode != 0
    assert "image reference already exists" in result.stderr
    assert not evidence_dir.exists()
    calls = docker_log.read_text(encoding="utf-8")
    assert " compose " not in calls
    assert " tag " not in calls
    assert "image rm" not in calls


@pytest.mark.parametrize(
    "occupied_ref",
    [
        "owned-tags-api:known-good",
        "owned-tags-ai:known-good",
        "owned-tags-web:known-good",
        "owned-tags-restore-api:latest",
        "owned-tags-restore-ai:latest",
        "owned-tags-restore-web:latest",
    ],
)
def test_pilot_verifier_rejects_verifier_owned_tag_collision_before_mutation(
    tmp_path: Path,
    occupied_ref: str,
) -> None:
    # Given: one verifier-owned known-good or restore tag already exists.
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    docker_log = tmp_path / "docker.log"
    _write_executable(fake_bin / "timeout", '#!/usr/bin/env bash\nshift\nexec "$@"\n')
    _write_executable(fake_bin / "sha256sum", "#!/usr/bin/env bash\nexit 0\n")
    _write_executable(
        fake_bin / "docker",
        "\n".join(
            [
                "#!/usr/bin/env bash",
                f"printf '%s\\n' \"$*\" >> {docker_log!s}",
                f"[[ \"$*\" == *'image ls --quiet --no-trunc {occupied_ref}' ]] && printf '%s\\n' \"sha256:{'d' * 64}\"",
                "exit 0",
                "",
            ]
        ),
    )
    compose_file = tmp_path / "compose.yml"
    compose_file.write_text("services: {}\n", encoding="utf-8")
    evidence_dir = tmp_path / "evidence"

    # When: ownership preflight reaches the occupied reference.
    result = subprocess.run(
        [str(PILOT_SCRIPT), "--compose-file", str(compose_file), "--evidence-dir", str(evidence_dir),
         "--project", "owned-tags"],
        env={**os.environ, "PATH": f"{fake_bin}:/usr/bin:/bin"},
        check=False,
        capture_output=True,
        text=True,
    )

    # Then: no project resources or image tags are changed.
    assert result.returncode != 0
    assert occupied_ref in result.stderr
    assert not evidence_dir.exists()
    calls = docker_log.read_text(encoding="utf-8")
    assert " compose " not in calls
    assert " tag " not in calls
    assert "image rm" not in calls


def test_pilot_verifier_has_no_mutable_restore_oidc_reference() -> None:
    source = PILOT_SCRIPT.read_text(encoding="utf-8")

    assert "RESTORE_OIDC_REFERENCE" not in source
    assert '"$RESTORE_PROJECT-oidc:latest"' not in source
    assert 'export SUPPORT_COPILOT_OIDC_IMAGE="$RESTORE_OIDC_IMAGE_ID"' in source
    assert '"referenceKind": "immutableLocalImageId"' in source


def test_pilot_verifier_rejects_previous_image_aliasing_owned_project_ref(
    tmp_path: Path,
) -> None:
    # Given: the previous-image input aliases a primary latest reference owned by the run.
    compose_file = tmp_path / "compose.yml"
    compose_file.write_text("services: {}\n", encoding="utf-8")
    evidence_dir = tmp_path / "compatible-build"
    previous_revision = ("1234567890abcdef" * 2) + "12345678"

    # When: argument preflight parses all three rollback inputs.
    result = subprocess.run(
        [str(PILOT_SCRIPT), "--compose-file", str(compose_file), "--project", "alias-pilot",
         "--previous-api-image", "alias-pilot-api:latest",
         "--previous-api-revision", previous_revision,
         "--previous-api-build-evidence", str(evidence_dir)],
        env={**os.environ, "PATH": "/usr/bin:/bin"},
        check=False,
        capture_output=True,
        text=True,
    )

    # Then: aliasing is rejected before Docker or evidence access is required.
    assert result.returncode != 0
    assert "aliases a verifier-owned project image reference" in result.stderr


def test_pilot_verifier_requires_previous_image_revision_and_build_evidence_together(
    tmp_path: Path,
) -> None:
    # Given: only one half of the previous-image identity is supplied.
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    docker_log = tmp_path / "docker.log"
    _write_executable(
        fake_bin / "docker",
        f"#!/usr/bin/env bash\nprintf '%s\\n' \"$*\" >> {docker_log!s}\n",
    )
    compose_file = tmp_path / "compose.yml"
    _ = compose_file.write_text("services: {}\n", encoding="utf-8")

    # When: the public CLI parses the incomplete pair.
    result = subprocess.run(
        [
            str(PILOT_SCRIPT),
            "--compose-file",
            str(compose_file),
            "--project",
            "pair-pilot",
            "--previous-api-image",
            "support-copilot-api:previous",
        ],
        env={**os.environ, "PATH": f"{fake_bin}:/usr/bin:/bin"},
        check=False,
        capture_output=True,
        text=True,
    )

    # Then: validation fails before any Docker read or mutation.
    assert result.returncode != 0
    assert "must be supplied together" in result.stderr
    assert not docker_log.exists()


def test_pilot_verifier_rejects_unsafe_previous_revision_before_docker(
    tmp_path: Path,
) -> None:
    # Given: a revision value unsuitable for durable source evidence.
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    docker_log = tmp_path / "docker.log"
    _write_executable(
        fake_bin / "docker",
        f"#!/usr/bin/env bash\nprintf '%s\\n' \"$*\" >> {docker_log!s}\n",
    )
    compose_file = tmp_path / "compose.yml"
    _ = compose_file.write_text("services: {}\n", encoding="utf-8")

    # When: the paired flags contain a non-commit revision.
    result = subprocess.run(
        [
            str(PILOT_SCRIPT),
            "--compose-file",
            str(compose_file),
            "--project",
            "revision-pilot",
            "--previous-api-image",
            "support-copilot-api:previous",
            "--previous-api-revision",
            "not a revision",
            "--previous-api-build-evidence",
            str(tmp_path / "compatible-build"),
        ],
        env={**os.environ, "PATH": f"{fake_bin}:/usr/bin:/bin"},
        check=False,
        capture_output=True,
        text=True,
    )

    # Then: validation fails before Docker can inspect or mutate anything.
    assert result.returncode != 0
    assert "previous API revision" in result.stderr
    assert not docker_log.exists()


def test_pilot_verifier_rejects_mismatched_previous_image_revision(
    tmp_path: Path,
) -> None:
    # Given: an existing image whose OCI revision label names another commit.
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    docker_log = tmp_path / "docker.log"
    _write_executable(fake_bin / "timeout", '#!/usr/bin/env bash\nshift\nexec "$@"\n')
    _write_executable(
        fake_bin / "sha256sum",
        f"#!/usr/bin/env bash\nprintf '%s  %s\\n' '{SHA256_ZERO}' \"$1\"\n",
    )
    _write_executable(
        fake_bin / "docker",
        "\n".join(
            [
                "#!/usr/bin/env bash",
                f"printf '%s\\n' \"$*\" >> {docker_log!s}",
                "case \"$*\" in",
                f"  *'io.support-copilot.packaging-dockerfile-sha256'*'sha256:{'a' * 64}'*) printf '%s\\n' \"linux/amd64|sha256:{'a' * 64}|linux|amd64|{'1' * 40}|{SHA256_ZERO}\" ;;",
                f"  *'image inspect --format {{{{.Id}}}} support-copilot-api:previous'*) printf '%s\\n' \"sha256:{'a' * 64}\" ;;",
                f"  *'image inspect --format {{{{.Os}}}}/{{{{.Architecture}}}}|{{{{.Id}}}} sha256:{'a' * 64}'*) printf '%s\\n' \"linux/amd64|sha256:{'a' * 64}\" ;;",
                f"  *'image inspect --format {{{{.Id}}}} sha256:{'a' * 64}'*) printf '%s\\n' \"sha256:{'a' * 64}\" ;;",
                "esac",
                "",
            ]
        ),
    )
    compose_file = tmp_path / "compose.yml"
    _ = compose_file.write_text("services: {}\n", encoding="utf-8")
    evidence_dir = tmp_path / "evidence"
    build_evidence = tmp_path / "compatible-build"
    _write_compatible_build_evidence(
        build_evidence,
        image_ref="support-copilot-api:previous",
        image_id=f"sha256:{'a' * 64}",
        revision="2222222222222222222222222222222222222222",
        packaging_sha256=SHA256_ZERO,
    )

    # When: preflight compares the label to the expected revision.
    result = subprocess.run(
        [
            str(PILOT_SCRIPT),
            "--compose-file",
            str(compose_file),
            "--evidence-dir",
            str(evidence_dir),
            "--project",
            "mismatch-pilot",
            "--previous-api-image",
            "support-copilot-api:previous",
            "--previous-api-revision",
            "2222222222222222222222222222222222222222",
            "--previous-api-build-evidence",
            str(build_evidence),
        ],
        env={**os.environ, "PATH": f"{fake_bin}:/usr/bin:/bin"},
        check=False,
        capture_output=True,
        text=True,
    )

    # Then: the mismatch is rejected and Compose is never invoked.
    assert result.returncode != 0
    assert "revision label does not match" in result.stderr
    assert " compose " not in docker_log.read_text(encoding="utf-8")
    assert not evidence_dir.exists()


@pytest.mark.parametrize("defect", ["complete-sha", "stale", "extra-field", "packaging"])
def test_pilot_verifier_rejects_invalid_previous_build_evidence_before_mutation(
    tmp_path: Path,
    defect: str,
) -> None:
    # Given: the previous image exists, but its helper evidence violates one acceptance rule.
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    docker_log = tmp_path / "docker.log"
    previous_id = f"sha256:{'a' * 64}"
    revision = "1234567890abcdef1234567890abcdef12345678"
    _write_executable(fake_bin / "timeout", '#!/usr/bin/env bash\nshift\nexec "$@"\n')
    _write_executable(
        fake_bin / "sha256sum",
        f"#!/usr/bin/env bash\nprintf '%s  %s\\n' '{SHA256_ZERO}' \"$1\"\n",
    )
    _write_executable(
        fake_bin / "docker",
        "\n".join(
            [
                "#!/usr/bin/env bash",
                f"printf '%s\\n' \"$*\" >> {docker_log!s}",
                "case \"$*\" in",
                f"  *'image inspect --format {{{{.Id}}}} support-copilot-api:previous'*) printf '%s\\n' '{previous_id}' ;;",
                "esac",
                "exit 0",
                "",
            ]
        ),
    )
    compose_file = tmp_path / "compose.yml"
    compose_file.write_text("services: {}\n", encoding="utf-8")
    build_evidence = tmp_path / "compatible-build"
    _write_compatible_build_evidence(
        build_evidence,
        image_ref="support-copilot-api:previous",
        image_id=previous_id,
        revision=revision,
        packaging_sha256="8" * 64 if defect == "packaging" else SHA256_ZERO,
    )
    if defect == "complete-sha":
        (build_evidence / "COMPLETE").write_text(f"manifest_sha256={'f' * 64}\n", encoding="utf-8")
    elif defect == "stale":
        os.utime(build_evidence / "manifest.json", (1, 1))
        os.utime(build_evidence / "COMPLETE", (2, 2))
    elif defect == "extra-field":
        manifest_path = build_evidence / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["unexpected"] = True
        manifest_path.write_text(json.dumps(manifest, separators=(",", ":")) + "\n", encoding="utf-8")
        (build_evidence / "COMPLETE").write_text(
            f"manifest_sha256={hashlib.sha256(manifest_path.read_bytes()).hexdigest()}\n",
            encoding="utf-8",
        )

    # When: rollback provenance is validated before verifier mutation.
    evidence_dir = tmp_path / "operations-evidence"
    result = subprocess.run(
        [str(PILOT_SCRIPT), "--compose-file", str(compose_file), "--evidence-dir", str(evidence_dir),
         "--project", "evidence-pilot", "--previous-api-image", "support-copilot-api:previous",
         "--previous-api-revision", revision, "--previous-api-build-evidence", str(build_evidence)],
        env={**os.environ, "PATH": f"{fake_bin}:/usr/bin:/bin"},
        check=False,
        capture_output=True,
        text=True,
    )

    # Then: no output directory, Compose call, tag, or cleanup mutation is possible.
    assert result.returncode != 0
    assert "build evidence" in result.stderr
    assert not evidence_dir.exists()
    calls = docker_log.read_text(encoding="utf-8")
    assert " compose " not in calls
    assert " tag " not in calls
    assert "image rm" not in calls


def test_pilot_verifier_rejects_missing_prebuilt_current_image_before_compose(
    tmp_path: Path,
) -> None:
    # Given: only two of the three exact project image tags exist.
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    docker_log = tmp_path / "docker.log"
    _write_executable(fake_bin / "timeout", '#!/usr/bin/env bash\nshift\nexec "$@"\n')
    _write_executable(fake_bin / "sha256sum", "#!/usr/bin/env bash\nexit 0\n")
    _write_executable(
        fake_bin / "docker",
        "\n".join(
            [
                "#!/usr/bin/env bash",
                f"printf '%s\\n' \"$*\" >> {docker_log!s}",
                "case \"${*: -1}\" in",
                f"  prebuilt-pilot-api:latest) printf '%s\\n' \"sha256:{'a' * 64}\" ;;",
                f"  prebuilt-pilot-ai:latest) printf '%s\\n' \"sha256:{'b' * 64}\" ;;",
                f"  prebuilt-pilot-mysql:latest) printf '%s\\n' \"sha256:{'d' * 64}\" ;;",
                f"  prebuilt-pilot-oidc:latest) printf '%s\\n' \"sha256:{'e' * 64}\" ;;",
                f"  sha256:{'a' * 64}) printf '%s\\n' \"linux/amd64|sha256:{'a' * 64}\" ;;",
                f"  sha256:{'b' * 64}) printf '%s\\n' \"linux/amd64|sha256:{'b' * 64}\" ;;",
                f"  sha256:{'d' * 64}) printf '%s\\n' \"linux/amd64|sha256:{'d' * 64}\" ;;",
                f"  sha256:{'e' * 64}) printf '%s\\n' \"linux/amd64|sha256:{'e' * 64}\" ;;",
                "  prebuilt-pilot-web:latest) exit 1 ;;",
                "esac",
                "",
            ]
        ),
    )
    compose_file = tmp_path / "compose.yml"
    _ = compose_file.write_text("services: {}\n", encoding="utf-8")
    evidence_dir = tmp_path / "evidence"

    # When: prebuilt-current mode validates its complete image set.
    result = subprocess.run(
        [str(PILOT_SCRIPT), "--compose-file", str(compose_file), "--evidence-dir", str(evidence_dir),
         "--project", "prebuilt-pilot", "--use-prebuilt-current-images"],
        env={**os.environ, "PATH": f"{fake_bin}:/usr/bin:/bin"},
        check=False,
        capture_output=True,
        text=True,
    )

    # Then: it fails before Compose or evidence mutation.
    assert result.returncode != 0
    assert "prebuilt current image is missing" in result.stderr
    assert " compose " not in docker_log.read_text(encoding="utf-8")
    assert not evidence_dir.exists()


def test_pilot_verifier_starts_with_no_build_for_prebuilt_current_images(
    tmp_path: Path,
) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    docker_log = tmp_path / "docker.log"
    _write_executable(
        fake_bin / "timeout",
        '#!/usr/bin/env bash\nshift\nexec "$@"\n',
    )
    _write_executable(fake_bin / "sha256sum", "#!/usr/bin/env bash\nexit 0\n")
    _write_executable(
        fake_bin / "docker",
        "\n".join(
            [
                "#!/usr/bin/env bash",
                f"printf '%s\\n' \"$*\" >> {docker_log!s}",
                "[[ \"$*\" == *'up --no-build --detach --wait'* ]] && exit 124",
                "case \"${*: -1}\" in",
                f"  prebuilt-start-mysql:latest) printf '%s\\n' \"sha256:{'d' * 64}\" ;;",
                f"  prebuilt-start-oidc:latest) printf '%s\\n' \"sha256:{'e' * 64}\" ;;",
                f"  prebuilt-start-api:latest) printf '%s\\n' \"sha256:{'a' * 64}\" ;;",
                f"  prebuilt-start-ai:latest) printf '%s\\n' \"sha256:{'b' * 64}\" ;;",
                f"  prebuilt-start-web:latest) printf '%s\\n' \"sha256:{'c' * 64}\" ;;",
                f"  sha256:{'a' * 64}) printf '%s\\n' \"linux/amd64|sha256:{'a' * 64}\" ;;",
                f"  sha256:{'b' * 64}) printf '%s\\n' \"linux/amd64|sha256:{'b' * 64}\" ;;",
                f"  sha256:{'c' * 64}) printf '%s\\n' \"linux/amd64|sha256:{'c' * 64}\" ;;",
                f"  sha256:{'d' * 64}) printf '%s\\n' \"linux/amd64|sha256:{'d' * 64}\" ;;",
                f"  sha256:{'e' * 64}) printf '%s\\n' \"linux/amd64|sha256:{'e' * 64}\" ;;",
                "esac",
                "",
            ]
        ),
    )
    compose_file = tmp_path / "compose.yml"
    _ = compose_file.write_text("services: {}\n", encoding="utf-8")
    evidence_dir = tmp_path / "evidence"

    # When: startup reaches the observable timeout boundary.
    result = subprocess.run(
        [str(PILOT_SCRIPT), "--compose-file", str(compose_file), "--evidence-dir", str(evidence_dir),
         "--project", "prebuilt-start", "--use-prebuilt-current-images"],
        env={**os.environ, "PATH": f"{fake_bin}:/usr/bin:/bin"},
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )

    # Then: startup is explicitly no-build and the resolved IDs are recorded.
    assert result.returncode == 124
    calls = docker_log.read_text(encoding="utf-8")
    assert " up --no-build --detach --wait" in calls
    assert " up --build --detach --wait" not in calls
    assert json.loads((evidence_dir / "prebuilt-current-images.json").read_text(encoding="utf-8")) == {
        "mysql": {
            "reference": "prebuilt-start-mysql:latest",
            "imageId": f"sha256:{'d' * 64}",
            "platformImageId": f"sha256:{'d' * 64}",
        },
        "oidc": {
            "reference": "prebuilt-start-oidc:latest",
            "imageId": f"sha256:{'e' * 64}",
            "platformImageId": f"sha256:{'e' * 64}",
        },
        "api": {
            "reference": "prebuilt-start-api:latest",
            "imageId": f"sha256:{'a' * 64}",
            "platformImageId": f"sha256:{'a' * 64}",
        },
        "ai": {
            "reference": "prebuilt-start-ai:latest",
            "imageId": f"sha256:{'b' * 64}",
            "platformImageId": f"sha256:{'b' * 64}",
        },
        "web": {
            "reference": "prebuilt-start-web:latest",
            "imageId": f"sha256:{'c' * 64}",
            "platformImageId": f"sha256:{'c' * 64}",
        },
    }
    for service, image_id in (("mysql", "d"), ("oidc", "e"), ("api", "a"), ("ai", "b"), ("web", "c")):
        reference = f"prebuilt-start-{service}:latest"
        assert f"tag sha256:{image_id * 64} {reference}" not in calls
        assert f"image rm {reference}" not in calls
    cleanup_receipt = (evidence_dir / "cleanup-receipt.log").read_text(encoding="utf-8")
    assert cleanup_receipt.count("prebuilt_reference_verified=") == 5
    assert "prebuilt_primary_tags_verified=true" in cleanup_receipt


def test_pilot_verifier_removes_owned_secret_directory_when_generation_fails(
    tmp_path: Path,
) -> None:
    # Given: secret generation succeeds once, then fails before Compose is invoked.
    fake_bin = tmp_path / "bin"
    secret_parent = tmp_path / "secret-parent"
    fake_bin.mkdir()
    secret_parent.mkdir()
    caller_owned_dir = secret_parent / "caller-owned"
    caller_owned_dir.mkdir()
    caller_owned_marker = caller_owned_dir / "keep"
    _ = caller_owned_marker.write_text("preserve\n", encoding="utf-8")
    docker_log = tmp_path / "docker.log"
    secret_path_log = tmp_path / "secret-path.log"
    openssl_count = tmp_path / "openssl-count"
    _write_executable(fake_bin / "timeout", '#!/usr/bin/env bash\nshift\nexec "$@"\n')
    _write_executable(fake_bin / "sha256sum", "#!/usr/bin/env bash\nexit 0\n")
    _write_executable(
        fake_bin / "docker",
        f"#!/usr/bin/env bash\nprintf '%s\\n' \"$*\" >> {docker_log!s}\nexit 0\n",
    )
    _write_executable(
        fake_bin / "openssl",
        """#!/usr/bin/env bash
count=$(cat "$FAKE_OPENSSL_COUNT" 2>/dev/null || printf 0)
count=$((count + 1))
printf '%s' "$count" >"$FAKE_OPENSSL_COUNT"
shopt -s nullglob
secret_dirs=("$TMPDIR"/support-copilot-task15-secrets.*)
[[ ${#secret_dirs[@]} -eq 1 ]] || exit 98
printf '%s\n' "${secret_dirs[0]}" >"$FAKE_SECRET_PATH_LOG"
[[ "$count" -ne 2 ]] || exit 55
printf '%s\n' 'synthetic-secret'
""",
    )
    compose_file = tmp_path / "compose.yml"
    _ = compose_file.write_text("services: {}\n", encoding="utf-8")
    evidence_dir = tmp_path / "evidence"

    # When: the verifier reaches the failing second secret write.
    result = subprocess.run(
        [str(PILOT_SCRIPT), "--compose-file", str(compose_file), "--evidence-dir", str(evidence_dir),
         "--project", "secret-failure"],
        env={**os.environ, "PATH": f"{fake_bin}:/usr/bin:/bin", "TMPDIR": str(secret_parent),
             "FAKE_OPENSSL_COUNT": str(openssl_count), "FAKE_SECRET_PATH_LOG": str(secret_path_log)},
        check=False,
        capture_output=True,
        text=True,
    )

    # Then: only the exact owned temporary directory is removed and Compose is untouched.
    assert result.returncode == 55
    secret_path = Path(secret_path_log.read_text(encoding="utf-8").strip())
    assert secret_path.parent == secret_parent
    assert secret_path.name.startswith("support-copilot-task15-secrets.")
    assert not secret_path.exists()
    assert caller_owned_marker.read_text(encoding="utf-8") == "preserve\n"
    calls = docker_log.read_text(encoding="utf-8")
    assert " compose " not in calls
    assert " down " not in calls


def test_pilot_verifier_propagates_compose_timeout_without_stale_success(
    tmp_path: Path,
) -> None:
    # Given: GNU timeout reports 124 only for the topology startup command.
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_executable(
        fake_bin / "timeout",
        """#!/usr/bin/env bash
shift
if [[ "$*" == *' compose '*' up --build --detach --wait' ]]; then exit 124; fi
exec "$@"
""",
    )
    _write_executable(fake_bin / "docker", "#!/usr/bin/env bash\nexit 0\n")
    _write_executable(fake_bin / "sha256sum", "#!/usr/bin/env bash\nexit 0\n")
    compose_file = tmp_path / "compose.yml"
    _ = compose_file.write_text("services: {}\n", encoding="utf-8")
    evidence_dir = tmp_path / "evidence"

    # When: startup reaches its exact timeout boundary.
    result = subprocess.run(
        [
            str(PILOT_SCRIPT),
            "--compose-file",
            str(compose_file),
            "--evidence-dir",
            str(evidence_dir),
            "--project",
            "timeout-pilot",
        ],
        env={**os.environ, "PATH": f"{fake_bin}:/usr/bin:/bin"},
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )

    # Then: timeout remains distinguishable from a runtime failure or success.
    assert result.returncode == 124
    assert not (evidence_dir / "operations-result.json").exists()


def test_pilot_verifier_rejects_health_only_fake_and_cleans_exact_projects(
    tmp_path: Path,
) -> None:
    # Given: external commands that claim health but never return business IDs.
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    docker_log = tmp_path / "docker.log"
    _write_executable(
        fake_bin / "timeout",
        '#!/usr/bin/env bash\nshift\nexec "$@"\n',
    )
    _write_executable(
        fake_bin / "docker",
        "\n".join(
            [
                "#!/usr/bin/env bash",
                f"printf '%s\\n' \"$*\" >> {docker_log!s}",
                'case "$*" in',
                "  'image inspect --help') printf '%s\\n' 'Usage: docker image inspect' ;;",
                f"  *'exec -T ai python - build-artifact'*) printf '%s\\n' '{{\"artifactId\":\"{'b' * 64}\",\"rows\":3}}' ;;",
                f"  *'exec -T ai python - inspect-artifact'*) printf '%s\\n' '{{\"artifactId\":\"{'b' * 64}\",\"manifestPath\":\"{'b' * 64}/manifest.json\",\"manifestSha256\":\"{'c' * 64}\"}}' ;;",
                f"  *'exec -T ai python - support-copilot-agent'*) printf '%s\\n' '{_jwt('pilot-agent', 'SUPPORT_AGENT')}' ;;",
                f"  *'exec -T ai python - support-copilot-reviewer'*) printf '%s\\n' '{_jwt('pilot-reviewer', 'SUPPORT_REVIEWER')}' ;;",
                f"  *'exec -T ai python - support-copilot-admin'*) printf '%s\\n' '{_jwt('pilot-admin', 'SUPPORT_ADMIN')}' ;;",
                f"  *'image inspect --format {{{{.Id}}}} fake-pilot-api:latest'*) printf '%s\\n' 'sha256:{'a' * 64}' ;;",
                f"  *'image inspect --format {{{{.Id}}}} fake-pilot-ai:latest'*) printf '%s\\n' 'sha256:{'b' * 64}' ;;",
                f"  *'image inspect --format {{{{.Id}}}} fake-pilot-web:latest'*) printf '%s\\n' 'sha256:{'c' * 64}' ;;",
                f"  *'image inspect --format {{{{.Id}}}} fake-pilot-mysql:latest'*) printf '%s\\n' 'sha256:{'d' * 64}' ;;",
                f"  *'image inspect --format {{{{.Id}}}} fake-pilot-oidc:latest'*) printf '%s\\n' 'sha256:{'e' * 64}' ;;",
                f"  *'image inspect --format {{{{.Os}}}}/{{{{.Architecture}}}}|{{{{.Id}}}} sha256:{'a' * 64}'*) printf '%s\\n' 'linux/amd64|sha256:{'a' * 64}' ;;",
                f"  *'image inspect --format {{{{.Os}}}}/{{{{.Architecture}}}}|{{{{.Id}}}} sha256:{'b' * 64}'*) printf '%s\\n' 'linux/amd64|sha256:{'b' * 64}' ;;",
                f"  *'image inspect --format {{{{.Os}}}}/{{{{.Architecture}}}}|{{{{.Id}}}} sha256:{'c' * 64}'*) printf '%s\\n' 'linux/amd64|sha256:{'c' * 64}' ;;",
                f"  *'image inspect --format {{{{.Os}}}}/{{{{.Architecture}}}}|{{{{.Id}}}} sha256:{'d' * 64}'*) printf '%s\\n' 'linux/amd64|sha256:{'d' * 64}' ;;",
                f"  *'image inspect --format {{{{.Os}}}}/{{{{.Architecture}}}}|{{{{.Id}}}} sha256:{'e' * 64}'*) printf '%s\\n' 'linux/amd64|sha256:{'e' * 64}' ;;",
                "  *' ps -q mysql'*) printf '%s\\n' 'fake-mysql-container' ;;",
                f"  *'inspect --format {{{{.Image}}}} fake-mysql-container'*) printf '%s\\n' 'sha256:{'d' * 64}' ;;",
                "  *' ps -q oidc'*) printf '%s\\n' 'fake-oidc-container' ;;",
                f"  *'inspect --format {{{{.Image}}}} fake-oidc-container'*) printf '%s\\n' 'sha256:{'e' * 64}' ;;",
                "esac",
                "",
            ]
        ),
    )
    _write_executable(
        fake_bin / "curl",
        """#!/usr/bin/env bash
output=''
while [[ $# -gt 0 ]]; do
  if [[ "$1" == '--output' ]]; then output="$2"; shift 2; else shift; fi
done
if [[ -n "$output" ]]; then printf '%s\\n' '{"status":"up"}' >"$output"; printf 200; fi
""",
    )
    _write_executable(fake_bin / "sha256sum", "#!/usr/bin/env bash\nexit 1\n")
    compose_file = tmp_path / "compose.yml"
    _ = compose_file.write_text("services: {}\n", encoding="utf-8")
    evidence_dir = tmp_path / "evidence"

    # When: the full verifier is driven through its public CLI.
    result = subprocess.run(
        [
            str(PILOT_SCRIPT),
            "--compose-file",
            str(compose_file),
            "--evidence-dir",
            str(evidence_dir),
            "--project",
            "fake-pilot",
        ],
        env={**os.environ, "PATH": f"{fake_bin}:/usr/bin:/bin"},
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )

    # Then: status-only output cannot pass and cleanup is exact and non-destructive.
    assert result.returncode != 0
    assert not (evidence_dir / "operations-result.json").exists()
    calls = docker_log.read_text(encoding="utf-8")
    assert calls.count("--project-name fake-pilot ") >= 1
    assert calls.count("--project-name fake-pilot-restore ") >= 1
    assert " down --volumes --remove-orphans" not in calls
    assert "label=io.support-copilot.run-ownership=" in calls
    assert "exec -T ai python - support-copilot-agent" in calls
    assert "exec -T ai python - support-copilot-reviewer" in calls
    assert "exec -T ai python - support-copilot-admin" in calls
    assert "exec -T oidc" not in calls
    assert "prune" not in calls
    for token in (
        _jwt("pilot-agent", "SUPPORT_AGENT"),
        _jwt("pilot-reviewer", "SUPPORT_REVIEWER"),
        _jwt("pilot-admin", "SUPPORT_ADMIN"),
    ):
        assert token not in result.stdout
        assert token not in result.stderr
    cleanup = (evidence_dir / "cleanup-receipt.log").read_text(encoding="utf-8")
    assert "project_absent=fake-pilot" in cleanup
    assert "project_absent=fake-pilot-restore" in cleanup


@pytest.mark.parametrize(
    ("platform_mode", "container_api_image", "container_oidc_image", "expected_error"),
    [
        ("manifest", f"sha256:{'1' * 64}", f"sha256:{'5' * 64}", None),
        ("legacy", f"sha256:{'a' * 64}", f"sha256:{'e' * 64}", None),
        ("legacy-wrong-platform", f"sha256:{'a' * 64}", f"sha256:{'e' * 64}", "could not inspect prebuilt current runtime image"),
        ("legacy-oidc-wrong-platform", f"sha256:{'a' * 64}", f"sha256:{'e' * 64}", "could not inspect prebuilt current runtime image"),
        ("manifest", f"sha256:{'f' * 64}", f"sha256:{'5' * 64}", "running API does not match prebuilt current image"),
        ("manifest", f"sha256:{'1' * 64}", f"sha256:{'f' * 64}", "running OIDC does not match prebuilt current image"),
        ("error", f"sha256:{'a' * 64}", f"sha256:{'e' * 64}", "could not inspect prebuilt current runtime image"),
    ],
    ids=["manifest-list", "legacy-single-platform", "legacy-wrong-platform", "oidc-wrong-platform", "wrong-api-runtime-image", "wrong-oidc-runtime-image", "platform-inspect-error"],
)
def test_pilot_verifier_compares_prebuilt_images_to_running_containers(
    tmp_path: Path,
    platform_mode: Literal["manifest", "legacy", "legacy-wrong-platform", "legacy-oidc-wrong-platform", "error"],
    container_api_image: str,
    container_oidc_image: str,
    expected_error: str | None,
) -> None:
    # Given: Docker 29 keeps OCI index IDs on containers while platform inspection resolves children.
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    docker_log = tmp_path / "docker.log"
    index = {
        "mysql": f"sha256:{'4' * 64}",
        "oidc": f"sha256:{'5' * 64}",
        "api": f"sha256:{'1' * 64}",
        "ai": f"sha256:{'2' * 64}",
        "web": f"sha256:{'3' * 64}",
    }
    runtime = {
        "mysql": f"sha256:{'d' * 64}",
        "oidc": f"sha256:{'e' * 64}",
        "api": f"sha256:{'a' * 64}",
        "ai": f"sha256:{'b' * 64}",
        "web": f"sha256:{'c' * 64}",
    }
    reference_id = runtime if platform_mode.startswith("legacy") else index
    _write_executable(fake_bin / "timeout", '#!/usr/bin/env bash\nshift\nexec "$@"\n')
    _write_executable(fake_bin / "sha256sum", "#!/usr/bin/env bash\nexit 0\n")
    _write_executable(
        fake_bin / "docker",
        "\n".join(
            [
                "#!/usr/bin/env bash",
                f"printf '%s\\n' \"$*\" >> {docker_log!s}",
                'case "$*" in',
                "  'image inspect --help')",
                f"    [[ {str(not platform_mode.startswith('legacy')).lower()} == true ]] && printf '%s\\n' '      --platform string' || printf '%s\\n' 'Usage: docker image inspect' ;;",
                "  *'image inspect --platform linux/amd64 --format {{.Id}}'*)",
                f"    [[ {str(platform_mode != 'error').lower()} == true ]] || {{ printf '%s\\n' 'daemon inspection failed' >&2; exit 70; }}",
                "    case \"$*\" in",
                f"      *'{index['mysql']}'*) printf '%s\\n' '{runtime['mysql']}' ;;",
                f"      *'{index['oidc']}'*) printf '%s\\n' '{runtime['oidc']}' ;;",
                f"      *'{index['api']}'*) printf '%s\\n' '{runtime['api']}' ;;",
                f"      *'{index['ai']}'*) printf '%s\\n' '{runtime['ai']}' ;;",
                f"      *'{index['web']}'*) printf '%s\\n' '{runtime['web']}' ;;",
                "    esac ;;",
                "  *'image inspect --format {{.Os}}/{{.Architecture}}|{{.Id}}'*)",
                f"    platform={'linux/arm64' if platform_mode == 'legacy-wrong-platform' else 'linux/amd64'}",
                "    case \"$*\" in",
                f"      *'{runtime['mysql']}'*) printf '%s|%s\\n' \"$platform\" '{runtime['mysql']}' ;;",
                f"      *'{runtime['oidc']}'*) [[ {str(platform_mode == 'legacy-oidc-wrong-platform').lower()} == true ]] && platform=linux/arm64; printf '%s|%s\\n' \"$platform\" '{runtime['oidc']}' ;;",
                f"      *'{runtime['api']}'*) printf '%s|%s\\n' \"$platform\" '{runtime['api']}' ;;",
                f"      *'{runtime['ai']}'*) printf '%s|%s\\n' \"$platform\" '{runtime['ai']}' ;;",
                f"      *'{runtime['web']}'*) printf '%s|%s\\n' \"$platform\" '{runtime['web']}' ;;",
                "    esac ;;",
                "  *'image inspect --format {{.Id}}'*)",
                "    case \"$*\" in",
                f"      *'identity-pilot-mysql:latest'*) printf '%s\\n' '{reference_id['mysql']}' ;;",
                f"      *'identity-pilot-oidc:latest'*) printf '%s\\n' '{reference_id['oidc']}' ;;",
                f"      *'identity-pilot-api:latest'*) printf '%s\\n' '{reference_id['api']}' ;;",
                f"      *'identity-pilot-ai:latest'*) printf '%s\\n' '{reference_id['ai']}' ;;",
                f"      *'identity-pilot-web:latest'*) printf '%s\\n' '{reference_id['web']}' ;;",
                f"      *'{runtime['api']}'*) printf '%s\\n' '{runtime['api']}' ;;",
                f"      *'{runtime['ai']}'*) printf '%s\\n' '{runtime['ai']}' ;;",
                f"      *'{runtime['web']}'*) printf '%s\\n' '{runtime['web']}' ;;",
                f"      *'{runtime['mysql']}'*) printf '%s\\n' '{runtime['mysql']}' ;;",
                f"      *'{runtime['oidc']}'*) printf '%s\\n' '{runtime['oidc']}' ;;",
                "    esac ;;",
                "  *' ps -q api'*) printf '%s\\n' 'identity-api-container' ;;",
                "  *' ps -q ai'*) printf '%s\\n' 'identity-ai-container' ;;",
                "  *' ps -q web'*) printf '%s\\n' 'identity-web-container' ;;",
                "  *' ps -q mysql'*) printf '%s\\n' 'identity-mysql-container' ;;",
                "  *' ps -q oidc'*) printf '%s\\n' 'identity-oidc-container' ;;",
                f"  *'inspect --format {{{{.Image}}}} identity-api-container'*) printf '%s\\n' '{container_api_image}' ;;",
                f"  *'inspect --format {{{{.Image}}}} identity-ai-container'*) printf '%s\\n' '{reference_id['ai']}' ;;",
                f"  *'inspect --format {{{{.Image}}}} identity-web-container'*) printf '%s\\n' '{reference_id['web']}' ;;",
                f"  *'inspect --format {{{{.Image}}}} identity-mysql-container'*) printf '%s\\n' '{reference_id['mysql']}' ;;",
                f"  *'inspect --format {{{{.Image}}}} identity-oidc-container'*) printf '%s\\n' '{container_oidc_image}' ;;",
                "  *'exec -T ai python - build-artifact'*) exit 71 ;;",
                "esac",
                "",
            ]
        ),
    )
    _write_executable(
        fake_bin / "curl",
        """#!/usr/bin/env bash
output=''
while [[ $# -gt 0 ]]; do
  if [[ "$1" == '--output' ]]; then output="$2"; shift 2; else shift; fi
done
[[ -z "$output" ]] || { printf '%s\n' '{"status":"up"}' >"$output"; printf 200; }
""",
    )
    compose_file = tmp_path / "compose.yml"
    _ = compose_file.write_text("services: {}\n", encoding="utf-8")
    evidence_dir = tmp_path / "evidence"

    # When: the public verifier starts with prebuilt images.
    result = subprocess.run(
        [
            str(PILOT_SCRIPT),
            "--compose-file",
            str(compose_file),
            "--evidence-dir",
            str(evidence_dir),
            "--project",
            "identity-pilot",
            "--use-prebuilt-current-images",
        ],
        env={**os.environ, "PATH": f"{fake_bin}:/usr/bin:/bin"},
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )

    # Then: platform metadata is validated, while exact running-container identity gates execution.
    calls = docker_log.read_text(encoding="utf-8")
    assert "image inspect --help" in calls
    if platform_mode.startswith("legacy"):
        assert "image inspect --platform linux/amd64" not in calls
    else:
        first_platform_service = "mysql" if platform_mode == "error" else "api"
        assert (
            f"image inspect --platform linux/amd64 --format {{{{.Id}}}} "
            f"{index[first_platform_service]}"
        ) in calls
        if platform_mode != "error":
            assert f"image inspect --platform linux/amd64 --format {{{{.Id}}}} {index['oidc']}" in calls
            assert f"image inspect --platform linux/amd64 --format {{{{.Id}}}} {index['ai']}" in calls
            assert f"image inspect --platform linux/amd64 --format {{{{.Id}}}} {index['web']}" in calls
    if expected_error is None:
        assert result.returncode != 0
        assert "running API does not match prebuilt current image" not in result.stderr
        assert "inspect --format {{.Image}} identity-api-container" in calls
        assert "exec -T ai python - build-artifact" in calls
    else:
        assert result.returncode != 0
        assert expected_error in result.stderr
        assert "exec -T ai python - build-artifact" not in calls


@pytest.mark.parametrize(
    (
        "use_prebuilt",
        "fail_after_retag",
        "with_cross_version",
        "cleanup_inspection_failure",
        "infrastructure_identity_failure",
        "oidc_restore_fault",
    ),
    [
        (False, False, True, None, "none", "none"),
        (True, False, True, None, "none", "none"),
        (True, True, True, None, "none", "none"),
        (True, False, False, None, "none", "none"),
        (True, False, False, None, "running-mismatch", "none"),
        (True, False, False, None, "candidate-container", "none"),
        (True, False, False, None, "known-good-image", "none"),
        (True, False, False, None, "oidc-candidate-container", "none"),
        (True, False, False, None, "oidc-known-good-image", "none"),
        (True, False, False, None, "tag-rebound", "none"),
        (True, False, False, None, "oidc-tag-rebound", "none"),
        (True, False, False, None, "none", "primary-rebound"),
        (True, False, False, None, "none", "primary-deleted"),
        (False, False, False, None, "none", "primary-rebound"),
        (False, False, False, None, "none", "primary-deleted"),
        (True, False, False, "container", "none", "none"),
        (True, False, False, "network", "none", "none"),
        (True, False, False, "volume", "none", "none"),
        (True, False, False, "mixed-container", "none", "none"),
        (True, False, False, "mixed-network", "none", "none"),
        (True, False, False, "mixed-volume", "none", "none"),
    ],
    ids=[
        "default-build-cross-version",
        "prebuilt-cross-version",
        "prebuilt-failure-after-retag",
        "prebuilt-same-schema",
        "prebuilt-mysql-running-mismatch",
        "prebuilt-candidate-mysql-container-drift",
        "prebuilt-known-good-mysql-image-drift",
        "prebuilt-candidate-oidc-container-drift",
        "prebuilt-known-good-oidc-image-drift",
        "prebuilt-mysql-tag-rebound",
        "prebuilt-oidc-tag-rebound",
        "prebuilt-restore-oidc-primary-rebound",
        "prebuilt-restore-oidc-primary-deleted",
        "build-restore-oidc-primary-rebound",
        "build-restore-oidc-primary-deleted",
        "cleanup-container-inspection-fails",
        "cleanup-network-inspection-fails",
        "cleanup-volume-inspection-fails",
        "cleanup-container-failure-preserves-later-output",
        "cleanup-network-failure-preserves-earlier-output",
        "cleanup-volume-failure-preserves-earlier-output",
    ],
)
def test_pilot_verifier_executes_stateful_rollback_acceptance(
    tmp_path: Path,
    use_prebuilt: bool,
    fail_after_retag: bool,
    with_cross_version: bool,
    cleanup_inspection_failure: Literal[
        "container",
        "network",
        "volume",
        "mixed-container",
        "mixed-network",
        "mixed-volume",
    ]
    | None,
    infrastructure_identity_failure: Literal[
        "none",
        "running-mismatch",
        "candidate-container",
        "known-good-image",
        "oidc-candidate-container",
        "oidc-known-good-image",
        "tag-rebound",
        "oidc-tag-rebound",
    ],
    oidc_restore_fault: Literal["none", "primary-rebound", "primary-deleted"],
) -> None:
    # Given: a stateful Linux-shaped Compose surface with distinct current and previous APIs.
    fake_bin, state_dir = tmp_path / "bin", tmp_path / "state"
    for directory in (fake_bin, state_dir):
        directory.mkdir()
    known = {
        "api": f"sha256:{'a' * 64}",
        "ai": f"sha256:{'b' * 64}",
        "web": f"sha256:{'c' * 64}",
        "mysql": f"sha256:{'6' * 64}",
        "oidc": f"sha256:{'4' * 64}",
    }
    candidate = {
        "api": f"sha256:{'d' * 64}",
        "ai": f"sha256:{'e' * 64}",
        "web": f"sha256:{'f' * 64}",
        "mysql": f"sha256:{'5' * 64}",
        "oidc": f"sha256:{'3' * 64}",
    }
    previous_api = f"sha256:{'9' * 64}"
    mutated_previous_api = f"sha256:{'8' * 64}"
    rebound_image = f"sha256:{'7' * 64}"
    previous_revision = "1234567890abcdef1234567890abcdef12345678"
    for service, image in known.items():
        _ = (state_dir / f"current-{service}").write_text(image, encoding="utf-8")
    _ = (state_dir / "api-container").write_text("api-container-0", encoding="utf-8")
    _ = (state_dir / "api-tag").write_text(known["api"], encoding="utf-8")
    _ = (state_dir / "ai-tag").write_text(known["ai"], encoding="utf-8")
    _ = (state_dir / "web-tag").write_text(known["web"], encoding="utf-8")
    _ = (state_dir / "mysql-tag").write_text(known["mysql"], encoding="utf-8")
    _ = (state_dir / "oidc-tag").write_text(known["oidc"], encoding="utf-8")
    _ = (state_dir / "caller-restore-oidc-tag").write_text(
        rebound_image,
        encoding="utf-8",
    )
    _write_executable(fake_bin / "timeout", '#!/usr/bin/env bash\nshift\nexec "$@"\n')
    _write_executable(fake_bin / "sha256sum", "#!/usr/bin/env bash\nprintf '%064d  %s\\n' 0 \"$1\"\n")
    real_python = shutil.which("python3", path="/usr/bin:/bin")
    assert real_python is not None
    _write_executable(
        fake_bin / "python3",
        """#!/usr/bin/env bash
if [[ "${FAKE_SECRET_CLEANUP_FAILURE:-false}" == true && "${4:-}" == support-copilot-task15-secrets. ]]; then
  printf '%s/%s\n' "$2" "$3" >"$FAKE_STATE_DIR/failed-secret-path"
  exit 77
fi
exec "$FAKE_REAL_PYTHON" "$@"
""",
    )
    _write_executable(
        fake_bin / "docker",
        f"""#!/usr/bin/env bash
state="$FAKE_STATE_DIR"; printf '%s\n' "$*" >>"$state/docker.log"
case "$*" in
  'image inspect --help') printf '%s\n' 'Usage: docker image inspect' ;;
  *'io.support-copilot.packaging-dockerfile-sha256'*'{previous_api}'*) printf '%s\n' 'linux/amd64|{previous_api}|linux|amd64|{previous_revision}|{SHA256_ZERO}' ;;
  *'image inspect --format {{{{.Os}}}}/{{{{.Architecture}}}}|{{{{.Id}}}} '*) case "${{*: -1}}" in
    '{previous_api}') printf '%s\n' 'linux/amd64|{previous_api}' ;;
    '{known['api']}') printf '%s\n' 'linux/amd64|{known['api']}' ;;
    '{known['ai']}') printf '%s\n' 'linux/amd64|{known['ai']}' ;;
    '{known['web']}') printf '%s\n' 'linux/amd64|{known['web']}' ;;
    '{known['mysql']}') printf '%s\n' 'linux/amd64|{known['mysql']}' ;;
    '{known['oidc']}') printf '%s\n' 'linux/amd64|{known['oidc']}' ;;
    '{candidate['api']}') printf '%s\n' 'linux/amd64|{candidate['api']}' ;;
    '{candidate['ai']}') printf '%s\n' 'linux/amd64|{candidate['ai']}' ;;
    '{candidate['web']}') printf '%s\n' 'linux/amd64|{candidate['web']}' ;;
    '{candidate['mysql']}') printf '%s\n' 'linux/amd64|{candidate['mysql']}' ;;
    '{candidate['oidc']}') printf '%s\n' 'linux/amd64|{candidate['oidc']}' ;;
    rehearsal-pilot-api:latest) printf 'linux/amd64|'; cat "$state/api-tag" ;;
    rehearsal-pilot-ai:latest) printf 'linux/amd64|'; cat "$state/ai-tag" ;;
    rehearsal-pilot-web:latest) printf 'linux/amd64|'; cat "$state/web-tag" ;;
    rehearsal-pilot-mysql:latest) printf 'linux/amd64|'; cat "$state/mysql-tag" ;;
    rehearsal-pilot-oidc:latest) printf 'linux/amd64|'; cat "$state/oidc-tag" ;;
  esac ;;
  *'image inspect --format '*'Id'*'support-copilot-api:previous'*) if [[ -f "$state/previous-ref-mutated" ]]; then printf '%s\n' '{mutated_previous_api}'; else printf '%s\n' '{previous_api}'; printf '%s' '{mutated_previous_api}' >"$state/previous-ref-mutated"; fi ;;
  *'image inspect --format '*'Id'*'{previous_api}'*) printf '%s\n' '{previous_api}' ;;
  *'image inspect --format '*'Id'*'{known['api']}'*) printf '%s\n' '{known['api']}' ;;
  *'image inspect --format '*'Id'*'{known['ai']}'*) printf '%s\n' '{known['ai']}' ;;
  *'image inspect --format '*'Id'*'{known['web']}'*) printf '%s\n' '{known['web']}' ;;
  *'image inspect --format '*'Id'*'{known['mysql']}'*) printf '%s\n' '{known['mysql']}' ;;
  *'image inspect --format '*'Id'*'{known['oidc']}'*) if [[ -f "$state/backup-completed" && ! -f "$state/pilot-restore-started" && ! -f "$state/restore-oidc-validated" ]]; then touch "$state/restore-oidc-validated"; printf 'restore-oidc-validated:{known['oidc']}\n' >>"$state/events"; fi; printf '%s\n' '{known['oidc']}' ;;
  *'image inspect --format '*'Id'*'rehearsal-pilot-api:latest'*) cat "$state/api-tag" ;;
  *'image inspect --format '*'Id'*'rehearsal-pilot-ai:latest'*) cat "$state/ai-tag" ;;
  *'image inspect --format '*'Id'*'rehearsal-pilot-web:latest'*) cat "$state/web-tag" ;;
  *'image inspect --format '*'Id'*'rehearsal-pilot-mysql:latest'*) if [[ -f "$state/cleanup-started" && "$FAKE_INFRASTRUCTURE_IDENTITY_FAILURE" == tag-rebound ]]; then printf '%s\n' '{rebound_image}'; else cat "$state/mysql-tag"; fi ;;
  *'image inspect --format '*'Id'*'rehearsal-pilot-oidc:latest'*) if [[ -f "$state/oidc-primary-deleted" ]]; then exit 1; elif [[ -f "$state/oidc-primary-rebound" || -f "$state/cleanup-started" && "$FAKE_INFRASTRUCTURE_IDENTITY_FAILURE" == oidc-tag-rebound ]]; then printf '%s\n' '{rebound_image}'; else cat "$state/oidc-tag"; fi ;;
  *'image inspect --format '*'Id'*'rehearsal-pilot-api:known-good'*) if [[ -f "$state/cleanup-started" && "${{FAKE_IMAGE_REBIND_REFERENCE:-}}" == rehearsal-pilot-api:known-good ]]; then printf '%s\n' '{rebound_image}'; else printf '%s\n' '{known['api']}'; fi ;;
  *'image inspect --format '*'Id'*'rehearsal-pilot-ai:known-good'*) printf '%s\n' '{known['ai']}' ;;
  *'image inspect --format '*'Id'*'rehearsal-pilot-web:known-good'*) printf '%s\n' '{known['web']}' ;;
  *'image inspect --format '*'Id'*'rehearsal-pilot-restore-api:latest'*) printf '%s\n' '{known['api']}' ;;
  *'image inspect --format '*'Id'*'rehearsal-pilot-restore-ai:latest'*) printf '%s\n' '{known['ai']}' ;;
  *'image inspect --format '*'Id'*'rehearsal-pilot-restore-web:latest'*) printf '%s\n' '{known['web']}' ;;
  *'exec -T ai python - build-artifact'*) printf '%s\n' '{{"artifactId":"{'1' * 64}","rows":3}}' ;;
  *'exec -T ai python - inspect-artifact'*) printf '%s\n' '{{"artifactId":"{'1' * 64}","manifestPath":"{'1' * 64}/manifest.json","manifestSha256":"{'2' * 64}"}}' ;;
  *'exec -T ai python - support-copilot-agent'*) printf '%s\n' "$FAKE_AGENT_TOKEN" ;;
  *'exec -T ai python - support-copilot-reviewer'*) printf '%s\n' "$FAKE_REVIEWER_TOKEN" ;;
  *'exec -T ai python - support-copilot-admin'*) printf '%s\n' "$FAKE_ADMIN_TOKEN" ;;
  *'exec -T api wget '*'readiness'*) printf '%s\n' '{{"status":"UP"}}' ;;
  *'exec -T api timeout 15 bash '*direct-ai*) printf '401\n' ;; *'exec -T api cat /tmp/direct-ai.json'*) printf '%s\n' '{{"code":"INTERNAL_SERVICE_AUTHENTICATION_REQUIRED"}}' ;;
  *'exec -T api bash '*admin-actuator*) printf '200\n' ;; *'exec -T api cat /tmp/admin-actuator.json'*) printf '{{}}\n' ;;
  *flyway_schema_history*) printf '5\t123\n' ;; *'SELECT DATABASE()'*) printf 'wrong_database\n' ;;
  *' ps -q api') cat "$state/api-container" ;;
  *' ps -q mysql') if [[ "$FAKE_INFRASTRUCTURE_IDENTITY_FAILURE" == candidate-container && "$(cat "$state/rehearsal-phase" 2>/dev/null)" == candidate ]]; then printf 'mysql-container-candidate\n'; else printf 'mysql-container\n'; fi ;;
  *' ps -q ai') printf 'ai-container\n' ;;
  *' ps -q oidc') if [[ "$FAKE_INFRASTRUCTURE_IDENTITY_FAILURE" == oidc-candidate-container && "$(cat "$state/rehearsal-phase" 2>/dev/null)" == candidate ]]; then printf 'oidc-container-candidate\n'; else printf 'oidc-container\n'; fi ;;
  *' ps -q web') printf 'web-container\n' ;;
  *' ps --format json') printf '[]\n' ;;
  *'inspect --format {{{{.Image}}}} api-container'*) cat "$state/current-api" ;;
  *'inspect --format {{{{.Image}}}} ai-container'*) cat "$state/current-ai" ;;
  *'inspect --format {{{{.Image}}}} web-container'*) cat "$state/current-web" ;;
  *'inspect --format {{{{.Image}}}} mysql-container'*) if [[ "$FAKE_INFRASTRUCTURE_IDENTITY_FAILURE" == running-mismatch || "$FAKE_INFRASTRUCTURE_IDENTITY_FAILURE" == known-good-image && "$(cat "$state/rehearsal-phase" 2>/dev/null)" == known-good ]]; then printf '%s\n' '{rebound_image}'; else cat "$state/current-mysql"; fi ;;
  *'inspect --format {{{{.Image}}}} oidc-container'*) if [[ "$FAKE_INFRASTRUCTURE_IDENTITY_FAILURE" == oidc-known-good-image && "$(cat "$state/rehearsal-phase" 2>/dev/null)" == known-good ]]; then printf '%s\n' '{rebound_image}'; else cat "$state/current-oidc"; fi ;;
  *' images -q api') cat "$state/current-api" ;; *' images -q ai') cat "$state/current-ai" ;; *' images -q web') cat "$state/current-web" ;;
  *'State.StartedAt'*) count=$(cat "$state/inspect-count" 2>/dev/null || printf 0); count=$((count+1)); printf '%s' "$count" >"$state/inspect-count"; printf '2026-08-31T00:00:%02dZ\n' "$count" ;;
  *'ps -aq --filter label=com.docker.compose.project=rehearsal-pilot-restore --filter label=io.support-copilot.run-ownership='*) touch "$state/cleanup-started"; printf '%s\n' '222222222222' ;;
  *'network ls -q --filter label=com.docker.compose.project=rehearsal-pilot-restore --filter label=io.support-copilot.run-ownership='*) printf '%s\n' '444444444444' ;;
  *'volume ls -q --filter label=com.docker.compose.project=rehearsal-pilot-restore --filter label=io.support-copilot.run-ownership='*) printf '%s\n' 'rehearsal-pilot-restore-mysql-data' ;;
  *'ps -aq --filter label=com.docker.compose.project=rehearsal-pilot --filter label=io.support-copilot.run-ownership='*) touch "$state/cleanup-started"; printf '%s\n' '111111111111' ;;
  *'network ls -q --filter label=com.docker.compose.project=rehearsal-pilot --filter label=io.support-copilot.run-ownership='*) printf '%s\n' '333333333333' ;;
  *'volume ls -q --filter label=com.docker.compose.project=rehearsal-pilot --filter label=io.support-copilot.run-ownership='*) printf '%s\n' 'rehearsal-pilot-mysql-data' ;;
  'container rm --force 222222222222'|'network rm 444444444444'|'volume rm rehearsal-pilot-restore-mysql-data'|'container rm --force 111111111111'|'network rm 333333333333'|'volume rm rehearsal-pilot-mysql-data') ;;
  'ps -aq --filter label=com.docker.compose.project=rehearsal-pilot') if [[ -f "$state/cleanup-started" ]]; then case "$FAKE_CLEANUP_INSPECTION_FAILURE" in mixed-container|mixed-network|mixed-volume) printf '%s\\n' leftover-container ;; esac; [[ "$FAKE_CLEANUP_INSPECTION_FAILURE" != container && "$FAKE_CLEANUP_INSPECTION_FAILURE" != mixed-container ]] || exit 61; fi ;;
  'network ls -q --filter label=com.docker.compose.project=rehearsal-pilot') if [[ -f "$state/cleanup-started" ]]; then case "$FAKE_CLEANUP_INSPECTION_FAILURE" in mixed-container|mixed-network|mixed-volume) printf '%s\\n' leftover-network ;; esac; [[ "$FAKE_CLEANUP_INSPECTION_FAILURE" != network && "$FAKE_CLEANUP_INSPECTION_FAILURE" != mixed-network ]] || exit 62; fi ;;
  'volume ls -q --filter label=com.docker.compose.project=rehearsal-pilot') if [[ -f "$state/cleanup-started" ]]; then case "$FAKE_CLEANUP_INSPECTION_FAILURE" in mixed-container|mixed-network|mixed-volume) printf '%s\\n' leftover-volume ;; esac; [[ "$FAKE_CLEANUP_INSPECTION_FAILURE" != volume && "$FAKE_CLEANUP_INSPECTION_FAILURE" != mixed-volume ]] || exit 63; fi ;;
      *'image inspect '*) if [[ -f "$state/cleanup-started" && "${{FAKE_IMAGE_LOOKUP_FAILURE:-}}" == all ]]; then case "${{*: -1}}" in rehearsal-pilot-api:known-good|rehearsal-pilot-ai:known-good|rehearsal-pilot-web:known-good|rehearsal-pilot-restore-api:latest|rehearsal-pilot-restore-ai:latest|rehearsal-pilot-restore-web:latest|rehearsal-pilot-api:latest|rehearsal-pilot-ai:latest|rehearsal-pilot-web:latest|rehearsal-pilot-mysql:latest|rehearsal-pilot-oidc:latest) exit 67 ;; esac; fi ;;
      *'image ls --quiet --no-trunc '*) if [[ -f "$state/cleanup-started" ]]; then [[ "${{FAKE_IMAGE_LOOKUP_FAILURE:-}}" != all ]] || exit 67; case "${{*: -1}}" in
        rehearsal-pilot-api:known-good|rehearsal-pilot-api:latest) printf '%s\n' '{known['api']}' ;;
        rehearsal-pilot-ai:known-good|rehearsal-pilot-ai:latest) printf '%s\n' '{known['ai']}' ;;
        rehearsal-pilot-web:known-good|rehearsal-pilot-web:latest) printf '%s\n' '{known['web']}' ;;
        rehearsal-pilot-mysql:latest) printf '%s\n' '{known['mysql']}' ;;
        rehearsal-pilot-oidc:latest) if [[ ! -f "$state/oidc-primary-deleted" ]]; then printf '%s\n' '{known['oidc']}'; fi ;;
        rehearsal-pilot-restore-api:latest) if grep -q '^restore-tag:api:' "$state/events"; then printf '%s\n' '{known['api']}'; fi ;;
        rehearsal-pilot-restore-ai:latest) if grep -q '^restore-tag:ai:' "$state/events"; then printf '%s\n' '{known['ai']}'; fi ;;
        rehearsal-pilot-restore-web:latest) if grep -q '^restore-tag:web:' "$state/events"; then printf '%s\n' '{known['web']}'; fi ;;
      esac; fi ;;
  'tag rehearsal-pilot-api:latest rehearsal-pilot-api:known-good') printf 'capture:api:{known['api']}\n' >>"$state/events" ;;
  'tag rehearsal-pilot-ai:latest rehearsal-pilot-ai:known-good') printf 'capture:ai:{known['ai']}\n' >>"$state/events" ;;
  'tag rehearsal-pilot-web:latest rehearsal-pilot-web:known-good') printf 'capture:web:{known['web']}\n' >>"$state/events" ;;
  'tag rehearsal-pilot-api:known-good rehearsal-pilot-restore-api:latest') printf 'restore-tag:api:{known['api']}\n' >>"$state/events" ;;
  'tag rehearsal-pilot-ai:known-good rehearsal-pilot-restore-ai:latest') printf 'restore-tag:ai:{known['ai']}\n' >>"$state/events" ;;
  'tag rehearsal-pilot-web:known-good rehearsal-pilot-restore-web:latest') printf 'restore-tag:web:{known['web']}\n' >>"$state/events" ;;
  'tag rehearsal-pilot-api:known-good rehearsal-pilot-api:latest') count=$(cat "$state/known-good-api-tag-count" 2>/dev/null || printf 0); count=$((count+1)); printf '%s' "$count" >"$state/known-good-api-tag-count"; printf '%s' '{known['api']}' >"$state/api-tag"; if [[ "$count" == 1 ]]; then printf 'rollback-tag:api\n' >>"$state/events"; else printf 'candidate-return-tag:{known['api']}\n' >>"$state/events"; fi ;;
  'tag rehearsal-pilot-ai:known-good rehearsal-pilot-ai:latest') printf '%s' '{known['ai']}' >"$state/ai-tag"; printf 'rollback-tag:ai\n' >>"$state/events" ;;
  'tag rehearsal-pilot-web:known-good rehearsal-pilot-web:latest') printf '%s' '{known['web']}' >"$state/web-tag"; printf 'rollback-tag:web\n' >>"$state/events" ;;
  *' up --build --no-deps --force-recreate --detach --wait api ai web'*) printf 'candidate' >"$state/rehearsal-phase"; printf '%s' '{candidate['api']}' >"$state/current-api"; printf '%s' '{candidate['ai']}' >"$state/current-ai"; printf '%s' '{candidate['web']}' >"$state/current-web"; printf '%s' '{candidate['api']}' >"$state/api-tag"; printf '%s' '{candidate['ai']}' >"$state/ai-tag"; printf '%s' '{candidate['web']}' >"$state/web-tag"; printf 'candidate-current:{candidate['api']}\n' >>"$state/events" ;;
  *' up --no-build --no-deps --force-recreate --detach --wait api ai web'*) phase=candidate; [[ -f "$state/rehearsal-phase" ]] && phase=known-good; printf '%s' "$phase" >"$state/rehearsal-phase"; printf '%s' "$(cat "$state/api-tag")" >"$state/current-api"; printf '%s' "$(cat "$state/ai-tag")" >"$state/current-ai"; printf '%s' "$(cat "$state/web-tag")" >"$state/current-web"; [[ "$phase" != known-good ]] || printf 'rollback-reapplied:{known['api']}\n' >>"$state/events" ;;
  'tag {previous_api} rehearsal-pilot-api:latest') printf '%s' '{previous_api}' >"$state/api-tag"; printf 'previous-captured-tag:{previous_api}\n' >>"$state/events" ;;
  'tag support-copilot-api:previous rehearsal-pilot-api:latest') printf '%s' '{mutated_previous_api}' >"$state/api-tag"; printf 'previous-mutable-tag:{mutated_previous_api}\n' >>"$state/events" ;;
  'tag {known['api']} rehearsal-pilot-api:latest') printf '%s' '{known['api']}' >"$state/api-tag"; printf 'candidate-return-tag:{known['api']}\n' >>"$state/events" ;;
  'tag {known['ai']} rehearsal-pilot-ai:latest') printf '%s' '{known['ai']}' >"$state/ai-tag"; printf 'cleanup-current-tag:ai:{known['ai']}\n' >>"$state/events" ;;
  'tag {known['web']} rehearsal-pilot-web:latest') printf '%s' '{known['web']}' >"$state/web-tag"; printf 'cleanup-current-tag:web:{known['web']}\n' >>"$state/events" ;;
  *'--project-name rehearsal-pilot-restore'*' up --no-build --detach --wait') printf '%s\n' "$SUPPORT_COPILOT_OIDC_IMAGE" >"$state/restore-compose-oidc-image.log"; printf 'restore-compose-oidc:%s\n' "$SUPPORT_COPILOT_OIDC_IMAGE" >>"$state/events" ;;
  *'--project-name rehearsal-pilot-restore'*' up --detach --wait') printf '%s\n' "$SUPPORT_COPILOT_OIDC_IMAGE" >"$state/restore-compose-oidc-image.log"; printf 'restore-compose-oidc:%s\n' "$SUPPORT_COPILOT_OIDC_IMAGE" >>"$state/events" ;;
  *' up --no-build --no-deps --force-recreate --detach --wait api'*) current=$(cat "$state/api-tag"); if [[ "$FAKE_FAIL_AFTER_RETAG" == true && ! -f "$state/failed-after-retag" ]]; then touch "$state/failed-after-retag"; printf 'api-only-failed:%s\n' "$current" >>"$state/events"; exit 73; fi; printf '%s' "$current" >"$state/current-api"; count=$(cat "$state/api-cross-count" 2>/dev/null || printf 0); count=$((count+1)); printf '%s' "$count" >"$state/api-cross-count"; printf 'api-container-%s' "$count" >"$state/api-container"; printf 'api-only:%s\n' "$current" >>"$state/events" ;;
  *' up --no-build --force-recreate --detach --wait'*) printf '%s' '{known['api']}' >"$state/current-api"; printf '%s' '{known['ai']}' >"$state/current-ai"; printf '%s' '{known['web']}' >"$state/current-web"; printf '%s' '{known['api']}' >"$state/api-tag"; printf 'rollback-reapplied:{known['api']}\n' >>"$state/events" ;;
esac
""",
    )
    _write_executable(
        fake_bin / "curl",
        """#!/usr/bin/env bash
printf '%s\n' "$*" >>"$FAKE_STATE_DIR/curl.log"
if [[ "$*" == *'--header @-'* ]]; then
  IFS= read -r authorization_header
  printf '%s\n' "$authorization_header" >>"$FAKE_STATE_DIR/curl-headers.log"
fi
output=''; while [[ $# -gt 0 ]]; do [[ "$1" == '--output' ]] && { output="$2"; shift 2; } || shift; done
[[ -n "$output" ]] || exit 0; name="${output##*/}"
case "$name" in
  gateway-health.json|previous-api-gateway-health.json|current-api-return-gateway-health.json) status=200; body='{"status":"up"}' ;; anonymous.json) status=401; body='{"code":"AUTHENTICATION_REQUIRED"}' ;; agent-audit-denied.json) status=403; body='{"code":"ACCESS_DENIED"}' ;;
  ticket-create.json) status=201; body='{"id":"ticket-1","version":1}' ;; ticket-read.json|persisted-ticket-*) status=200; body='{"id":"ticket-1","version":3}' ;; ticket-patch.json) status=200; body='{"id":"ticket-1","version":2}' ;;
  analysis.json) status=200; body='{"id":"run_AAAAAAAAAAAA","traceId":"trace-1","mode":"mock","status":"SUCCEEDED","suggestedReply":{"content":"reply"}}' ;; persisted-analysis-*) status=200; body='[{"id":"run_AAAAAAAAAAAA"}]' ;;
  review.json) status=200; body='{"id":"review-1","analysisId":"run_AAAAAAAAAAAA","ticketVersion":3}' ;; audit.json|persisted-audit-*) status=200; body='{"items":[{"id":"audit-1"}]}' ;; post-restart-write.json) status=201; body='{"id":"ticket-post","version":0}' ;;
  previous-api-safe-write.json) status=201; body='{"id":"ticket-previous","version":0,"subject":"Safe previous API write"}' ;; previous-api-write-after-return.json) status=200; body='{"id":"ticket-previous","version":0,"subject":"Safe previous API write"}' ;; restored-api-read.json) status=200; body='{"id":"ticket-1","version":3}' ;; restored-post-write.json) status=201; body='{"id":"ticket-restored","version":0}' ;; *) status=500; body='{"code":"UNEXPECTED_FAKE_REQUEST"}' ;;
esac
printf '%s\n' "$body" >"$output"; printf '%s' "$status"
""",
    )
    compose_file, evidence_dir = tmp_path / "compose.yml", tmp_path / "evidence"
    _ = compose_file.write_text("services: {}\n", encoding="utf-8")
    build_evidence = tmp_path / "compatible-build"
    build_manifest_sha = _write_compatible_build_evidence(
        build_evidence,
        image_ref="support-copilot-api:previous",
        image_id=previous_api,
        revision=previous_revision,
        packaging_sha256=SHA256_ZERO,
    )
    pilot_script = PILOT_SCRIPT
    if use_prebuilt or oidc_restore_fault != "none":
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        pilot_script = scripts_dir / "verify-pilot-operations.sh"
        _ = shutil.copy2(PILOT_SCRIPT, pilot_script)
        temporary_dockerfile = tmp_path / "services/support-copilot-api/Dockerfile"
        temporary_dockerfile.parent.mkdir(parents=True)
        _ = shutil.copy2(
            REPOSITORY_ROOT / "services/support-copilot-api/Dockerfile",
            temporary_dockerfile,
        )
        _write_executable(
            scripts_dir / "pilot-backup.sh",
            """#!/usr/bin/env bash
set -euo pipefail
while [[ $# -gt 0 ]]; do
  if [[ "$1" == "--evidence-dir" ]]; then
    evidence_dir="$2"
    shift 2
  else
    shift
  fi
done
mkdir -p "$evidence_dir"
printf '%s\\n' "$SUPPORT_COPILOT_MYSQL_IMAGE" >"$FAKE_STATE_DIR/backup-mysql-image.log"
printf '%s\\n' "$SUPPORT_COPILOT_OIDC_IMAGE" >"$FAKE_STATE_DIR/backup-oidc-image.log"
printf '%s\\n' '{"embeddingArtifacts":{"activeArtifactId":"1111111111111111111111111111111111111111111111111111111111111111","archiveSha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}}' >"$evidence_dir/manifest.json"
touch "$FAKE_STATE_DIR/backup-completed"
""",
        )
        _write_executable(
            scripts_dir / "pilot-restore.sh",
            f"""#!/usr/bin/env bash
set -euo pipefail
[[ -f "$FAKE_STATE_DIR/restore-oidc-validated" ]] || exit 79
touch "$FAKE_STATE_DIR/pilot-restore-started"
printf '%s\\n' "$SUPPORT_COPILOT_MYSQL_IMAGE" >"$FAKE_STATE_DIR/restore-mysql-image.log"
printf '%s\\n' "$SUPPORT_COPILOT_OIDC_IMAGE" >"$FAKE_STATE_DIR/restore-oidc-image.log"
resolved_oidc_id="$(docker image inspect --format '{{{{.Id}}}}' "$SUPPORT_COPILOT_OIDC_IMAGE")"
printf 'pilot-restore-oidc:%s\\n' "$resolved_oidc_id" >>"$FAKE_STATE_DIR/events"
printf 'pilot-restore-mysql-mutated\\n' >>"$FAKE_STATE_DIR/events"
case "$FAKE_OIDC_RESTORE_FAULT" in
  primary-rebound)
    printf '%s' '{rebound_image}' >"$FAKE_STATE_DIR/oidc-tag"
    touch "$FAKE_STATE_DIR/oidc-primary-rebound"
    printf 'primary-oidc-rebound:%s\\n' '{rebound_image}' >>"$FAKE_STATE_DIR/events"
    ;;
  primary-deleted)
    touch "$FAKE_STATE_DIR/oidc-primary-deleted"
    printf 'primary-oidc-deleted\\n' >>"$FAKE_STATE_DIR/events"
    ;;
esac
printf '%s\\n' "$*" >"$RESTORE_ARGUMENT_LOG"
""",
        )

    rollback_arguments = [
        "--previous-api-image",
        "support-copilot-api:previous",
        "--previous-api-revision",
        previous_revision,
        "--previous-api-build-evidence",
        str(build_evidence),
    ] if with_cross_version else []

    # When: the verifier runs with controlled rollback and backup/restore boundaries.
    run_env = {
        **os.environ,
        "PATH": f"{fake_bin}:/usr/bin:/bin",
        "FAKE_STATE_DIR": str(state_dir),
        "FAKE_REAL_PYTHON": real_python,
        "FAKE_AGENT_TOKEN": _jwt(
            "pilot-agent",
            "SUPPORT_AGENT",
            audience_as_list=False,
        ),
        "FAKE_REVIEWER_TOKEN": _jwt("pilot-reviewer", "SUPPORT_REVIEWER"),
        "FAKE_ADMIN_TOKEN": _jwt("pilot-admin", "SUPPORT_ADMIN"),
        "RESTORE_ARGUMENT_LOG": str(state_dir / "restore-arguments.log"),
        "FAKE_FAIL_AFTER_RETAG": str(fail_after_retag).lower(),
        "FAKE_CLEANUP_INSPECTION_FAILURE": cleanup_inspection_failure or "",
        "FAKE_INFRASTRUCTURE_IDENTITY_FAILURE": infrastructure_identity_failure,
        "FAKE_OIDC_RESTORE_FAULT": oidc_restore_fault,
    }
    result = subprocess.run(
        [str(pilot_script), "--compose-file", str(compose_file), "--evidence-dir", str(evidence_dir), "--project", "rehearsal-pilot",
         *rollback_arguments,
         *(["--use-prebuilt-current-images"] if use_prebuilt else [])],
        env=run_env,
        check=False, capture_output=True, text=True, timeout=30,
    )

    docker_calls = (state_dir / "docker.log").read_text(encoding="utf-8")
    mutable_restore_oidc_reference = "rehearsal-pilot-restore-oidc:latest"
    assert mutable_restore_oidc_reference not in docker_calls
    assert (state_dir / "caller-restore-oidc-tag").read_text(encoding="utf-8") == (
        rebound_image
    )
    cleanup_receipt_path = evidence_dir / "cleanup-receipt.log"
    if cleanup_receipt_path.exists():
        assert mutable_restore_oidc_reference not in cleanup_receipt_path.read_text(
            encoding="utf-8"
        )
    if infrastructure_identity_failure == "running-mismatch":
        assert result.returncode != 0
        assert "running MySQL does not match prebuilt current image" in result.stderr
        assert not (evidence_dir / "artifact-build.json").exists()
        return
    if infrastructure_identity_failure == "candidate-container":
        assert result.returncode != 0
        assert "MySQL container changed during candidate redeploy" in result.stderr
        return
    if infrastructure_identity_failure == "known-good-image":
        assert result.returncode != 0
        assert "MySQL image changed during known-good reapply" in result.stderr
        return
    if infrastructure_identity_failure == "oidc-candidate-container":
        assert result.returncode != 0
        assert "OIDC container changed during candidate redeploy" in result.stderr
        return
    if infrastructure_identity_failure == "oidc-known-good-image":
        assert result.returncode != 0
        assert "OIDC image changed during known-good reapply" in result.stderr
        return
    curl_calls = (state_dir / "curl.log").read_text(encoding="utf-8")
    curl_headers = (state_dir / "curl-headers.log").read_text(encoding="utf-8")
    assert "--header @-" in curl_calls
    for token in (
        run_env["FAKE_AGENT_TOKEN"],
        run_env["FAKE_REVIEWER_TOKEN"],
        run_env["FAKE_ADMIN_TOKEN"],
    ):
        assert token not in curl_calls
        assert f"Authorization: Bearer {token}" in curl_headers
    restart_call = "restart api"
    readiness_wait_call = "up --no-deps --no-recreate --detach --wait api"
    assert docker_calls.count(restart_call) == 1
    assert docker_calls.count(readiness_wait_call) == 1
    assert docker_calls.index(restart_call) < docker_calls.index(readiness_wait_call)
    assert json.loads(
        (evidence_dir / "api-readiness-after-api-restart.json").read_text(encoding="utf-8")
    ) == {"status": "UP"}

    # Then: the previous API and candidate return are distinct, API-only, and evidence-backed.
    if fail_after_retag:
        assert result.returncode == 73, result.stderr
        assert (state_dir / "api-tag").read_text(encoding="utf-8") == previous_api
        assert (state_dir / "ai-tag").read_text(encoding="utf-8") == known["ai"]
        assert (state_dir / "web-tag").read_text(encoding="utf-8") == known["web"]
        events = (state_dir / "events").read_text(encoding="utf-8").splitlines()
        assert events[-1] == f"api-only-failed:{previous_api}"
        for service in ("api", "ai", "web"):
            assert f"image rm rehearsal-pilot-{service}:latest" not in docker_calls
        cleanup_receipt = (evidence_dir / "cleanup-receipt.log").read_text(encoding="utf-8")
        assert "prebuilt_reference_identity_mismatch=rehearsal-pilot-api:latest" in cleanup_receipt
        assert "prebuilt_primary_tags_verified=false" in cleanup_receipt
        assert "cleanup_completed=false" in cleanup_receipt
        assert not (evidence_dir / "operations-result.json").exists()
        return
    if cleanup_inspection_failure is not None:
        assert result.returncode == 1, result.stderr
        cleanup_lines = (evidence_dir / "cleanup-receipt.log").read_text(encoding="utf-8").splitlines()
        expected_exit = {
            "container": 61,
            "network": 62,
            "volume": 63,
            "mixed-container": 61,
            "mixed-network": 62,
            "mixed-volume": 63,
        }[cleanup_inspection_failure]
        assert "project_inspection_failed=rehearsal-pilot" in cleanup_lines
        assert f"project_inspection_exit={expected_exit}" in cleanup_lines
        assert "project_absent=rehearsal-pilot" not in cleanup_lines
        assert "cleanup_completed=false" in cleanup_lines
        assert "cleanup_completed=true" not in cleanup_lines
        assert (evidence_dir / "operations-result.json").is_file()
        assert "PASS:" not in result.stdout
        assert "completed;" not in result.stdout
        if cleanup_inspection_failure.startswith("mixed-"):
            expected_primary_receipt = [
                "cleanup_started=true",
                "owned_container_removed=rehearsal-pilot-restore:222222222222",
                "owned_network_removed=rehearsal-pilot-restore:444444444444",
                "owned_volume_removed=rehearsal-pilot-restore:rehearsal-pilot-restore-mysql-data",
                "owned_container_removed=rehearsal-pilot:111111111111",
                "owned_network_removed=rehearsal-pilot:333333333333",
                "owned_volume_removed=rehearsal-pilot:rehearsal-pilot-mysql-data",
                "resource_inspection_project=rehearsal-pilot",
                "containers_inspection_exit=0" if cleanup_inspection_failure != "mixed-container" else "containers_inspection_exit=61",
                "containers_output_begin",
                "leftover-container",
                "containers_output_end",
                "networks_inspection_exit=0" if cleanup_inspection_failure != "mixed-network" else "networks_inspection_exit=62",
                "networks_output_begin",
                "leftover-network",
                "networks_output_end",
                "volumes_inspection_exit=0" if cleanup_inspection_failure != "mixed-volume" else "volumes_inspection_exit=63",
                "volumes_output_begin",
                "leftover-volume",
                "volumes_output_end",
                "project_inspection_failed=rehearsal-pilot",
                f"project_inspection_exit={expected_exit}",
            ]
            assert cleanup_lines[: len(expected_primary_receipt)] == expected_primary_receipt
            assert cleanup_lines[len(expected_primary_receipt) :] == [
                "resource_inspection_project=rehearsal-pilot-restore",
                "containers_inspection_exit=0",
                "containers_output_begin",
                "",
                "containers_output_end",
                "networks_inspection_exit=0",
                "networks_output_begin",
                "",
                "networks_output_end",
                "volumes_inspection_exit=0",
                "volumes_output_begin",
                "",
                "volumes_output_end",
                "project_absent=rehearsal-pilot-restore",
                "prebuilt_reference_verified=rehearsal-pilot-mysql:latest",
                "prebuilt_reference_verified=rehearsal-pilot-oidc:latest",
                "prebuilt_reference_verified=rehearsal-pilot-api:latest",
                "prebuilt_reference_verified=rehearsal-pilot-ai:latest",
                "prebuilt_reference_verified=rehearsal-pilot-web:latest",
                "prebuilt_primary_tags_verified=true",
                f"image_reference_retained=rehearsal-pilot-api:known-good:{known['api']}",
                f"image_reference_retained=rehearsal-pilot-ai:known-good:{known['ai']}",
                f"image_reference_retained=rehearsal-pilot-web:known-good:{known['web']}",
                f"image_reference_retained=rehearsal-pilot-restore-api:latest:{known['api']}",
                f"image_reference_retained=rehearsal-pilot-restore-ai:latest:{known['ai']}",
                f"image_reference_retained=rehearsal-pilot-restore-web:latest:{known['web']}",
                "secret_cleanup_exit=0",
                "secret_directory_removed=true",
                "cleanup_completed=false",
            ]
        return
    if infrastructure_identity_failure == "tag-rebound":
        assert result.returncode == 1
        cleanup_receipt = (evidence_dir / "cleanup-receipt.log").read_text(encoding="utf-8")
        assert "prebuilt_reference_identity_mismatch=rehearsal-pilot-mysql:latest" in cleanup_receipt
        assert "prebuilt_primary_tags_verified=false" in cleanup_receipt
        assert "cleanup_completed=false" in cleanup_receipt
        assert "PASS:" not in result.stdout
        return
    if infrastructure_identity_failure == "oidc-tag-rebound":
        assert result.returncode == 1
        cleanup_receipt = (evidence_dir / "cleanup-receipt.log").read_text(encoding="utf-8")
        assert "prebuilt_reference_identity_mismatch=rehearsal-pilot-oidc:latest" in cleanup_receipt
        assert "prebuilt_primary_tags_verified=false" in cleanup_receipt
        assert "cleanup_completed=false" in cleanup_receipt
        assert "image rm rehearsal-pilot-oidc:latest" not in docker_calls
        assert "PASS:" not in result.stdout
        return
    if oidc_restore_fault != "none":
        assert result.returncode == 1, result.stderr
        cleanup_receipt = (evidence_dir / "cleanup-receipt.log").read_text(encoding="utf-8")
        if oidc_restore_fault == "primary-rebound":
            expected_receipt = (
                "prebuilt_reference_identity_mismatch=rehearsal-pilot-oidc:latest"
                if use_prebuilt
                else "image_reference_identity_mismatch=rehearsal-pilot-oidc:latest"
            )
        elif use_prebuilt:
            expected_receipt = (
                "prebuilt_reference_identity_inspection_failed="
                "rehearsal-pilot-oidc:latest"
            )
        else:
            expected_receipt = "image_reference_missing=rehearsal-pilot-oidc:latest"
        assert expected_receipt in cleanup_receipt
        assert "cleanup_completed=false" in cleanup_receipt
        assert "cleanup_completed=true" not in cleanup_receipt
        assert "PASS:" not in result.stdout
        assert "prune" not in docker_calls
        assert "down --volumes --remove-orphans" not in docker_calls
        assert "image rm rehearsal-pilot-oidc:latest" not in docker_calls
        restore_oidc_image = (state_dir / "restore-oidc-image.log").read_text(encoding="utf-8").strip()
        assert restore_oidc_image == known["oidc"]
        assert (state_dir / "restore-compose-oidc-image.log").read_text(
            encoding="utf-8"
        ).strip() == known["oidc"]
        expected_identity = {
            "reference": known["oidc"],
            "imageId": known["oidc"],
            "platformImageId": known["oidc"],
            "referenceKind": "immutableLocalImageId",
            "ownership": (
                "caller-owned-prebuilt-image"
                if use_prebuilt
                else "verifier-owned-built-image"
            ),
        }
        assert json.loads(
            (evidence_dir / "restore-oidc-identity.json").read_text(encoding="utf-8")
        ) == expected_identity
        if use_prebuilt:
            assert json.loads(
                (evidence_dir / "restore-prebuilt-images.json").read_text(
                    encoding="utf-8"
                )
            )["oidc"] == expected_identity
        events = (state_dir / "events").read_text(encoding="utf-8").splitlines()
        pilot_restore_consumption = f"pilot-restore-oidc:{known['oidc']}"
        verifier_validation = f"restore-oidc-validated:{known['oidc']}"
        primary_drift = (
            f"primary-oidc-rebound:{rebound_image}"
            if oidc_restore_fault == "primary-rebound"
            else "primary-oidc-deleted"
        )
        compose_consumption = f"restore-compose-oidc:{known['oidc']}"
        assert events.index(verifier_validation) < events.index(pilot_restore_consumption)
        assert events.index(pilot_restore_consumption) < events.index(
            "pilot-restore-mysql-mutated"
        )
        assert events.index("pilot-restore-mysql-mutated") < events.index(primary_drift)
        assert events.index(primary_drift) < events.index(compose_consumption)
        return
    if use_prebuilt:
        assert result.returncode == 0, result.stderr
    else:
        assert result.returncode != 0 and (evidence_dir / "backup-command.log").exists()
        built_images = json.loads(
            (evidence_dir / "current-built-images.json").read_text(encoding="utf-8")
        )
        assert built_images["oidc"] == {
            "reference": "rehearsal-pilot-oidc:latest",
            "imageId": known["oidc"],
            "platformImageId": known["oidc"],
        }
    expected_restore_oidc_identity = {
        "reference": known["oidc"],
        "imageId": known["oidc"],
        "platformImageId": known["oidc"],
        "referenceKind": "immutableLocalImageId",
        "ownership": (
            "caller-owned-prebuilt-image"
            if use_prebuilt
            else "verifier-owned-built-image"
        ),
    }
    assert json.loads(
        (evidence_dir / "restore-oidc-identity.json").read_text(encoding="utf-8")
    ) == expected_restore_oidc_identity
    events = (state_dir / "events").read_text(encoding="utf-8").splitlines()
    expected_events = [f"capture:api:{known['api']}", f"capture:ai:{known['ai']}", f"capture:web:{known['web']}"]
    if not use_prebuilt:
        expected_events.append(f"candidate-current:{candidate['api']}")
    expected_events.extend(["rollback-tag:api", "rollback-tag:ai", "rollback-tag:web",
                            f"rollback-reapplied:{known['api']}"])
    if with_cross_version:
        expected_events.extend([f"previous-captured-tag:{previous_api}", f"api-only:{previous_api}",
                                f"candidate-return-tag:{known['api']}", f"api-only:{known['api']}"])
    if use_prebuilt:
        expected_events.extend([
            f"restore-tag:api:{known['api']}",
            f"restore-tag:ai:{known['ai']}",
            f"restore-tag:web:{known['web']}",
            f"restore-oidc-validated:{known['oidc']}",
            f"pilot-restore-oidc:{known['oidc']}",
            "pilot-restore-mysql-mutated",
            f"restore-compose-oidc:{known['oidc']}",
        ])
    assert events == expected_events
    if not use_prebuilt:
        assert candidate["api"] != known["api"]
    assert json.loads((evidence_dir / "persisted-ticket-after-rollback-rehearsal.json").read_text())["version"] == 3
    assert json.loads((evidence_dir / "persisted-analysis-after-rollback-rehearsal.json").read_text())[0]["id"] == "run_AAAAAAAAAAAA"
    assert json.loads((evidence_dir / "persisted-audit-after-rollback-rehearsal.json").read_text())["items"][0]["id"] == "audit-1"
    assert (evidence_dir / "persisted-migration-after-rollback-rehearsal.txt").read_text().strip() == "5\t123"
    assert (evidence_dir / "artifact-after-rehearsal.json").read_text() == (evidence_dir / "artifact-before-restarts.json").read_text()
    assert (evidence_dir / "rollback-rehearsal.txt").read_text().strip() == "same-schema deployment sequencing and rollback rehearsal; this is not a real cross-version production rollback"
    if with_cross_version:
        cross_version = json.loads((evidence_dir / "cross-version-rollback.json").read_text(encoding="utf-8"))
        assert cross_version["realCrossVersionRollback"] is True
        assert cross_version["previousApi"] == {
            "image": "support-copilot-api:previous",
            "imageId": previous_api,
            "revision": previous_revision,
        }
        assert cross_version["currentCandidateApiImageId"] == known["api"]
        assert cross_version["schema"] == {
            "before": "5\t123",
            "underPreviousApi": "5\t123",
            "afterCurrentReturn": "5\t123",
        }
        assert cross_version["embeddingArtifact"]["before"] == cross_version["embeddingArtifact"]["underPreviousApi"]
        assert cross_version["embeddingArtifact"]["before"] == cross_version["embeddingArtifact"]["afterCurrentReturn"]
        assert cross_version["safeWriteId"] == "ticket-previous"
        assert cross_version["buildEvidence"] == {
            "contract": "build-compatible-api-image/v1",
            "schemaVersion": 1,
            "manifestSha256": build_manifest_sha,
            "identity": f"compatible-api-build-sha256-{build_manifest_sha}",
        }
        assert cross_version["onlyApiRecreated"] is True
        assert cross_version["persistedWriteReadableAfterReturn"] is True
        assert (state_dir / "previous-ref-mutated").read_text(encoding="utf-8") == mutated_previous_api
    else:
        assert not (evidence_dir / "cross-version-rollback.json").exists()
        assert not (state_dir / "previous-ref-mutated").exists()
    if use_prebuilt:
        assert (state_dir / "backup-mysql-image.log").read_text(encoding="utf-8").strip() == (
            "rehearsal-pilot-mysql:latest"
        )
        assert (state_dir / "restore-mysql-image.log").read_text(encoding="utf-8").strip() == (
            "rehearsal-pilot-mysql:latest"
        )
        assert (state_dir / "backup-oidc-image.log").read_text(encoding="utf-8").strip() == (
            known["oidc"]
        )
        assert (state_dir / "restore-oidc-image.log").read_text(encoding="utf-8").strip() == (
            known["oidc"]
        )
        assert (state_dir / "restore-compose-oidc-image.log").read_text(
            encoding="utf-8"
        ).strip() == (
            known["oidc"]
        )
        assert (state_dir / "restore-arguments.log").read_text(encoding="utf-8").split()[-1] == known["ai"]
        assert json.loads((evidence_dir / "restore-prebuilt-images.json").read_text(encoding="utf-8")) == {
            "api": {"reference": "rehearsal-pilot-restore-api:latest", "imageId": known["api"]},
            "ai": {"reference": "rehearsal-pilot-restore-ai:latest", "imageId": known["ai"]},
            "web": {"reference": "rehearsal-pilot-restore-web:latest", "imageId": known["web"]},
            "oidc": expected_restore_oidc_identity,
        }
        docker_calls = (state_dir / "docker.log").read_text(encoding="utf-8")
        assert "--project-name rehearsal-pilot-restore --file" in docker_calls
        assert "up --no-build --detach --wait" in docker_calls
        assert "up --build --detach --wait" not in docker_calls
        assert "image rm rehearsal-pilot-api:latest" not in docker_calls
        assert "image rm rehearsal-pilot-ai:latest" not in docker_calls
        assert "image rm rehearsal-pilot-web:latest" not in docker_calls
        operations_result = json.loads((evidence_dir / "operations-result.json").read_text(encoding="utf-8"))
        assert operations_result["realCrossVersionRollback"] is with_cross_version
        if with_cross_version:
            assert operations_result["crossVersionRollback"]["buildEvidence"]["manifestSha256"] == build_manifest_sha
            assert "real cross-version rollback completed" in result.stdout
            assert str(evidence_dir / "cross-version-rollback.json") in result.stdout
            assert str(evidence_dir / "operations-result.json") in result.stdout
            assert "NOT REQUESTED" not in result.stdout
        else:
            assert operations_result["crossVersionRollback"] is None
            assert build_manifest_sha not in json.dumps(operations_result)
            assert str(build_evidence) not in json.dumps(operations_result)
            assert "same-schema, persistence, and backup/restore completed" in result.stdout
            assert "cross-version rollback NOT REQUESTED" in result.stdout
            assert str(evidence_dir / "operations-result.json") in result.stdout
            assert "cross-version-rollback.json" not in result.stdout
    expected_api_only_commands = 2 if with_cross_version else 0
    assert sum(
        call.endswith("up --no-build --no-deps --force-recreate --detach --wait api")
        for call in docker_calls.splitlines()
    ) == expected_api_only_commands
    assert docker_calls.count(
        "up --no-build --no-deps --force-recreate --detach --wait api ai web"
    ) == (2 if use_prebuilt else 1)
    assert "force-recreate --detach --wait mysql" not in docker_calls
    assert "force-recreate --detach --wait oidc" not in docker_calls
    assert f"tag {mutated_previous_api} rehearsal-pilot-api:latest" not in docker_calls

    if use_prebuilt and not with_cross_version and cleanup_inspection_failure is None:
        owned_references = [
            "rehearsal-pilot-api:known-good",
            "rehearsal-pilot-ai:known-good",
            "rehearsal-pilot-web:known-good",
            "rehearsal-pilot-restore-api:latest",
            "rehearsal-pilot-restore-ai:latest",
            "rehearsal-pilot-restore-web:latest",
            "rehearsal-pilot-api:latest",
            "rehearsal-pilot-ai:latest",
            "rehearsal-pilot-web:latest",
        ]

        def reset_fake_state() -> None:
            for name in (
                "api-cross-count",
                "backup-completed",
                "build-count",
                "cleanup-started",
                "curl-headers.log",
                "curl.log",
                "failed-after-retag",
                "failed-secret-path",
                "inspect-count",
                "known-good-api-tag-count",
                "oidc-primary-deleted",
                "oidc-primary-rebound",
                "previous-ref-mutated",
                "pilot-restore-started",
                "restore-arguments.log",
                "restore-compose-oidc-image.log",
                "restore-oidc-image.log",
                "restore-oidc-validated",
            ):
                (state_dir / name).unlink(missing_ok=True)
            for service, image_id in known.items():
                _ = (state_dir / f"current-{service}").write_text(image_id, encoding="utf-8")
                _ = (state_dir / f"{service}-tag").write_text(image_id, encoding="utf-8")
            _ = (state_dir / "api-container").write_text("api-container-0", encoding="utf-8")
            _ = (state_dir / "caller-restore-oidc-tag").write_text(
                rebound_image,
                encoding="utf-8",
            )
            _ = (state_dir / "events").write_text("", encoding="utf-8")
            _ = (state_dir / "docker.log").write_text("", encoding="utf-8")

        reset_fake_state()
        image_failure_evidence = tmp_path / "image-failure-evidence"
        image_failure = subprocess.run(
            [
                str(pilot_script),
                "--compose-file",
                str(compose_file),
                "--evidence-dir",
                str(image_failure_evidence),
                "--project",
                "rehearsal-pilot",
            ],
            env={**run_env, "FAKE_FAIL_AFTER_RETAG": "false", "FAKE_IMAGE_LOOKUP_FAILURE": "all"},
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert image_failure.returncode == 1, image_failure.stderr
        assert "PASS:" not in image_failure.stdout
        image_receipt = (image_failure_evidence / "cleanup-receipt.log").read_text(encoding="utf-8")
        image_calls = (state_dir / "docker.log").read_text(encoding="utf-8")
        for reference in owned_references:
            assert f"image_reference_inspection_failed={reference}" in image_receipt
            assert f"image_reference_inspection_exit={reference}:67" in image_receipt
            assert f"image_reference_retained={reference}" not in image_receipt
            assert f"image rm {reference}" not in image_calls
        assert "cleanup_completed=false" in image_receipt
        assert "cleanup_completed=true" not in image_receipt

        reset_fake_state()
        rebind_evidence = tmp_path / "image-rebind-evidence"
        rebind_result = subprocess.run(
            [
                str(pilot_script),
                "--compose-file",
                str(compose_file),
                "--evidence-dir",
                str(rebind_evidence),
                "--project",
                "rehearsal-pilot",
            ],
            env={
                **run_env,
                "FAKE_FAIL_AFTER_RETAG": "false",
                "FAKE_IMAGE_REBIND_REFERENCE": "rehearsal-pilot-api:known-good",
            },
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert rebind_result.returncode == 1, rebind_result.stderr
        rebind_receipt = (rebind_evidence / "cleanup-receipt.log").read_text(encoding="utf-8")
        rebind_calls = (state_dir / "docker.log").read_text(encoding="utf-8")
        assert "image_reference_identity_mismatch=rehearsal-pilot-api:known-good" in rebind_receipt
        assert f"image_reference_observed_id=rehearsal-pilot-api:known-good:{rebound_image}" in rebind_receipt
        assert "image rm rehearsal-pilot-api:known-good" not in rebind_calls
        cleanup_start = rebind_calls.index(
            "ps -aq --filter label=com.docker.compose.project=rehearsal-pilot-restore "
            "--filter label=io.support-copilot.run-ownership="
        )
        cleanup_calls = rebind_calls[cleanup_start:]
        assert "image rm " not in cleanup_calls
        assert "tag " not in cleanup_calls
        assert "cleanup_completed=false" in rebind_receipt
        assert "PASS:" not in rebind_result.stdout

        reset_fake_state()
        secret_parent = tmp_path / "secret-cleanup-failure"
        secret_parent.mkdir()
        secret_failure_evidence = tmp_path / "secret-failure-evidence"
        secret_failure = subprocess.run(
            [
                str(pilot_script),
                "--compose-file",
                str(compose_file),
                "--evidence-dir",
                str(secret_failure_evidence),
                "--project",
                "rehearsal-pilot",
                "--use-prebuilt-current-images",
            ],
            env={
                **run_env,
                "FAKE_FAIL_AFTER_RETAG": "false",
                "FAKE_SECRET_CLEANUP_FAILURE": "true",
                "TMPDIR": str(secret_parent),
            },
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert secret_failure.returncode == 1, secret_failure.stderr
        assert "PASS:" not in secret_failure.stdout
        failed_secret_path = Path((state_dir / "failed-secret-path").read_text(encoding="utf-8").strip())
        assert failed_secret_path.parent == secret_parent
        assert failed_secret_path.is_dir()
        secret_receipt = (secret_failure_evidence / "cleanup-receipt.log").read_text(encoding="utf-8")
        assert "prebuilt_primary_tags_verified=true" in secret_receipt
        assert "secret_cleanup_exit=77" in secret_receipt
        assert "secret_directory_removed=false" in secret_receipt
        assert "cleanup_completed=false" in secret_receipt
        assert "cleanup_completed=true" not in secret_receipt

"""Fake-Docker contract coverage for pilot backup and restore.

# noqa: SIZE_OK
Cohesion: one backup-set fake verifies validation and restore lifecycle boundaries end to end.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import stat
import subprocess
import tarfile
from collections.abc import Mapping
from pathlib import Path
from typing import Literal, assert_never

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
BACKUP_SCRIPT = REPOSITORY_ROOT / "scripts/pilot-backup.sh"
RESTORE_SCRIPT = REPOSITORY_ROOT / "scripts/pilot-restore.sh"


def _write_executable(path: Path, content: str) -> None:
    _ = path.write_text(content, encoding="utf-8")
    _ = path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _run_restore(
    backup_dir: Path,
    *arguments: str,
    path: str = "/usr/bin:/bin",
    extra_env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(RESTORE_SCRIPT), "--backup-dir", str(backup_dir), *arguments],
        env={
            **os.environ,
            "PATH": path,
            "SUPPORT_COPILOT_RUN_OWNERSHIP": "0" * 32,
            "SUPPORT_COPILOT_OIDC_IMAGE": "restore-pilot-oidc:latest",
            **(extra_env or {}),
        },
        check=False,
        capture_output=True,
        text=True,
    )


def _run_backup(
    evidence_dir: Path,
    *arguments: str,
    path: str = "/usr/bin:/bin",
    extra_env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(BACKUP_SCRIPT), "--evidence-dir", str(evidence_dir), *arguments],
        env={**os.environ, "PATH": path, **(extra_env or {})},
        check=False,
        capture_output=True,
        text=True,
    )


def _write_manifest(
    backup_dir: Path,
    database: str,
    *,
    schema_version: Literal[2, 3] = 2,
    image_reference: str | None = None,
    reference_kind: Literal["immutableDigest", "projectLocalTag"] | None = None,
) -> None:
    dump_path = backup_dir / "support-copilot.sql"
    archive_path = backup_dir / "embedding-artifacts.tar"
    artifact_id = "b" * 64
    mysql_runtime = {
        "imageReference": image_reference or f"mysql:test@sha256:{'c' * 64}",
        "imageId": f"sha256:{'a' * 64}",
        "platform": "linux/amd64",
    }
    if reference_kind is not None:
        mysql_runtime["referenceKind"] = reference_kind
    manifest = {
        "schemaVersion": schema_version,
        "dumpFile": dump_path.name,
        "dumpSha256": hashlib.sha256(dump_path.read_bytes()).hexdigest(),
        "dumpBytes": dump_path.stat().st_size,
        "database": database,
        "mysqlRuntime": mysql_runtime,
        "flyway": {"version": "5", "checksum": 123},
        "sentinels": {
            "ticketId": "ticket-1",
            "analysisId": "analysis-1",
            "auditId": "audit-1",
        },
        "embeddingArtifacts": {
            "archiveFile": archive_path.name,
            "archiveSha256": hashlib.sha256(archive_path.read_bytes()).hexdigest(),
            "archiveBytes": archive_path.stat().st_size,
            "activeArtifactId": artifact_id,
            "activeManifestPath": f"{artifact_id}/manifest.json",
        },
    }
    _ = (backup_dir / "manifest.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )


def _write_valid_backup(backup_dir: Path, *, database: str = "support_copilot") -> None:
    backup_dir.mkdir(mode=0o700)
    dump = (
        f"CREATE DATABASE `{database}`;\nUSE `{database}`;\n"
        "CREATE TABLE sentinel (id int);\n-- Dump completed on 2026-08-30\n"
    )
    dump_path = backup_dir / "support-copilot.sql"
    _ = dump_path.write_text(dump, encoding="utf-8")
    artifact_id = "b" * 64
    with tarfile.open(backup_dir / "embedding-artifacts.tar", mode="w") as archive:
        for name, content in (
            ("active.json", json.dumps({"active_artifact_id": artifact_id}).encode()),
            (f"{artifact_id}/manifest.json", b"{}\n"),
            (f"{artifact_id}/metadata.json", b"[]\n"),
            (f"{artifact_id}/matrix.npy", b"matrix"),
        ):
            info = tarfile.TarInfo(name)
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
    _write_manifest(backup_dir, database)


def test_direct_compose_project_tag_reaches_real_backup_identity_parser(tmp_path: Path) -> None:
    # Given: the documented direct Compose project and its controlled local MySQL tag.
    seed_backup = tmp_path / "seed-backup"
    _write_valid_backup(seed_backup)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    docker_log = tmp_path / "docker.log"
    compose_file = tmp_path / "compose.yml"
    compose_file.write_text("services: {}\n", encoding="utf-8")
    secret_dir = tmp_path / "secrets"
    secret_dir.mkdir(mode=0o700)
    (secret_dir / "mysql_app_password").write_text("fixture-password\n", encoding="utf-8")
    image_id = f"sha256:{'a' * 64}"
    direct_project = "task15-pilot-local"
    local_reference = f"{direct_project}-mysql:latest"
    artifact_id = "b" * 64
    _write_executable(fake_bin / "timeout", '#!/usr/bin/env bash\nshift\nexec "$@"\n')
    _write_executable(
        fake_bin / "sha256sum",
        "#!/usr/bin/env bash\n/usr/bin/shasum -a 256 \"$1\"\n",
    )
    _write_executable(
        fake_bin / "docker",
        f"""#!/usr/bin/env bash
printf '%s\\n' "$*" >> {docker_log!s}
if [[ "$*" == *'--project-name restore-pilot'* ]]; then
  [[ "$SUPPORT_COPILOT_MYSQL_IMAGE" == '{local_reference}' ]] || exit 91
  [[ "$SUPPORT_COPILOT_OIDC_IMAGE" == 'restore-pilot-oidc:latest' ]] || exit 92
fi
case "$*" in
  *'SELECT DATABASE()'*) printf 'support_copilot\\n' ;;
  *'FROM tickets WHERE'*) printf '1\\t1\\t1\\n' ;;
  *flyway_schema_history*) printf '5\\t123\\n' ;;
  *information_schema.tables*) printf '0\\t0\\t0\\n' ;;
  *' ps -q mysql') printf 'mysql-container\\n' ;;
  'inspect --format {{{{.Config.Image}}}}|{{{{.Image}}}} mysql-container') printf '%s\\n' '{local_reference}|{image_id}' ;;
  'image inspect --format {{{{.Os}}}}/{{{{.Architecture}}}} {image_id}') printf 'linux/amd64\\n' ;;
  *mysqldump*) printf '%s\\n' 'CREATE DATABASE `support_copilot`;' 'USE `support_copilot`;' 'CREATE TABLE sentinel (id int);' '-- Dump completed on 2026-08-31' ;;
  *'exec -T ai python -'*) printf '%s\\n' '{{"artifactId":"{artifact_id}","manifestPath":"{artifact_id}/manifest.json"}}' ;;
  *'exec -T ai sh -ceu'*) cat "$FAKE_ARCHIVE" ;;
  *'run --no-deps --rm --entrypoint python ai'*) printf '%s\\n' '{{"artifactId":"{artifact_id}","manifestPath":"{artifact_id}/manifest.json"}}' ;;
esac
""",
    )
    backup_dir = tmp_path / "backup"
    common_env = {"FAKE_ARCHIVE": str(seed_backup / "embedding-artifacts.tar")}

    # When: the real producer creates schema v3 and the real consumer imports it.
    backup_result = _run_backup(
        backup_dir,
        "--compose-file", str(compose_file),
        "--project", direct_project,
        "--secret-dir", str(secret_dir),
        "--sentinel-ticket-id", "ticket-1",
        "--sentinel-analysis-id", "analysis-1",
        "--sentinel-audit-id", "audit-1",
        path=f"{fake_bin}:/usr/bin:/bin",
        extra_env=common_env,
    )
    restore_result = _run_restore(
        backup_dir,
        "--compose-file", str(compose_file),
        "--project", "restore-pilot",
        "--secret-dir", str(secret_dir),
        "--evidence-dir", str(tmp_path / "restore-evidence"),
        path=f"{fake_bin}:/usr/bin:/bin",
        extra_env=common_env,
    )

    # Then: the manifest declares the local kind and restore checks all three identities.
    assert backup_result.returncode == 0, backup_result.stderr
    assert restore_result.returncode == 0, restore_result.stderr
    manifest = json.loads((backup_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schemaVersion"] == 3
    assert manifest["mysqlRuntime"] == {
        "imageReference": local_reference,
        "referenceKind": "projectLocalTag",
        "imageId": image_id,
        "platform": "linux/amd64",
    }
    calls = docker_log.read_text(encoding="utf-8")
    assert calls.count(
        "inspect --format {{.Config.Image}}|{{.Image}} mysql-container"
    ) == 2


@pytest.mark.parametrize(
    ("schema_version", "image_reference", "reference_kind"),
    [
        (3, "bad reference:latest", "projectLocalTag"),
        (3, "backup-pilot-mysql:latest", "immutableDigest"),
        (3, f"mysql:test@sha256:{'c' * 64}", "projectLocalTag"),
        (2, "backup-pilot-mysql:latest", None),
    ],
    ids=["whitespace", "local-declared-digest", "digest-declared-local", "v2-local-tag"],
)
def test_restore_rejects_malformed_or_kind_mismatched_mysql_reference(
    tmp_path: Path,
    schema_version: Literal[2, 3],
    image_reference: str,
    reference_kind: Literal["immutableDigest", "projectLocalTag"] | None,
) -> None:
    # Given: a complete backup set with an invalid MySQL reference contract.
    backup_dir = tmp_path / "backup"
    _write_valid_backup(backup_dir)
    _write_manifest(
        backup_dir,
        "support_copilot",
        schema_version=schema_version,
        image_reference=image_reference,
        reference_kind=reference_kind,
    )

    # When: the real restore consumer parses the manifest boundary.
    result = _run_restore(backup_dir)

    # Then: it rejects the manifest before any Docker operation is needed.
    assert result.returncode != 0
    assert "manifest is malformed or has unsupported fields" in result.stderr


def test_restore_accepts_schema_v2_digest_manifest(tmp_path: Path) -> None:
    # Given: a legacy schema v2 manifest with an immutable digest reference.
    backup_dir = tmp_path / "backup"
    _write_valid_backup(backup_dir)

    # When: the real restore consumer parses it before required runtime arguments.
    result = _run_restore(backup_dir)

    # Then: parsing succeeds and validation advances to the next public contract.
    assert result.returncode != 0
    assert "--compose-file, --project, --secret-dir, and --evidence-dir are required" in result.stderr


def test_restore_accepts_schema_v3_immutable_digest_manifest(tmp_path: Path) -> None:
    # Given: a schema v3 manifest whose declared kind matches its digest reference.
    backup_dir = tmp_path / "backup"
    _write_valid_backup(backup_dir)
    _write_manifest(
        backup_dir,
        "support_copilot",
        schema_version=3,
        image_reference=f"registry.example.test/mysql:8.4@sha256:{'c' * 64}",
        reference_kind="immutableDigest",
    )

    # When: the real restore consumer parses it before required runtime arguments.
    result = _run_restore(backup_dir)

    # Then: schema parsing succeeds and validation advances to the next contract.
    assert result.returncode != 0
    assert "--compose-file, --project, --secret-dir, and --evidence-dir are required" in result.stderr


def test_backup_rejects_existing_evidence_directory(tmp_path: Path) -> None:
    # Given: an evidence path containing stale output from an earlier run.
    evidence_dir = tmp_path / "existing-evidence"
    evidence_dir.mkdir()

    # When: backup is asked to reuse that path.
    result = subprocess.run(
        [str(BACKUP_SCRIPT), "--evidence-dir", str(evidence_dir)],
        check=False,
        capture_output=True,
        text=True,
    )

    # Then: it fails before invoking any external command.
    assert result.returncode != 0
    assert "must not already exist" in result.stderr


def test_restore_rejects_symlinked_dump(tmp_path: Path) -> None:
    # Given: a plausible manifest whose dump path is a symlink.
    backup_dir = tmp_path / "backup"
    backup_dir.mkdir(mode=0o700)
    real_dump = tmp_path / "real.sql"
    _ = real_dump.write_text("CREATE DATABASE `support_copilot`;\n", encoding="utf-8")
    dump_path = backup_dir / "support-copilot.sql"
    _ = dump_path.symlink_to(real_dump)
    digest = hashlib.sha256(real_dump.read_bytes()).hexdigest()
    _ = (backup_dir / "manifest.json").write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "dumpFile": dump_path.name,
                "dumpSha256": digest,
                "dumpBytes": real_dump.stat().st_size,
                "database": "support_copilot",
                "mysqlImageId": f"sha256:{'a' * 64}",
                "flyway": {"version": "5", "checksum": 123},
                "sentinels": {
                    "ticketId": "ticket-1",
                    "analysisId": "analysis-1",
                    "auditId": "audit-1",
                },
            }
        ),
        encoding="utf-8",
    )

    # When: restore validates the backup set.
    result = _run_restore(backup_dir, "--database", "support_copilot")

    # Then: no external dependency is reached and the symlink is named.
    assert result.returncode != 0
    assert "regular non-symlink" in result.stderr


def test_restore_rejects_nonexistent_backup_directory(tmp_path: Path) -> None:
    result = _run_restore(tmp_path / "missing")
    assert result.returncode != 0
    assert "backup directory" in result.stderr


def test_restore_rejects_empty_dump(tmp_path: Path) -> None:
    backup_dir = tmp_path / "backup"
    _write_valid_backup(backup_dir)
    _ = (backup_dir / "support-copilot.sql").write_bytes(b"")

    result = _run_restore(backup_dir)
    assert result.returncode != 0
    assert "dump must not be empty" in result.stderr


def test_restore_rejects_missing_artifact_archive_before_docker(tmp_path: Path) -> None:
    # Given: the previous database-only backup shape with no embedding archive.
    backup_dir = tmp_path / "backup"
    _write_valid_backup(backup_dir)
    (backup_dir / "embedding-artifacts.tar").unlink()

    # When: restore validates the backup set.
    result = _run_restore(backup_dir)

    # Then: it fails at the artifact boundary without reaching Docker.
    assert result.returncode != 0
    assert "artifact archive" in result.stderr


@pytest.mark.parametrize("mutation", ["empty", "symlink", "tampered"])
def test_restore_rejects_invalid_artifact_archive_before_docker(
    tmp_path: Path,
    mutation: Literal["empty", "symlink", "tampered"],
) -> None:
    # Given: a valid backup whose artifact archive is empty, linked, or modified.
    backup_dir = tmp_path / "backup"
    _write_valid_backup(backup_dir)
    archive_path = backup_dir / "embedding-artifacts.tar"
    match mutation:
        case "empty":
            _ = archive_path.write_bytes(b"")
        case "symlink":
            real_archive = tmp_path / "real.tar"
            _ = archive_path.replace(real_archive)
            _ = archive_path.symlink_to(real_archive)
        case "tampered":
            with archive_path.open("ab") as stream:
                _ = stream.write(b"tampered")
        case unreachable:
            assert_never(unreachable)

    # When: restore validates the backup set.
    result = _run_restore(backup_dir)

    # Then: validation fails before any Docker dependency is required.
    assert result.returncode != 0
    assert "artifact archive" in result.stderr


def test_restore_rejects_malformed_manifest(tmp_path: Path) -> None:
    backup_dir = tmp_path / "backup"
    _write_valid_backup(backup_dir)
    _ = (backup_dir / "manifest.json").write_text("{", encoding="utf-8")

    result = _run_restore(backup_dir)
    assert result.returncode != 0
    assert "manifest is malformed" in result.stderr


def test_restore_rejects_tampered_dump_checksum(tmp_path: Path) -> None:
    backup_dir = tmp_path / "backup"
    _write_valid_backup(backup_dir)
    with (backup_dir / "support-copilot.sql").open("a", encoding="utf-8") as stream:
        _ = stream.write("-- tampered\n")

    result = _run_restore(backup_dir)
    assert result.returncode != 0
    assert "dump size does not match" in result.stderr


def test_restore_rejects_truncated_dump_with_matching_hash(tmp_path: Path) -> None:
    backup_dir = tmp_path / "backup"
    _write_valid_backup(backup_dir)
    dump_path = backup_dir / "support-copilot.sql"
    _ = dump_path.write_text(
        "CREATE DATABASE `support_copilot`;\nUSE `support_copilot`;\n",
        encoding="utf-8",
    )
    _write_manifest(backup_dir, "support_copilot")

    result = _run_restore(backup_dir)
    assert result.returncode != 0
    assert "completion marker" in result.stderr


def test_restore_rejects_wrong_database(tmp_path: Path) -> None:
    backup_dir = tmp_path / "backup"
    _write_valid_backup(backup_dir, database="other_database")

    result = _run_restore(backup_dir, "--database", "support_copilot")
    assert result.returncode != 0
    assert "manifest database does not match" in result.stderr


@pytest.mark.parametrize(
    ("target_image_id", "expected_error", "expected_mysql_calls"),
    [(f"sha256:{'a' * 64}", "did not recreate all sentinel rows", 3),
     (f"sha256:{'d' * 64}", "target MySQL image ID", 0)],
)
def test_restore_rejects_runtime_mismatch_or_no_op_import(
    tmp_path: Path,
    target_image_id: str,
    expected_error: str,
    expected_mysql_calls: int,
) -> None:
    backup_dir = tmp_path / "backup"
    _write_valid_backup(backup_dir)
    secret_dir = tmp_path / "secrets"
    secret_dir.mkdir(mode=0o700)
    _ = (secret_dir / "mysql_app_password").write_text(
        "not-a-secret-fixture\n",
        encoding="utf-8",
    )
    compose_file = tmp_path / "compose.yml"
    _ = compose_file.write_text("services: {}\n", encoding="utf-8")
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    docker_log = tmp_path / "docker.log"
    _write_executable(fake_bin / "timeout", '#!/usr/bin/env bash\nshift\nexec "$@"\n')
    _write_executable(
        fake_bin / "docker",
        f"""#!/usr/bin/env bash
printf '%s\\n' "$*" >> {docker_log!s}
case "$*" in
  *' ps -q mysql') printf 'mysql-container\\n' ;;
  'inspect --format {{{{.Config.Image}}}}|{{{{.Image}}}} mysql-container') printf '%s\\n' 'mysql:test@sha256:{'c' * 64}|{target_image_id}' ;;
  'image inspect --format {{{{.Os}}}}/{{{{.Architecture}}}} '*) printf 'linux/amd64\\n' ;;
  *information_schema.tables*) printf '0\\t0\\t0\\n' ;;
  *'FROM tickets WHERE'*) printf '0\\t0\\t0\\n' ;;
esac
""",
    )

    result = _run_restore(
        backup_dir,
        "--compose-file",
        str(compose_file),
        "--project",
        "fake-restore",
        "--secret-dir",
        str(secret_dir),
        "--evidence-dir",
        str(tmp_path / "restore-evidence"),
        path=f"{fake_bin}:/usr/bin:/bin",
    )
    assert result.returncode != 0
    assert expected_error in result.stderr
    calls = docker_log.read_text(encoding="utf-8")
    assert calls.count('exec mysql --user="$MYSQL_USER"') == expected_mysql_calls
    assert " down --volumes --remove-orphans" not in calls
    assert calls.count(
        "ps -aq --filter label=com.docker.compose.project=fake-restore "
        "--filter label=io.support-copilot.run-ownership=" + "0" * 32
    ) == 1


def test_restore_uses_exact_prebuilt_ai_image_without_building(tmp_path: Path) -> None:
    # Given: a valid backup and the restore project's AI tag resolving to the expected ID.
    backup_dir = tmp_path / "backup"
    _write_valid_backup(backup_dir)
    secret_dir = tmp_path / "secrets"
    secret_dir.mkdir(mode=0o700)
    _ = (secret_dir / "mysql_app_password").write_text("fixture-password\n", encoding="utf-8")
    compose_file = tmp_path / "compose.yml"
    _ = compose_file.write_text("services: {}\n", encoding="utf-8")
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    docker_log = tmp_path / "docker.log"
    expected_ai = f"sha256:{'d' * 64}"
    _write_executable(fake_bin / "timeout", '#!/usr/bin/env bash\nshift\nexec "$@"\n')
    _write_executable(
        fake_bin / "docker",
        f"""#!/usr/bin/env bash
printf '%s\\n' "$*" >> {docker_log!s}
case "$*" in
  *'image inspect --format {{{{.Id}}}} fake-restore-ai:latest'*) printf '%s\\n' '{expected_ai}' ;;
  *' ps -q mysql') printf 'mysql-container\\n' ;;
  'inspect --format {{{{.Config.Image}}}}|{{{{.Image}}}} mysql-container') printf '%s\\n' 'mysql:test@sha256:{'c' * 64}|sha256:{'a' * 64}' ;;
  'image inspect --format {{{{.Os}}}}/{{{{.Architecture}}}} '*) printf 'linux/amd64\\n' ;;
  *information_schema.tables*) printf '0\\t0\\t0\\n' ;;
  *'FROM tickets WHERE'*) printf '1\\t1\\t1\\n' ;;
  *flyway_schema_history*) printf '5\\t123\\n' ;;
  *'run --no-deps --rm --entrypoint python ai'*) printf '%s\\n' '{{"artifactId":"{'b' * 64}","manifestPath":"{'b' * 64}/manifest.json"}}' ;;
esac
""",
    )

    # When: restore receives the prebuilt AI identity.
    result = _run_restore(
        backup_dir,
        "--compose-file",
        str(compose_file),
        "--project",
        "fake-restore",
        "--secret-dir",
        str(secret_dir),
        "--evidence-dir",
        str(tmp_path / "restore-evidence"),
        "--prebuilt-ai-image-id",
        expected_ai,
        path=f"{fake_bin}:/usr/bin:/bin",
    )

    # Then: both artifact operations use v5-compatible run syntax without a build.
    assert result.returncode == 0, result.stderr
    calls = docker_log.read_text(encoding="utf-8")
    assert calls.count("image inspect --format {{.Id}} fake-restore-ai:latest") == 3
    assert " build ai" not in calls
    assert calls.count("run --no-deps --rm") == 2
    assert "run --no-build" not in calls


@pytest.mark.parametrize(
    ("collision", "expected_error"),
    [
        ("container", "restore project already owns containers"),
        ("network", "restore project already owns networks"),
        ("volume", "restore project already owns volumes"),
        ("default-image", "restore AI image tag already exists"),
    ],
)
def test_restore_rejects_existing_restore_resources_before_mutation(
    tmp_path: Path,
    collision: Literal["container", "network", "volume", "default-image"],
    expected_error: str,
) -> None:
    # Given: a valid backup and one pre-existing resource in the restore namespace.
    backup_dir = tmp_path / "backup"
    _write_valid_backup(backup_dir)
    secret_dir = tmp_path / "secrets"
    secret_dir.mkdir(mode=0o700)
    _ = (secret_dir / "mysql_app_password").write_text("fixture-password\n", encoding="utf-8")
    compose_file = tmp_path / "compose.yml"
    _ = compose_file.write_text("services: {}\n", encoding="utf-8")
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    docker_log = tmp_path / "docker.log"
    _write_executable(fake_bin / "timeout", "#!/usr/bin/env bash\nshift\nexec \"$@\"\n")
    _write_executable(
        fake_bin / "docker",
        f"""#!/usr/bin/env bash
printf '%s\\n' "$*" >> {docker_log!s}
case "$*" in
  *' ps -aq') [[ "$COLLISION" == container ]] && printf '%s\\n' 'existing-container' ;;
  *'network ls -q --filter label=com.docker.compose.project=fake-restore') [[ "$COLLISION" == network ]] && printf '%s\\n' 'existing-network' ;;
  *'volume ls -q --filter label=com.docker.compose.project=fake-restore') [[ "$COLLISION" == volume ]] && printf '%s\\n' 'existing-volume' ;;
  *'image inspect --format {{{{.Id}}}} fake-restore-ai:latest') [[ "$COLLISION" == default-image ]] && printf '%s\\n' 'sha256:{'e' * 64}' ;;
esac
exit 0
""",
    )
    evidence_dir = tmp_path / "restore-evidence"

    # When: restore runs its preflight against the occupied namespace.
    result = _run_restore(
        backup_dir,
        "--compose-file",
        str(compose_file),
        "--project",
        "fake-restore",
        "--secret-dir",
        str(secret_dir),
        "--evidence-dir",
        str(evidence_dir),
        path=f"{fake_bin}:/usr/bin:/bin",
        extra_env={"COLLISION": collision},
    )

    # Then: it fails before evidence, cleanup, or any resource mutation.
    assert result.returncode != 0
    assert expected_error in result.stderr
    calls = docker_log.read_text(encoding="utf-8")
    assert " down --volumes --remove-orphans" not in calls
    for mutation in (" up ", " build ", " run ", " exec "):
        assert mutation not in calls
    assert not evidence_dir.exists()


@pytest.mark.parametrize(
    ("failed_inspection", "failed_command", "expected_error"),
    [
        ("container", " ps -aq", "cannot inspect restore project containers"),
        (
            "network",
            "network ls -q --filter label=com.docker.compose.project=inspection-restore",
            "cannot inspect restore project networks",
        ),
        (
            "volume",
            "volume ls -q --filter label=com.docker.compose.project=inspection-restore",
            "cannot inspect restore project volumes",
        ),
    ],
)
def test_restore_rejects_resource_inspection_failure_before_mutation(
    tmp_path: Path,
    failed_inspection: Literal["container", "network", "volume"],
    failed_command: str,
    expected_error: str,
) -> None:
    # Given: a valid backup whose restore namespace cannot be inspected reliably.
    backup_dir = tmp_path / "backup"
    _write_valid_backup(backup_dir)
    secret_dir = tmp_path / "secrets"
    secret_dir.mkdir(mode=0o700)
    _ = (secret_dir / "mysql_app_password").write_text("fixture-password\n", encoding="utf-8")
    compose_file = tmp_path / "compose.yml"
    _ = compose_file.write_text("services: {}\n", encoding="utf-8")
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    docker_log = tmp_path / "docker.log"
    _write_executable(fake_bin / "timeout", '#!/usr/bin/env bash\nshift\nexec "$@"\n')
    _write_executable(
        fake_bin / "docker",
        f"""#!/usr/bin/env bash
printf '%s\n' "$*" >> {docker_log!s}
case "$*" in
  *'image inspect --format {{{{.Id}}}} inspection-restore-ai:latest') exit 1 ;;
  *' ps -aq') [[ "$FAILED_INSPECTION" != container ]] || exit 71 ;;
  'network ls -q --filter label=com.docker.compose.project=inspection-restore') [[ "$FAILED_INSPECTION" != network ]] || exit 72 ;;
  'volume ls -q --filter label=com.docker.compose.project=inspection-restore') [[ "$FAILED_INSPECTION" != volume ]] || exit 73 ;;
esac
exit 0
""",
    )
    evidence_dir = tmp_path / "restore-evidence"

    # When: restore performs collision preflight through its public CLI.
    result = _run_restore(
        backup_dir,
        "--compose-file",
        str(compose_file),
        "--project",
        "inspection-restore",
        "--secret-dir",
        str(secret_dir),
        "--evidence-dir",
        str(evidence_dir),
        path=f"{fake_bin}:/usr/bin:/bin",
        extra_env={"FAILED_INSPECTION": failed_inspection},
    )

    # Then: inspection failure cannot be treated as an empty namespace or trigger mutation.
    assert result.returncode != 0
    assert expected_error in result.stderr
    calls = docker_log.read_text(encoding="utf-8")
    assert failed_command in calls
    for mutation in (" up ", " down ", " build ", " run ", " exec "):
        assert mutation not in calls
    assert not evidence_dir.exists()


def test_restore_cleans_partial_project_when_compose_up_fails(tmp_path: Path) -> None:
    # Given: a clean namespace whose Compose up creates resources before failing.
    backup_dir = tmp_path / "backup"
    _write_valid_backup(backup_dir)
    secret_dir = tmp_path / "secrets"
    secret_dir.mkdir(mode=0o700)
    _ = (secret_dir / "mysql_app_password").write_text("fixture-password\n", encoding="utf-8")
    compose_file = tmp_path / "compose.yml"
    _ = compose_file.write_text("services: {}\n", encoding="utf-8")
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    docker_log = tmp_path / "docker.log"
    partial_resource = tmp_path / "partial-resource"
    _write_executable(fake_bin / "timeout", '#!/usr/bin/env bash\nshift\nexec "$@"\n')
    _write_executable(
        fake_bin / "docker",
        f"""#!/usr/bin/env bash
printf '%s\\n' "$*" >> {docker_log!s}
case "$*" in
  *'image inspect --format {{{{.Id}}}} partial-restore-ai:latest') exit 1 ;;
  *' up --detach --wait mysql') : > {partial_resource!s}; exit 42 ;;
  'ps -aq --filter label=com.docker.compose.project=partial-restore --filter label=io.support-copilot.run-ownership={'0' * 32}') [[ -f {partial_resource!s} ]] && printf '%s\\n' '111111111111' ;;
  'container rm --force 111111111111') rm -f {partial_resource!s} ;;
esac
""",
    )
    evidence_dir = tmp_path / "restore-evidence"

    # When: standalone restore attempts the first mutating Compose operation.
    result = _run_restore(
        backup_dir,
        "--compose-file",
        str(compose_file),
        "--project",
        "partial-restore",
        "--secret-dir",
        str(secret_dir),
        "--evidence-dir",
        str(evidence_dir),
        path=f"{fake_bin}:/usr/bin:/bin",
    )

    # Then: the original failure is preserved and only the owned project is cleaned.
    assert result.returncode == 42
    calls = docker_log.read_text(encoding="utf-8").splitlines()
    expected_prefix = f"compose --project-name partial-restore --file {compose_file!s}"
    assert calls.count(f"{expected_prefix} up --detach --wait mysql") == 1
    assert calls.count("container rm --force 111111111111") == 1
    assert not any(" down " in call for call in calls)
    assert not partial_resource.exists()


@pytest.mark.parametrize(
    ("leave_resources", "expected_cleanup_complete"),
    [(True, False), (False, True)],
    ids=["failed-owned-removal-with-leftovers", "owned-removal-resources-absent"],
)
def test_restore_records_exact_removal_and_inspects_project_resources(
    tmp_path: Path,
    leave_resources: bool,
    expected_cleanup_complete: bool,
) -> None:
    # Given: Compose up fails and exact owned-resource removal may also fail.
    backup_dir = tmp_path / "backup"
    _write_valid_backup(backup_dir)
    secret_dir = tmp_path / "secrets"
    secret_dir.mkdir(mode=0o700)
    _ = (secret_dir / "mysql_app_password").write_text("fixture-password\n", encoding="utf-8")
    compose_file = tmp_path / "compose.yml"
    _ = compose_file.write_text("services: {}\n", encoding="utf-8")
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    docker_log = tmp_path / "docker.log"
    resource_state = tmp_path / "resource-created"
    _write_executable(fake_bin / "timeout", '#!/usr/bin/env bash\nshift\nexec "$@"\n')
    _write_executable(
        fake_bin / "docker",
        f"""#!/usr/bin/env bash
printf '%s\n' "$*" >> {docker_log!s}
case "$*" in
  *'image inspect --format {{{{.Id}}}} cleanup-restore-ai:latest') exit 1 ;;
  *' up --detach --wait mysql') : >"$FAKE_RESOURCE_STATE"; exit 42 ;;
  'ps -aq --filter label=com.docker.compose.project=cleanup-restore --filter label=io.support-copilot.run-ownership={'0' * 32}') [[ -f "$FAKE_RESOURCE_STATE" ]] && printf '%s\n' '111111111111' ;;
  'container rm --force 111111111111') if [[ "$LEAVE_RESOURCES" == true ]]; then exit 17; else rm -f "$FAKE_RESOURCE_STATE"; fi ;;
  'ps -aq --filter label=com.docker.compose.project=cleanup-restore') [[ -f "$FAKE_RESOURCE_STATE" && "$LEAVE_RESOURCES" == true ]] && printf '%s\n' 'leftover-container' ;;
  'network ls -q --filter label=com.docker.compose.project=cleanup-restore') [[ -f "$FAKE_RESOURCE_STATE" && "$LEAVE_RESOURCES" == true ]] && printf '%s\n' 'leftover-network' ;;
  'volume ls -q --filter label=com.docker.compose.project=cleanup-restore') [[ -f "$FAKE_RESOURCE_STATE" && "$LEAVE_RESOURCES" == true ]] && printf '%s\n' 'leftover-volume' ;;
esac
exit 0
""",
    )
    evidence_dir = tmp_path / "restore-evidence"

    # When: standalone restore handles the failed first mutation.
    result = _run_restore(
        backup_dir,
        "--compose-file",
        str(compose_file),
        "--project",
        "cleanup-restore",
        "--secret-dir",
        str(secret_dir),
        "--evidence-dir",
        str(evidence_dir),
        path=f"{fake_bin}:/usr/bin:/bin",
        extra_env={
            "FAKE_RESOURCE_STATE": str(resource_state),
            "LEAVE_RESOURCES": str(leave_resources).lower(),
        },
    )

    # Then: the original failure wins and exact cleanup outcome is recorded.
    assert result.returncode == 42
    calls = docker_log.read_text(encoding="utf-8").splitlines()
    removal_call = "container rm --force 111111111111"
    assert calls.count(removal_call) == 1
    post_removal_calls = calls[calls.index(removal_call) + 1 :]
    for command in (
        "ps -aq --filter label=com.docker.compose.project=cleanup-restore",
        "network ls -q --filter label=com.docker.compose.project=cleanup-restore",
        "volume ls -q --filter label=com.docker.compose.project=cleanup-restore",
    ):
        assert post_removal_calls.count(command) == 1
    assert not any(" down " in call for call in calls)
    cleanup_result = json.loads(
        (evidence_dir / "error-cleanup-result.json").read_text(encoding="utf-8")
    )
    assert cleanup_result["removalExit"] == int(leave_resources)
    assert cleanup_result["cleanupComplete"] is expected_cleanup_complete
    expected_leftovers = ["leftover-container", "leftover-network", "leftover-volume"] if leave_resources else []
    observed_leftovers = [
        *cleanup_result["containers"]["leftovers"],
        *cleanup_result["networks"]["leftovers"],
        *cleanup_result["volumes"]["leftovers"],
    ]
    assert observed_leftovers == expected_leftovers
    assert cleanup_result["containers"]["inspectExit"] == 0
    assert cleanup_result["networks"]["inspectExit"] == 0
    assert cleanup_result["volumes"]["inspectExit"] == 0


def test_restore_never_removes_same_project_resources_with_different_ownership(
    tmp_path: Path,
) -> None:
    # Given: exact owned resources and foreign resources sharing the Compose project.
    backup_dir = tmp_path / "backup"
    _write_valid_backup(backup_dir)
    secret_dir = tmp_path / "secrets"
    secret_dir.mkdir(mode=0o700)
    _ = (secret_dir / "mysql_app_password").write_text("fixture-password\n", encoding="utf-8")
    compose_file = tmp_path / "compose.yml"
    _ = compose_file.write_text("services: {}\n", encoding="utf-8")
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    docker_log = tmp_path / "docker.log"
    resource_state = tmp_path / "resource-created"
    _write_executable(fake_bin / "timeout", '#!/usr/bin/env bash\nshift\nexec "$@"\n')
    _write_executable(
        fake_bin / "docker",
        f"""#!/usr/bin/env bash
printf '%s\n' "$*" >> {docker_log!s}
case "$*" in
  *'image inspect --format {{{{.Id}}}} ownership-restore-ai:latest') exit 1 ;;
  *' up --detach --wait mysql') : >"$FAKE_RESOURCE_STATE"; exit 42 ;;
  'ps -aq --filter label=com.docker.compose.project=ownership-restore --filter label=io.support-copilot.run-ownership={'0' * 32}') [[ -f "$FAKE_RESOURCE_STATE" ]] && printf '%s\n' '111111111111' ;;
  'network ls -q --filter label=com.docker.compose.project=ownership-restore --filter label=io.support-copilot.run-ownership={'0' * 32}') [[ -f "$FAKE_RESOURCE_STATE" ]] && printf '%s\n' '222222222222' ;;
  'volume ls -q --filter label=com.docker.compose.project=ownership-restore --filter label=io.support-copilot.run-ownership={'0' * 32}') [[ -f "$FAKE_RESOURCE_STATE" ]] && printf '%s\n' 'ownership-restore-owned' ;;
  'container rm --force 111111111111'|'network rm 222222222222'|'volume rm ownership-restore-owned') ;;
  'ps -aq --filter label=com.docker.compose.project=ownership-restore') [[ -f "$FAKE_RESOURCE_STATE" ]] && printf '%s\n' 'ffffffffffff' ;;
  'network ls -q --filter label=com.docker.compose.project=ownership-restore') [[ -f "$FAKE_RESOURCE_STATE" ]] && printf '%s\n' 'eeeeeeeeeeee' ;;
  'volume ls -q --filter label=com.docker.compose.project=ownership-restore') [[ -f "$FAKE_RESOURCE_STATE" ]] && printf '%s\n' 'ownership-restore-foreign' ;;
esac
exit 0
""",
    )
    evidence_dir = tmp_path / "restore-evidence"

    result = _run_restore(
        backup_dir,
        "--compose-file",
        str(compose_file),
        "--project",
        "ownership-restore",
        "--secret-dir",
        str(secret_dir),
        "--evidence-dir",
        str(evidence_dir),
        path=f"{fake_bin}:/usr/bin:/bin",
        extra_env={"FAKE_RESOURCE_STATE": str(resource_state)},
    )

    assert result.returncode == 42
    calls = docker_log.read_text(encoding="utf-8").splitlines()
    assert "container rm --force 111111111111" in calls
    assert "network rm 222222222222" in calls
    assert "volume rm ownership-restore-owned" in calls
    assert not any("ffffffffffff" in call and " rm " in call for call in calls)
    assert not any("eeeeeeeeeeee" in call and " rm " in call for call in calls)
    assert not any("ownership-restore-foreign" in call and " rm " in call for call in calls)
    assert not any(" down " in call for call in calls)
    cleanup_result = json.loads(
        (evidence_dir / "error-cleanup-result.json").read_text(encoding="utf-8")
    )
    assert cleanup_result["cleanupComplete"] is False
    assert cleanup_result["containers"]["leftovers"] == ["ffffffffffff"]
    assert cleanup_result["networks"]["leftovers"] == ["eeeeeeeeeeee"]
    assert cleanup_result["volumes"]["leftovers"] == ["ownership-restore-foreign"]


@pytest.mark.parametrize("prebuilt_id", [f"sha256:{'e' * 64}", f"sha256:{'f' * 64}"])
def test_restore_rejects_missing_or_mismatched_prebuilt_ai_before_mutation(
    tmp_path: Path,
    prebuilt_id: str,
) -> None:
    # Given: an expected ID that is either absent or differs from the exact restore tag.
    backup_dir = tmp_path / "backup"
    _write_valid_backup(backup_dir)
    secret_dir = tmp_path / "secrets"
    secret_dir.mkdir(mode=0o700)
    _ = (secret_dir / "mysql_app_password").write_text("fixture-password\n", encoding="utf-8")
    compose_file = tmp_path / "compose.yml"
    _ = compose_file.write_text("services: {}\n", encoding="utf-8")
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    docker_log = tmp_path / "docker.log"
    resolved_id = f"sha256:{'d' * 64}"
    docker_body = "exit 1" if prebuilt_id.endswith("e" * 64) else f"printf '%s\\n' '{resolved_id}'"
    _write_executable(fake_bin / "timeout", '#!/usr/bin/env bash\nshift\nexec "$@"\n')
    _write_executable(
        fake_bin / "docker",
        f"#!/usr/bin/env bash\nprintf '%s\\n' \"$*\" >> {docker_log!s}\n{docker_body}\n",
    )
    evidence_dir = tmp_path / "restore-evidence"

    # When: restore validates the prebuilt contract.
    result = _run_restore(
        backup_dir,
        "--compose-file",
        str(compose_file),
        "--project",
        "fake-restore",
        "--secret-dir",
        str(secret_dir),
        "--evidence-dir",
        str(evidence_dir),
        "--prebuilt-ai-image-id",
        prebuilt_id,
        path=f"{fake_bin}:/usr/bin:/bin",
    )

    # Then: it fails before Compose, restore resources, or evidence are created.
    assert result.returncode != 0
    assert "prebuilt AI image" in result.stderr
    assert " compose " not in docker_log.read_text(encoding="utf-8")
    assert not evidence_dir.exists()

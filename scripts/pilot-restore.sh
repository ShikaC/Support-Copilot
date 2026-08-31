#!/usr/bin/env bash
set -euo pipefail

umask 077

BACKUP_DIR=""
COMPOSE_FILE=""
COMPOSE_PROJECT=""
SECRET_DIR=""
EVIDENCE_DIR=""
DATABASE="support_copilot"
COMMAND_TIMEOUT_SECONDS="${SUPPORT_COPILOT_COMMAND_TIMEOUT_SECONDS:-60}"
PREBUILT_AI_IMAGE_ID=""
RUN_OWNERSHIP_LABEL="io.support-copilot.run-ownership"
RUN_OWNERSHIP="${SUPPORT_COPILOT_RUN_OWNERSHIP:-}"

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

regular_file() {
  [[ -f "$1" && ! -L "$1" ]] || fail "$2 must be a regular non-symlink file: $1"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --backup-dir) BACKUP_DIR="${2:-}"; shift 2 ;;
    --compose-file) COMPOSE_FILE="${2:-}"; shift 2 ;;
    --project) COMPOSE_PROJECT="${2:-}"; shift 2 ;;
    --secret-dir) SECRET_DIR="${2:-}"; shift 2 ;;
    --evidence-dir) EVIDENCE_DIR="${2:-}"; shift 2 ;;
    --database) DATABASE="${2:-}"; shift 2 ;;
    --prebuilt-ai-image-id) PREBUILT_AI_IMAGE_ID="${2:-}"; shift 2 ;;
    *) fail "unknown argument: $1" ;;
  esac
done

[[ -n "$BACKUP_DIR" ]] || fail "--backup-dir is required"
[[ -d "$BACKUP_DIR" && ! -L "$BACKUP_DIR" ]] || fail "backup directory must be a non-symlink directory"
MANIFEST_PATH="$BACKUP_DIR/manifest.json"
DUMP_PATH="$BACKUP_DIR/support-copilot.sql"
ARTIFACT_ARCHIVE_PATH="$BACKUP_DIR/embedding-artifacts.tar"
regular_file "$MANIFEST_PATH" "manifest"
regular_file "$DUMP_PATH" "dump"
regular_file "$ARTIFACT_ARCHIVE_PATH" "artifact archive"
[[ -s "$MANIFEST_PATH" ]] || fail "manifest must not be empty"
[[ -s "$DUMP_PATH" ]] || fail "dump must not be empty"
[[ -s "$ARTIFACT_ARCHIVE_PATH" ]] || fail "artifact archive must not be empty"
[[ "$DATABASE" =~ ^[A-Za-z0-9_]+$ ]] || fail "invalid database identity"

command -v python3 >/dev/null 2>&1 || fail "python3 is required"

if ! MANIFEST_VALUES="$(python3 - "$MANIFEST_PATH" "$ARTIFACT_ARCHIVE_PATH" <<'PY'
import json
from pathlib import PurePosixPath
import re
import sys
import tarfile
from pathlib import Path

value = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if not isinstance(value, dict) or set(value) != {
    "schemaVersion", "dumpFile", "dumpSha256", "dumpBytes", "database",
    "mysqlRuntime", "flyway", "sentinels", "embeddingArtifacts",
}:
    raise SystemExit(2)
mysql_runtime = value["mysqlRuntime"]
flyway = value["flyway"]
sentinels = value["sentinels"]
artifacts = value["embeddingArtifacts"]
if value["schemaVersion"] != 2 or value["dumpFile"] != "support-copilot.sql":
    raise SystemExit(2)
if not isinstance(value["dumpBytes"], int) or value["dumpBytes"] <= 0:
    raise SystemExit(2)
if not isinstance(value["dumpSha256"], str) or re.fullmatch(r"[a-f0-9]{64}", value["dumpSha256"]) is None:
    raise SystemExit(2)
if not isinstance(value["database"], str) or re.fullmatch(r"[A-Za-z0-9_]+", value["database"]) is None:
    raise SystemExit(2)
if not isinstance(mysql_runtime, dict) or set(mysql_runtime) != {"imageReference", "imageId", "platform"}:
    raise SystemExit(2)
if not isinstance(mysql_runtime["imageReference"], str) or "@sha256:" not in mysql_runtime["imageReference"]:
    raise SystemExit(2)
if not isinstance(mysql_runtime["imageId"], str) or re.fullmatch(r"sha256:[a-f0-9]{64}", mysql_runtime["imageId"]) is None:
    raise SystemExit(2)
if not isinstance(mysql_runtime["platform"], str) or re.fullmatch(r"[a-z0-9]+/[a-z0-9_]+", mysql_runtime["platform"]) is None:
    raise SystemExit(2)
if not isinstance(flyway, dict) or set(flyway) != {"version", "checksum"}:
    raise SystemExit(2)
if not isinstance(flyway["version"], str) or not isinstance(flyway["checksum"], int):
    raise SystemExit(2)
if not isinstance(sentinels, dict) or set(sentinels) != {"ticketId", "analysisId", "auditId"}:
    raise SystemExit(2)
ids = [sentinels["ticketId"], sentinels["analysisId"], sentinels["auditId"]]
if any(not isinstance(item, str) or re.fullmatch(r"[A-Za-z0-9_-]+", item) is None for item in ids):
    raise SystemExit(2)
if not isinstance(artifacts, dict) or set(artifacts) != {
    "archiveFile", "archiveSha256", "archiveBytes", "activeArtifactId", "activeManifestPath",
}:
    raise SystemExit(2)
artifact_id = artifacts["activeArtifactId"]
if artifacts["archiveFile"] != "embedding-artifacts.tar":
    raise SystemExit(2)
if not isinstance(artifacts["archiveSha256"], str) or re.fullmatch(r"[a-f0-9]{64}", artifacts["archiveSha256"]) is None:
    raise SystemExit(2)
if not isinstance(artifacts["archiveBytes"], int) or artifacts["archiveBytes"] <= 0:
    raise SystemExit(2)
if not isinstance(artifact_id, str) or re.fullmatch(r"[a-f0-9]{64}", artifact_id) is None:
    raise SystemExit(2)
if artifacts["activeManifestPath"] != f"{artifact_id}/manifest.json":
    raise SystemExit(2)
with tarfile.open(sys.argv[2], mode="r:") as archive:
    files = []
    active_pointer = None
    for member in archive.getmembers():
        normalized = member.name.removeprefix("./")
        path = PurePosixPath(normalized)
        if member.name.startswith("/") or ".." in path.parts or not (member.isfile() or member.isdir()):
            raise SystemExit(2)
        if member.isfile():
            files.append(normalized)
            if normalized == "active.json":
                stream = archive.extractfile(member)
                if stream is None:
                    raise SystemExit(2)
                active_pointer = json.load(stream)
    if not files or artifacts["activeManifestPath"] not in files:
        raise SystemExit(2)
    if not isinstance(active_pointer, dict) or active_pointer.get("active_artifact_id") != artifact_id:
        raise SystemExit(2)
print("\t".join([
    value["dumpSha256"], str(value["dumpBytes"]), value["database"],
    mysql_runtime["imageReference"], mysql_runtime["imageId"], mysql_runtime["platform"],
    flyway["version"], str(flyway["checksum"]), *ids,
    artifacts["archiveSha256"], str(artifacts["archiveBytes"]), artifact_id,
    artifacts["activeManifestPath"],
]))
PY
)"; then
  fail "manifest is malformed or has unsupported fields"
fi

IFS=$'\t' read -r EXPECTED_SHA EXPECTED_BYTES MANIFEST_DATABASE MYSQL_IMAGE_REFERENCE MYSQL_IMAGE_ID \
  MYSQL_PLATFORM FLYWAY_VERSION FLYWAY_CHECKSUM TICKET_ID ANALYSIS_ID AUDIT_ID \
  EXPECTED_ARTIFACT_SHA EXPECTED_ARTIFACT_BYTES ARTIFACT_ID ARTIFACT_MANIFEST_PATH <<<"$MANIFEST_VALUES"
[[ "$MANIFEST_DATABASE" == "$DATABASE" ]] || fail "manifest database does not match requested database"
[[ "$(wc -c <"$DUMP_PATH" | tr -d ' ')" == "$EXPECTED_BYTES" ]] || fail "dump size does not match manifest (truncated or extended backup)"
ACTUAL_SHA="$(python3 - "$DUMP_PATH" <<'PY'
import hashlib
import sys
from pathlib import Path

print(hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest())
PY
)"
[[ "$ACTUAL_SHA" == "$EXPECTED_SHA" ]] || fail "dump checksum does not match manifest"
grep -Fq "CREATE DATABASE" "$DUMP_PATH" || fail "dump is missing database creation metadata"
grep -Fq "USE \`$DATABASE\`;" "$DUMP_PATH" || fail "dump database identity does not match manifest"
grep -Fq -- "-- Dump completed on" "$DUMP_PATH" || fail "dump completion marker is missing (truncated backup)"
[[ "$(wc -c <"$ARTIFACT_ARCHIVE_PATH" | tr -d ' ')" == "$EXPECTED_ARTIFACT_BYTES" ]] || fail "artifact archive size does not match manifest"
ACTUAL_ARTIFACT_SHA="$(python3 - "$ARTIFACT_ARCHIVE_PATH" <<'PY'
import hashlib
import sys
from pathlib import Path

print(hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest())
PY
)"
[[ "$ACTUAL_ARTIFACT_SHA" == "$EXPECTED_ARTIFACT_SHA" ]] || fail "artifact archive checksum does not match manifest"

[[ -n "$COMPOSE_FILE" && -n "$COMPOSE_PROJECT" && -n "$SECRET_DIR" && -n "$EVIDENCE_DIR" ]] || fail "--compose-file, --project, --secret-dir, and --evidence-dir are required"
[[ "$RUN_OWNERSHIP" =~ ^[0-9a-f]{32}$ ]] || fail "SUPPORT_COPILOT_RUN_OWNERSHIP must be a 32-character lowercase hexadecimal run identity"
for command in timeout docker; do
  command -v "$command" >/dev/null 2>&1 || fail "$command is required"
done
[[ "$COMPOSE_PROJECT" =~ ^[a-z0-9][a-z0-9_-]{2,62}$ ]] || fail "invalid Compose project name"
regular_file "$COMPOSE_FILE" "Compose file"
[[ -d "$SECRET_DIR" && ! -L "$SECRET_DIR" ]] || fail "secret directory must be a non-symlink directory"
[[ "$(stat -c '%a' "$SECRET_DIR" 2>/dev/null || stat -f '%Lp' "$SECRET_DIR")" == "700" ]] || fail "secret directory must have mode 700"
regular_file "$SECRET_DIR/mysql_app_password" "MySQL password secret"
[[ -s "$SECRET_DIR/mysql_app_password" ]] || fail "MySQL password secret must not be empty"
[[ ! -e "$EVIDENCE_DIR" && ! -L "$EVIDENCE_DIR" ]] || fail "restore evidence directory must not already exist"
[[ -z "$PREBUILT_AI_IMAGE_ID" || "$PREBUILT_AI_IMAGE_ID" =~ ^sha256:[0-9a-f]{64}$ ]] || fail "prebuilt AI image ID must be a sha256 image ID"

PREBUILT_AI_IMAGE_REFERENCE="$COMPOSE_PROJECT-ai:latest"
assert_prebuilt_ai_image() {
  local resolved_image_id
  resolved_image_id="$(timeout "$COMMAND_TIMEOUT_SECONDS" docker image inspect --format '{{.Id}}' "$PREBUILT_AI_IMAGE_REFERENCE")" || fail "prebuilt AI image is missing: $PREBUILT_AI_IMAGE_REFERENCE"
  [[ "$resolved_image_id" == "$PREBUILT_AI_IMAGE_ID" ]] || fail "prebuilt AI image does not match expected ID: $PREBUILT_AI_IMAGE_REFERENCE"
}

if [[ -n "$PREBUILT_AI_IMAGE_ID" ]]; then
  assert_prebuilt_ai_image
else
  if EXISTING_AI_IMAGE_ID="$(timeout "$COMMAND_TIMEOUT_SECONDS" docker image inspect --format '{{.Id}}' "$PREBUILT_AI_IMAGE_REFERENCE" 2>/dev/null)"; then
    [[ -z "$EXISTING_AI_IMAGE_ID" ]] || fail "restore AI image tag already exists and would be overwritten: $PREBUILT_AI_IMAGE_REFERENCE"
  else
    IMAGE_INSPECT_STATUS=$?
    [[ "$IMAGE_INSPECT_STATUS" -eq 1 ]] || fail "cannot inspect restore AI image tag: $PREBUILT_AI_IMAGE_REFERENCE"
  fi
fi

compose() {
  PILOT_SECRET_DIR="$SECRET_DIR" SUPPORT_COPILOT_RUN_OWNERSHIP="$RUN_OWNERSHIP" \
    timeout "$COMMAND_TIMEOUT_SECONDS" \
    docker compose --project-name "$COMPOSE_PROJECT" --file "$COMPOSE_FILE" "$@"
}

remove_owned_restore_resources() {
  local cleanup_log="$1"
  local container_ids network_ids volume_names resource
  local removal_exit=0

  if container_ids="$(timeout "$COMMAND_TIMEOUT_SECONDS" docker ps -aq \
    --filter "label=com.docker.compose.project=$COMPOSE_PROJECT" \
    --filter "label=$RUN_OWNERSHIP_LABEL=$RUN_OWNERSHIP" 2>>"$cleanup_log")"; then
    :
  else
    echo "ERROR: cannot inspect owned restore containers" >>"$cleanup_log"
    return 1
  fi
  if network_ids="$(timeout "$COMMAND_TIMEOUT_SECONDS" docker network ls -q \
    --filter "label=com.docker.compose.project=$COMPOSE_PROJECT" \
    --filter "label=$RUN_OWNERSHIP_LABEL=$RUN_OWNERSHIP" 2>>"$cleanup_log")"; then
    :
  else
    echo "ERROR: cannot inspect owned restore networks" >>"$cleanup_log"
    return 1
  fi
  if volume_names="$(timeout "$COMMAND_TIMEOUT_SECONDS" docker volume ls -q \
    --filter "label=com.docker.compose.project=$COMPOSE_PROJECT" \
    --filter "label=$RUN_OWNERSHIP_LABEL=$RUN_OWNERSHIP" 2>>"$cleanup_log")"; then
    :
  else
    echo "ERROR: cannot inspect owned restore volumes" >>"$cleanup_log"
    return 1
  fi

  while IFS= read -r resource; do
    [[ -n "$resource" ]] || continue
    if [[ ! "$resource" =~ ^[0-9a-f]{12,64}$ ]]; then
      echo "ERROR: invalid owned restore container identity" >>"$cleanup_log"
      removal_exit=1
      continue
    fi
    timeout "$COMMAND_TIMEOUT_SECONDS" docker container rm --force "$resource" \
      >>"$cleanup_log" 2>&1 || removal_exit=1
  done <<<"$container_ids"
  while IFS= read -r resource; do
    [[ -n "$resource" ]] || continue
    if [[ ! "$resource" =~ ^[0-9a-f]{12,64}$ ]]; then
      echo "ERROR: invalid owned restore network identity" >>"$cleanup_log"
      removal_exit=1
      continue
    fi
    timeout "$COMMAND_TIMEOUT_SECONDS" docker network rm "$resource" \
      >>"$cleanup_log" 2>&1 || removal_exit=1
  done <<<"$network_ids"
  while IFS= read -r resource; do
    [[ -n "$resource" ]] || continue
    if [[ ! "$resource" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]{0,254}$ ]]; then
      echo "ERROR: invalid owned restore volume identity" >>"$cleanup_log"
      removal_exit=1
      continue
    fi
    timeout "$COMMAND_TIMEOUT_SECONDS" docker volume rm "$resource" \
      >>"$cleanup_log" 2>&1 || removal_exit=1
  done <<<"$volume_names"
  return "$removal_exit"
}

if RESTORE_CONTAINERS="$(compose ps -aq)"; then
  [[ -z "$RESTORE_CONTAINERS" ]] || fail "restore project already owns containers"
else
  RESOURCE_INSPECT_EXIT=$?
  fail "cannot inspect restore project containers (exit $RESOURCE_INSPECT_EXIT)"
fi
if RESTORE_NETWORKS="$(timeout "$COMMAND_TIMEOUT_SECONDS" docker network ls -q --filter "label=com.docker.compose.project=$COMPOSE_PROJECT")"; then
  [[ -z "$RESTORE_NETWORKS" ]] || fail "restore project already owns networks"
else
  RESOURCE_INSPECT_EXIT=$?
  fail "cannot inspect restore project networks (exit $RESOURCE_INSPECT_EXIT)"
fi
if RESTORE_VOLUMES="$(timeout "$COMMAND_TIMEOUT_SECONDS" docker volume ls -q --filter "label=com.docker.compose.project=$COMPOSE_PROJECT")"; then
  [[ -z "$RESTORE_VOLUMES" ]] || fail "restore project already owns volumes"
else
  RESOURCE_INSPECT_EXIT=$?
  fail "cannot inspect restore project volumes (exit $RESOURCE_INSPECT_EXIT)"
fi

RESTORE_PROJECT_CREATED=0
cleanup_on_error() {
  local primary_exit=$?
  local cleanup_exit=0
  trap - EXIT

  if [[ "$primary_exit" -ne 0 && "$RESTORE_PROJECT_CREATED" -eq 1 ]]; then
    local cleanup_log="$EVIDENCE_DIR/error-cleanup.log"
    local cleanup_result="$EVIDENCE_DIR/error-cleanup-result.json"
    local removal_exit container_inspect_exit network_inspect_exit volume_inspect_exit
    local container_leftovers network_leftovers volume_leftovers
    local cleanup_complete=false

    set +e
    : >"$cleanup_log"
    remove_owned_restore_resources "$cleanup_log"
    removal_exit=$?
    container_leftovers="$(timeout "$COMMAND_TIMEOUT_SECONDS" docker ps -aq \
      --filter "label=com.docker.compose.project=$COMPOSE_PROJECT" 2>>"$cleanup_log")"
    container_inspect_exit=$?
    network_leftovers="$(timeout "$COMMAND_TIMEOUT_SECONDS" docker network ls -q \
      --filter "label=com.docker.compose.project=$COMPOSE_PROJECT" 2>>"$cleanup_log")"
    network_inspect_exit=$?
    volume_leftovers="$(timeout "$COMMAND_TIMEOUT_SECONDS" docker volume ls -q \
      --filter "label=com.docker.compose.project=$COMPOSE_PROJECT" 2>>"$cleanup_log")"
    volume_inspect_exit=$?

    if [[ "$removal_exit" -eq 0 && "$container_inspect_exit" -eq 0 && \
      "$network_inspect_exit" -eq 0 && \
      "$volume_inspect_exit" -eq 0 && -z "$container_leftovers" && \
      -z "$network_leftovers" && -z "$volume_leftovers" ]]; then
      cleanup_complete=true
    else
      cleanup_exit=1
      echo "ERROR: restore cleanup left resources or could not verify their absence" >&2
    fi

    python3 - "$cleanup_result" "$removal_exit" "$cleanup_complete" \
      "$container_inspect_exit" "$container_leftovers" \
      "$network_inspect_exit" "$network_leftovers" \
      "$volume_inspect_exit" "$volume_leftovers" <<'PY'
import json
import sys
from pathlib import Path


def lines(value: str) -> list[str]:
    return [line for line in value.splitlines() if line]


Path(sys.argv[1]).write_text(
    json.dumps(
        {
            "removalExit": int(sys.argv[2]),
            "cleanupComplete": sys.argv[3] == "true",
            "containers": {
                "inspectExit": int(sys.argv[4]),
                "leftovers": lines(sys.argv[5]),
            },
            "networks": {
                "inspectExit": int(sys.argv[6]),
                "leftovers": lines(sys.argv[7]),
            },
            "volumes": {
                "inspectExit": int(sys.argv[8]),
                "leftovers": lines(sys.argv[9]),
            },
        },
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)
PY
    [[ "$?" -eq 0 ]] || cleanup_exit=1
    chmod 600 "$cleanup_result"
    [[ "$?" -eq 0 ]] || cleanup_exit=1
  fi

  if [[ "$primary_exit" -eq 0 && "$cleanup_exit" -ne 0 ]]; then
    primary_exit="$cleanup_exit"
  fi
  exit "$primary_exit"
}
trap cleanup_on_error EXIT

mkdir -m 700 "$EVIDENCE_DIR"
RESTORE_PROJECT_CREATED=1
compose up --detach --wait mysql

MYSQL_CONTAINER="$(compose ps -q mysql)"
[[ -n "$MYSQL_CONTAINER" ]] || fail "restore MySQL container identity is missing"
TARGET_RUNTIME="$(timeout "$COMMAND_TIMEOUT_SECONDS" docker inspect --format '{{.Config.Image}}|{{.Image}}' "$MYSQL_CONTAINER")"
TARGET_IMAGE_REFERENCE="${TARGET_RUNTIME%%|*}"
TARGET_IMAGE_ID="${TARGET_RUNTIME#*|}"
TARGET_PLATFORM="$(timeout "$COMMAND_TIMEOUT_SECONDS" docker image inspect --format '{{.Os}}/{{.Architecture}}' "$TARGET_IMAGE_ID")"
[[ "$TARGET_IMAGE_REFERENCE" == "$MYSQL_IMAGE_REFERENCE" ]] || fail "target MySQL image reference does not match backup manifest"
[[ "$TARGET_IMAGE_ID" == "$MYSQL_IMAGE_ID" ]] || fail "target MySQL image ID does not match backup manifest"
[[ "$TARGET_PLATFORM" == "$MYSQL_PLATFORM" ]] || fail "target MySQL platform does not match backup manifest"

mysql_query() {
  compose exec -T mysql sh -ceu '
    MYSQL_PWD="$(cat /run/secrets/mysql_app_password)"
    export MYSQL_PWD
    exec mysql --user="$MYSQL_USER" --database="$MYSQL_DATABASE" --batch --skip-column-names --execute="$1"
  ' sh "$1"
}

PRE_RESTORE="$(mysql_query "SELECT (SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='$DATABASE' AND table_name='tickets'),(SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='$DATABASE' AND table_name='analysis_runs'),(SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='$DATABASE' AND table_name='audit_events')")"
[[ "$PRE_RESTORE" == $'0\t0\t0' ]] || fail "fresh restore target is not empty"

compose exec -T mysql sh -ceu '
  MYSQL_PWD="$(cat /run/secrets/mysql_app_password)"
  export MYSQL_PWD
  exec mysql --user="$MYSQL_USER"
' <"$DUMP_PATH"

POST_RESTORE="$(mysql_query "SELECT (SELECT COUNT(*) FROM tickets WHERE id='$TICKET_ID'),(SELECT COUNT(*) FROM analysis_runs WHERE id='$ANALYSIS_ID'),(SELECT COUNT(*) FROM audit_events WHERE id='$AUDIT_ID')")"
[[ "$POST_RESTORE" == $'1\t1\t1' ]] || fail "restore did not recreate all sentinel rows"
RESTORED_MIGRATION="$(mysql_query 'SELECT version, checksum FROM flyway_schema_history WHERE success=1 ORDER BY installed_rank DESC LIMIT 1')"
[[ "$RESTORED_MIGRATION" == "$FLYWAY_VERSION"$'\t'"$FLYWAY_CHECKSUM" ]] || fail "restored Flyway state does not match manifest"

run_ai() {
  if [[ -n "$PREBUILT_AI_IMAGE_ID" ]]; then
    assert_prebuilt_ai_image
    compose run --no-deps --rm "$@"
  else
    compose run --no-deps --rm "$@"
  fi
}

if [[ -z "$PREBUILT_AI_IMAGE_ID" ]]; then
  compose build ai
fi
run_ai --entrypoint sh ai -ceu '
  root="$EMBEDDING_ARTIFACT_ROOT"
  test -z "$(find "$root" -mindepth 1 -print -quit)"
  exec tar --numeric-owner -xpf - -C "$root"
' <"$ARTIFACT_ARCHIVE_PATH"
RESTORED_ARTIFACT_INFO="$(run_ai --entrypoint python ai -c '
import json

from app.config import Settings
from app.embedding_artifact import EmbeddingArtifactStore
from app.knowledge_source import load_knowledge_corpus

settings = Settings()
artifact = EmbeddingArtifactStore(settings, load_knowledge_corpus(settings.knowledge_path)).load_active()
print(json.dumps({"artifactId": artifact.manifest.artifact_id,
                  "manifestPath": f"{artifact.manifest.artifact_id}/manifest.json"},
                 separators=(",", ":")))
')"
[[ "$(python3 -c 'import json,sys; print(json.load(sys.stdin)["artifactId"])' <<<"$RESTORED_ARTIFACT_INFO")" == "$ARTIFACT_ID" ]] || fail "restored active artifact ID does not match manifest"
[[ "$(python3 -c 'import json,sys; print(json.load(sys.stdin)["manifestPath"])' <<<"$RESTORED_ARTIFACT_INFO")" == "$ARTIFACT_MANIFEST_PATH" ]] || fail "restored active artifact path does not match manifest"

python3 - "$EVIDENCE_DIR/restore-result.json" "$DATABASE" "$MYSQL_IMAGE_REFERENCE" "$MYSQL_IMAGE_ID" "$MYSQL_PLATFORM" \
  "$TICKET_ID" "$ANALYSIS_ID" "$AUDIT_ID" "$PRE_RESTORE" "$POST_RESTORE" "$ARTIFACT_ID" \
  "$ARTIFACT_MANIFEST_PATH" "$ACTUAL_ARTIFACT_SHA" <<'PY'
import json
import sys
from pathlib import Path

Path(sys.argv[1]).write_text(json.dumps({
    "database": sys.argv[2],
    "mysqlRuntime": {"imageReference": sys.argv[3], "imageId": sys.argv[4], "platform": sys.argv[5]},
    "ticketId": sys.argv[6],
    "analysisId": sys.argv[7],
    "auditId": sys.argv[8],
    "preRestoreTableCounts": sys.argv[9],
    "postRestoreSentinelCounts": sys.argv[10],
    "embeddingArtifacts": {"activeArtifactId": sys.argv[11], "activeManifestPath": sys.argv[12], "archiveSha256": sys.argv[13]},
    "restoreChangedFreshDatabase": True,
}, indent=2) + "\n", encoding="utf-8")
PY
chmod 600 "$EVIDENCE_DIR/restore-result.json"
echo "PASS: validated backup restored into fresh project $COMPOSE_PROJECT with all sentinel rows present."

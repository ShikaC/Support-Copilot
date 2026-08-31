#!/usr/bin/env bash
set -euo pipefail

umask 077

COMPOSE_FILE=""
COMPOSE_PROJECT=""
SECRET_DIR=""
EVIDENCE_DIR=""
DATABASE="support_copilot"
TICKET_ID=""
ANALYSIS_ID=""
AUDIT_ID=""
COMMAND_TIMEOUT_SECONDS="${SUPPORT_COPILOT_COMMAND_TIMEOUT_SECONDS:-60}"

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

require_regular_file() {
  [[ -f "$1" && ! -L "$1" ]] || fail "$2 must be a regular non-symlink file: $1"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --compose-file) COMPOSE_FILE="${2:-}"; shift 2 ;;
    --project) COMPOSE_PROJECT="${2:-}"; shift 2 ;;
    --secret-dir) SECRET_DIR="${2:-}"; shift 2 ;;
    --evidence-dir) EVIDENCE_DIR="${2:-}"; shift 2 ;;
    --database) DATABASE="${2:-}"; shift 2 ;;
    --sentinel-ticket-id) TICKET_ID="${2:-}"; shift 2 ;;
    --sentinel-analysis-id) ANALYSIS_ID="${2:-}"; shift 2 ;;
    --sentinel-audit-id) AUDIT_ID="${2:-}"; shift 2 ;;
    *) fail "unknown argument: $1" ;;
  esac
done

[[ -n "$EVIDENCE_DIR" ]] || fail "--evidence-dir is required"
[[ ! -e "$EVIDENCE_DIR" && ! -L "$EVIDENCE_DIR" ]] || fail "evidence directory must not already exist: $EVIDENCE_DIR"
[[ -n "$COMPOSE_FILE" && -n "$COMPOSE_PROJECT" && -n "$SECRET_DIR" ]] || fail "--compose-file, --project, and --secret-dir are required"
[[ "$COMPOSE_PROJECT" =~ ^[a-z0-9][a-z0-9_-]{2,62}$ ]] || fail "invalid Compose project name"
[[ "$DATABASE" =~ ^[A-Za-z0-9_]+$ ]] || fail "invalid database identity"
for sentinel in "$TICKET_ID" "$ANALYSIS_ID" "$AUDIT_ID"; do
  [[ "$sentinel" =~ ^[A-Za-z0-9_-]+$ ]] || fail "all sentinel IDs are required and must be safe identifiers"
done
require_regular_file "$COMPOSE_FILE" "Compose file"
[[ -d "$SECRET_DIR" && ! -L "$SECRET_DIR" ]] || fail "secret directory must be a non-symlink directory"
[[ "$(stat -c '%a' "$SECRET_DIR" 2>/dev/null || stat -f '%Lp' "$SECRET_DIR")" == "700" ]] || fail "secret directory must have mode 700"
require_regular_file "$SECRET_DIR/mysql_app_password" "MySQL password secret"
[[ -s "$SECRET_DIR/mysql_app_password" ]] || fail "MySQL password secret must not be empty"
for command in docker python3 sha256sum timeout; do
  command -v "$command" >/dev/null 2>&1 || fail "$command is required"
done

mkdir -m 700 "$EVIDENCE_DIR"
DUMP_PATH="$EVIDENCE_DIR/support-copilot.sql"
ARTIFACT_ARCHIVE_PATH="$EVIDENCE_DIR/embedding-artifacts.tar"
MANIFEST_PATH="$EVIDENCE_DIR/manifest.json"

compose() {
  PILOT_SECRET_DIR="$SECRET_DIR" timeout "$COMMAND_TIMEOUT_SECONDS" \
    docker compose --project-name "$COMPOSE_PROJECT" --file "$COMPOSE_FILE" "$@"
}

mysql_query() {
  compose exec -T mysql sh -ceu '
    MYSQL_PWD="$(cat /run/secrets/mysql_app_password)"
    export MYSQL_PWD
    exec mysql --user="$MYSQL_USER" --database="$MYSQL_DATABASE" --batch --skip-column-names --execute="$1"
  ' sh "$1"
}

DATABASE_IDENTITY="$(mysql_query 'SELECT DATABASE()')"
[[ "$DATABASE_IDENTITY" == "$DATABASE" ]] || fail "running database identity does not match requested database"

SENTINEL_COUNTS="$(mysql_query "SELECT (SELECT COUNT(*) FROM tickets WHERE id='$TICKET_ID'),(SELECT COUNT(*) FROM analysis_runs WHERE id='$ANALYSIS_ID'),(SELECT COUNT(*) FROM audit_events WHERE id='$AUDIT_ID')")"
[[ "$SENTINEL_COUNTS" == $'1\t1\t1' ]] || fail "sentinel IDs are not all present in the source database"

MIGRATION_ROW="$(mysql_query 'SELECT version, checksum FROM flyway_schema_history WHERE success=1 ORDER BY installed_rank DESC LIMIT 1')"
[[ "$MIGRATION_ROW" == *$'\t'* ]] || fail "Flyway version/checksum could not be observed"
MIGRATION_VERSION="${MIGRATION_ROW%%$'\t'*}"
MIGRATION_CHECKSUM="${MIGRATION_ROW#*$'\t'}"

MYSQL_CONTAINER="$(compose ps -q mysql)"
[[ -n "$MYSQL_CONTAINER" ]] || fail "running MySQL container identity is missing"
MYSQL_RUNTIME="$(timeout "$COMMAND_TIMEOUT_SECONDS" docker inspect --format '{{.Config.Image}}|{{.Image}}' "$MYSQL_CONTAINER")"
MYSQL_IMAGE_REFERENCE="${MYSQL_RUNTIME%%|*}"
MYSQL_IMAGE_ID="${MYSQL_RUNTIME#*|}"
MYSQL_PLATFORM="$(timeout "$COMMAND_TIMEOUT_SECONDS" docker image inspect --format '{{.Os}}/{{.Architecture}}' "$MYSQL_IMAGE_ID")"
[[ "$MYSQL_IMAGE_REFERENCE" == *@sha256:* ]] || fail "MySQL configured image reference is not digest pinned"
[[ "$MYSQL_IMAGE_ID" =~ ^sha256:[a-f0-9]{64}$ ]] || fail "MySQL image identity is missing or malformed"
[[ "$MYSQL_PLATFORM" =~ ^[a-z0-9]+/[a-z0-9_]+$ ]] || fail "MySQL image platform is missing or malformed"

compose exec -T mysql sh -ceu '
  MYSQL_PWD="$(cat /run/secrets/mysql_app_password)"
  export MYSQL_PWD
  exec mysqldump --user="$MYSQL_USER" --single-transaction --routines --events --hex-blob --set-gtid-purged=OFF --databases "$MYSQL_DATABASE"
' >"$DUMP_PATH"
chmod 600 "$DUMP_PATH"
[[ -s "$DUMP_PATH" ]] || fail "mysqldump produced an empty backup"
grep -Fq "CREATE DATABASE" "$DUMP_PATH" || fail "mysqldump is missing database creation metadata"
grep -Fq "USE \`$DATABASE\`;" "$DUMP_PATH" || fail "mysqldump database identity is missing"

ARTIFACT_INFO="$(compose exec -T ai python - <<'PY'
import json

from app.config import Settings
from app.embedding_artifact import EmbeddingArtifactStore
from app.knowledge_source import load_knowledge_corpus

settings = Settings()
artifact = EmbeddingArtifactStore(
    settings,
    load_knowledge_corpus(settings.knowledge_path),
).load_active()
print(json.dumps({
    "artifactId": artifact.manifest.artifact_id,
    "manifestPath": f"{artifact.manifest.artifact_id}/manifest.json",
}, separators=(",", ":")))
PY
)"
IFS=$'\t' read -r ARTIFACT_ID ARTIFACT_MANIFEST_PATH <<<"$(python3 -c '
import json
import sys

value = json.load(sys.stdin)
print(value["artifactId"] + "\t" + value["manifestPath"])
' <<<"$ARTIFACT_INFO")"
[[ "$ARTIFACT_ID" =~ ^[a-f0-9]{64}$ ]] || fail "active embedding artifact identity is malformed"
[[ "$ARTIFACT_MANIFEST_PATH" == "$ARTIFACT_ID/manifest.json" ]] || fail "active embedding artifact path is malformed"
compose exec -T ai sh -ceu '
  root="$EMBEDDING_ARTIFACT_ROOT"
  test -f "$root/active.json" && test ! -L "$root/active.json"
  test -z "$(find "$root" -type l -print -quit)"
  test -n "$(find "$root" -type f -print -quit)"
  cd "$root"
  exec tar --sort=name --mtime="UTC 1970-01-01" --numeric-owner -cf - .
' >"$ARTIFACT_ARCHIVE_PATH"
chmod 600 "$ARTIFACT_ARCHIVE_PATH"
[[ -s "$ARTIFACT_ARCHIVE_PATH" ]] || fail "embedding artifact archive is empty"

DUMP_SHA256="$(sha256sum "$DUMP_PATH" | awk '{print $1}')"
DUMP_SIZE="$(wc -c <"$DUMP_PATH" | tr -d ' ')"
ARTIFACT_SHA256="$(sha256sum "$ARTIFACT_ARCHIVE_PATH" | awk '{print $1}')"
ARTIFACT_SIZE="$(wc -c <"$ARTIFACT_ARCHIVE_PATH" | tr -d ' ')"
python3 - "$MANIFEST_PATH" "$DUMP_SHA256" "$DUMP_SIZE" "$DATABASE" "$MYSQL_IMAGE_REFERENCE" \
  "$MYSQL_IMAGE_ID" "$MYSQL_PLATFORM" "$MIGRATION_VERSION" "$MIGRATION_CHECKSUM" \
  "$TICKET_ID" "$ANALYSIS_ID" "$AUDIT_ID" "$ARTIFACT_SHA256" "$ARTIFACT_SIZE" \
  "$ARTIFACT_ID" "$ARTIFACT_MANIFEST_PATH" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
manifest = {
    "schemaVersion": 2,
    "dumpFile": "support-copilot.sql",
    "dumpSha256": sys.argv[2],
    "dumpBytes": int(sys.argv[3]),
    "database": sys.argv[4],
    "mysqlRuntime": {
        "imageReference": sys.argv[5],
        "imageId": sys.argv[6],
        "platform": sys.argv[7],
    },
    "flyway": {"version": sys.argv[8], "checksum": int(sys.argv[9])},
    "sentinels": {
        "ticketId": sys.argv[10],
        "analysisId": sys.argv[11],
        "auditId": sys.argv[12],
    },
    "embeddingArtifacts": {
        "archiveFile": "embedding-artifacts.tar",
        "archiveSha256": sys.argv[13],
        "archiveBytes": int(sys.argv[14]),
        "activeArtifactId": sys.argv[15],
        "activeManifestPath": sys.argv[16],
    },
}
path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
PY
chmod 600 "$MANIFEST_PATH"

echo "PASS: logical MySQL backup created with validated manifest at $EVIDENCE_DIR (secret values suppressed)."

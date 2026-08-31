#!/usr/bin/env bash
set -euo pipefail

umask 077

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/infra/compose.pilot.yml"
EVIDENCE_DIR=""
RUN_ID="task15-$(date -u +%Y%m%dt%H%M%Sz)-$$"
PRIMARY_PROJECT="sc-$RUN_ID"
RESTORE_PROJECT="sc-${RUN_ID}-restore"
WEB_PORT="${SUPPORT_COPILOT_WEB_PORT:-$((20000 + $$ % 10000))}"
RESTORE_WEB_PORT="$((WEB_PORT + 1))"
COMMAND_TIMEOUT_SECONDS="${SUPPORT_COPILOT_COMMAND_TIMEOUT_SECONDS:-900}"
HTTP_TIMEOUT_SECONDS="${SUPPORT_COPILOT_HTTP_TIMEOUT_SECONDS:-15}"
SECRET_DIR=""
SECRET_PARENT=""
SECRET_NAME=""
SECRET_PARENT_DEVICE=""
SECRET_PARENT_INODE=""
SECRET_DEVICE=""
SECRET_INODE=""
SECRET_UID=""
SECRET_DIR_OWNED=0
CLEANED=0
PREVIOUS_API_IMAGE=""
PREVIOUS_API_REVISION=""
PREVIOUS_API_BUILD_EVIDENCE=""
PREVIOUS_API_IMAGE_ID=""
PREVIOUS_API_IMAGE_REFERENCE_ID=""
PREVIOUS_API_PLATFORM_IMAGE_ID=""
PREVIOUS_API_BUILD_MANIFEST_SHA=""
PREVIOUS_API_BUILD_IDENTITY=""
REAL_CROSS_VERSION_ROLLBACK=false
REQUESTED_CROSS_VERSION_ROLLBACK=false
USE_PREBUILT_CURRENT_IMAGES=false
PREBUILT_API_IMAGE_ID=""
PREBUILT_AI_IMAGE_ID=""
PREBUILT_WEB_IMAGE_ID=""
PREBUILT_API_PLATFORM_IMAGE_ID=""
PREBUILT_AI_PLATFORM_IMAGE_ID=""
PREBUILT_WEB_PLATFORM_IMAGE_ID=""
RUN_OWNERSHIP_LABEL="io.support-copilot.run-ownership"
RUN_OWNERSHIP=""
OWNED_PRIMARY_API_REFERENCE_ID=""
OWNED_PRIMARY_AI_REFERENCE_ID=""
OWNED_PRIMARY_WEB_REFERENCE_ID=""
OWNED_PRIMARY_API_KNOWN_GOOD_REFERENCE_ID=""
OWNED_PRIMARY_AI_KNOWN_GOOD_REFERENCE_ID=""
OWNED_PRIMARY_WEB_KNOWN_GOOD_REFERENCE_ID=""
OWNED_RESTORE_API_REFERENCE_ID=""
OWNED_RESTORE_AI_REFERENCE_ID=""
OWNED_RESTORE_WEB_REFERENCE_ID=""

fail() {
  echo "ERROR: $*" >&2
  return 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --compose-file) COMPOSE_FILE="${2:-}"; shift 2 ;;
    --evidence-dir) EVIDENCE_DIR="${2:-}"; shift 2 ;;
    --project) PRIMARY_PROJECT="${2:-}"; RESTORE_PROJECT="${2:-}-restore"; shift 2 ;;
    --previous-api-image) PREVIOUS_API_IMAGE="${2:-}"; shift 2 ;;
    --previous-api-revision) PREVIOUS_API_REVISION="${2:-}"; shift 2 ;;
    --previous-api-build-evidence) PREVIOUS_API_BUILD_EVIDENCE="${2:-}"; shift 2 ;;
    --use-prebuilt-current-images) USE_PREBUILT_CURRENT_IMAGES=true; shift ;;
    *) fail "unknown argument: $1"; exit 2 ;;
  esac
done

[[ -n "$EVIDENCE_DIR" ]] || EVIDENCE_DIR="$ROOT_DIR/.omo/evidence/$RUN_ID"
[[ ! -e "$EVIDENCE_DIR" && ! -L "$EVIDENCE_DIR" ]] || { fail "evidence directory must not already exist: $EVIDENCE_DIR"; exit 2; }
[[ -f "$COMPOSE_FILE" && ! -L "$COMPOSE_FILE" ]] || { fail "Compose file must be a regular non-symlink file"; exit 2; }
[[ "$PRIMARY_PROJECT" =~ ^[a-z0-9][a-z0-9_-]{2,62}$ ]] || { fail "invalid primary Compose project"; exit 2; }
[[ "$RESTORE_PROJECT" =~ ^[a-z0-9][a-z0-9_-]{2,62}$ ]] || { fail "invalid restore Compose project"; exit 2; }
ROLLBACK_INPUT_COUNT=0
[[ -n "$PREVIOUS_API_IMAGE" ]] && ROLLBACK_INPUT_COUNT=$((ROLLBACK_INPUT_COUNT + 1))
[[ -n "$PREVIOUS_API_REVISION" ]] && ROLLBACK_INPUT_COUNT=$((ROLLBACK_INPUT_COUNT + 1))
[[ -n "$PREVIOUS_API_BUILD_EVIDENCE" ]] && ROLLBACK_INPUT_COUNT=$((ROLLBACK_INPUT_COUNT + 1))
if [[ "$ROLLBACK_INPUT_COUNT" -ne 0 && "$ROLLBACK_INPUT_COUNT" -ne 3 ]]; then
  fail "--previous-api-image, --previous-api-revision, and --previous-api-build-evidence must be supplied together"
  exit 2
fi
if [[ "$ROLLBACK_INPUT_COUNT" -eq 3 ]]; then
  [[ "$PREVIOUS_API_IMAGE" != *[[:space:]]* && "$PREVIOUS_API_IMAGE" != -* ]] || { fail "invalid previous API image reference"; exit 2; }
  [[ "$PREVIOUS_API_REVISION" =~ ^[0-9a-f]{7,64}$ ]] || { fail "previous API revision must be a 7-64 character lowercase hexadecimal source revision"; exit 2; }
  REQUESTED_CROSS_VERSION_ROLLBACK=true
fi
PRIMARY_API_REFERENCE="$PRIMARY_PROJECT-api:latest"
PRIMARY_AI_REFERENCE="$PRIMARY_PROJECT-ai:latest"
PRIMARY_WEB_REFERENCE="$PRIMARY_PROJECT-web:latest"
PRIMARY_API_KNOWN_GOOD_REFERENCE="$PRIMARY_PROJECT-api:known-good"
PRIMARY_AI_KNOWN_GOOD_REFERENCE="$PRIMARY_PROJECT-ai:known-good"
PRIMARY_WEB_KNOWN_GOOD_REFERENCE="$PRIMARY_PROJECT-web:known-good"
RESTORE_API_REFERENCE="$RESTORE_PROJECT-api:latest"
RESTORE_AI_REFERENCE="$RESTORE_PROJECT-ai:latest"
RESTORE_WEB_REFERENCE="$RESTORE_PROJECT-web:latest"

if [[ "$REQUESTED_CROSS_VERSION_ROLLBACK" == true ]]; then
  for owned_reference in \
    "$PRIMARY_API_REFERENCE" "$PRIMARY_AI_REFERENCE" "$PRIMARY_WEB_REFERENCE" \
    "$PRIMARY_API_KNOWN_GOOD_REFERENCE" "$PRIMARY_AI_KNOWN_GOOD_REFERENCE" "$PRIMARY_WEB_KNOWN_GOOD_REFERENCE" \
    "$RESTORE_API_REFERENCE" "$RESTORE_AI_REFERENCE" "$RESTORE_WEB_REFERENCE"; do
    [[ "$PREVIOUS_API_IMAGE" != "$owned_reference" ]] || { fail "previous API image aliases a verifier-owned project image reference: $owned_reference"; exit 2; }
  done
  [[ -d "$PREVIOUS_API_BUILD_EVIDENCE" && ! -L "$PREVIOUS_API_BUILD_EVIDENCE" ]] || { fail "previous API build evidence must be a regular non-symlink directory"; exit 2; }
  [[ -f "$PREVIOUS_API_BUILD_EVIDENCE/manifest.json" && ! -L "$PREVIOUS_API_BUILD_EVIDENCE/manifest.json" ]] || { fail "previous API build evidence manifest.json must be a regular non-symlink file"; exit 2; }
  [[ -f "$PREVIOUS_API_BUILD_EVIDENCE/COMPLETE" && ! -L "$PREVIOUS_API_BUILD_EVIDENCE/COMPLETE" ]] || { fail "previous API build evidence COMPLETE must be a regular non-symlink file"; exit 2; }
fi

for command in curl docker openssl python3 sha256sum timeout; do
  command -v "$command" >/dev/null 2>&1 || { fail "$command is required"; exit 127; }
done
RUN_OWNERSHIP="$(python3 -c 'import secrets; print(secrets.token_hex(16))')"
[[ "$RUN_OWNERSHIP" =~ ^[0-9a-f]{32}$ ]] || { fail "could not generate run ownership identity"; exit 1; }
export SUPPORT_COPILOT_RUN_OWNERSHIP="$RUN_OWNERSHIP"

owned_resources() {
  local project="$1"
  local container_exit network_exit volume_exit
  local container_output network_output volume_output
  local inspection_exit=0

  if container_output="$(timeout 30 docker ps -aq --filter "label=com.docker.compose.project=$project")"; then
    container_exit=0
  else
    container_exit=$?
    inspection_exit="$container_exit"
  fi
  if network_output="$(timeout 30 docker network ls -q --filter "label=com.docker.compose.project=$project")"; then
    network_exit=0
  else
    network_exit=$?
    [[ "$inspection_exit" -ne 0 ]] || inspection_exit="$network_exit"
  fi
  if volume_output="$(timeout 30 docker volume ls -q --filter "label=com.docker.compose.project=$project")"; then
    volume_exit=0
  else
    volume_exit=$?
    [[ "$inspection_exit" -ne 0 ]] || inspection_exit="$volume_exit"
  fi

  if [[ "$inspection_exit" -ne 0 ]]; then
    python3 - "$project" "$container_exit" "$container_output" \
      "$network_exit" "$network_output" "$volume_exit" "$volume_output" >&2 <<'PY'
import json
import sys

print(
    "resource_inspection="
    + json.dumps(
        {
            "phase": "preflight",
            "project": sys.argv[1],
            "containers": {"inspectExit": int(sys.argv[2]), "stdout": sys.argv[3]},
            "networks": {"inspectExit": int(sys.argv[4]), "stdout": sys.argv[5]},
            "volumes": {"inspectExit": int(sys.argv[6]), "stdout": sys.argv[7]},
        },
        separators=(",", ":"),
    )
)
PY
    return "$inspection_exit"
  fi
  printf '%s\n%s\n%s\n' "$container_output" "$network_output" "$volume_output"
}

record_project_resources() {
  local project="$1"
  local container_exit network_exit volume_exit
  local container_output network_output volume_output
  local inspection_exit=0

  if container_output="$(timeout 30 docker ps -aq --filter "label=com.docker.compose.project=$project")"; then
    container_exit=0
  else
    container_exit=$?
    inspection_exit="$container_exit"
  fi
  if network_output="$(timeout 30 docker network ls -q --filter "label=com.docker.compose.project=$project")"; then
    network_exit=0
  else
    network_exit=$?
    [[ "$inspection_exit" -ne 0 ]] || inspection_exit="$network_exit"
  fi
  if volume_output="$(timeout 30 docker volume ls -q --filter "label=com.docker.compose.project=$project")"; then
    volume_exit=0
  else
    volume_exit=$?
    [[ "$inspection_exit" -ne 0 ]] || inspection_exit="$volume_exit"
  fi

  printf 'resource_inspection_project=%s\n' "$project"
  printf 'containers_inspection_exit=%s\ncontainers_output_begin\n%s\ncontainers_output_end\n' \
    "$container_exit" "$container_output"
  printf 'networks_inspection_exit=%s\nnetworks_output_begin\n%s\nnetworks_output_end\n' \
    "$network_exit" "$network_output"
  printf 'volumes_inspection_exit=%s\nvolumes_output_begin\n%s\nvolumes_output_end\n' \
    "$volume_exit" "$volume_output"

  if [[ "$inspection_exit" -ne 0 ]]; then
    echo "project_inspection_failed=$project"
    echo "project_inspection_exit=$inspection_exit"
    return 1
  fi
  if [[ -n "$container_output$network_output$volume_output" ]]; then
    echo "leftover_project=$project"
    return 1
  fi
  echo "project_absent=$project"
}

remove_owned_project_resources() {
  local project="$1"
  local container_ids network_ids volume_names resource

  container_ids="$(timeout 30 docker ps -aq \
    --filter "label=com.docker.compose.project=$project" \
    --filter "label=$RUN_OWNERSHIP_LABEL=$RUN_OWNERSHIP")" || {
      echo "owned_container_inspection_failed=$project"
      return 1
    }
  network_ids="$(timeout 30 docker network ls -q \
    --filter "label=com.docker.compose.project=$project" \
    --filter "label=$RUN_OWNERSHIP_LABEL=$RUN_OWNERSHIP")" || {
      echo "owned_network_inspection_failed=$project"
      return 1
    }
  volume_names="$(timeout 30 docker volume ls -q \
    --filter "label=com.docker.compose.project=$project" \
    --filter "label=$RUN_OWNERSHIP_LABEL=$RUN_OWNERSHIP")" || {
      echo "owned_volume_inspection_failed=$project"
      return 1
    }

  while IFS= read -r resource; do
    [[ -n "$resource" ]] || continue
    [[ "$resource" =~ ^[0-9a-f]{12,64}$ ]] || {
      echo "owned_container_identity_invalid=$project"
      return 1
    }
    timeout 30 docker container rm --force "$resource" || return 1
    echo "owned_container_removed=$project:$resource"
  done <<<"$container_ids"
  while IFS= read -r resource; do
    [[ -n "$resource" ]] || continue
    [[ "$resource" =~ ^[0-9a-f]{12,64}$ ]] || {
      echo "owned_network_identity_invalid=$project"
      return 1
    }
    timeout 30 docker network rm "$resource" || return 1
    echo "owned_network_removed=$project:$resource"
  done <<<"$network_ids"
  while IFS= read -r resource; do
    [[ -n "$resource" ]] || continue
    [[ "$resource" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]{0,254}$ ]] || {
      echo "owned_volume_identity_invalid=$project"
      return 1
    }
    timeout 30 docker volume rm "$resource" || return 1
    echo "owned_volume_removed=$project:$resource"
  done <<<"$volume_names"
}

assert_image_reference_absent() {
  local reference="$1"
  local image_ids
  image_ids="$(timeout 30 docker image ls --quiet --no-trunc "$reference")" || { fail "could not verify image reference ownership: $reference"; exit 2; }
  [[ -z "$image_ids" ]] || { fail "image reference already exists and is not caller-owned for this mode: $reference"; exit 2; }
}

image_inspect_linux_amd64() {
  local format="$1"
  local reference="$2"
  local inspect_help inspected platform

  inspect_help="$(timeout 30 docker image inspect --help)" || return
  if [[ "$inspect_help" == *"--platform"* ]]; then
    timeout 30 docker image inspect --platform linux/amd64 --format "$format" "$reference"
  else
    inspected="$(timeout 30 docker image inspect --format "{{.Os}}/{{.Architecture}}|$format" "$reference")" || return
    platform="${inspected%%|*}"
    [[ "$platform" == "linux/amd64" && "$inspected" == *"|"* ]] || return 1
    printf '%s\n' "${inspected#*|}"
  fi
}

image_reference_id() {
  local reference="$1"
  local image_id

  image_id="$(timeout 30 docker image inspect --format '{{.Id}}' "$reference")" || return 1
  [[ "$image_id" =~ ^sha256:[0-9a-f]{64}$ ]] || return 1
  printf '%s\n' "$image_id"
}

image_platform_id() {
  local reference="$1"
  local image_id

  image_id="$(image_inspect_linux_amd64 '{{.Id}}' "$reference")" || return 1
  [[ "$image_id" =~ ^sha256:[0-9a-f]{64}$ ]] || return 1
  printf '%s\n' "$image_id"
}

record_retained_image_reference() {
  local reference="$1"
  local expected_id="$2"
  local image_ids current_id inspection_exit

  if image_ids="$(timeout 30 docker image ls --quiet --no-trunc "$reference")"; then
    [[ -n "$image_ids" ]] || return 0
  else
    inspection_exit=$?
    echo "image_reference_inspection_failed=$reference"
    echo "image_reference_inspection_exit=$reference:$inspection_exit"
    return 1
  fi

  if [[ ! "$expected_id" =~ ^sha256:[0-9a-f]{64}$ ]]; then
    echo "image_reference_ownership_unproven=$reference"
    return 1
  fi
  current_id="$(image_reference_id "$reference")" || {
    echo "image_reference_identity_inspection_failed=$reference"
    return 1
  }
  if [[ "$current_id" != "$expected_id" ]]; then
    echo "image_reference_identity_mismatch=$reference"
    echo "image_reference_expected_id=$reference:$expected_id"
    echo "image_reference_observed_id=$reference:$current_id"
    return 1
  fi
  echo "image_reference_retained=$reference:$current_id"
}

verify_prebuilt_image_reference() {
  local reference="$1"
  local original_id="$2"
  local original_platform_id="$3"
  local current_id

  current_id="$(image_reference_id "$reference")" || {
    echo "prebuilt_reference_identity_inspection_failed=$reference"
    return 1
  }
  if [[ "$current_id" != "$original_id" ]]; then
    echo "prebuilt_reference_identity_mismatch=$reference"
    echo "prebuilt_reference_expected_id=$reference:$original_id"
    echo "prebuilt_reference_observed_id=$reference:$current_id"
    return 1
  fi
  [[ "$(image_platform_id "$current_id" || true)" == "$original_platform_id" ]] || return 1
  echo "prebuilt_reference_verified=$reference"
}

remove_owned_secret_dir() {
  local removal_exit=0
  [[ "$SECRET_DIR_OWNED" -eq 1 ]] || return 0
  python3 - "$SECRET_PARENT" "$SECRET_NAME" "support-copilot-task15-secrets." \
    "$SECRET_PARENT_DEVICE" "$SECRET_PARENT_INODE" "$SECRET_DEVICE" "$SECRET_INODE" "$SECRET_UID" <<'PY' || removal_exit=$?
import os
import stat
import sys

parent, name, prefix = sys.argv[1:4]
expected = tuple(int(value) for value in sys.argv[4:])
if not name.startswith(prefix) or "/" in name:
    raise SystemExit(3)
flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
parent_fd = os.open(parent, flags)
try:
    parent_stat = os.fstat(parent_fd)
    if (parent_stat.st_dev, parent_stat.st_ino) != expected[:2]:
        raise SystemExit(3)
    try:
        secret_fd = os.open(name, flags, dir_fd=parent_fd)
    except FileNotFoundError:
        raise SystemExit(0)
    try:
        secret_stat = os.fstat(secret_fd)
        if (secret_stat.st_dev, secret_stat.st_ino, secret_stat.st_uid) != expected[2:]:
            raise SystemExit(3)

        def remove_contents(directory_fd: int) -> None:
            for entry in os.scandir(directory_fd):
                entry_stat = entry.stat(follow_symlinks=False)
                if stat.S_ISDIR(entry_stat.st_mode) and not stat.S_ISLNK(entry_stat.st_mode):
                    child_fd = os.open(entry.name, flags, dir_fd=directory_fd)
                    try:
                        remove_contents(child_fd)
                    finally:
                        os.close(child_fd)
                    os.rmdir(entry.name, dir_fd=directory_fd)
                else:
                    os.unlink(entry.name, dir_fd=directory_fd)

        remove_contents(secret_fd)
    finally:
        os.close(secret_fd)
    current = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    if (current.st_dev, current.st_ino, current.st_uid) != expected[2:]:
        raise SystemExit(3)
    os.rmdir(name, dir_fd=parent_fd)
finally:
    os.close(parent_fd)
PY
  [[ "$removal_exit" -eq 0 ]] || return "$removal_exit"
  SECRET_DIR_OWNED=0
}

cleanup_secret_only() {
  local primary_exit=$?
  local cleanup_exit=0
  trap - EXIT
  remove_owned_secret_dir || cleanup_exit=1
  if [[ "$primary_exit" -eq 0 && "$cleanup_exit" -ne 0 ]]; then
    primary_exit="$cleanup_exit"
  fi
  exit "$primary_exit"
}

PRIMARY_RESOURCES="$(owned_resources "$PRIMARY_PROJECT")" || { fail "could not inspect primary project resources" || :; exit 2; }
[[ -z "$PRIMARY_RESOURCES" ]] || { fail "primary project already owns resources"; exit 2; }
RESTORE_RESOURCES="$(owned_resources "$RESTORE_PROJECT")" || { fail "could not inspect restore project resources" || :; exit 2; }
[[ -z "$RESTORE_RESOURCES" ]] || { fail "restore project already owns resources"; exit 2; }

for reference in \
  "$PRIMARY_API_KNOWN_GOOD_REFERENCE" "$PRIMARY_AI_KNOWN_GOOD_REFERENCE" "$PRIMARY_WEB_KNOWN_GOOD_REFERENCE" \
  "$RESTORE_API_REFERENCE" "$RESTORE_AI_REFERENCE" "$RESTORE_WEB_REFERENCE"; do
  assert_image_reference_absent "$reference"
done
if [[ "$USE_PREBUILT_CURRENT_IMAGES" == true ]]; then
  for service in api ai web; do
    image="$PRIMARY_PROJECT-$service:latest"
    image_id="$(image_reference_id "$image")" || { fail "prebuilt current image is missing or invalid: $image"; exit 2; }
    platform_image_id="$(image_platform_id "$image_id")" || { fail "could not inspect prebuilt current runtime image: $image"; exit 2; }
    case "$service" in
      api) PREBUILT_API_IMAGE_ID="$image_id"; PREBUILT_API_PLATFORM_IMAGE_ID="$platform_image_id" ;;
      ai) PREBUILT_AI_IMAGE_ID="$image_id"; PREBUILT_AI_PLATFORM_IMAGE_ID="$platform_image_id" ;;
      web) PREBUILT_WEB_IMAGE_ID="$image_id"; PREBUILT_WEB_PLATFORM_IMAGE_ID="$platform_image_id" ;;
    esac
  done
else
  assert_image_reference_absent "$PRIMARY_API_REFERENCE"
  assert_image_reference_absent "$PRIMARY_AI_REFERENCE"
  assert_image_reference_absent "$PRIMARY_WEB_REFERENCE"
fi

if [[ "$REQUESTED_CROSS_VERSION_ROLLBACK" == true ]]; then
  PREVIOUS_API_IMAGE_REFERENCE_ID="$(image_reference_id "$PREVIOUS_API_IMAGE")" || { fail "previous API image does not exist or has an invalid image ID: $PREVIOUS_API_IMAGE"; exit 2; }
  CURRENT_API_DOCKERFILE="$ROOT_DIR/services/support-copilot-api/Dockerfile"
  [[ -f "$CURRENT_API_DOCKERFILE" && ! -L "$CURRENT_API_DOCKERFILE" ]] || { fail "current API Dockerfile must be a regular non-symlink file"; exit 2; }
  PACKAGING_DOCKERFILE_SHA256="$(sha256sum "$CURRENT_API_DOCKERFILE" | awk '{print $1}')"
  [[ "$PACKAGING_DOCKERFILE_SHA256" =~ ^[0-9a-f]{64}$ ]] || { fail "could not hash current API Dockerfile"; exit 2; }
  PREVIOUS_API_BUILD_MANIFEST_SHA="$(python3 - "$PREVIOUS_API_BUILD_EVIDENCE" "$PREVIOUS_API_IMAGE" "$PREVIOUS_API_IMAGE_REFERENCE_ID" \
    "$PREVIOUS_API_REVISION" "$PACKAGING_DOCKERFILE_SHA256" <<'PY'
import hashlib
import json
import os
import re
import stat
import sys
import time
from pathlib import Path

directory = Path(sys.argv[1])
expected_image_ref, expected_image_id = sys.argv[2], sys.argv[3]
expected_revision, expected_packaging = sys.argv[4], sys.argv[5]
directory_stat = os.stat(directory, follow_symlinks=False)
if not stat.S_ISDIR(directory_stat.st_mode):
    raise SystemExit("evidence directory is not regular")
directory_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
try:
    if set(os.listdir(directory_fd)) != {"manifest.json", "COMPLETE"}:
        raise SystemExit("evidence directory shape is invalid")

    def read_regular(name: str, maximum: int) -> tuple[bytes, os.stat_result]:
        descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory_fd)
        with os.fdopen(descriptor, "rb") as stream:
            file_stat = os.fstat(stream.fileno())
            if not stat.S_ISREG(file_stat.st_mode):
                raise SystemExit(f"{name} is not a regular file")
            content = stream.read(maximum + 1)
        if len(content) > maximum:
            raise SystemExit(f"{name} is too large")
        return content, file_stat

    manifest_bytes, manifest_stat = read_regular("manifest.json", 16384)
    complete_bytes, complete_stat = read_regular("COMPLETE", 256)
finally:
    os.close(directory_fd)

now_ns = time.time_ns()
if complete_stat.st_mtime_ns < manifest_stat.st_mtime_ns:
    raise SystemExit("COMPLETE predates manifest.json")
if complete_stat.st_mtime_ns < now_ns - 86400 * 1_000_000_000:
    raise SystemExit("COMPLETE is older than 24 hours")
if complete_stat.st_mtime_ns > now_ns + 300 * 1_000_000_000:
    raise SystemExit("COMPLETE timestamp is in the future")
manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()
if complete_bytes != f"manifest_sha256={manifest_sha}\n".encode():
    raise SystemExit("COMPLETE manifest SHA is invalid")

def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise SystemExit(f"duplicate manifest key: {key}")
        value[key] = item
    return value

manifest = json.loads(manifest_bytes, object_pairs_hook=unique_object)
expected_fields = {
    "schema_version", "revision", "image_ref", "image_id", "source_archive_sha256",
    "packaging_dockerfile_sha256", "platform", "command_exit", "hash_binding",
}
if not isinstance(manifest, dict) or set(manifest) != expected_fields:
    raise SystemExit("manifest fields are invalid")
if type(manifest["schema_version"]) is not int or manifest["schema_version"] != 1:
    raise SystemExit("manifest schema_version is invalid")
if manifest["image_ref"] != expected_image_ref or manifest["image_id"] != expected_image_id:
    raise SystemExit("manifest image identity is invalid")
if manifest["revision"] != expected_revision or manifest["platform"] != "linux/amd64":
    raise SystemExit("manifest revision or platform is invalid")
hash_pattern = re.compile(r"^[0-9a-f]{64}$")
source_hash = manifest["source_archive_sha256"]
if not isinstance(source_hash, str) or hash_pattern.fullmatch(source_hash) is None:
    raise SystemExit("source archive hash is invalid")
if manifest["packaging_dockerfile_sha256"] != expected_packaging:
    raise SystemExit("packaging Dockerfile hash is invalid")
command_exit = manifest["command_exit"]
if not isinstance(command_exit, dict) or set(command_exit) != {"git_archive", "docker_build", "docker_inspect"}:
    raise SystemExit("command_exit fields are invalid")
if any(type(value) is not int or value != 0 for value in command_exit.values()):
    raise SystemExit("a builder command did not exit zero")
binding = manifest["hash_binding"]
if not isinstance(binding, dict) or set(binding) != {"oci_revision_label", "packaging_label", "source_archive_sha256"}:
    raise SystemExit("hash_binding fields are invalid")
if binding != {
    "oci_revision_label": expected_revision,
    "packaging_label": expected_packaging,
    "source_archive_sha256": source_hash,
}:
    raise SystemExit("hash_binding values are invalid")
print(manifest_sha)
PY
  )" || { fail "previous API build evidence validation failed"; exit 2; }
  [[ "$PREVIOUS_API_BUILD_MANIFEST_SHA" =~ ^[0-9a-f]{64}$ ]] || { fail "previous API build evidence manifest hash is invalid"; exit 2; }
  PREVIOUS_API_BUILD_IDENTITY="compatible-api-build-sha256-$PREVIOUS_API_BUILD_MANIFEST_SHA"
  PREVIOUS_API_IMAGE_ID="$PREVIOUS_API_IMAGE_REFERENCE_ID"
  PREVIOUS_API_PLATFORM_IMAGE_ID="$(image_platform_id "$PREVIOUS_API_IMAGE_REFERENCE_ID")" || { fail "could not inspect previous API runtime image"; exit 2; }
  if [[ "$USE_PREBUILT_CURRENT_IMAGES" == true && "$PREVIOUS_API_IMAGE_ID" == "$PREBUILT_API_IMAGE_ID" ]]; then
    fail "previous API image is the same image as the current candidate"
    exit 2
  fi
  PREVIOUS_IMAGE_METADATA="$(image_inspect_linux_amd64 '{{.Id}}|{{.Os}}|{{.Architecture}}|{{index .Config.Labels "org.opencontainers.image.revision"}}|{{index .Config.Labels "io.support-copilot.packaging-dockerfile-sha256"}}' "$PREVIOUS_API_IMAGE_REFERENCE_ID")" || { fail "could not inspect immutable previous API image metadata"; exit 2; }
  IFS='|' read -r INSPECTED_PREVIOUS_ID INSPECTED_PREVIOUS_OS INSPECTED_PREVIOUS_ARCH INSPECTED_PREVIOUS_REVISION INSPECTED_PREVIOUS_PACKAGING EXTRA_PREVIOUS_FIELD <<<"$PREVIOUS_IMAGE_METADATA"
  [[ -z "${EXTRA_PREVIOUS_FIELD:-}" && "$INSPECTED_PREVIOUS_ID" == "$PREVIOUS_API_PLATFORM_IMAGE_ID" && "$INSPECTED_PREVIOUS_OS" == "linux" && "$INSPECTED_PREVIOUS_ARCH" == "amd64" ]] || { fail "immutable previous API image metadata is malformed"; exit 2; }
  [[ "$INSPECTED_PREVIOUS_REVISION" == "$PREVIOUS_API_REVISION" ]] || { fail "previous API image revision label does not match --previous-api-revision"; exit 2; }
  [[ "$INSPECTED_PREVIOUS_PACKAGING" == "$PACKAGING_DOCKERFILE_SHA256" ]] || { fail "previous API image packaging label does not match the current API Dockerfile"; exit 2; }
  REAL_CROSS_VERSION_ROLLBACK=true
fi

mkdir -m 700 "$EVIDENCE_DIR"
printf 'primary_project_absent=%s\nrestore_project_absent=%s\n' "$PRIMARY_PROJECT" "$RESTORE_PROJECT" >"$EVIDENCE_DIR/resources-before.log"
if [[ "$USE_PREBUILT_CURRENT_IMAGES" == true ]]; then
  python3 - "$EVIDENCE_DIR/prebuilt-current-images.json" "$PREBUILT_API_IMAGE_ID" "$PREBUILT_AI_IMAGE_ID" "$PREBUILT_WEB_IMAGE_ID" <<'PY'
import json
import sys
from pathlib import Path

Path(sys.argv[1]).write_text(json.dumps({
    "api": sys.argv[2], "ai": sys.argv[3], "web": sys.argv[4],
}, indent=2) + "\n", encoding="utf-8")
PY
  chmod 600 "$EVIDENCE_DIR/prebuilt-current-images.json"
fi
SECRET_PARENT="$(cd -- "${TMPDIR:-/tmp}" && pwd -P)"
SECRET_DIR="$(mktemp -d "$SECRET_PARENT/support-copilot-task15-secrets.XXXXXX")"
trap cleanup_secret_only EXIT
SECRET_NAME="${SECRET_DIR##*/}"
[[ "$SECRET_NAME" == support-copilot-task15-secrets.* && "$SECRET_NAME" != */* ]] || { fail "owned secret directory name is invalid"; exit 1; }
SECRET_IDENTITY="$(python3 - "$SECRET_PARENT" "$SECRET_DIR" <<'PY'
import os
import stat
import sys

parent_stat = os.stat(sys.argv[1], follow_symlinks=False)
secret_stat = os.stat(sys.argv[2], follow_symlinks=False)
if not stat.S_ISDIR(parent_stat.st_mode) or not stat.S_ISDIR(secret_stat.st_mode):
    raise SystemExit(3)
print(f"{parent_stat.st_dev}:{parent_stat.st_ino}:{secret_stat.st_dev}:{secret_stat.st_ino}:{secret_stat.st_uid}")
PY
)"
IFS=':' read -r SECRET_PARENT_DEVICE SECRET_PARENT_INODE SECRET_DEVICE SECRET_INODE SECRET_UID <<<"$SECRET_IDENTITY"
[[ "$SECRET_PARENT_DEVICE" =~ ^[0-9]+$ && "$SECRET_PARENT_INODE" =~ ^[0-9]+$ && \
   "$SECRET_DEVICE" =~ ^[0-9]+$ && "$SECRET_INODE" =~ ^[0-9]+$ && "$SECRET_UID" =~ ^[0-9]+$ ]] || { fail "owned secret directory identity is invalid"; exit 1; }
SECRET_DIR_OWNED=1
trap 'exit 130' INT TERM HUP
chmod 700 "$SECRET_DIR"
openssl rand -hex 24 >"$SECRET_DIR/mysql_app_password"
openssl rand -hex 24 >"$SECRET_DIR/mysql_root_password"
openssl rand -hex 32 >"$SECRET_DIR/internal_service_token"
printf '%s\n' 'mock-mode-no-external-api-key' >"$SECRET_DIR/openai_api_key"
chmod 600 "$SECRET_DIR"/*

compose_for() {
  local project="$1"
  local port="$2"
  shift 2
  PILOT_SECRET_DIR="$SECRET_DIR" SUPPORT_COPILOT_WEB_PORT="$port" \
    SUPPORT_COPILOT_RUN_OWNERSHIP="$RUN_OWNERSHIP" \
    timeout "$COMMAND_TIMEOUT_SECONDS" docker compose \
      --project-name "$project" --file "$COMPOSE_FILE" "$@"
}

compose_service_image_id() {
  local project="$1"
  local port="$2"
  local service="$3"
  local container_id image_id

  container_id="$(compose_for "$project" "$port" ps -q "$service")" || return 1
  [[ -n "$container_id" ]] || return 1
  image_id="$(timeout 30 docker inspect --format '{{.Image}}' "$container_id")" || return 1
  [[ "$image_id" =~ ^sha256:[0-9a-f]{64}$ ]] || return 1
  printf '%s\n' "$image_id"
}

cleanup() {
  local primary_exit="$1"
  local cleanup_exit=0
  local prebuilt_verify_exit=0
  [[ "$CLEANED" -eq 0 ]] || return "$primary_exit"
  CLEANED=1
  {
    echo "cleanup_started=true"
    compose_for "$RESTORE_PROJECT" "$RESTORE_WEB_PORT" logs --no-color >"$EVIDENCE_DIR/restore-compose.log" 2>&1 || true
    compose_for "$PRIMARY_PROJECT" "$WEB_PORT" logs --no-color >"$EVIDENCE_DIR/primary-compose.log" 2>&1 || true
    remove_owned_project_resources "$RESTORE_PROJECT" || cleanup_exit=1
    remove_owned_project_resources "$PRIMARY_PROJECT" || cleanup_exit=1
    for project in "$PRIMARY_PROJECT" "$RESTORE_PROJECT"; do
      record_project_resources "$project" || cleanup_exit=1
    done
    if [[ "$USE_PREBUILT_CURRENT_IMAGES" == true ]]; then
      verify_prebuilt_image_reference "$PRIMARY_API_REFERENCE" "$PREBUILT_API_IMAGE_ID" \
        "$PREBUILT_API_PLATFORM_IMAGE_ID" || prebuilt_verify_exit=1
      verify_prebuilt_image_reference "$PRIMARY_AI_REFERENCE" "$PREBUILT_AI_IMAGE_ID" \
        "$PREBUILT_AI_PLATFORM_IMAGE_ID" || prebuilt_verify_exit=1
      verify_prebuilt_image_reference "$PRIMARY_WEB_REFERENCE" "$PREBUILT_WEB_IMAGE_ID" \
        "$PREBUILT_WEB_PLATFORM_IMAGE_ID" || prebuilt_verify_exit=1
      if [[ "$prebuilt_verify_exit" -eq 0 ]]; then
        echo "prebuilt_primary_tags_verified=true"
      else
        echo "prebuilt_primary_tags_verified=false"
        cleanup_exit=1
      fi
    fi
    record_retained_image_reference "$PRIMARY_API_KNOWN_GOOD_REFERENCE" "$OWNED_PRIMARY_API_KNOWN_GOOD_REFERENCE_ID" || cleanup_exit=1
    record_retained_image_reference "$PRIMARY_AI_KNOWN_GOOD_REFERENCE" "$OWNED_PRIMARY_AI_KNOWN_GOOD_REFERENCE_ID" || cleanup_exit=1
    record_retained_image_reference "$PRIMARY_WEB_KNOWN_GOOD_REFERENCE" "$OWNED_PRIMARY_WEB_KNOWN_GOOD_REFERENCE_ID" || cleanup_exit=1
    record_retained_image_reference "$RESTORE_API_REFERENCE" "$OWNED_RESTORE_API_REFERENCE_ID" || cleanup_exit=1
    record_retained_image_reference "$RESTORE_AI_REFERENCE" "$OWNED_RESTORE_AI_REFERENCE_ID" || cleanup_exit=1
    record_retained_image_reference "$RESTORE_WEB_REFERENCE" "$OWNED_RESTORE_WEB_REFERENCE_ID" || cleanup_exit=1
    if [[ "$USE_PREBUILT_CURRENT_IMAGES" == false ]]; then
      record_retained_image_reference "$PRIMARY_API_REFERENCE" "$OWNED_PRIMARY_API_REFERENCE_ID" || cleanup_exit=1
      record_retained_image_reference "$PRIMARY_AI_REFERENCE" "$OWNED_PRIMARY_AI_REFERENCE_ID" || cleanup_exit=1
      record_retained_image_reference "$PRIMARY_WEB_REFERENCE" "$OWNED_PRIMARY_WEB_REFERENCE_ID" || cleanup_exit=1
    fi
  } >"$EVIDENCE_DIR/cleanup-receipt.log" 2>&1

  local secret_cleanup_exit=0
  if remove_owned_secret_dir; then
    secret_cleanup_exit=0
  else
    secret_cleanup_exit=$?
    cleanup_exit=1
  fi
  {
    echo "secret_cleanup_exit=$secret_cleanup_exit"
    if [[ "$secret_cleanup_exit" -eq 0 ]]; then
      echo "secret_directory_removed=true"
    else
      echo "secret_directory_removed=false"
    fi
    if [[ "$cleanup_exit" -eq 0 ]]; then
      echo "cleanup_completed=true"
    else
      echo "cleanup_completed=false"
    fi
  } >>"$EVIDENCE_DIR/cleanup-receipt.log" 2>&1
  if [[ "$primary_exit" -eq 0 && "$cleanup_exit" -ne 0 ]]; then
    primary_exit="$cleanup_exit"
  fi
  return "$primary_exit"
}
cleanup_on_exit() {
  local primary_exit=$?
  local final_exit
  trap - EXIT
  if cleanup "$primary_exit"; then
    final_exit=0
  else
    final_exit=$?
  fi
  exit "$final_exit"
}
trap cleanup_on_exit EXIT

status_request() {
  local output="$1"
  shift
  curl --silent --show-error --max-time "$HTTP_TIMEOUT_SECONDS" \
    --output "$output" --write-out '%{http_code}' "$@"
}

authenticated_status_request() {
  local output="$1"
  local token="$2"
  local authorization_header
  shift 2
  [[ "$token" =~ ^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$ ]] || {
    fail "refusing to send malformed bearer token"
    return 1
  }
  printf -v authorization_header 'Authorization: Bearer %s' "$token"
  curl --silent --show-error --max-time "$HTTP_TIMEOUT_SECONDS" \
    --output "$output" --write-out '%{http_code}' --header @- "$@" <<<"$authorization_header"
}

assert_status() {
  local expected="$1"
  local actual="$2"
  local scenario="$3"
  [[ "$actual" == "$expected" ]] || fail "$scenario expected HTTP $expected, observed $actual"
}

json_field() {
  python3 - "$1" "$2" <<'PY'
import json
import sys
from pathlib import Path

value = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
for part in sys.argv[2].split("."):
    value = value[int(part)] if isinstance(value, list) else value[part]
if isinstance(value, (dict, list)):
    print(json.dumps(value, separators=(",", ":")))
elif value is None:
    print("null")
else:
    print(value)
PY
}

token_for() {
  local project="$1"
  local port="$2"
  local client_id="$3"
  local expected_subject="$4"
  local expected_role="$5"
  local expected_scopes="$6"
  local response
  response="$(compose_for "$project" "$port" exec -T ai python - "$client_id" <<'PY'
import sys
from pathlib import Path

import httpx

client_secret = Path("/run/secrets/internal_service_token").read_text(encoding="utf-8").strip()
if not client_secret:
    raise SystemExit("OIDC client authentication secret is empty")
response = httpx.post(
    "http://oidc:8080/default/token",
    data={"grant_type": "client_credentials"},
    auth=(sys.argv[1], client_secret),
    timeout=10.0,
)
if response.status_code != 200:
    raise SystemExit(f"OIDC token request returned HTTP {response.status_code}")
token = response.json()["access_token"]
assert isinstance(token, str) and token.count(".") == 2
print(token)
PY
)" || return 1
  python3 -c '
import base64
import json
import sys

token = sys.stdin.read().strip()
payload_segment = token.split(".")[1]
payload = json.loads(base64.urlsafe_b64decode(payload_segment + "=" * (-len(payload_segment) % 4)))
assert payload["iss"] == "http://oidc:8080/default"
assert payload["aud"] == "support-copilot-api" or payload["aud"] == ["support-copilot-api"]
assert payload["sub"] == sys.argv[1]
assert payload["roles"] == [sys.argv[2]]
expected_scopes = [scope for scope in sys.argv[3].split(",") if scope]
assert payload.get("support_scopes", []) == expected_scopes
print(token)
' "$expected_subject" "$expected_role" "$expected_scopes" <<<"$response"
}

container_started_at() {
  local container_id="$1"
  timeout 30 docker inspect --format '{{.State.StartedAt}}' "$container_id"
}

wait_gateway() {
  local port="$1"
  local deadline=$((SECONDS + COMMAND_TIMEOUT_SECONDS))
  while (( SECONDS < deadline )); do
    if curl --fail --silent --show-error --max-time 3 "http://127.0.0.1:$port/health" >/dev/null; then
      return 0
    fi
    sleep 1
  done
  fail "web gateway did not become ready before monotonic deadline"
}

artifact_info() {
  local project="$1"
  local port="$2"
  compose_for "$project" "$port" exec -T ai python - inspect-artifact <<'PY'
import hashlib
import json

from app.config import Settings
from app.embedding_artifact import EmbeddingArtifactStore
from app.knowledge_source import load_knowledge_corpus

settings = Settings(embedding_vector_dimension=2)
artifact = EmbeddingArtifactStore(settings, load_knowledge_corpus(settings.knowledge_path)).load_active()
manifest_path = settings.embedding_artifact_root / artifact.manifest.artifact_id / "manifest.json"
print(json.dumps({
    "artifactId": artifact.manifest.artifact_id,
    "manifestPath": f"{artifact.manifest.artifact_id}/manifest.json",
    "manifestSha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
}, separators=(",", ":")))
PY
}

echo "INFO: starting complete pilot topology under $PRIMARY_PROJECT (secret values suppressed)."
set +e
if [[ "$USE_PREBUILT_CURRENT_IMAGES" == true ]]; then
  compose_for "$PRIMARY_PROJECT" "$WEB_PORT" up --no-build --detach --wait >"$EVIDENCE_DIR/compose-up.log" 2>&1
else
  compose_for "$PRIMARY_PROJECT" "$WEB_PORT" up --build --detach --wait >"$EVIDENCE_DIR/compose-up.log" 2>&1
fi
COMPOSE_UP_EXIT=$?
set -e
if [[ "$COMPOSE_UP_EXIT" -ne 0 ]]; then
  fail "complete pilot topology did not reach healthy state; inspect compose-up.log and primary-compose.log" || true
  exit "$COMPOSE_UP_EXIT"
fi
if [[ "$USE_PREBUILT_CURRENT_IMAGES" == false ]]; then
  OWNED_PRIMARY_API_REFERENCE_ID="$(image_reference_id "$PRIMARY_API_REFERENCE")" || { fail "could not bind owned primary API image reference"; exit 1; }
  OWNED_PRIMARY_AI_REFERENCE_ID="$(image_reference_id "$PRIMARY_AI_REFERENCE")" || { fail "could not bind owned primary AI image reference"; exit 1; }
  OWNED_PRIMARY_WEB_REFERENCE_ID="$(image_reference_id "$PRIMARY_WEB_REFERENCE")" || { fail "could not bind owned primary web image reference"; exit 1; }
fi
wait_gateway "$WEB_PORT"
compose_for "$PRIMARY_PROJECT" "$WEB_PORT" ps --format json >"$EVIDENCE_DIR/topology.json"
if [[ "$USE_PREBUILT_CURRENT_IMAGES" == true ]]; then
  [[ "$(compose_service_image_id "$PRIMARY_PROJECT" "$WEB_PORT" api)" == "$PREBUILT_API_IMAGE_ID" ]] || fail "running API does not match prebuilt current image"
  [[ "$(compose_service_image_id "$PRIMARY_PROJECT" "$WEB_PORT" ai)" == "$PREBUILT_AI_IMAGE_ID" ]] || fail "running AI does not match prebuilt current image"
  [[ "$(compose_service_image_id "$PRIMARY_PROJECT" "$WEB_PORT" web)" == "$PREBUILT_WEB_IMAGE_ID" ]] || fail "running web does not match prebuilt current image"
fi

compose_for "$PRIMARY_PROJECT" "$WEB_PORT" exec -T ai python - build-artifact <<'PY' >"$EVIDENCE_DIR/artifact-build.json"
import json

import anyio

from app.config import Settings
from app.embedding_artifact import EmbeddingArtifactStore
from app.knowledge_source import load_knowledge_corpus


class DeterministicProvider:
    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, float(index % 2)] for index, _text in enumerate(texts)]


async def main() -> None:
    settings = Settings(embedding_vector_dimension=2)
    store = EmbeddingArtifactStore(settings, load_knowledge_corpus(settings.knowledge_path))
    manifest = await store.build(DeterministicProvider())
    store.activate(manifest.artifact_id)
    print(json.dumps({"artifactId": manifest.artifact_id, "rows": manifest.row_count}, separators=(",", ":")))


anyio.run(main)
PY
ARTIFACT_BEFORE="$(artifact_info "$PRIMARY_PROJECT" "$WEB_PORT")"
printf '%s\n' "$ARTIFACT_BEFORE" >"$EVIDENCE_DIR/artifact-before-restarts.json"
ARTIFACT_ID="$(json_field "$EVIDENCE_DIR/artifact-before-restarts.json" artifactId)"
ARTIFACT_PATH="$(json_field "$EVIDENCE_DIR/artifact-before-restarts.json" manifestPath)"
ARTIFACT_MANIFEST_SHA="$(json_field "$EVIDENCE_DIR/artifact-before-restarts.json" manifestSha256)"
[[ "$ARTIFACT_ID" =~ ^[a-f0-9]{64}$ && "$ARTIFACT_PATH" == "$ARTIFACT_ID/manifest.json" && "$ARTIFACT_MANIFEST_SHA" =~ ^[a-f0-9]{64}$ ]] || fail "active artifact observables are malformed"

AGENT_TOKEN="$(token_for "$PRIMARY_PROJECT" "$WEB_PORT" support-copilot-agent pilot-agent SUPPORT_AGENT ACCOUNT)"
REVIEWER_TOKEN="$(token_for "$PRIMARY_PROJECT" "$WEB_PORT" support-copilot-reviewer pilot-reviewer SUPPORT_REVIEWER "")"
ADMIN_TOKEN="$(token_for "$PRIMARY_PROJECT" "$WEB_PORT" support-copilot-admin pilot-admin SUPPORT_ADMIN "")"
BASE_URL="http://127.0.0.1:$WEB_PORT"

status="$(status_request "$EVIDENCE_DIR/gateway-health.json" "$BASE_URL/health")"
assert_status 200 "$status" "gateway liveness"
[[ "$(json_field "$EVIDENCE_DIR/gateway-health.json" status)" == "up" ]] || fail "gateway liveness body changed"
compose_for "$PRIMARY_PROJECT" "$WEB_PORT" exec -T api wget -qO- http://127.0.0.1:8080/actuator/health/readiness >"$EVIDENCE_DIR/api-readiness.json"
[[ "$(json_field "$EVIDENCE_DIR/api-readiness.json" status)" == "UP" ]] || fail "API readiness is not UP"

status="$(status_request "$EVIDENCE_DIR/anonymous.json" "$BASE_URL/api/tickets")"
assert_status 401 "$status" "anonymous ticket access"
[[ "$(json_field "$EVIDENCE_DIR/anonymous.json" code)" == "AUTHENTICATION_REQUIRED" ]] || fail "anonymous response has unstable error code"

status="$(authenticated_status_request "$EVIDENCE_DIR/agent-audit-denied.json" "$AGENT_TOKEN" "$BASE_URL/api/audit-events")"
assert_status 403 "$status" "agent audit access"
[[ "$(json_field "$EVIDENCE_DIR/agent-audit-denied.json" code)" == "ACCESS_DENIED" ]] || fail "role boundary has unstable error code"

status="$(authenticated_status_request "$EVIDENCE_DIR/ticket-create.json" "$AGENT_TOKEN" -X POST -H 'Content-Type: application/json' \
  --data '{"channel":"EMAIL","customerName":"Pilot Sentinel","customerCompany":"Synthetic Operations","customerTier":"STANDARD","subject":"Enterprise SSO login loop","description":"An enterprise SSO user sees a login loop after an identity provider domain configuration change. This is synthetic pilot data.","language":"en-US"}' \
  "$BASE_URL/api/tickets")"
assert_status 201 "$status" "authenticated ticket create"
TICKET_ID="$(json_field "$EVIDENCE_DIR/ticket-create.json" id)"
TICKET_VERSION="$(json_field "$EVIDENCE_DIR/ticket-create.json" version)"
[[ "$TICKET_ID" =~ ^ticket-[A-Za-z0-9-]+$ && "$TICKET_VERSION" =~ ^[0-9]+$ ]] || fail "ticket create omitted stable id/version fields"

status="$(authenticated_status_request "$EVIDENCE_DIR/ticket-read.json" "$AGENT_TOKEN" "$BASE_URL/api/tickets/$TICKET_ID")"
assert_status 200 "$status" "authenticated ticket read"
[[ "$(json_field "$EVIDENCE_DIR/ticket-read.json" id)" == "$TICKET_ID" ]] || fail "ticket read returned a different id"

status="$(authenticated_status_request "$EVIDENCE_DIR/ticket-patch.json" "$AGENT_TOKEN" -X PATCH -H 'Content-Type: application/json' \
  --data "{\"status\":\"IN_PROGRESS\",\"expectedVersion\":$TICKET_VERSION}" "$BASE_URL/api/tickets/$TICKET_ID")"
assert_status 200 "$status" "authenticated ticket patch"
PATCHED_VERSION="$(json_field "$EVIDENCE_DIR/ticket-patch.json" version)"
[[ "$PATCHED_VERSION" -gt "$TICKET_VERSION" ]] || fail "ticket patch did not advance version"

IDEMPOTENCY_KEY="pilot-analysis-$RUN_ID"
status="$(authenticated_status_request "$EVIDENCE_DIR/analysis.json" "$AGENT_TOKEN" -X POST -H "Idempotency-Key: $IDEMPOTENCY_KEY" "$BASE_URL/api/tickets/$TICKET_ID/analyze")"
assert_status 200 "$status" "Java-to-Python mock analysis"
ANALYSIS_ID="$(json_field "$EVIDENCE_DIR/analysis.json" id)"
ANALYSIS_TRACE="$(json_field "$EVIDENCE_DIR/analysis.json" traceId)"
ANALYSIS_MODE="$(json_field "$EVIDENCE_DIR/analysis.json" mode)"
ANALYSIS_STATUS="$(json_field "$EVIDENCE_DIR/analysis.json" status)"
[[ "$ANALYSIS_ID" =~ ^run_[A-F0-9]{12}$ && -n "$ANALYSIS_TRACE" && "$ANALYSIS_MODE" == "mock" && "$ANALYSIS_STATUS" == "SUCCEEDED" ]] || fail "analysis lacks stable successful mock id/trace/mode/status fields"

DIRECT_STATUS="$(compose_for "$PRIMARY_PROJECT" "$WEB_PORT" exec -T api timeout 15 bash -ceu '
  response=/tmp/direct-ai.response
  body=/tmp/direct-ai.json
  exec 3<>/dev/tcp/ai/8000
  printf "POST /analyze HTTP/1.1\r\nHost: ai:8000\r\nContent-Type: application/json\r\nContent-Length: 2\r\nConnection: close\r\n\r\n{}" >&3
  cat <&3 >"$response"
  exec 3<&-
  exec 3>&-
  awk "BEGIN { body = 0 } body { sub(/\\r$/, \"\"); print; next } /^\\r?$/ { body = 1 }" "$response" >"$body"
  awk "NR == 1 { print \$2; exit }" "$response"
')"
[[ "$DIRECT_STATUS" == "401" ]] || fail "direct Python analysis without internal token did not return 401"
compose_for "$PRIMARY_PROJECT" "$WEB_PORT" exec -T api cat /tmp/direct-ai.json >"$EVIDENCE_DIR/direct-python-no-token.json"
[[ "$(json_field "$EVIDENCE_DIR/direct-python-no-token.json" code)" == "INTERNAL_SERVICE_AUTHENTICATION_REQUIRED" ]] || fail "direct Python auth failure lacks stable code"

REPLY_CONTENT="$(json_field "$EVIDENCE_DIR/analysis.json" suggestedReply.content)"
status="$(authenticated_status_request "$EVIDENCE_DIR/review.json" "$REVIEWER_TOKEN" -X POST -H "Idempotency-Key: pilot-review-$RUN_ID" -H 'Content-Type: application/json' \
  --data "$(python3 -c 'import json,sys; print(json.dumps({"replyContent":sys.argv[1]}))' "$REPLY_CONTENT")" \
  "$BASE_URL/api/tickets/$TICKET_ID/analyses/$ANALYSIS_ID/reviews")"
assert_status 200 "$status" "reviewer review"
REVIEW_ID="$(json_field "$EVIDENCE_DIR/review.json" id)"
[[ "$(json_field "$EVIDENCE_DIR/review.json" analysisId)" == "$ANALYSIS_ID" && "$REVIEW_ID" =~ ^review- ]] || fail "review response lacks stable ids"
FINAL_TICKET_VERSION="$(json_field "$EVIDENCE_DIR/review.json" ticketVersion)"

status="$(authenticated_status_request "$EVIDENCE_DIR/audit.json" "$REVIEWER_TOKEN" "$BASE_URL/api/audit-events?targetId=$TICKET_ID&limit=100")"
assert_status 200 "$status" "reviewer audit query"
AUDIT_ID="$(json_field "$EVIDENCE_DIR/audit.json" items.0.id)"
[[ "$AUDIT_ID" =~ ^audit- ]] || fail "audit response lacks stable event id"

ADMIN_ACTUATOR_STATUS="$(compose_for "$PRIMARY_PROJECT" "$WEB_PORT" exec -T api bash -ceu '
  read -r token
  response=/tmp/admin-actuator.response
  body=/tmp/admin-actuator.json
  exec 3<>/dev/tcp/127.0.0.1/8080
  printf "GET /actuator/info HTTP/1.1\r\nHost: 127.0.0.1:8080\r\nAuthorization: Bearer %s\r\nConnection: close\r\n\r\n" "$token" >&3
  cat <&3 >"$response"
  exec 3<&-
  exec 3>&-
  awk "BEGIN { body = 0 } body { sub(/\\r$/, \"\"); print; next } /^\\r?$/ { body = 1 }" "$response" >"$body"
  awk "NR == 1 { print \$2; exit }" "$response"
' <<<"$ADMIN_TOKEN")"
assert_status 200 "$ADMIN_ACTUATOR_STATUS" "admin protected actuator access"
compose_for "$PRIMARY_PROJECT" "$WEB_PORT" exec -T api cat /tmp/admin-actuator.json >"$EVIDENCE_DIR/admin-actuator.json"

MIGRATION_ROW="$(compose_for "$PRIMARY_PROJECT" "$WEB_PORT" exec -T mysql sh -ceu '
  MYSQL_PWD="$(cat /run/secrets/mysql_app_password)"; export MYSQL_PWD
  exec mysql --user="$MYSQL_USER" --database="$MYSQL_DATABASE" --batch --skip-column-names --execute="SELECT version, checksum FROM flyway_schema_history WHERE success=1 ORDER BY installed_rank DESC LIMIT 1"
')"
[[ "$MIGRATION_ROW" == *$'\t'* ]] || fail "migration observable lacks version/checksum"

prove_persisted() {
  local phase="$1"
  local ticket_file="$EVIDENCE_DIR/persisted-ticket-after-$phase.json"
  local analysis_file="$EVIDENCE_DIR/persisted-analysis-after-$phase.json"
  local audit_file="$EVIDENCE_DIR/persisted-audit-after-$phase.json"
  local observed_status
  observed_status="$(authenticated_status_request "$ticket_file" "$AGENT_TOKEN" "$BASE_URL/api/tickets/$TICKET_ID")"
  assert_status 200 "$observed_status" "persisted ticket after $phase restart"
  [[ "$(json_field "$ticket_file" id)" == "$TICKET_ID" && "$(json_field "$ticket_file" version)" == "$FINAL_TICKET_VERSION" ]] || fail "ticket id/version changed after $phase restart"
  observed_status="$(authenticated_status_request "$analysis_file" "$AGENT_TOKEN" "$BASE_URL/api/tickets/$TICKET_ID/analyses")"
  assert_status 200 "$observed_status" "persisted analysis after $phase restart"
  [[ "$(json_field "$analysis_file" 0.id)" == "$ANALYSIS_ID" ]] || fail "analysis id changed after $phase restart"
  observed_status="$(authenticated_status_request "$audit_file" "$ADMIN_TOKEN" "$BASE_URL/api/audit-events?targetId=$TICKET_ID&limit=100")"
  assert_status 200 "$observed_status" "persisted audit after $phase restart"
  python3 - "$audit_file" "$AUDIT_ID" <<'PY'
import json
import sys
from pathlib import Path

value = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert sys.argv[2] in {item["id"] for item in value["items"]}
PY
  local observed_migration
  observed_migration="$(compose_for "$PRIMARY_PROJECT" "$WEB_PORT" exec -T mysql sh -ceu '
    MYSQL_PWD="$(cat /run/secrets/mysql_app_password)"; export MYSQL_PWD
    exec mysql --user="$MYSQL_USER" --database="$MYSQL_DATABASE" --batch --skip-column-names --execute="SELECT version, checksum FROM flyway_schema_history WHERE success=1 ORDER BY installed_rank DESC LIMIT 1"
  ')"
  [[ "$observed_migration" == "$MIGRATION_ROW" ]] || fail "Flyway state changed after $phase restart"
  printf '%s\n' "$observed_migration" >"$EVIDENCE_DIR/persisted-migration-after-$phase.txt"
}

API_CONTAINER="$(compose_for "$PRIMARY_PROJECT" "$WEB_PORT" ps -q api)"
API_STARTED_BEFORE="$(container_started_at "$API_CONTAINER")"
compose_for "$PRIMARY_PROJECT" "$WEB_PORT" restart api >"$EVIDENCE_DIR/restart-api.log" 2>&1
compose_for "$PRIMARY_PROJECT" "$WEB_PORT" up --no-deps --no-recreate --detach --wait api >"$EVIDENCE_DIR/recover-api.log" 2>&1
wait_gateway "$WEB_PORT"
compose_for "$PRIMARY_PROJECT" "$WEB_PORT" exec -T api wget -qO- http://127.0.0.1:8080/actuator/health/readiness >"$EVIDENCE_DIR/api-readiness-after-api-restart.json"
[[ "$(json_field "$EVIDENCE_DIR/api-readiness-after-api-restart.json" status)" == "UP" ]] || fail "API readiness is not UP after API restart"
API_STARTED_AFTER="$(container_started_at "$API_CONTAINER")"
[[ "$API_STARTED_BEFORE" != "$API_STARTED_AFTER" ]] || fail "API restart was a no-op"
prove_persisted api

MYSQL_CONTAINER="$(compose_for "$PRIMARY_PROJECT" "$WEB_PORT" ps -q mysql)"
MYSQL_STARTED_BEFORE="$(container_started_at "$MYSQL_CONTAINER")"
compose_for "$PRIMARY_PROJECT" "$WEB_PORT" restart mysql >"$EVIDENCE_DIR/restart-mysql.log" 2>&1
compose_for "$PRIMARY_PROJECT" "$WEB_PORT" up --detach --wait >"$EVIDENCE_DIR/recover-mysql.log" 2>&1
wait_gateway "$WEB_PORT"
MYSQL_STARTED_AFTER="$(container_started_at "$MYSQL_CONTAINER")"
[[ "$MYSQL_STARTED_BEFORE" != "$MYSQL_STARTED_AFTER" ]] || fail "MySQL restart was a no-op"
prove_persisted mysql

STACK_STARTED_BEFORE="$(container_started_at "$API_CONTAINER")"
compose_for "$PRIMARY_PROJECT" "$WEB_PORT" stop >"$EVIDENCE_DIR/restart-stack-stop.log" 2>&1
compose_for "$PRIMARY_PROJECT" "$WEB_PORT" start --wait >"$EVIDENCE_DIR/restart-stack-start.log" 2>&1
wait_gateway "$WEB_PORT"
STACK_STARTED_AFTER="$(container_started_at "$API_CONTAINER")"
[[ "$STACK_STARTED_BEFORE" != "$STACK_STARTED_AFTER" ]] || fail "complete-stack restart was a no-op"
prove_persisted stack
ARTIFACT_AFTER_STACK="$(artifact_info "$PRIMARY_PROJECT" "$WEB_PORT")"
[[ "$ARTIFACT_AFTER_STACK" == "$ARTIFACT_BEFORE" ]] || fail "embedding artifact identity changed after complete-stack restart"
printf '%s\n' "$ARTIFACT_AFTER_STACK" >"$EVIDENCE_DIR/artifact-after-stack-restart.json"

status="$(authenticated_status_request "$EVIDENCE_DIR/post-restart-write.json" "$AGENT_TOKEN" -X POST -H 'Content-Type: application/json' \
  --data '{"channel":"CHAT","customerName":"Post Restart","customerCompany":"Synthetic Operations","customerTier":"STANDARD","subject":"Safe post restart write","description":"Synthetic verification write after all restart boundaries.","language":"en-US"}' "$BASE_URL/api/tickets")"
assert_status 201 "$status" "post-restart safe write"
POST_RESTART_TICKET_ID="$(json_field "$EVIDENCE_DIR/post-restart-write.json" id)"
[[ "$POST_RESTART_TICKET_ID" != "$TICKET_ID" ]] || fail "post-restart write did not create a new id"

KNOWN_GOOD_API_IMAGE="$(compose_service_image_id "$PRIMARY_PROJECT" "$WEB_PORT" api)"
KNOWN_GOOD_AI_IMAGE="$(compose_service_image_id "$PRIMARY_PROJECT" "$WEB_PORT" ai)"
KNOWN_GOOD_WEB_IMAGE="$(compose_service_image_id "$PRIMARY_PROJECT" "$WEB_PORT" web)"
CONFIG_SHA="$(sha256sum "$COMPOSE_FILE" | awk '{print $1}')"
SCHEMA_BEFORE="$MIGRATION_ROW"
timeout 30 docker tag "$PRIMARY_API_REFERENCE" "$PRIMARY_PROJECT-api:known-good"
OWNED_PRIMARY_API_KNOWN_GOOD_REFERENCE_ID="$KNOWN_GOOD_API_IMAGE"
timeout 30 docker tag "$PRIMARY_AI_REFERENCE" "$PRIMARY_PROJECT-ai:known-good"
OWNED_PRIMARY_AI_KNOWN_GOOD_REFERENCE_ID="$KNOWN_GOOD_AI_IMAGE"
timeout 30 docker tag "$PRIMARY_WEB_REFERENCE" "$PRIMARY_PROJECT-web:known-good"
OWNED_PRIMARY_WEB_KNOWN_GOOD_REFERENCE_ID="$KNOWN_GOOD_WEB_IMAGE"
if [[ "$USE_PREBUILT_CURRENT_IMAGES" == true ]]; then
  compose_for "$PRIMARY_PROJECT" "$WEB_PORT" up --no-build --force-recreate --detach --wait >"$EVIDENCE_DIR/candidate-redeploy.log" 2>&1
else
  compose_for "$PRIMARY_PROJECT" "$WEB_PORT" up --build --detach --wait >"$EVIDENCE_DIR/candidate-redeploy.log" 2>&1
  OWNED_PRIMARY_API_REFERENCE_ID="$(image_reference_id "$PRIMARY_API_REFERENCE")" || fail "could not rebind candidate API image reference"
  OWNED_PRIMARY_AI_REFERENCE_ID="$(image_reference_id "$PRIMARY_AI_REFERENCE")" || fail "could not rebind candidate AI image reference"
  OWNED_PRIMARY_WEB_REFERENCE_ID="$(image_reference_id "$PRIMARY_WEB_REFERENCE")" || fail "could not rebind candidate web image reference"
fi
timeout 30 docker tag "$PRIMARY_PROJECT-api:known-good" "$PRIMARY_PROJECT-api:latest"
OWNED_PRIMARY_API_REFERENCE_ID="$KNOWN_GOOD_API_IMAGE"
timeout 30 docker tag "$PRIMARY_PROJECT-ai:known-good" "$PRIMARY_PROJECT-ai:latest"
OWNED_PRIMARY_AI_REFERENCE_ID="$KNOWN_GOOD_AI_IMAGE"
timeout 30 docker tag "$PRIMARY_PROJECT-web:known-good" "$PRIMARY_PROJECT-web:latest"
OWNED_PRIMARY_WEB_REFERENCE_ID="$KNOWN_GOOD_WEB_IMAGE"
compose_for "$PRIMARY_PROJECT" "$WEB_PORT" up --no-build --force-recreate --detach --wait >"$EVIDENCE_DIR/known-good-reapply.log" 2>&1
wait_gateway "$WEB_PORT"
echo "same-schema deployment sequencing and rollback rehearsal; this is not a real cross-version production rollback" >"$EVIDENCE_DIR/rollback-rehearsal.txt"
[[ "$(compose_service_image_id "$PRIMARY_PROJECT" "$WEB_PORT" api)" == "$KNOWN_GOOD_API_IMAGE" ]] || fail "known-good API image was not reapplied"
[[ "$(compose_service_image_id "$PRIMARY_PROJECT" "$WEB_PORT" ai)" == "$KNOWN_GOOD_AI_IMAGE" ]] || fail "known-good AI image was not reapplied"
[[ "$(compose_service_image_id "$PRIMARY_PROJECT" "$WEB_PORT" web)" == "$KNOWN_GOOD_WEB_IMAGE" ]] || fail "known-good web image was not reapplied"
prove_persisted rollback-rehearsal
ARTIFACT_AFTER_REHEARSAL="$(artifact_info "$PRIMARY_PROJECT" "$WEB_PORT")"
[[ "$ARTIFACT_AFTER_REHEARSAL" == "$ARTIFACT_BEFORE" ]] || fail "embedding artifact identity changed during same-schema rehearsal"
printf '%s\n' "$ARTIFACT_AFTER_REHEARSAL" >"$EVIDENCE_DIR/artifact-after-rehearsal.json"

if [[ "$REAL_CROSS_VERSION_ROLLBACK" == true ]]; then
  CURRENT_CANDIDATE_API_IMAGE_ID="$(compose_service_image_id "$PRIMARY_PROJECT" "$WEB_PORT" api)"
  [[ "$CURRENT_CANDIDATE_API_IMAGE_ID" =~ ^sha256:[0-9a-f]{64}$ ]] || fail "current candidate API image has an invalid image ID"
  CURRENT_CANDIDATE_API_PLATFORM_IMAGE_ID="$(image_platform_id "$CURRENT_CANDIDATE_API_IMAGE_ID")" || fail "could not inspect current candidate API runtime image"
  [[ "$PREVIOUS_API_IMAGE_ID" != "$CURRENT_CANDIDATE_API_IMAGE_ID" ]] || fail "previous API image is the same image as the current candidate"
  API_CONTAINER_BEFORE_CROSS_VERSION="$(compose_for "$PRIMARY_PROJECT" "$WEB_PORT" ps -q api)"
  MYSQL_CONTAINER_BEFORE_CROSS_VERSION="$(compose_for "$PRIMARY_PROJECT" "$WEB_PORT" ps -q mysql)"
  AI_CONTAINER_BEFORE_CROSS_VERSION="$(compose_for "$PRIMARY_PROJECT" "$WEB_PORT" ps -q ai)"
  OIDC_CONTAINER_BEFORE_CROSS_VERSION="$(compose_for "$PRIMARY_PROJECT" "$WEB_PORT" ps -q oidc)"
  WEB_CONTAINER_BEFORE_CROSS_VERSION="$(compose_for "$PRIMARY_PROJECT" "$WEB_PORT" ps -q web)"

  timeout 30 docker tag "$PREVIOUS_API_IMAGE_REFERENCE_ID" "$PRIMARY_PROJECT-api:latest"
  OWNED_PRIMARY_API_REFERENCE_ID="$PREVIOUS_API_IMAGE_ID"
  [[ "$(image_reference_id "$PRIMARY_PROJECT-api:latest")" == "$PREVIOUS_API_IMAGE_ID" ]] || fail "project API tag did not resolve to the previous image"
  [[ "$(image_platform_id "$PRIMARY_PROJECT-api:latest")" == "$PREVIOUS_API_PLATFORM_IMAGE_ID" ]] || fail "project API tag did not resolve to the previous platform image"
  compose_for "$PRIMARY_PROJECT" "$WEB_PORT" up --no-build --no-deps --force-recreate --detach --wait api >"$EVIDENCE_DIR/previous-api-up.log" 2>&1
  wait_gateway "$WEB_PORT"
  status="$(status_request "$EVIDENCE_DIR/previous-api-gateway-health.json" "$BASE_URL/health")"
  assert_status 200 "$status" "gateway health under previous API"
  [[ "$(json_field "$EVIDENCE_DIR/previous-api-gateway-health.json" status)" == "up" ]] || fail "gateway health body changed under previous API"
  [[ "$(compose_service_image_id "$PRIMARY_PROJECT" "$WEB_PORT" api)" == "$PREVIOUS_API_IMAGE_ID" ]] || fail "previous API image was not applied"
  API_CONTAINER_UNDER_PREVIOUS="$(compose_for "$PRIMARY_PROJECT" "$WEB_PORT" ps -q api)"
  [[ -n "$API_CONTAINER_UNDER_PREVIOUS" && "$API_CONTAINER_UNDER_PREVIOUS" != "$API_CONTAINER_BEFORE_CROSS_VERSION" ]] || fail "previous API transition was a no-op"
  [[ "$(compose_for "$PRIMARY_PROJECT" "$WEB_PORT" ps -q mysql)" == "$MYSQL_CONTAINER_BEFORE_CROSS_VERSION" ]] || fail "MySQL was recreated during API-only rollback"
  [[ "$(compose_for "$PRIMARY_PROJECT" "$WEB_PORT" ps -q ai)" == "$AI_CONTAINER_BEFORE_CROSS_VERSION" ]] || fail "AI was recreated during API-only rollback"
  [[ "$(compose_for "$PRIMARY_PROJECT" "$WEB_PORT" ps -q oidc)" == "$OIDC_CONTAINER_BEFORE_CROSS_VERSION" ]] || fail "OIDC was recreated during API-only rollback"
  [[ "$(compose_for "$PRIMARY_PROJECT" "$WEB_PORT" ps -q web)" == "$WEB_CONTAINER_BEFORE_CROSS_VERSION" ]] || fail "web was recreated during API-only rollback"
  compose_for "$PRIMARY_PROJECT" "$WEB_PORT" exec -T api wget -qO- http://127.0.0.1:8080/actuator/health/readiness >"$EVIDENCE_DIR/previous-api-readiness.json"
  [[ "$(json_field "$EVIDENCE_DIR/previous-api-readiness.json" status)" == "UP" ]] || fail "previous API readiness is not UP"
  prove_persisted previous-api
  ARTIFACT_UNDER_PREVIOUS="$(artifact_info "$PRIMARY_PROJECT" "$WEB_PORT")"
  [[ "$ARTIFACT_UNDER_PREVIOUS" == "$ARTIFACT_BEFORE" ]] || fail "embedding artifact identity changed under previous API"
  printf '%s\n' "$ARTIFACT_UNDER_PREVIOUS" >"$EVIDENCE_DIR/artifact-under-previous-api.json"
  status="$(authenticated_status_request "$EVIDENCE_DIR/previous-api-safe-write.json" "$AGENT_TOKEN" -X POST -H 'Content-Type: application/json' \
    --data '{"channel":"EMAIL","customerName":"Previous API Writer","customerCompany":"Synthetic Operations","customerTier":"STANDARD","subject":"Safe previous API write","description":"Synthetic write proving the previous API remains compatible with the current schema.","language":"en-US"}' "$BASE_URL/api/tickets")"
  assert_status 201 "$status" "previous API safe write"
  PREVIOUS_API_SAFE_WRITE_ID="$(json_field "$EVIDENCE_DIR/previous-api-safe-write.json" id)"
  [[ "$PREVIOUS_API_SAFE_WRITE_ID" =~ ^ticket-[A-Za-z0-9-]+$ && "$PREVIOUS_API_SAFE_WRITE_ID" != "$TICKET_ID" && "$PREVIOUS_API_SAFE_WRITE_ID" != "$POST_RESTART_TICKET_ID" ]] || fail "previous API safe write omitted a distinct stable id"
  SCHEMA_UNDER_PREVIOUS="$(cat "$EVIDENCE_DIR/persisted-migration-after-previous-api.txt")"

  timeout 30 docker tag "$PRIMARY_API_KNOWN_GOOD_REFERENCE" "$PRIMARY_PROJECT-api:latest"
  OWNED_PRIMARY_API_REFERENCE_ID="$CURRENT_CANDIDATE_API_IMAGE_ID"
  [[ "$(image_reference_id "$PRIMARY_PROJECT-api:latest")" == "$CURRENT_CANDIDATE_API_IMAGE_ID" ]] || fail "project API tag did not resolve back to the current candidate"
  [[ "$(image_platform_id "$PRIMARY_PROJECT-api:latest")" == "$CURRENT_CANDIDATE_API_PLATFORM_IMAGE_ID" ]] || fail "project API tag did not resolve back to the current platform image"
  compose_for "$PRIMARY_PROJECT" "$WEB_PORT" up --no-build --no-deps --force-recreate --detach --wait api >"$EVIDENCE_DIR/current-api-return-up.log" 2>&1
  wait_gateway "$WEB_PORT"
  status="$(status_request "$EVIDENCE_DIR/current-api-return-gateway-health.json" "$BASE_URL/health")"
  assert_status 200 "$status" "gateway health after current API return"
  [[ "$(json_field "$EVIDENCE_DIR/current-api-return-gateway-health.json" status)" == "up" ]] || fail "gateway health body changed after current API return"
  [[ "$(compose_service_image_id "$PRIMARY_PROJECT" "$WEB_PORT" api)" == "$CURRENT_CANDIDATE_API_IMAGE_ID" ]] || fail "current candidate API image was not restored"
  API_CONTAINER_AFTER_RETURN="$(compose_for "$PRIMARY_PROJECT" "$WEB_PORT" ps -q api)"
  [[ -n "$API_CONTAINER_AFTER_RETURN" && "$API_CONTAINER_AFTER_RETURN" != "$API_CONTAINER_UNDER_PREVIOUS" ]] || fail "current candidate API return was a no-op"
  [[ "$(compose_for "$PRIMARY_PROJECT" "$WEB_PORT" ps -q mysql)" == "$MYSQL_CONTAINER_BEFORE_CROSS_VERSION" ]] || fail "MySQL was recreated while restoring current API"
  [[ "$(compose_for "$PRIMARY_PROJECT" "$WEB_PORT" ps -q ai)" == "$AI_CONTAINER_BEFORE_CROSS_VERSION" ]] || fail "AI was recreated while restoring current API"
  [[ "$(compose_for "$PRIMARY_PROJECT" "$WEB_PORT" ps -q oidc)" == "$OIDC_CONTAINER_BEFORE_CROSS_VERSION" ]] || fail "OIDC was recreated while restoring current API"
  [[ "$(compose_for "$PRIMARY_PROJECT" "$WEB_PORT" ps -q web)" == "$WEB_CONTAINER_BEFORE_CROSS_VERSION" ]] || fail "web was recreated while restoring current API"
  compose_for "$PRIMARY_PROJECT" "$WEB_PORT" exec -T api wget -qO- http://127.0.0.1:8080/actuator/health/readiness >"$EVIDENCE_DIR/current-api-return-readiness.json"
  [[ "$(json_field "$EVIDENCE_DIR/current-api-return-readiness.json" status)" == "UP" ]] || fail "restored current API readiness is not UP"
  status="$(authenticated_status_request "$EVIDENCE_DIR/previous-api-write-after-return.json" "$AGENT_TOKEN" "$BASE_URL/api/tickets/$PREVIOUS_API_SAFE_WRITE_ID")"
  assert_status 200 "$status" "previous API write after current candidate return"
  [[ "$(json_field "$EVIDENCE_DIR/previous-api-write-after-return.json" id)" == "$PREVIOUS_API_SAFE_WRITE_ID" && \
     "$(json_field "$EVIDENCE_DIR/previous-api-write-after-return.json" subject)" == "Safe previous API write" ]] || fail "previous API write was not persisted after current candidate return"
  prove_persisted current-api-return
  SCHEMA_AFTER_RETURN="$(cat "$EVIDENCE_DIR/persisted-migration-after-current-api-return.txt")"
  ARTIFACT_AFTER_RETURN="$(artifact_info "$PRIMARY_PROJECT" "$WEB_PORT")"
  [[ "$ARTIFACT_AFTER_RETURN" == "$ARTIFACT_BEFORE" ]] || fail "embedding artifact identity changed after current API return"
  printf '%s\n' "$ARTIFACT_AFTER_RETURN" >"$EVIDENCE_DIR/artifact-after-current-api-return.json"
  python3 - "$EVIDENCE_DIR/cross-version-rollback.json" "$PREVIOUS_API_IMAGE" "$PREVIOUS_API_IMAGE_ID" "$PREVIOUS_API_REVISION" \
    "$CURRENT_CANDIDATE_API_IMAGE_ID" "$MIGRATION_ROW" "$SCHEMA_UNDER_PREVIOUS" "$SCHEMA_AFTER_RETURN" \
    "$EVIDENCE_DIR/artifact-before-restarts.json" "$EVIDENCE_DIR/artifact-under-previous-api.json" \
    "$EVIDENCE_DIR/artifact-after-current-api-return.json" "$PREVIOUS_API_SAFE_WRITE_ID" \
    "$PREVIOUS_API_BUILD_MANIFEST_SHA" "$PREVIOUS_API_BUILD_IDENTITY" <<'PY'
import json
import sys
from pathlib import Path

Path(sys.argv[1]).write_text(json.dumps({
    "realCrossVersionRollback": True,
    "previousApi": {"image": sys.argv[2], "imageId": sys.argv[3], "revision": sys.argv[4]},
    "currentCandidateApiImageId": sys.argv[5],
    "schema": {"before": sys.argv[6], "underPreviousApi": sys.argv[7], "afterCurrentReturn": sys.argv[8]},
    "embeddingArtifact": {
        "before": json.loads(Path(sys.argv[9]).read_text(encoding="utf-8")),
        "underPreviousApi": json.loads(Path(sys.argv[10]).read_text(encoding="utf-8")),
        "afterCurrentReturn": json.loads(Path(sys.argv[11]).read_text(encoding="utf-8")),
    },
    "safeWriteId": sys.argv[12],
    "buildEvidence": {
        "contract": "build-compatible-api-image/v1",
        "schemaVersion": 1,
        "manifestSha256": sys.argv[13],
        "identity": sys.argv[14],
    },
    "onlyApiRecreated": True,
    "persistedWriteReadableAfterReturn": True,
}, indent=2) + "\n", encoding="utf-8")
PY
  chmod 600 "$EVIDENCE_DIR/cross-version-rollback.json"
fi

if [[ "$USE_PREBUILT_CURRENT_IMAGES" == true ]]; then
  RESTORE_PREBUILT_API_REFERENCE="$RESTORE_PROJECT-api:latest"
  RESTORE_PREBUILT_AI_REFERENCE="$RESTORE_PROJECT-ai:latest"
  RESTORE_PREBUILT_WEB_REFERENCE="$RESTORE_PROJECT-web:latest"
  timeout 30 docker tag "$PRIMARY_API_KNOWN_GOOD_REFERENCE" "$RESTORE_PREBUILT_API_REFERENCE"
  OWNED_RESTORE_API_REFERENCE_ID="$KNOWN_GOOD_API_IMAGE"
  timeout 30 docker tag "$PRIMARY_AI_KNOWN_GOOD_REFERENCE" "$RESTORE_PREBUILT_AI_REFERENCE"
  OWNED_RESTORE_AI_REFERENCE_ID="$KNOWN_GOOD_AI_IMAGE"
  timeout 30 docker tag "$PRIMARY_WEB_KNOWN_GOOD_REFERENCE" "$RESTORE_PREBUILT_WEB_REFERENCE"
  OWNED_RESTORE_WEB_REFERENCE_ID="$KNOWN_GOOD_WEB_IMAGE"
  [[ "$(image_reference_id "$RESTORE_PREBUILT_API_REFERENCE")" == "$KNOWN_GOOD_API_IMAGE" ]] || fail "restore API prebuilt tag does not match current image"
  [[ "$(image_reference_id "$RESTORE_PREBUILT_AI_REFERENCE")" == "$KNOWN_GOOD_AI_IMAGE" ]] || fail "restore AI prebuilt tag does not match current image"
  [[ "$(image_reference_id "$RESTORE_PREBUILT_WEB_REFERENCE")" == "$KNOWN_GOOD_WEB_IMAGE" ]] || fail "restore web prebuilt tag does not match current image"
  python3 - "$EVIDENCE_DIR/restore-prebuilt-images.json" \
    "$RESTORE_PREBUILT_API_REFERENCE" "$KNOWN_GOOD_API_IMAGE" \
    "$RESTORE_PREBUILT_AI_REFERENCE" "$KNOWN_GOOD_AI_IMAGE" \
    "$RESTORE_PREBUILT_WEB_REFERENCE" "$KNOWN_GOOD_WEB_IMAGE" <<'PY'
import json
import sys
from pathlib import Path

Path(sys.argv[1]).write_text(json.dumps({
    "api": {"reference": sys.argv[2], "imageId": sys.argv[3]},
    "ai": {"reference": sys.argv[4], "imageId": sys.argv[5]},
    "web": {"reference": sys.argv[6], "imageId": sys.argv[7]},
}, indent=2) + "\n", encoding="utf-8")
PY
  chmod 600 "$EVIDENCE_DIR/restore-prebuilt-images.json"
fi

"$ROOT_DIR/scripts/pilot-backup.sh" --compose-file "$COMPOSE_FILE" --project "$PRIMARY_PROJECT" --secret-dir "$SECRET_DIR" \
  --evidence-dir "$EVIDENCE_DIR/backup" --database support_copilot --sentinel-ticket-id "$TICKET_ID" \
  --sentinel-analysis-id "$ANALYSIS_ID" --sentinel-audit-id "$AUDIT_ID" >"$EVIDENCE_DIR/backup-command.log" 2>&1

RESTORE_ARGUMENTS=(--backup-dir "$EVIDENCE_DIR/backup" --compose-file "$COMPOSE_FILE" \
  --project "$RESTORE_PROJECT" --secret-dir "$SECRET_DIR" --evidence-dir "$EVIDENCE_DIR/restore" \
  --database support_copilot)
if [[ "$USE_PREBUILT_CURRENT_IMAGES" == true ]]; then
  RESTORE_ARGUMENTS+=(--prebuilt-ai-image-id "$KNOWN_GOOD_AI_IMAGE")
fi
"$ROOT_DIR/scripts/pilot-restore.sh" "${RESTORE_ARGUMENTS[@]}" >"$EVIDENCE_DIR/restore-command.log" 2>&1
BACKUP_ARTIFACT_ID="$(json_field "$EVIDENCE_DIR/backup/manifest.json" embeddingArtifacts.activeArtifactId)"
BACKUP_ARTIFACT_SHA="$(json_field "$EVIDENCE_DIR/backup/manifest.json" embeddingArtifacts.archiveSha256)"
[[ "$BACKUP_ARTIFACT_ID" == "$ARTIFACT_ID" && "$BACKUP_ARTIFACT_SHA" =~ ^[a-f0-9]{64}$ ]] || fail "backup manifest artifact observables do not match the active artifact"
if [[ "$USE_PREBUILT_CURRENT_IMAGES" == true ]]; then
  compose_for "$RESTORE_PROJECT" "$RESTORE_WEB_PORT" up --no-build --detach --wait >"$EVIDENCE_DIR/restore-stack-up.log" 2>&1
else
  compose_for "$RESTORE_PROJECT" "$RESTORE_WEB_PORT" up --detach --wait >"$EVIDENCE_DIR/restore-stack-up.log" 2>&1
  OWNED_RESTORE_API_REFERENCE_ID="$(image_reference_id "$RESTORE_API_REFERENCE")" || fail "could not bind restore API image reference"
  OWNED_RESTORE_AI_REFERENCE_ID="$(image_reference_id "$RESTORE_AI_REFERENCE")" || fail "could not bind restore AI image reference"
  OWNED_RESTORE_WEB_REFERENCE_ID="$(image_reference_id "$RESTORE_WEB_REFERENCE")" || fail "could not bind restore web image reference"
fi
wait_gateway "$RESTORE_WEB_PORT"
if [[ "$USE_PREBUILT_CURRENT_IMAGES" == true ]]; then
  [[ "$(compose_service_image_id "$RESTORE_PROJECT" "$RESTORE_WEB_PORT" api)" == "$KNOWN_GOOD_API_IMAGE" ]] || fail "restored API does not match original current image"
  [[ "$(compose_service_image_id "$RESTORE_PROJECT" "$RESTORE_WEB_PORT" ai)" == "$KNOWN_GOOD_AI_IMAGE" ]] || fail "restored AI does not match original current image"
  [[ "$(compose_service_image_id "$RESTORE_PROJECT" "$RESTORE_WEB_PORT" web)" == "$KNOWN_GOOD_WEB_IMAGE" ]] || fail "restored web does not match original current image"
fi
RESTORED_ARTIFACT="$(artifact_info "$RESTORE_PROJECT" "$RESTORE_WEB_PORT")"
[[ "$RESTORED_ARTIFACT" == "$ARTIFACT_BEFORE" ]] || fail "restored embedding artifact identity/hash/path changed"
printf '%s\n' "$RESTORED_ARTIFACT" >"$EVIDENCE_DIR/restored-artifact.json"
RESTORE_AGENT_TOKEN="$(token_for "$RESTORE_PROJECT" "$RESTORE_WEB_PORT" support-copilot-agent pilot-agent SUPPORT_AGENT ACCOUNT)"
RESTORE_BASE_URL="http://127.0.0.1:$RESTORE_WEB_PORT"
status="$(authenticated_status_request "$EVIDENCE_DIR/restored-api-read.json" "$RESTORE_AGENT_TOKEN" "$RESTORE_BASE_URL/api/tickets/$TICKET_ID")"
assert_status 200 "$status" "authenticated restored API read"
[[ "$(json_field "$EVIDENCE_DIR/restored-api-read.json" id)" == "$TICKET_ID" ]] || fail "restored API returned wrong ticket id"
status="$(authenticated_status_request "$EVIDENCE_DIR/restored-post-write.json" "$RESTORE_AGENT_TOKEN" -X POST -H 'Content-Type: application/json' \
  --data '{"channel":"EMAIL","customerName":"Restore Writer","customerCompany":"Synthetic Operations","customerTier":"STANDARD","subject":"Safe restored write","description":"Synthetic write proving restored database remains writable.","language":"en-US"}' "$RESTORE_BASE_URL/api/tickets")"
assert_status 201 "$status" "post-restore safe write"
RESTORED_WRITE_ID="$(json_field "$EVIDENCE_DIR/restored-post-write.json" id)"
[[ "$RESTORED_WRITE_ID" != "$TICKET_ID" ]] || fail "post-restore write did not create a new id"

python3 - "$EVIDENCE_DIR/operations-result.json" "$PRIMARY_PROJECT" "$RESTORE_PROJECT" "$TICKET_ID" "$PATCHED_VERSION" \
  "$ANALYSIS_ID" "$ANALYSIS_TRACE" "$REVIEW_ID" "$AUDIT_ID" "$MIGRATION_ROW" "$POST_RESTART_TICKET_ID" \
  "$RESTORED_WRITE_ID" "$KNOWN_GOOD_API_IMAGE" "$KNOWN_GOOD_AI_IMAGE" "$KNOWN_GOOD_WEB_IMAGE" "$CONFIG_SHA" "$SCHEMA_BEFORE" \
  "$ARTIFACT_ID" "$ARTIFACT_PATH" "$ARTIFACT_MANIFEST_SHA" "$BACKUP_ARTIFACT_SHA" "$REAL_CROSS_VERSION_ROLLBACK" \
  "$EVIDENCE_DIR/cross-version-rollback.json" "$USE_PREBUILT_CURRENT_IMAGES" "$EVIDENCE_DIR/prebuilt-current-images.json" <<'PY'
import json
import sys
from pathlib import Path

real_cross_version = sys.argv[22] == "true"
cross_version = json.loads(Path(sys.argv[23]).read_text(encoding="utf-8")) if real_cross_version else None
used_prebuilt = sys.argv[24] == "true"
prebuilt_images = json.loads(Path(sys.argv[25]).read_text(encoding="utf-8")) if used_prebuilt else None
Path(sys.argv[1]).write_text(json.dumps({
    "primaryProject": sys.argv[2], "restoreProject": sys.argv[3],
    "ticketId": sys.argv[4], "ticketVersion": int(sys.argv[5]),
    "analysisId": sys.argv[6], "analysisTraceId": sys.argv[7],
    "reviewId": sys.argv[8], "auditId": sys.argv[9], "flyway": sys.argv[10],
    "postRestartTicketId": sys.argv[11], "postRestoreTicketId": sys.argv[12],
    "knownGoodImages": {"api": sys.argv[13], "ai": sys.argv[14], "web": sys.argv[15]},
    "composeSha256": sys.argv[16], "schemaBefore": sys.argv[17],
    "embeddingArtifact": {"artifactId": sys.argv[18], "manifestPath": sys.argv[19],
                          "manifestSha256": sys.argv[20], "archiveSha256": sys.argv[21]},
    "rehearsalKind": "same-schema deployment sequencing and rollback rehearsal",
    "realCrossVersionRollback": real_cross_version,
    "crossVersionRollback": cross_version,
    "usedPrebuiltCurrentImages": used_prebuilt,
    "prebuiltCurrentImages": prebuilt_images,
    "anonymous401": True, "agentAudit403": True, "directPythonWithoutToken401": True,
    "apiRestartObserved": True, "mysqlRestartObserved": True, "stackRestartObserved": True,
    "restoredDirectDb": True, "restoredAuthenticatedApi": True, "postRestoreWrite": True,
    "agentClaimsValidated": True, "reviewerClaimsValidated": True, "adminClaimsValidated": True,
    "reviewerReviewAndAuditAllowed": True, "adminProtectedActuatorAllowed": True,
    "artifactRestartIdentity": True, "artifactRestoreIdentity": True,
}, indent=2) + "\n", encoding="utf-8")
PY
chmod 600 "$EVIDENCE_DIR/operations-result.json"

if cleanup 0; then
  trap - EXIT
else
  cleanup_exit=$?
  trap - EXIT
  exit "$cleanup_exit"
fi

if [[ "$REAL_CROSS_VERSION_ROLLBACK" == true ]]; then
  printf 'PASS: real cross-version rollback completed. Evidence: %s and %s\n' \
    "$EVIDENCE_DIR/cross-version-rollback.json" "$EVIDENCE_DIR/operations-result.json"
else
  printf 'PASS: same-schema, persistence, and backup/restore completed; cross-version rollback NOT REQUESTED. Evidence: %s\n' \
    "$EVIDENCE_DIR/operations-result.json"
fi

#!/usr/bin/env bash
set -Eeuo pipefail

readonly SCANNER_IMAGE="aquasec/trivy:0.66.0@sha256:086971aaf400beebd94e8300fd8ea623774419597169156cec56eec5b00dfb1e"
readonly SCANNER_DIGEST="${SCANNER_IMAGE##*@}"
readonly SCANNER_PLATFORM="linux/amd64"
readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
readonly DOCKER_BIN="${DOCKER_BIN:-docker}"
readonly PYTHON_BIN="${PYTHON_BIN:-python3}"
readonly TIMEOUT_BIN="${TIMEOUT_BIN:-timeout}"
readonly SCAN_TIMEOUT_SECONDS="${SCAN_TIMEOUT_SECONDS:-300}"
readonly CLEANUP_TIMEOUT_SECONDS="${CLEANUP_TIMEOUT_SECONDS:-30}"
readonly docker_use_sudo="${DOCKER_USE_SUDO:-0}"

if (( $# < 2 )); then
  echo "usage: $0 OUTPUT_DIR IMAGE [IMAGE ...]" >&2
  exit 64
fi

readonly requested_output_dir="$1"
shift
readonly -a images=("$@")

if [[ -z "$requested_output_dir" || -e "$requested_output_dir" || -L "$requested_output_dir" ]]; then
  echo "refusing non-fresh output path: $requested_output_dir" >&2
  exit 1
fi
for image in "${images[@]}"; do
  if [[ -z "$image" ]]; then
    echo "image references must be nonempty" >&2
    exit 1
  fi
done

if ! command -v "$TIMEOUT_BIN" >/dev/null 2>&1; then
  echo "required timeout command is unavailable" >&2
  exit 1
fi
if ! [[ "$SCAN_TIMEOUT_SECONDS" =~ ^[1-9][0-9]*$ ]]; then
  echo "SCAN_TIMEOUT_SECONDS must be a positive integer" >&2
  exit 1
fi
if ! [[ "$CLEANUP_TIMEOUT_SECONDS" =~ ^[1-9][0-9]*$ ]]; then
  echo "CLEANUP_TIMEOUT_SECONDS must be a positive integer" >&2
  exit 1
fi
if ! command -v "$DOCKER_BIN" >/dev/null 2>&1; then
  echo "required Docker command is unavailable" >&2
  exit 1
fi
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "required Python command is unavailable" >&2
  exit 1
fi
if [[ "$docker_use_sudo" != "0" && "$docker_use_sudo" != "1" ]]; then
  echo "DOCKER_USE_SUDO must be 0 or 1" >&2
  exit 1
fi
if [[ "$docker_use_sudo" == "1" ]] && ! command -v sudo >/dev/null 2>&1; then
  echo "required sudo command is unavailable" >&2
  exit 1
fi

umask 077
mkdir -- "$requested_output_dir"
readonly output_dir="$(cd -- "$requested_output_dir" && pwd -P)"
readonly namespace="support-copilot-image-scan-$$-$RANDOM"
readonly cache_volume="${namespace}-cache"
active_container=""
volume_created=0
container_cleanup_attempted=0
volume_cleanup_attempted=0
scanner_acquired=0
scanner_cleanup_attempted=0

cleanup() {
  local status=$?
  local cleanup_status=0
  if ! cleanup_active_container; then
    cleanup_status=1
  fi
  if ! cleanup_cache_volume; then
    cleanup_status=1
  fi
  if ! cleanup_scanner_image; then
    cleanup_status=1
  fi
  if (( status == 0 && cleanup_status )); then
    exit 1
  fi
  exit "$status"
}
trap cleanup EXIT INT TERM

docker_bounded_command() {
  if [[ "$docker_use_sudo" == "1" ]]; then
    "$TIMEOUT_BIN" "$SCAN_TIMEOUT_SECONDS" sudo -n "$DOCKER_BIN" "$@"
  else
    "$TIMEOUT_BIN" "$SCAN_TIMEOUT_SECONDS" "$DOCKER_BIN" "$@"
  fi
}

docker_cleanup_command() {
  if [[ "$docker_use_sudo" == "1" ]]; then
    "$TIMEOUT_BIN" "$CLEANUP_TIMEOUT_SECONDS" sudo -n "$DOCKER_BIN" "$@"
  else
    "$TIMEOUT_BIN" "$CLEANUP_TIMEOUT_SECONDS" "$DOCKER_BIN" "$@"
  fi
}

scanner_acquisition_stderr="$output_dir/scanner-acquisition.stderr"

record_acquisition_failure() {
  local reason="$1"
  printf 'scanner acquisition failed: %s\n' "$reason" >"$scanner_acquisition_stderr"
  echo "scanner acquisition failed: $reason" >&2
  exit 1
}

record_cleanup_diagnostic() {
  local outcome="$1"
  local reason="$2"
  local scan_stderr="$output_dir/scanner-001.stderr"
  if [[ -f "$scan_stderr" ]]; then
    printf 'scanner cleanup %s: %s\n' "$outcome" "$reason" >>"$scan_stderr"
  else
    printf 'scanner cleanup %s: %s\n' "$outcome" "$reason" >>"$scanner_acquisition_stderr"
  fi
}

record_cleanup_failure() {
  record_cleanup_diagnostic "failed" "$1"
}

record_cleanup_timeout() {
  record_cleanup_diagnostic "timed out" "$1"
}

cleanup_active_container() {
  local cleanup_status=0
  if [[ -z "$active_container" ]] || (( container_cleanup_attempted )); then
    return 0
  fi
  container_cleanup_attempted=1
  set +e
  docker_cleanup_command rm -f "$active_container" >/dev/null 2>&1
  cleanup_status=$?
  set -e
  if (( cleanup_status == 124 )); then
    record_cleanup_timeout "active scanner container removal"
    return 1
  fi
  if (( cleanup_status != 0 )); then
    record_cleanup_failure "cannot remove active scanner container"
    return 1
  fi
  active_container=""
}

cleanup_cache_volume() {
  local cleanup_status=0
  if (( ! volume_created || volume_cleanup_attempted )); then
    return 0
  fi
  volume_cleanup_attempted=1
  set +e
  docker_cleanup_command volume rm "$cache_volume" >/dev/null 2>&1
  cleanup_status=$?
  set -e
  if (( cleanup_status == 124 )); then
    record_cleanup_timeout "scanner cache volume removal"
    return 1
  fi
  if (( cleanup_status != 0 )); then
    record_cleanup_failure "cannot remove scanner cache volume"
    return 1
  fi
  volume_created=0
}

cleanup_scanner_image() {
  local references=""
  local references_status=0
  local removal_status=0
  if (( ! scanner_acquired || scanner_cleanup_attempted )); then
    return 0
  fi
  scanner_cleanup_attempted=1
  set +e
  references="$(docker_cleanup_command container ls -a --filter "ancestor=$SCANNER_IMAGE" --format '{{.ID}}' 2>/dev/null)"
  references_status=$?
  set -e
  if (( references_status != 0 )); then
    if (( references_status == 124 )); then
      record_cleanup_timeout "container reference inspection"
    else
      record_cleanup_failure "cannot inspect container references"
    fi
    return 1
  fi
  if [[ -n "$references" ]]; then
    record_cleanup_failure "container references remain"
    return 1
  fi
  set +e
  docker_cleanup_command image rm "$SCANNER_IMAGE" >/dev/null 2>&1
  removal_status=$?
  set -e
  if (( removal_status != 0 )); then
    if (( removal_status == 124 )); then
      record_cleanup_timeout "acquired scanner image removal"
    else
      record_cleanup_failure "cannot remove acquired scanner image"
    fi
    return 1
  fi
  scanner_acquired=0
}

inspect_scanner_image() {
  local identity=""
  local inspect_status=0
  set +e
  identity="$(docker_bounded_command image inspect --format '{{json .RepoDigests}} {{.Os}}/{{.Architecture}}' "$SCANNER_IMAGE" 2>"$scanner_acquisition_stderr")"
  inspect_status=$?
  set -e
  if (( inspect_status == 0 )); then
    printf '%s' "$identity"
    return 0
  fi
  return "$inspect_status"
}

scanner_identity=""
set +e
scanner_identity="$(inspect_scanner_image)"
scanner_inspect_status=$?
set -e
if (( scanner_inspect_status != 0 )); then
  if (( scanner_inspect_status == 124 )); then
    record_acquisition_failure "local scanner inspection timed out"
  fi
  if ! grep -Eq '^Error response from daemon: No such image: |^Error: No such image: ' "$scanner_acquisition_stderr"; then
    record_acquisition_failure "local scanner inspection failed"
  fi
  set +e
  docker_bounded_command pull --platform "$SCANNER_PLATFORM" "$SCANNER_IMAGE" >/dev/null 2>"$scanner_acquisition_stderr"
  scanner_pull_status=$?
  set -e
  if (( scanner_pull_status != 0 )); then
    if (( scanner_pull_status == 124 )); then
      record_acquisition_failure "pinned scanner pull timed out"
    fi
    record_acquisition_failure "pinned scanner pull failed"
  fi
  scanner_acquired=1
  set +e
  scanner_identity="$(inspect_scanner_image)"
  scanner_inspect_status=$?
  set -e
  if (( scanner_inspect_status != 0 )); then
    if (( scanner_inspect_status == 124 )); then
      record_acquisition_failure "acquired scanner inspection timed out"
    fi
    record_acquisition_failure "acquired scanner inspection failed"
  fi
fi
rm -f -- "$scanner_acquisition_stderr"
scanner_repo_digests="${scanner_identity% *}"
scanner_platform="${scanner_identity##* }"
if [[ "$scanner_repo_digests" != *"\"aquasec/trivy@$SCANNER_DIGEST\""* ]]; then
  record_acquisition_failure "scanner digest does not match required pin"
fi
if [[ "$scanner_platform" != "$SCANNER_PLATFORM" ]]; then
  record_acquisition_failure "scanner platform does not match required platform"
fi
readonly scanner_id="$SCANNER_DIGEST"

docker_bounded_command volume create "$cache_volume" >/dev/null
volume_created=1

records=()
gate_status=0
index=0
for image in "${images[@]}"; do
  index=$((index + 1))
  report_name="$(printf 'report-%03d.json' "$index")"
  identity="$(docker_bounded_command image inspect --format '{{.Id}} {{json .RepoDigests}}' "$image")"
  image_id="${identity%% *}"
  repo_digests="${identity#* }"
  active_container="${namespace}-$(printf '%03d' "$index")"
  set +e
  docker_bounded_command run --rm --name "$active_container" \
    --platform "$SCANNER_PLATFORM" \
    -v /var/run/docker.sock:/var/run/docker.sock:ro \
    -v "$cache_volume:/root/.cache/trivy" \
    -v "$output_dir:/reports" \
    "$SCANNER_IMAGE" image --scanners vuln --pkg-types os,library --severity HIGH,CRITICAL \
    --ignore-unfixed=false --format json --output "/reports/$report_name" \
    --exit-code 1 "$image_id" 2>"$output_dir/scanner-$(printf '%03d' "$index").stderr"
  scanner_exit=$?
  set -e
  if (( scanner_exit > 1 )); then
    echo "scanner operational failure for image index $index (exit $scanner_exit)" >&2
    exit 1
  fi
  active_container=""
  if (( scanner_exit == 1 )); then
    gate_status=1
  fi
  records+=("$image" "$image_id" "$repo_digests" "$report_name" "$scanner_exit")
done

active_container="${namespace}-version"
docker_bounded_command run --rm --name "$active_container" \
  --platform "$SCANNER_PLATFORM" \
  -v "$cache_volume:/root/.cache/trivy" \
  "$SCANNER_IMAGE" version --format json >"$output_dir/scanner-version.json"
active_container=""

scanner_cleanup_status=0
if ! cleanup_cache_volume; then
  scanner_cleanup_status=1
fi
if ! cleanup_scanner_image; then
  scanner_cleanup_status=1
fi

"$PYTHON_BIN" "$SCRIPT_DIR/validate_pilot_image_scan.py" finalize \
  "$output_dir" "$SCANNER_IMAGE" "$scanner_id" scanner-version.json "${records[@]}"
"$PYTHON_BIN" "$SCRIPT_DIR/validate_pilot_image_scan.py" verify "$output_dir"

if (( gate_status )); then
  echo "pilot image scan blocked by HIGH or CRITICAL findings" >&2
  exit 1
fi
if (( scanner_cleanup_status )); then
  echo "pilot image scan cleanup failed; see scanner-001.stderr" >&2
  exit 1
fi
echo "pilot image scan evidence complete: $output_dir"

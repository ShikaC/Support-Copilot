#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
AI_PORT="${SUPPORT_COPILOT_AI_PORT:-8000}"
JAVA_PORT="${SUPPORT_COPILOT_JAVA_PORT:-8080}"
WEB_PORT="${SUPPORT_COPILOT_WEB_PORT:-5173}"
HTTP_TIMEOUT_SECONDS="${SUPPORT_COPILOT_HTTP_TIMEOUT_SECONDS:-3}"

usage() {
  cat <<'EOF'
Usage: ./scripts/check-local-startup.sh [--preflight|--health|--all]

  --preflight  Check local runtimes and installed project dependencies.
  --health     Check the Python, Java, and React HTTP endpoints.
  --all        Run both checks in order.
EOF
}

failures=0

report_failure() {
  printf 'FAIL: %s\n' "$1" >&2
  failures=$((failures + 1))
}

require_command() {
  local command_name="$1"
  if ! command -v "$command_name" >/dev/null 2>&1; then
    report_failure "missing command: $command_name"
  fi
}

require_executable() {
  local path="$1"
  if [[ ! -x "$path" ]]; then
    report_failure "missing executable: ${path#"$ROOT_DIR"/}"
  fi
}

run_preflight() {
  failures=0
  require_command curl
  require_command java
  require_command node
  require_command npm
  require_command python3
  require_executable "$ROOT_DIR/services/support-copilot-ai/.venv/bin/python"
  require_executable "$ROOT_DIR/services/support-copilot-ai/.venv/bin/uvicorn"
  require_executable "$ROOT_DIR/services/support-copilot-api/gradlew"
  require_executable "$ROOT_DIR/apps/support-copilot-web/node_modules/.bin/vite"

  if (( failures > 0 )); then
    printf 'Preflight failed with %d issue(s).\n' "$failures" >&2
    return 1
  fi

  printf 'Preflight passed: runtimes and local dependencies are ready.\n'
}

check_endpoint() {
  local service_name="$1"
  local url="$2"
  local expected_body="${3:-}"
  local response

  if ! response="$(curl --fail --silent --show-error --max-time "$HTTP_TIMEOUT_SECONDS" "$url")"; then
    report_failure "$service_name is not healthy: $url"
    return 1
  fi
  if [[ -n "$expected_body" ]] && ! grep -Fq "$expected_body" <<<"$response"; then
    report_failure "$service_name returned an unexpected health response: $url"
    return 1
  fi

  printf 'Healthy: %s (%s)\n' "$service_name" "$url"
}

run_health() {
  failures=0
  check_endpoint "Python AI" "http://127.0.0.1:${AI_PORT}/health" '"status":"up"' || true
  check_endpoint "Java API" "http://127.0.0.1:${JAVA_PORT}/actuator/health" '"status":"UP"' || true
  check_endpoint "React Web" "http://127.0.0.1:${WEB_PORT}/" || true

  if (( failures > 0 )); then
    printf 'Health check failed with %d issue(s).\n' "$failures" >&2
    return 1
  fi
}

main() {
  local mode="${1:---preflight}"
  case "$mode" in
    --preflight)
      run_preflight
      ;;
    --health)
      run_health
      ;;
    --all)
      run_preflight
      run_health
      ;;
    --help|-h)
      usage
      ;;
    *)
      usage >&2
      return 2
      ;;
  esac
}

main "$@"

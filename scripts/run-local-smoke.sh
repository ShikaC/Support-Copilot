#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
AI_DIR="$ROOT_DIR/services/support-copilot-ai"
JAVA_DIR="$ROOT_DIR/services/support-copilot-api"
WEB_DIR="$ROOT_DIR/apps/support-copilot-web"

AI_PORT="${SUPPORT_COPILOT_SMOKE_AI_PORT:-18000}"
JAVA_PORT="${SUPPORT_COPILOT_SMOKE_JAVA_PORT:-18080}"
WEB_PORT="${SUPPORT_COPILOT_SMOKE_WEB_PORT:-15173}"
STARTUP_TIMEOUT_SECONDS="${SUPPORT_COPILOT_SMOKE_STARTUP_TIMEOUT_SECONDS:-120}"
AI_BASE_URL="http://127.0.0.1:${AI_PORT}"
JAVA_BASE_URL="http://127.0.0.1:${JAVA_PORT}"
WEB_BASE_URL="http://127.0.0.1:${WEB_PORT}"

LOG_DIR=""
PIDS=()

usage() {
  cat <<'EOF'
Usage: ./scripts/run-local-smoke.sh

Starts isolated mock services, runs startup, analysis, and frontend contract
checks, then stops only the processes started by this script.
The latest mock evaluation report is regenerated before services start.

Override ports with SUPPORT_COPILOT_SMOKE_AI_PORT,
SUPPORT_COPILOT_SMOKE_JAVA_PORT, and SUPPORT_COPILOT_SMOKE_WEB_PORT.
EOF
}

port_is_in_use() {
  python3 - "$1" <<'PY'
import socket
import sys

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    raise SystemExit(0 if sock.connect_ex(("127.0.0.1", int(sys.argv[1]))) == 0 else 1)
PY
}

assert_ports_are_free() {
  local port
  for port in "$AI_PORT" "$JAVA_PORT" "$WEB_PORT"; do
    if port_is_in_use "$port"; then
      printf 'FAIL: smoke port is already in use: %s\n' "$port" >&2
      printf 'Set a different SUPPORT_COPILOT_SMOKE_*_PORT or stop that service.\n' >&2
      return 1
    fi
  done
}

kill_process_tree() {
  local pid="$1"
  local child
  local children

  children="$(pgrep -P "$pid" 2>/dev/null || true)"
  for child in $children; do
    kill_process_tree "$child"
  done
  kill "$pid" 2>/dev/null || true
}

cleanup() {
  local exit_code="$?"
  local pid

  trap - EXIT INT TERM
  if (( ${#PIDS[@]} > 0 )); then
    for pid in "${PIDS[@]}"; do
      kill_process_tree "$pid"
    done
    for pid in "${PIDS[@]}"; do
      wait "$pid" 2>/dev/null || true
    done
  fi

  if (( exit_code != 0 )) && [[ -n "$LOG_DIR" ]]; then
    printf '\nSmoke service logs: %s\n' "$LOG_DIR" >&2
    for log_file in "$LOG_DIR"/*.log; do
      [[ -e "$log_file" ]] || continue
      printf '\n--- %s ---\n' "$(basename "$log_file")" >&2
      tail -n 40 "$log_file" >&2 || true
    done
  fi

  if [[ -n "$LOG_DIR" && -d "$LOG_DIR" ]]; then
    rm -rf "$LOG_DIR"
  fi
  exit "$exit_code"
}

start_services() {
  LOG_DIR="$(mktemp -d "${TMPDIR:-/tmp}/support-copilot-smoke.XXXXXX")"

  (
    cd "$AI_DIR"
    exec env AI_MODE=mock .venv/bin/python -m uvicorn app.main:app \
      --host 127.0.0.1 --port "$AI_PORT"
  ) >"$LOG_DIR/ai.log" 2>&1 &
  PIDS+=("$!")

  (
    cd "$JAVA_DIR"
    exec env SPRING_PROFILES_ACTIVE=demo SERVER_PORT="$JAVA_PORT" AI_SERVICE_BASE_URL="$AI_BASE_URL" \
      ./gradlew bootRun --no-daemon
  ) >"$LOG_DIR/java.log" 2>&1 &
  PIDS+=("$!")

  (
    cd "$WEB_DIR"
    exec env VITE_DEV_API_TARGET="$JAVA_BASE_URL" \
      node node_modules/vite/bin/vite.js --host 127.0.0.1 --port "$WEB_PORT"
  ) >"$LOG_DIR/web.log" 2>&1 &
  PIDS+=("$!")
}

refresh_mock_evaluation() {
  (
    cd "$AI_DIR"
    exec env AI_MODE=mock .venv/bin/python -m evaluation.run_mock_evaluation
  )
}

wait_for_endpoint() {
  local service_name="$1"
  local url="$2"
  local expected_body="$3"
  local deadline=$((SECONDS + STARTUP_TIMEOUT_SECONDS))
  local response

  while (( SECONDS < deadline )); do
    if response="$(curl --silent --show-error --max-time 2 "$url" 2>/dev/null)" \
      && grep -Fq "$expected_body" <<<"$response"; then
      printf 'Ready: %s (%s)\n' "$service_name" "$url"
      return 0
    fi
    sleep 1
  done

  printf 'FAIL: timed out waiting for %s (%s)\n' "$service_name" "$url" >&2
  return 1
}

run_checks() {
  env \
    SUPPORT_COPILOT_AI_PORT="$AI_PORT" \
    SUPPORT_COPILOT_JAVA_PORT="$JAVA_PORT" \
    SUPPORT_COPILOT_WEB_PORT="$WEB_PORT" \
    "$ROOT_DIR/scripts/check-local-startup.sh" --all

  env \
    SUPPORT_COPILOT_JAVA_BASE_URL="$JAVA_BASE_URL" \
    SUPPORT_COPILOT_WEB_BASE_URL="$WEB_BASE_URL" \
    "$ROOT_DIR/scripts/check-local-analysis-flow.sh" --success

  env \
    SUPPORT_COPILOT_JAVA_BASE_URL="$JAVA_BASE_URL" \
    SUPPORT_COPILOT_WEB_BASE_URL="$WEB_BASE_URL" \
    "$ROOT_DIR/scripts/check-local-analysis-flow.sh" --contract
}

main() {
  case "${1:---run}" in
    --run)
      assert_ports_are_free
      refresh_mock_evaluation
      start_services
      wait_for_endpoint "Python AI" "$AI_BASE_URL/health" '"status":"up"'
      wait_for_endpoint "Java API" "$JAVA_BASE_URL/actuator/health" '"status":"UP"'
      wait_for_endpoint "React Web" "$WEB_BASE_URL/" '<!doctype html>'
      run_checks
      printf 'Local mock smoke passed.\n'
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

trap cleanup EXIT INT TERM
main "$@"

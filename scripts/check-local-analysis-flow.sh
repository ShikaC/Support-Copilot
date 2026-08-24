#!/usr/bin/env bash

set -euo pipefail

WEB_BASE_URL="${SUPPORT_COPILOT_WEB_BASE_URL:-http://127.0.0.1:5173}"
JAVA_BASE_URL="${SUPPORT_COPILOT_JAVA_BASE_URL:-http://127.0.0.1:8080}"
TICKET_ID="${SUPPORT_COPILOT_TICKET_ID:-ticket-10042}"
HTTP_TIMEOUT_SECONDS="${SUPPORT_COPILOT_HTTP_TIMEOUT_SECONDS:-10}"
TRACE_ID="${SUPPORT_COPILOT_TRACE_ID:-flow-check-trace}"

usage() {
  cat <<'EOF'
Usage: ./scripts/check-local-analysis-flow.sh --success|--fallback

  --success   Verify a mock analysis through React -> Java -> Python.
  --fallback  Verify Java fallback after Python is intentionally stopped.

The script never starts or stops services. Run --fallback only after stopping
the Python AI service yourself, then restart it after the check.
EOF
}

assert_analysis() {
  local expected_mode="$1"
  local expected_status="$2"
  local response="$3"

  python3 -c '
import json
import sys

body = json.loads(sys.stdin.read())
expected_mode, expected_status = sys.argv[1:3]
mode = body["mode"]
status = body["status"]
if mode != expected_mode or status != expected_status:
    raise SystemExit(
        f"unexpected analysis state: mode={mode}, status={status}"
    )
if not body["traceId"]:
    raise SystemExit("analysis response did not preserve traceId")
expected_trace_id = sys.argv[3]
actual_trace_id = body["traceId"]
if actual_trace_id != expected_trace_id:
    raise SystemExit(
        f"traceId changed across services: expected={expected_trace_id} actual={actual_trace_id}"
    )

hits = len(body["retrieval"]["hits"])
citations = len(body["suggestedReply"]["citations"])
warnings = len(body["suggestedReply"]["warnings"])
category = body["classification"]["category"]
if expected_mode == "mock" and (hits == 0 or citations == 0):
    raise SystemExit("successful mock analysis must include evidence and citations")
if expected_mode == "fallback" and warnings == 0:
    raise SystemExit("fallback analysis must include a manual-review warning")

print(
    f"analysis: mode={mode} status={status} "
    f"category={category} "
    f"hits={hits} citations={citations} warnings={warnings} traceId={actual_trace_id}"
)
' "$expected_mode" "$expected_status" "$TRACE_ID" <<<"$response"
}

assert_persisted_latest() {
  local expected_mode="$1"
  local expected_status="$2"
  local history

  history="$(curl --fail --silent --show-error --max-time "$HTTP_TIMEOUT_SECONDS" \
    "$JAVA_BASE_URL/api/tickets/$TICKET_ID/analyses")"
  python3 -c '
import json
import sys

body = json.loads(sys.stdin.read())
expected_mode, expected_status = sys.argv[1:3]
if not body:
    raise SystemExit("analysis history is empty")
latest = body[0]
mode = latest["mode"]
status = latest["status"]
if mode != expected_mode or status != expected_status:
    raise SystemExit(
        f"latest persisted analysis is mode={mode}, status={status}"
    )
print(
    f"history: count={len(body)} latestMode={mode} latestStatus={status}"
)
' "$expected_mode" "$expected_status" <<<"$history"
}

run_flow() {
  local expected_mode="$1"
  local expected_status="$2"
  local response

  response="$(curl --fail --silent --show-error --max-time "$HTTP_TIMEOUT_SECONDS" \
    -X POST \
    -H "X-Trace-Id: $TRACE_ID" \
    "$WEB_BASE_URL/api/tickets/$TICKET_ID/analyze")"
  assert_analysis "$expected_mode" "$expected_status" "$response"
  assert_persisted_latest "$expected_mode" "$expected_status"
}

main() {
  case "${1:---success}" in
    --success)
      run_flow mock SUCCEEDED
      ;;
    --fallback)
      run_flow fallback FALLBACK
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

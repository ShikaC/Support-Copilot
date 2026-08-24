#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
AI_DIR="$ROOT_DIR/services/support-copilot-ai"
AI_BASE_URL="${SUPPORT_COPILOT_AI_BASE_URL:-http://127.0.0.1:8000}"
JAVA_BASE_URL="${SUPPORT_COPILOT_JAVA_BASE_URL:-http://127.0.0.1:8080}"
WEB_BASE_URL="${SUPPORT_COPILOT_WEB_BASE_URL:-http://127.0.0.1:5173}"
TICKET_ID="${SUPPORT_COPILOT_LIVE_TICKET_ID:-ticket-10041}"
TRACE_ID="${SUPPORT_COPILOT_TRACE_ID:-live-rag-$(date -u +%Y%m%d%H%M%S)}"
HTTP_TIMEOUT_SECONDS="${SUPPORT_COPILOT_HTTP_TIMEOUT_SECONDS:-60}"
VALIDATED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
REPORT_STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
EVIDENCE_PATH="${SUPPORT_COPILOT_LIVE_EVIDENCE_PATH:-$AI_DIR/evaluation/reports/live-$REPORT_STAMP.md}"

TEMP_FILES=()
CONFIG_JSON=""
NEW_TEMP_FILE=""

cleanup() {
  local path

  if (( ${#TEMP_FILES[@]} == 0 )); then
    return
  fi
  for path in "${TEMP_FILES[@]}"; do
    if [[ -e "$path" ]]; then
      unlink "$path"
    fi
  done
}

trap cleanup EXIT

usage() {
  cat <<'EOF'
Usage: ./scripts/check-live-rag.sh --preflight|--success

  --preflight  Verify live configuration and a clean Git commit without calling APIs.
  --success    Verify a live RAG request through React -> Java -> Python and write
               a redacted Markdown evidence record.

The script never starts services. Start Python with AI_MODE=live, then Java and
React, before running --success. It never prints or records API credentials.
EOF
}

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  return 1
}

new_temp_file() {
  local label="$1"

  NEW_TEMP_FILE="$(mktemp "${TMPDIR:-/tmp}/support-copilot-live-${label}.XXXXXX")"
  TEMP_FILES+=("$NEW_TEMP_FILE")
}

load_live_config() {
  local python="$AI_DIR/.venv/bin/python"

  if [[ ! -x "$python" ]]; then
    fail "Python virtual environment is missing: services/support-copilot-ai/.venv"
    return 1
  fi

  if ! CONFIG_JSON="$(
    cd "$AI_DIR"
    "$python" -c '
import json

from app.config import Settings

settings = Settings()
if not settings.live_ready or settings.effective_mode != "live":
    raise SystemExit(1)
endpoint_type = (
    "official"
    if not settings.openai_base_url
    or settings.openai_base_url.rstrip("/") == "https://api.openai.com/v1"
    else "compatible"
)
print(
    json.dumps(
        {
            "chatModel": settings.openai_chat_model,
            "embeddingModel": settings.openai_embedding_model,
            "endpointType": endpoint_type,
        },
        separators=(",", ":"),
    )
)
' 2>/dev/null
  )"; then
    fail "live configuration is not ready; set AI_MODE=live and all three OpenAI model/API variables"
    return 1
  fi
}

require_clean_commit() {
  if [[ -n "$(git -C "$ROOT_DIR" status --porcelain)" ]]; then
    fail "Git worktree must be clean so the live record can reference an exact commit"
    return 1
  fi
}

print_config_summary() {
  python3 -c '
import json
import sys

config = json.loads(sys.stdin.read())
print(
    f"Live configuration: chatModel={config['"'"'chatModel'"'"']} "
    f"embeddingModel={config['"'"'embeddingModel'"'"']} "
    f"endpoint={config['"'"'endpointType'"'"']}"
)
' <<<"$CONFIG_JSON"
}

run_preflight() {
  load_live_config
  require_clean_commit
  print_config_summary
  printf 'Live preflight passed without calling external APIs.\n'
}

assert_live_health() {
  local health_file="$1"

  python3 -c '
import json
import sys
from pathlib import Path

body = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if body.get("mode") != "live" or body.get("liveReady") is not True:
    raise SystemExit(
        f"Python health is not live-ready: mode={body.get('"'"'mode'"'"')} "
        f"liveReady={body.get('"'"'liveReady'"'"')}"
    )
print("Python health: mode=live liveReady=true")
' "$health_file"
}

verify_analysis() {
  local analysis_file="$1"

  python3 -c '
import json
import sys
from pathlib import Path

body = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
expected_trace_id = sys.argv[2]
if body.get("mode") != "live" or body.get("status") != "SUCCEEDED":
    raise SystemExit(
        f"analysis is not a live success: mode={body.get('"'"'mode'"'"')} "
        f"status={body.get('"'"'status'"'"')}"
    )
if body.get("traceId") != expected_trace_id:
    raise SystemExit("analysis did not preserve the requested traceId")

hits = body["retrieval"]["hits"]
if not hits or any(hit["retrievalMethod"] != "VECTOR" for hit in hits):
    raise SystemExit("live analysis must return VECTOR retrieval evidence")
citations = body["suggestedReply"]["citations"]
if not citations:
    raise SystemExit("live analysis must return at least one citation")
usage = body["usage"]
if usage["inputTokens"] <= 0 or usage["outputTokens"] <= 0:
    raise SystemExit("live analysis must report positive model token usage")

summary = {
    "traceId": body["traceId"],
    "mode": body["mode"],
    "status": body["status"],
    "modelName": body["modelName"],
    "category": body["classification"]["category"],
    "escalationRequired": body["decision"]["escalationRequired"],
    "inputTokens": usage["inputTokens"],
    "outputTokens": usage["outputTokens"],
    "durationMs": usage["durationMs"],
    "chunks": [
        {
            "chunkId": hit["chunkId"],
            "sourceUri": hit["sourceUri"],
            "rank": hit["rerankPosition"],
        }
        for hit in hits
    ],
    "citations": citations,
}
print(json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
' "$analysis_file" "$TRACE_ID"
}

assert_persisted_live() {
  local history_file="$1"

  python3 -c '
import json
import sys
from pathlib import Path

body = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
expected_trace_id = sys.argv[2]
if not body:
    raise SystemExit("Java analysis history is empty")
latest = body[0]
if (
    latest.get("traceId") != expected_trace_id
    or latest.get("mode") != "live"
    or latest.get("status") != "SUCCEEDED"
):
    raise SystemExit("Java did not persist the verified live analysis as the latest record")
print("Java history: latest mode=live status=SUCCEEDED traceId=preserved")
' "$history_file" "$TRACE_ID"
}

write_evidence() {
  local summary_json="$1"
  local git_commit="$2"

  python3 -c '
import json
import sys
from pathlib import Path

config = json.loads(sys.argv[1])
summary = json.loads(sys.argv[2])
output_path = Path(sys.argv[3])
validated_at, git_commit, ticket_id = sys.argv[4:7]

chunk_lines = [
    f"- `{chunk['"'"'chunkId'"'"']}` rank={chunk['"'"'rank'"'"']} source=`{chunk['"'"'sourceUri'"'"']}`"
    for chunk in summary["chunks"]
]
citation_lines = [f"- {citation}" for citation in summary["citations"]]
content = "\n".join(
    [
        "# Live RAG validation record",
        "",
        f"- Validated at: `{validated_at}`",
        f"- Git commit: `{git_commit}`",
        "- Worktree dirty: `false`",
        f"- Endpoint type: `{config['"'"'endpointType'"'"']}`",
        f"- Chat model: `{config['"'"'chatModel'"'"']}`",
        f"- Embedding model: `{config['"'"'embeddingModel'"'"']}`",
        f"- Ticket ID: `{ticket_id}`",
        f"- Trace ID: `{summary['"'"'traceId'"'"']}`",
        f"- Mode/status: `{summary['"'"'mode'"'"']}` / `{summary['"'"'status'"'"']}`",
        f"- Category: `{summary['"'"'category'"'"']}`",
        f"- Escalation required: `{str(summary['"'"'escalationRequired'"'"']).lower()}`",
        f"- Tokens: input `{summary['"'"'inputTokens'"'"']}`, output `{summary['"'"'outputTokens'"'"']}`",
        f"- Duration: `{summary['"'"'durationMs'"'"']} ms`",
        "- Fallback occurred: `false`",
        "",
        "## Retrieved evidence",
        "",
        *chunk_lines,
        "",
        "## Citations",
        "",
        *citation_lines,
        "",
        "API keys, authorization headers, ticket subject, ticket description, and customer data are intentionally omitted.",
        "",
    ]
)
output_path.parent.mkdir(parents=True, exist_ok=True)
output_path.write_text(content, encoding="utf-8")
print(f"Evidence record: {output_path}")
' "$CONFIG_JSON" "$summary_json" "$EVIDENCE_PATH" "$VALIDATED_AT" "$git_commit" "$TICKET_ID"
}

run_success() {
  local health_file headers_file analysis_file history_file
  local response_trace_header summary_json git_commit

  run_preflight
  new_temp_file health
  health_file="$NEW_TEMP_FILE"
  new_temp_file headers
  headers_file="$NEW_TEMP_FILE"
  new_temp_file analysis
  analysis_file="$NEW_TEMP_FILE"
  new_temp_file history
  history_file="$NEW_TEMP_FILE"

  curl --fail --silent --show-error --max-time "$HTTP_TIMEOUT_SECONDS" \
    --output "$health_file" "$AI_BASE_URL/health"
  assert_live_health "$health_file"

  curl --fail --silent --show-error --max-time "$HTTP_TIMEOUT_SECONDS" \
    --dump-header "$headers_file" \
    --output "$analysis_file" \
    -X POST \
    -H "X-Trace-Id: $TRACE_ID" \
    "$WEB_BASE_URL/api/tickets/$TICKET_ID/analyze"
  response_trace_header="$(
    awk 'tolower($1) == "x-trace-id:" {gsub("\r", "", $2); print $2}' "$headers_file" | tail -1
  )"
  if [[ "$response_trace_header" != "$TRACE_ID" ]]; then
    fail "Java response header did not preserve X-Trace-Id"
    return 1
  fi

  summary_json="$(verify_analysis "$analysis_file")"
  printf 'Analysis: mode=live status=SUCCEEDED traceId=%s\n' "$TRACE_ID"

  curl --fail --silent --show-error --max-time "$HTTP_TIMEOUT_SECONDS" \
    --output "$history_file" "$JAVA_BASE_URL/api/tickets/$TICKET_ID/analyses"
  assert_persisted_live "$history_file"

  git_commit="$(git -C "$ROOT_DIR" rev-parse HEAD)"
  write_evidence "$summary_json" "$git_commit"
}

main() {
  case "${1:---preflight}" in
    --preflight)
      run_preflight
      ;;
    --success)
      run_success
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

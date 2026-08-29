#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
AI_DIR="$ROOT_DIR/services/support-copilot-ai"
AI_BASE_URL="${SUPPORT_COPILOT_AI_BASE_URL:-http://127.0.0.1:8000}"
JAVA_BASE_URL="${SUPPORT_COPILOT_JAVA_BASE_URL:-http://127.0.0.1:8080}"
WEB_BASE_URL="${SUPPORT_COPILOT_WEB_BASE_URL:-http://127.0.0.1:5173}"
TICKET_ID="${SUPPORT_COPILOT_LIVE_TICKET_ID:-ticket-10041}"
TRACE_ID="${SUPPORT_COPILOT_TRACE_ID:-live-rag-$(date -u +%Y%m%d%H%M%S)}"
HTTP_TIMEOUT_SECONDS="${SUPPORT_COPILOT_HTTP_TIMEOUT_SECONDS:-120}"
JAVA_TIMEOUT_MS="${AI_SERVICE_TIMEOUT_MS:-105000}"
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
import sys
from hashlib import sha256

from app.config import DEFAULT_KNOWLEDGE_PATH, Settings
from app.knowledge_source import KnowledgeProvenance, load_knowledge_chunks
from app.timeout_budget import validate_timeout_budget

settings = Settings()
if not settings.live_ready or settings.effective_mode != "live":
    raise SystemExit(1)
validate_timeout_budget(settings, int(sys.argv[1]), int(sys.argv[2]))
knowledge_path = settings.knowledge_path
provenance_path = settings.knowledge_provenance_path
knowledge_chunks = load_knowledge_chunks(knowledge_path, provenance_path)
provenance = (
    KnowledgeProvenance.model_validate_json(
        provenance_path.read_text(encoding="utf-8")
    )
    if provenance_path is not None
    else None
)
def endpoint_type(base_url: str | None) -> str:
    return (
        "official"
        if not base_url or base_url.rstrip("/") == "https://api.openai.com/v1"
        else "compatible"
    )
chat_endpoint_type = endpoint_type(settings.openai_base_url)
embedding_endpoint_type = endpoint_type(settings.embedding_base_url)
print(
    json.dumps(
        {
            "chatModel": settings.openai_chat_model,
            "chatProtocol": settings.openai_chat_protocol,
            "embeddingModel": settings.openai_embedding_model,
            "externalTimeoutSeconds": settings.openai_timeout_seconds,
            "externalMaxRetries": settings.openai_max_retries,
            "processingTimeoutSeconds": settings.ai_processing_timeout_seconds,
            "javaTimeoutMs": int(sys.argv[1]),
            "clientTimeoutSeconds": int(sys.argv[2]),
            "endpointType": chat_endpoint_type,
            "embeddingEndpointType": embedding_endpoint_type,
            "knowledgeSource": (
                "repository-default"
                if knowledge_path.resolve() == DEFAULT_KNOWLEDGE_PATH.resolve()
                else "configured-external"
            ),
            "knowledgeChunks": len(knowledge_chunks),
            "knowledgeSha256": sha256(knowledge_path.read_bytes()).hexdigest(),
            "knowledgeFormat": (
                "generated-corpus" if provenance is not None else "pre-chunked-json"
            ),
            "knowledgeDocuments": (
                len(provenance.documents) if provenance is not None else None
            ),
            "knowledgeIndexVersion": (
                provenance.index_version if provenance is not None else None
            ),
            "knowledgeManifestSha256": (
                provenance.manifest_sha256 if provenance is not None else None
            ),
        },
        separators=(",", ":"),
    )
)
' "$JAVA_TIMEOUT_MS" "$HTTP_TIMEOUT_SECONDS" 2>/dev/null
  )"; then
    fail "live configuration or knowledge source is not ready"
    return 1
  fi
  validate_config_json
}

validate_config_json() {
  python3 -c '
import json
import sys

config = json.loads(sys.stdin.read())
if config.get("chatProtocol") not in {"responses", "chat_completions"}:
    raise SystemExit("chatProtocol must be responses or chat_completions")
' <<<"$CONFIG_JSON"
}

require_clean_commit() {
  local task_status
  task_status="$(git -C "$ROOT_DIR" status --porcelain -- . \
    ':(exclude)infra/README.md' \
    ':(exclude)infra/compose.pilot.yml' \
    ':(exclude)scripts/verify-mysql-persistence.sh')"
  if [[ -n "$task_status" ]]; then
    fail "Task 10 tracked scope must be clean so the live record can reference an exact commit"
    return 1
  fi
  if [[ "$(shasum -a 256 "$ROOT_DIR/infra/README.md" | awk '{print $1}')" != "6d96929d9bc44db7d90aecc4583c03b3671b829b145abc5b769d7a782188ea85" \
    || "$(shasum -a 256 "$ROOT_DIR/infra/compose.pilot.yml" | awk '{print $1}')" != "5e902c608b6e5984dde2f2242697349ac90921e104bad6dabcfa08cdecb58b32" \
    || "$(shasum -a 256 "$ROOT_DIR/scripts/verify-mysql-persistence.sh" | awk '{print $1}')" != "1d092ba952dd57f9baf8c6d5f0ef81734b1884ff73fa4bf637e71989d53d03b4" ]]; then
    fail "Protected Task 15 path hashes changed"
    return 1
  fi
}

print_config_summary() {
  python3 -c '
import json
import sys

config = json.loads(sys.stdin.read())
print(
    f"Live configuration: chatProtocol={config['"'"'chatProtocol'"'"']} "
    f"chatModel={config['"'"'chatModel'"'"']} "
    f"embeddingModel={config['"'"'embeddingModel'"'"']} "
    f"chatEndpoint={config['"'"'endpointType'"'"']} "
    f"embeddingEndpoint={config['"'"'embeddingEndpointType'"'"']} "
    f"knowledgeSource={config['"'"'knowledgeSource'"'"']} "
    f"knowledgeFormat={config['"'"'knowledgeFormat'"'"']} "
    f"knowledgeChunks={config['"'"'knowledgeChunks'"'"']}"
)
print(
    f"Timeout budget: external={config['"'"'externalTimeoutSeconds'"'"']}s "
    f"retries={config['"'"'externalMaxRetries'"'"']} "
    f"python={config['"'"'processingTimeoutSeconds'"'"']}s "
    f"java={config['"'"'javaTimeoutMs'"'"']}ms "
    f"client={config['"'"'clientTimeoutSeconds'"'"']}s"
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
    "retrievalMethod": hits[0]["retrievalMethod"],
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
print(json.dumps({
    "persisted": True,
    "traceId": latest["traceId"],
    "mode": latest["mode"],
    "status": latest["status"],
}, separators=(",", ":")))
' "$history_file" "$TRACE_ID"
}

write_evidence() {
  local summary_json="$1"
  local history_summary_json="$2"
  local git_commit="$3"
  local worktree_dirty="$4"

  python3 -c '
import json
import sys
from pathlib import Path

config = json.loads(sys.argv[1])
summary = json.loads(sys.argv[2])
history = json.loads(sys.argv[3])
output_path = Path(sys.argv[4])
validated_at, git_commit, ticket_id, worktree_dirty = sys.argv[5:9]

if summary["retrievalMethod"] != "VECTOR":
    raise SystemExit("refusing to write success evidence without verified VECTOR retrieval")
if config.get("chatProtocol") not in {"responses", "chat_completions"}:
    raise SystemExit("refusing to write evidence without a valid chat protocol")
if (
    history["persisted"] is not True
    or history["mode"] != "live"
    or history["status"] != "SUCCEEDED"
    or history["traceId"] != summary["traceId"]
):
    raise SystemExit("refusing to write success evidence without verified Java history persistence")

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
        f"- Worktree dirty: `{worktree_dirty}`",
        "- Task 10 tracked scope clean: `true`",
        f"- Chat protocol: `{config['"'"'chatProtocol'"'"']}`",
        f"- Chat endpoint type: `{config['"'"'endpointType'"'"']}`",
        f"- Embedding endpoint type: `{config['"'"'embeddingEndpointType'"'"']}`",
        f"- Chat model: `{config['"'"'chatModel'"'"']}`",
        f"- Embedding model: `{config['"'"'embeddingModel'"'"']}`",
        f"- External request timeout: `{config['"'"'externalTimeoutSeconds'"'"']} s`",
        f"- External maximum retries: `{config['"'"'externalMaxRetries'"'"']}`",
        f"- Python processing timeout: `{config['"'"'processingTimeoutSeconds'"'"']} s`",
        f"- Java AI service timeout: `{config['"'"'javaTimeoutMs'"'"']} ms`",
        f"- Verification client timeout: `{config['"'"'clientTimeoutSeconds'"'"']} s`",
        f"- Knowledge source: `{config['"'"'knowledgeSource'"'"']}`",
        f"- Knowledge format: `{config['"'"'knowledgeFormat'"'"']}`",
        f"- Knowledge source documents: `{config['"'"'knowledgeDocuments'"'"'] or '"'"'not-recorded'"'"'}`",
        f"- Knowledge index version: `{config['"'"'knowledgeIndexVersion'"'"'] or '"'"'not-recorded'"'"'}`",
        f"- Knowledge manifest SHA-256: `{config['"'"'knowledgeManifestSha256'"'"'] or '"'"'not-recorded'"'"'}`",
        f"- Knowledge chunks: `{config['"'"'knowledgeChunks'"'"']}`",
        f"- Knowledge SHA-256: `{config['"'"'knowledgeSha256'"'"']}`",
        f"- Ticket ID: `{ticket_id}`",
        f"- Trace ID: `{summary['"'"'traceId'"'"']}`",
        f"- Mode/status: `{summary['"'"'mode'"'"']}` / `{summary['"'"'status'"'"']}`",
        f"- Retrieval method: `{summary['"'"'retrievalMethod'"'"']}`",
        "- Java history persistence: `verified`",
        f"- Java history mode/status: `{history['"'"'mode'"'"']}` / `{history['"'"'status'"'"']}`",
        f"- Java history trace ID: `{history['"'"'traceId'"'"']}` (preserved)",
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
' "$CONFIG_JSON" "$summary_json" "$history_summary_json" "$EVIDENCE_PATH" "$VALIDATED_AT" "$git_commit" "$TICKET_ID" "$worktree_dirty"
}

run_live_dataset_evaluation() {
  (
    cd "$AI_DIR"
    .venv/bin/python -m evaluation.run_live_evaluation
  )
  printf 'Live dataset machine evaluation complete; publishable gate remains pending human review.\n'
}

run_success() {
  local health_file headers_file analysis_file history_file
  local response_trace_header summary_json history_summary_json git_commit idempotency_key worktree_dirty

  run_preflight
  new_temp_file health
  health_file="$NEW_TEMP_FILE"
  new_temp_file headers
  headers_file="$NEW_TEMP_FILE"
  new_temp_file analysis
  analysis_file="$NEW_TEMP_FILE"
  new_temp_file history
  history_file="$NEW_TEMP_FILE"
  idempotency_key="$(python3 -c 'import uuid; print(uuid.uuid4())')"

  curl --fail --silent --show-error --max-time "$HTTP_TIMEOUT_SECONDS" \
    --output "$health_file" "$AI_BASE_URL/health"
  assert_live_health "$health_file"

  curl --fail --silent --show-error --max-time "$HTTP_TIMEOUT_SECONDS" \
    --dump-header "$headers_file" \
    --output "$analysis_file" \
    -X POST \
    -H "Idempotency-Key: $idempotency_key" \
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
  history_summary_json="$(assert_persisted_live "$history_file")"
  printf 'Java history: latest mode=live status=SUCCEEDED traceId=preserved\n'

  git_commit="$(git -C "$ROOT_DIR" rev-parse HEAD)"
  worktree_dirty="false"
  if [[ -n "$(git -C "$ROOT_DIR" status --porcelain)" ]]; then
    worktree_dirty="true"
  fi
  write_evidence "$summary_json" "$history_summary_json" "$git_commit" "$worktree_dirty"
  run_live_dataset_evaluation
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

#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT_UNDER_TEST="$ROOT_DIR/scripts/check-live-rag.sh"
TEST_TEMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/support-copilot-live-evidence-test.XXXXXX")"
SOURCE_COPY="$(mktemp "$ROOT_DIR/scripts/.check-live-rag-source.XXXXXX")"

test_cleanup() {
  unlink "$SOURCE_COPY"
  find "$TEST_TEMP_DIR" -depth -delete
}

assert_contains() {
  local expected="$1"
  local path="$2"

  if ! grep -Fq -- "$expected" "$path"; then
    printf 'FAIL: generated evidence is missing required field: %s\n' "$expected" >&2
    return 1
  fi
}

# Load the production functions without invoking the script's final main call.
sed '/^main "\$@"$/d' "$SCRIPT_UNDER_TEST" >"$SOURCE_COPY"
source "$SOURCE_COPY"
trap test_cleanup EXIT

TRACE_ID="fixture-trace"
CONFIG_JSON='{"endpointType":"compatible","embeddingEndpointType":"compatible","chatModel":"fixture-chat","embeddingModel":"fixture-embedding","externalTimeoutSeconds":20,"externalMaxRetries":1,"processingTimeoutSeconds":90,"javaTimeoutMs":105000,"clientTimeoutSeconds":120,"knowledgeSource":"repository-default","knowledgeFormat":"pre-chunked-json","knowledgeDocuments":null,"knowledgeIndexVersion":null,"knowledgeManifestSha256":null,"knowledgeChunks":1,"knowledgeSha256":"fixture-sha256"}'

analysis_file="$TEST_TEMP_DIR/analysis.json"
history_file="$TEST_TEMP_DIR/history.json"
cat >"$analysis_file" <<'JSON'
{"traceId":"fixture-trace","mode":"live","status":"SUCCEEDED","modelName":"fixture-chat","classification":{"category":"ACCOUNT_ACCESS"},"decision":{"escalationRequired":false},"retrieval":{"hits":[{"chunkId":"fixture-chunk","sourceUri":"https://support.example.test/fixture","rerankPosition":1,"retrievalMethod":"VECTOR"}]},"suggestedReply":{"citations":["fixture-chunk"]},"usage":{"inputTokens":12,"outputTokens":8,"durationMs":34}}
JSON
cat >"$history_file" <<'JSON'
[{"traceId":"fixture-trace","mode":"live","status":"SUCCEEDED"}]
JSON

summary_json="$(verify_analysis "$analysis_file")"
history_summary_json="$(assert_persisted_live "$history_file")"
EVIDENCE_PATH="$TEST_TEMP_DIR/complete.md"
write_evidence "$summary_json" "$history_summary_json" "fixture-commit" >/dev/null

assert_contains '- Retrieval method: `VECTOR`' "$EVIDENCE_PATH"
assert_contains '- Java history persistence: `verified`' "$EVIDENCE_PATH"
assert_contains '- Java history mode/status: `live` / `SUCCEEDED`' "$EVIDENCE_PATH"
assert_contains '- Java history trace ID: `fixture-trace` (preserved)' "$EVIDENCE_PATH"

missing_retrieval_summary="$(python3 -c 'import json,sys; value=json.load(sys.stdin); value.pop("retrievalMethod", None); print(json.dumps(value))' <<<"$summary_json")"
EVIDENCE_PATH="$TEST_TEMP_DIR/missing-retrieval.md"
if write_evidence "$missing_retrieval_summary" "$history_summary_json" "fixture-commit" >/dev/null 2>&1; then
  printf 'FAIL: evidence writer accepted a missing retrieval method\n' >&2
  exit 1
fi
[[ ! -e "$EVIDENCE_PATH" ]]

EVIDENCE_PATH="$TEST_TEMP_DIR/missing-history.md"
if write_evidence "$summary_json" '{}' "fixture-commit" >/dev/null 2>&1; then
  printf 'FAIL: evidence writer accepted a missing Java history assertion\n' >&2
  exit 1
fi
[[ ! -e "$EVIDENCE_PATH" ]]

printf 'Live evidence fixture assertions passed.\n'

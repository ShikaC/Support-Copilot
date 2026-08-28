#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
aggregate="$repo_root/scripts/verify-ci-gates.sh"

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

[[ -x "$aggregate" ]] || fail "aggregate contract is missing or not executable: scripts/verify-ci-gates.sh"

gate_list="$($aggregate --list)"
for gate in \
  python-locks python-tests python-mock-evaluation \
  java-tests java-profile-contracts java-flyway-contracts \
  react-install react-lint react-tests react-build react-budget react-node-contracts react-e2e \
  workflow-syntax workflow-contract static-migration-profile static-security \
  dependency-vulnerabilities tracked-secrets; do
  grep -qx "$gate" <<<"$gate_list" || fail "missing gate: $gate"
done

deferred="$($aggregate --deferred)"
for capability in Docker Compose MySQL Testcontainers backup restore rollback; do
  grep -q "DEFERRED.*$capability" <<<"$deferred" || fail "$capability is not explicitly deferred"
done
if grep -q 'PASS.*\(Docker\|Compose\|MySQL\|Testcontainers\|backup\|restore\|rollback\)' <<<"$deferred"; then
  fail "a deferred container capability was reported as PASS"
fi

set +e
failure_output="$(CI_GATE_TEST_COMMAND=false "$aggregate" --test-failure-propagation 2>&1)"
failure_status=$?
set -e
[[ $failure_status -ne 0 ]] || fail "a failing gate did not propagate a nonzero status"
grep -q '^\[FAIL\] task13-failure-propagation$' <<<"$failure_output" || fail "failure output is not stable"

grep -q 'OSV_SCANNER_VERSION=' "$aggregate" || fail "OSV scanner version is not pinned"
grep -q 'GITLEAKS_VERSION=' "$aggregate" || fail "gitleaks version is not pinned"
grep -q -- '--format json' "$aggregate" || fail "OSV findings are not evaluated through structured output"
grep -Eq 'git .*log -p --all' "$aggregate" || fail "tracked history is not included in secret scanning"
grep -q -- '--redact' "$aggregate" || fail "secret findings are not redacted"

for workflow in "$repo_root"/.github/workflows/*.yml; do
  unpinned="$(grep -E '^[[:space:]]*uses:' "$workflow" | grep -Ev '@[0-9a-f]{40}[[:space:]]*$' || true)"
  [[ -z "$unpinned" ]] || fail "workflow action is not SHA-pinned: ${workflow#$repo_root/}"
  grep -q '^permissions:' "$workflow" || fail "workflow permissions are not explicit: ${workflow#$repo_root/}"
  grep -q 'contents: read' "$workflow" || fail "workflow permissions are not least-privileged: ${workflow#$repo_root/}"
  grep -q 'scripts/verify-ci-gates.sh' "$workflow" || fail "workflow bypasses aggregate contract: ${workflow#$repo_root/}"
done

grep -q 'verify-ci-gates.sh --mode python' "$repo_root/.github/workflows/python-ai-ci.yml" || fail "Python workflow mode drifted"
grep -q 'verify-ci-gates.sh --mode java' "$repo_root/.github/workflows/java-api-ci.yml" || fail "Java workflow mode drifted"
grep -q 'verify-ci-gates.sh --mode react' "$repo_root/.github/workflows/react-web-ci.yml" || fail "React workflow mode drifted"
grep -q 'verify-ci-gates.sh --mode release' "$repo_root/.github/workflows/release-gates-ci.yml" || fail "release workflow mode drifted"

if rg -n 'check-live-rag|docker|compose|mysql|verify-(backup|restore|rollback)' \
  "$repo_root/.github/workflows" "$aggregate"; then
  fail "Task 15 or live behavior leaked into Task 13 execution"
fi

printf 'PASS: Task 13 aggregate contract\n'

#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
gitleaks_bin="${1:-gitleaks}"
config="${2:-$repo_root/.gitleaks.toml}"
fixture_root="$(mktemp -d "${TMPDIR:-/tmp}/support-copilot-secret-scan.XXXXXX")"
trap 'rm -rf "$fixture_root"' EXIT
fixture_repo="$fixture_root/repo"
mkdir -p "$fixture_repo/docs/enterprise-workspace"

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

# Synthetic values are generated at runtime, never stored as credentials in Git.
checksum="$(printf 'secret-scanner-checksum-fixture' | shasum -a 256 | awk '{print $1}')"
github_token="$(printf 'gh%s_%s' p "${checksum:0:36}")"
evidence_files=(source-manifest.json source-manifest-r1.json persistence-results.json)
for filename in "${evidence_files[@]}"; do
  printf '{\n  "services/support-copilot-api/src/main/java/Api.java": "%s"\n}\n' \
    "$checksum" >"$fixture_repo/docs/enterprise-workspace/$filename"
done

scan() {
  local mode="$1" expected_generic="$2" expected_github="$3"
  local status=0 report="$fixture_root/report.json" log="$fixture_root/scan.log"
  local -a options=(--config "$config" --no-banner --redact --exit-code 1
    --report-format json --report-path "$report")
  rm -f "$report"
  if [[ "$mode" == git ]]; then
    "$gitleaks_bin" git "$fixture_repo" --log-opts=--all "${options[@]}" >"$log" 2>&1 || status=$?
  else
    (cd "$fixture_repo" && "$gitleaks_bin" dir . "${options[@]}") >"$log" 2>&1 || status=$?
  fi
  local expected_status=0
  [[ $((expected_generic + expected_github)) -eq 0 ]] || expected_status=1
  [[ "$status" -eq "$expected_status" ]] || fail "$mode scan exit $status, expected $expected_status"
  [[ -f "$report" ]] || fail "$mode scan did not produce a report"
  local generic_count github_count total_count
  generic_count="$(grep -c '"RuleID": "generic-api-key"' "$report" || true)"
  github_count="$(grep -c '"RuleID": "github-pat"' "$report" || true)"
  total_count="$(grep -c '"RuleID":' "$report" || true)"
  [[ "$generic_count" -eq "$expected_generic" ]] || fail "$mode generic findings: $generic_count, expected $expected_generic"
  [[ "$github_count" -eq "$expected_github" ]] || fail "$mode GitHub findings: $github_count, expected $expected_github"
  [[ "$total_count" -eq $((expected_generic + expected_github)) ]] || fail "$mode unexpected finding rule"
}

scan dir 0 0
printf '[PASS] three evidence files allow only source-path SHA-256 lines\n'

for filename in "${evidence_files[@]}"; do
  {
    printf '  "api_key": "%s"\n' "$checksum"
    printf '  "config/api_key": "%s"\n' "$checksum"
    printf '  "services/support-copilot-api/src/main/java/Api.java": "%s"\n' "$github_token"
  } >>"$fixture_repo/docs/enterprise-workspace/$filename"
done
for filename in unrelated.json source-manifest.json.bak; do
  printf '  "services/support-copilot-api/src/main/java/Api.java": "%s"\n' \
    "$checksum" >"$fixture_repo/docs/enterprise-workspace/$filename"
done
mkdir -p "$fixture_repo/nested/docs/enterprise-workspace"
printf '  "services/support-copilot-api/src/main/java/Api.java": "%s"\n' \
  "$checksum" >"$fixture_repo/nested/docs/enterprise-workspace/source-manifest.json"
scan dir 9 3
printf '[PASS] generic keys, path-like keys, other paths, and GitHub tokens remain detectable\n'

git -C "$fixture_repo" init -q
git -C "$fixture_repo" add .
git -C "$fixture_repo" -c user.name=SecretScanFixture -c user.email=fixture@localhost \
  -c commit.gpgsign=false -c core.hooksPath=/dev/null commit -qm 'synthetic detection controls'
git -C "$fixture_repo" rm -qr docs
git -C "$fixture_repo" -c user.name=SecretScanFixture -c user.email=fixture@localhost \
  -c commit.gpgsign=false -c core.hooksPath=/dev/null commit -qm 'remove synthetic controls'
scan git 9 3
printf '[PASS] Git history preserves path-scoped exceptions and detects deleted secrets\n'

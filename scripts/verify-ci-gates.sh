#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly ACTIONLINT_VERSION="1.7.7"
readonly OSV_SCANNER_VERSION="2.2.4"
readonly GITLEAKS_VERSION="8.30.1"

gate_names=(
  python-locks python-tests python-mock-evaluation
  java-tests java-profile-contracts java-flyway-contracts
  react-install react-lint react-tests react-build react-budget react-node-contracts react-e2e
  workflow-syntax workflow-contract static-migration-profile static-security
  dependency-vulnerabilities tracked-secrets
)

usage() {
  printf 'Usage: %s [--mode python|java|react|release|all | --list | --deferred]\n' "$0"
}

print_deferred() {
  printf '%s\n' \
    '[DEFERRED] Docker images/runtime (Task 15)' \
    '[DEFERRED] Docker Compose (Task 15)' \
    '[DEFERRED] MySQL runtime and Testcontainers (Task 15)' \
    '[DEFERRED] backup and restore drills (Task 15)' \
    '[DEFERRED] deployment rollback drills (Task 15)'
}

run_gate() {
  local name="$1"
  shift
  printf '[RUN] %s\n' "$name"
  if "$@"; then
    printf '[PASS] %s\n' "$name"
  else
    printf '[FAIL] %s\n' "$name" >&2
    return 1
  fi
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || {
    printf 'Required command is missing: %s\n' "$1" >&2
    return 1
  }
}

require_version() {
  local command_name="$1"
  local expected="$2"
  shift 2
  require_command "$command_name"
  local actual
  actual="$("$@" 2>&1)"
  grep -Eq "(^|[^0-9])v?${expected//./\\.}([^0-9]|$)" <<<"$actual" || {
    printf 'Expected %s %s, observed: %s\n' "$command_name" "$expected" "$actual" >&2
    return 1
  }
}

python_locks() {
  require_command python
  cd "$repo_root/services/support-copilot-ai"
  python -m scripts.check_dependency_locks
}

python_tests() {
  cd "$repo_root/services/support-copilot-ai"
  AI_MODE=mock OPENAI_API_KEY= OPENAI_EMBEDDING_API_KEY= python -m pytest -q
}

python_mock_evaluation() {
  cd "$repo_root/services/support-copilot-ai"
  AI_MODE=mock OPENAI_API_KEY= OPENAI_EMBEDDING_API_KEY= python -m evaluation.run_mock_evaluation
}

java_full_tests() {
  require_command java
  cd "$repo_root/services/support-copilot-api"
  env -u SUPPORT_COPILOT_RUN_MYSQL_TESTS ./gradlew test --no-daemon
}

java_profile_contracts() {
  cd "$repo_root/services/support-copilot-api"
  ./gradlew test --no-daemon --tests '*ProfileConfigurationTests' --tests '*RuntimeProfileIntegrationTests' \
    --tests '*DemoProfileIntegrationTests' --tests '*TestProfileIntegrationTests'
}

java_flyway_contracts() {
  cd "$repo_root/services/support-copilot-api"
  ./gradlew test --no-daemon --tests '*FlywayMigrationContractTests'
}

react_command() {
  cd "$repo_root/apps/support-copilot-web"
  "$@"
}

react_install() {
  require_command node
  require_command npm
  react_command npm ci
}

workflow_syntax() {
  require_version actionlint "$ACTIONLINT_VERSION" actionlint -version
  actionlint "$repo_root"/.github/workflows/*.{yml,yaml} 2>/dev/null || \
    actionlint "$repo_root"/.github/workflows/*.yml
}

static_migration_profile() {
  local resources="$repo_root/services/support-copilot-api/src/main/resources"
  if rg -ni '\b(drop[[:space:]]+table|truncate[[:space:]]+table|flyway[[:space:]]+clean)\b' \
    "$resources/db/migration"; then
    printf 'Destructive migration statement found.\n' >&2
    return 1
  fi
  for profile in local pilot; do
    local file="$resources/application-$profile.properties"
    grep -qx 'spring.jpa.hibernate.ddl-auto=validate' "$file"
    grep -qx 'spring.flyway.enabled=true' "$file"
    grep -qx 'spring.flyway.clean-disabled=true' "$file"
    grep -qx 'spring.h2.console.enabled=false' "$file"
    grep -qx 'support-copilot.demo-fixtures.enabled=false' "$file"
  done
}

static_security() {
  local resources="$repo_root/services/support-copilot-api/src/main/resources"
  for profile in local pilot; do
    local file="$resources/application-$profile.properties"
    grep -qx 'support-copilot.security.business-access=jwt' "$file"
    grep -qx 'support-copilot.security.internal-service-token=${SUPPORT_COPILOT_INTERNAL_SERVICE_TOKEN}' "$file"
    if rg -n 'permitAll|anonymous-demo|synthetic-(demo|test)' "$file"; then
      printf 'Open or synthetic security configuration found in %s.\n' "$file" >&2
      return 1
    fi
  done
  grep -qx 'support-copilot.security.business-access=anonymous-demo' \
    "$resources/application-demo.properties"
}

dependency_vulnerabilities() {
  require_version osv-scanner "$OSV_SCANNER_VERSION" osv-scanner --version
  local tracked_snapshot
  local report
  local scan_status
  tracked_snapshot="$(mktemp -d "${TMPDIR:-/tmp}/support-copilot-dependencies.XXXXXX")"
  report="$tracked_snapshot/osv-report.json"
  trap 'rm -rf "$tracked_snapshot"' RETURN
  git -C "$repo_root" ls-files -z | tar --null -T - -C "$repo_root" -cf - | tar -C "$tracked_snapshot" -xf -
  osv-scanner scan source --recursive --format json --output "$report" "$tracked_snapshot" || scan_status=$?
  scan_status="${scan_status:-0}"
  if [[ $scan_status -ne 0 ]]; then
    printf 'OSV-Scanner found known dependency vulnerabilities; details are intentionally not printed.\n' >&2
  fi
  rm -rf "$tracked_snapshot"
  trap - RETURN
  return "$scan_status"
}

tracked_secrets() {
  require_version gitleaks "$GITLEAKS_VERSION" gitleaks version
  local tracked_snapshot
  local scan_status=0
  tracked_snapshot="$(mktemp -d "${TMPDIR:-/tmp}/support-copilot-tracked.XXXXXX")"
  trap 'rm -rf "$tracked_snapshot"' RETURN
  git -C "$repo_root" ls-files -z | tar --null -T - -C "$repo_root" -cf - | tar -C "$tracked_snapshot" -xf -
  gitleaks dir "$tracked_snapshot" --no-banner --redact --exit-code 1 || scan_status=$?
  if [[ $scan_status -eq 0 ]]; then
    git -C "$repo_root" log -p --all | gitleaks stdin --no-banner --redact --exit-code 1 || scan_status=$?
  fi
  rm -rf "$tracked_snapshot"
  trap - RETURN
  return "$scan_status"
}

run_python() {
  run_gate python-locks python_locks
  run_gate python-tests python_tests
  run_gate python-mock-evaluation python_mock_evaluation
}

run_java() {
  run_gate java-tests java_full_tests
  run_gate java-profile-contracts java_profile_contracts
  run_gate java-flyway-contracts java_flyway_contracts
}

run_react() {
  run_gate react-install react_install
  run_gate react-lint react_command npm run lint
  run_gate react-tests react_command npm test -- --run
  run_gate react-build react_command npm run build
  run_gate react-budget react_command npm run build:budget
  run_gate react-node-contracts react_command npm run test:node
  run_gate react-e2e react_command npm run test:e2e
}

run_release() {
  require_command rg
  run_gate workflow-syntax workflow_syntax
  run_gate workflow-contract "$repo_root/scripts/tests/verify-ci-gates-contract.sh"
  run_gate static-migration-profile static_migration_profile
  run_gate static-security static_security
  run_gate dependency-vulnerabilities dependency_vulnerabilities
  run_gate tracked-secrets tracked_secrets
}

mode="all"
case "${1:-}" in
  --list)
    printf '%s\n' "${gate_names[@]}"
    exit 0
    ;;
  --deferred)
    print_deferred
    exit 0
    ;;
  --test-failure-propagation)
    run_gate task13-failure-propagation bash -c "${CI_GATE_TEST_COMMAND:-false}"
    exit 0
    ;;
  --mode)
    [[ $# -eq 2 ]] || { usage >&2; exit 2; }
    mode="$2"
    ;;
  '') ;;
  *) usage >&2; exit 2 ;;
esac

case "$mode" in
  python) run_python ;;
  java) run_java ;;
  react) run_react ;;
  release) run_release ;;
  all)
    run_python
    run_java
    run_react
    run_release
    ;;
  *) usage >&2; exit 2 ;;
esac

print_deferred
printf '[PASS] non-container CI gates (%s)\n' "$mode"

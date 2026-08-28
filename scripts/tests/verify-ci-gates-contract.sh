#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
aggregate="$repo_root/scripts/verify-ci-gates.sh"
fixture_root="$(mktemp -d "${TMPDIR:-/tmp}/support-copilot-ci-contract.XXXXXX")"
fixture_repo="$fixture_root/repo"
shim_dir="$fixture_root/bin"
command_log="$fixture_root/commands.log"
fixture_tmpdir="$fixture_root/tmp"

cleanup() {
	rm -rf "$fixture_root"
}
trap cleanup EXIT

fail() {
	printf 'FAIL: %s\n' "$*" >&2
	exit 1
}

[[ -x "$aggregate" ]] || fail "aggregate contract is missing or not executable: scripts/verify-ci-gates.sh"

mkdir -p "$fixture_repo" "$shim_dir" "$fixture_tmpdir"
git -C "$repo_root" ls-files -z | tar --null -T - -C "$repo_root" -cf - | tar -C "$fixture_repo" -xf -
cp "$repo_root/services/support-copilot-api/gradle.lockfile" \
	"$fixture_repo/services/support-copilot-api/gradle.lockfile"
git -C "$fixture_repo" init -q
git -C "$fixture_repo" add .

cat >"$shim_dir/python" <<'SHIM'
#!/usr/bin/env bash
set -euo pipefail
printf 'python %s\n' "$*" >>"$CI_GATE_COMMAND_LOG"
SHIM

cat >"$shim_dir/java" <<'SHIM'
#!/usr/bin/env bash
set -euo pipefail
printf 'java %s\n' "$*" >>"$CI_GATE_COMMAND_LOG"
SHIM

cat >"$shim_dir/node" <<'SHIM'
#!/usr/bin/env bash
set -euo pipefail
printf 'node %s\n' "$*" >>"$CI_GATE_COMMAND_LOG"
SHIM

cat >"$shim_dir/npm" <<'SHIM'
#!/usr/bin/env bash
set -euo pipefail
printf 'npm %s\n' "$*" >>"$CI_GATE_COMMAND_LOG"
SHIM

cat >"$shim_dir/actionlint" <<'SHIM'
#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == "-version" ]]; then
	printf 'actionlint 1.7.7\n'
	exit 0
fi
printf 'actionlint %s\n' "$*" >>"$CI_GATE_COMMAND_LOG"
SHIM

cat >"$shim_dir/gitleaks" <<'SHIM'
#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == "version" ]]; then
	printf '8.30.1\n'
	exit 0
fi
printf 'gitleaks %s\n' "$*" >>"$CI_GATE_COMMAND_LOG"
if [[ "${1:-}" == "stdin" ]]; then
	cat >/dev/null
fi
SHIM

cat >"$shim_dir/osv-scanner" <<'SHIM'
#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == "--version" ]]; then
	printf 'osv-scanner version: 2.2.4\n'
	exit 0
fi
printf 'osv-scanner %s\n' "$*" >>"$CI_GATE_COMMAND_LOG"
output=''
lockfile=''
for argument in "$@"; do
	case "$argument" in
		--output=*) output="${argument#--output=}" ;;
		--output-file=*) output="${argument#--output-file=}" ;;
		--lockfile=*) lockfile="${argument#--lockfile=}" ;;
	esac
done
[[ -n "$output" && -n "$lockfile" ]] || exit 64
if [[ "${CI_GATE_FAIL_PYTHON_OSV:-}" == 1 && "$lockfile" == "osv-scanner:"*"python-production-osv.json" ]]; then
	exit 73
fi
/usr/bin/python3 - "$lockfile" "$output" <<'PY'
import json
import re
import sys
from pathlib import Path

lock_argument, output_path = sys.argv[1:]
lock_type, inventory_path = lock_argument.split(":", 1)
inventory = Path(inventory_path)
packages = []
if lock_type == "osv-scanner":
    document = json.loads(inventory.read_text())
    packages = [
        (
            item["package"]["name"],
            item["package"]["version"],
            item["package"]["ecosystem"],
        )
        for result in document["results"]
        for item in result["packages"]
    ]
    with Path(__import__("os").environ["CI_GATE_COMMAND_LOG"]).open("a") as log:
        log.write(f'osv-source {document["results"][0]["source"]["path"]}\n')
elif inventory.name == "gradle.lockfile":
    for line in inventory.read_text().splitlines():
        if not line or line.startswith("#") or line.startswith("empty="):
            continue
        coordinate = line.split("=", 1)[0]
        group, name, version = coordinate.split(":", 2)
        packages.append((f"{group}:{name}", version, "Maven"))
elif inventory.name == "package-lock.json":
    document = json.loads(inventory.read_text())
    for path, package in document["packages"].items():
        if not path:
            continue
        name = package.get("name") or path.rsplit("node_modules/", 1)[-1]
        packages.append((name, package["version"], "npm"))
else:
    raise SystemExit(f"unsupported fixture lock type: {lock_type}:{inventory}")

result = {
    "results": [{
        "source": {"path": str(inventory), "type": "lockfile"},
        "packages": [{
            "package": {"name": name, "version": version, "ecosystem": ecosystem},
            "vulnerabilities": [],
        } for name, version, ecosystem in packages],
    }],
}
if (
    __import__("os").environ.get("CI_GATE_ADD_UNEXPECTED_PYTHON_PACKAGE") == "1"
    and lock_type == "osv-scanner"
    and inventory.name == "python-production-osv.json"
):
    result["results"][0]["packages"].append({
        "package": {
            "name": "unexpected-fixture-package",
            "version": "9.9.9",
            "ecosystem": "PyPI",
        },
        "vulnerabilities": [],
    })
Path(output_path).write_text(json.dumps(result))
PY
SHIM

cat >"$fixture_repo/services/support-copilot-api/gradlew" <<'SHIM'
#!/usr/bin/env bash
set -euo pipefail
printf 'gradlew %s\n' "$*" >>"$CI_GATE_COMMAND_LOG"
if [[ -n "${CI_GATE_FAIL_FLYWAY:-}" && "$*" == *FlywayMigrationContractTests* ]]; then
	exit 42
fi
SHIM

cat >"$fixture_repo/scripts/tests/verify-ci-gates-contract.sh" <<'SHIM'
#!/usr/bin/env bash
set -euo pipefail
printf 'workflow-contract %s\n' "$*" >>"$CI_GATE_COMMAND_LOG"
SHIM

chmod +x "$shim_dir"/* "$fixture_repo/services/support-copilot-api/gradlew" \
	"$fixture_repo/scripts/tests/verify-ci-gates-contract.sh"

mkdir -p "$fixture_root/scans"

run_fixture_mode() {
	local mode="$1"
	local output="$fixture_root/$mode.out"
	if ! PATH="$shim_dir:$PATH" CI_GATE_COMMAND_LOG="$command_log" TMPDIR="$fixture_tmpdir" \
		CI_GATE_SCAN_EVIDENCE_DIR="$fixture_root/scans" \
		"$fixture_repo/scripts/verify-ci-gates.sh" --mode "$mode" >"$output" 2>&1; then
		cat "$output" >&2
		fail "$mode mode failed while exercising the aggregate contract"
	fi
	grep -q "^\[PASS\] non-container CI gates ($mode)$" "$output" || \
		fail "$mode mode did not complete through the aggregate contract"
	assert_no_dependency_workspaces "successful $mode mode"
}

assert_no_dependency_workspaces() {
	local scenario="$1"
	local leaked
	leaked="$(find "$fixture_tmpdir" -maxdepth 1 -type d \
		\( -name 'support-copilot-dependencies.*' -o -name 'support-copilot-scans.*' \) -print -quit)"
	[[ -z "$leaked" ]] || fail "$scenario left dependency workspace: ${leaked#$fixture_tmpdir/}"
}

for mode in python java react release all; do
	run_fixture_mode "$mode"
done

all_output="$fixture_root/all.out"
for gate in \
	python-locks python-tests python-mock-evaluation \
	java-tests java-profile-contracts java-flyway-contracts \
	react-install react-lint react-tests react-build react-budget react-node-contracts react-e2e \
	workflow-syntax workflow-contract static-migration-profile static-security \
	dependency-vulnerabilities tracked-secrets; do
	grep -q "^\[RUN\] $gate$" "$all_output" || fail "all mode did not invoke gate: $gate"
	grep -q "^\[PASS\] $gate$" "$all_output" || fail "all mode did not complete gate: $gate"
done

grep -q '^python -m scripts.check_dependency_locks$' "$command_log" || fail "Python lock gate command was not invoked"
grep -q '^gradlew dependencies --write-locks --no-daemon$' "$command_log" || fail "Java resolved inventory was not regenerated"
grep -q '^npm ci$' "$command_log" || fail "React install gate command was not invoked"
for inventory in python-production-osv.json python-development-osv.json; do
	grep -q -- "--lockfile=osv-scanner:.*${inventory}" "$command_log" || \
		fail "generated Python inventory was not explicitly scanned: $inventory"
done
for inventory in \
	services/support-copilot-api/gradle.lockfile \
	apps/support-copilot-web/package-lock.json; do
	grep -q -- "--lockfile=.*${inventory}" "$command_log" || fail "resolved inventory was not explicitly scanned: $inventory"
done
for label in python-production python-development java node; do
	grep -Eq "^\[SCAN\] $label inventory-packages=[1-9][0-9]* scanned-packages=[1-9][0-9]* vulnerabilities=0$" \
		"$all_output" || fail "scan report was not validated against the $label inventory"
done

/usr/bin/python3 - "$fixture_root/scans" "$all_output" <<'PY'
import json
import re
import sys
from pathlib import Path

scan_dir = Path(sys.argv[1])
all_output = Path(sys.argv[2]).read_text(encoding="utf-8")
numpy_coordinates = {("numpy", "2.4.6", "PyPI"), ("numpy", "2.5.2", "PyPI")}

for label, inventory_name, report_name in (
    ("python-production", "python-production-osv.json", "python-production-report.json"),
    ("python-development", "python-development-osv.json", "python-development-report.json"),
):
    inventory = json.loads((scan_dir / inventory_name).read_text(encoding="utf-8"))
    report = json.loads((scan_dir / report_name).read_text(encoding="utf-8"))
    inventory_coordinates = {
        (item["package"]["name"], item["package"]["version"], item["package"]["ecosystem"])
        for result in inventory["results"]
        for item in result["packages"]
    }
    report_coordinates = {
        (item["package"]["name"], item["package"]["version"], item["package"]["ecosystem"])
        for result in report["results"]
        for item in result["packages"]
    }
    if not numpy_coordinates <= inventory_coordinates:
        raise SystemExit(f"{label}: inventory omitted a locked NumPy coordinate")
    if not numpy_coordinates <= report_coordinates:
        raise SystemExit(f"{label}: report omitted a scanned NumPy coordinate")
    summary = re.search(
        rf"^\[SCAN\] {label} inventory-packages=(\d+) scanned-packages=(\d+) vulnerabilities=0$",
        all_output,
        re.MULTILINE,
    )
    if summary is None:
        raise SystemExit(f"{label}: missing scan summary")
    if tuple(map(int, summary.groups())) != (len(inventory_coordinates), len(report_coordinates)):
        raise SystemExit(f"{label}: scan summary counts do not match inventory/report coordinates")
PY

reset_python_production_lock() {
	cp "$repo_root/services/support-copilot-ai/requirements.lock.txt" \
		"$fixture_repo/services/support-copilot-ai/requirements.lock.txt"
}

dependency_failure_count=0

record_dependency_failure() {
	printf 'FAIL: %s\n' "$*" >&2
	dependency_failure_count=$((dependency_failure_count + 1))
}

assert_dependency_failure_workspace_cleanup() {
	local scenario="$1"
	local scenario_tmpdir="$2"
	local leaked
	leaked="$(find "$scenario_tmpdir" -maxdepth 1 -type d \
		\( -name 'support-copilot-dependencies.*' -o -name 'support-copilot-scans.*' \) -print -quit)"
	[[ -z "$leaked" ]] || record_dependency_failure \
		"$scenario left dependency workspace: ${leaked#$scenario_tmpdir/}"
}

run_dependency_failure_case() {
	local scenario="$1"
	local failure_environment=''
	local output
	local scenario_tmpdir="$fixture_tmpdir/$scenario"
	local status
	reset_python_production_lock
	mkdir -p "$scenario_tmpdir"
	case "$scenario" in
		invalid-sha256)
			printf '\nfixture-invalid-sha256==1.0.0 \\\n    --hash=sha256:not-a-64-hex-digest\n' \
				>>"$fixture_repo/services/support-copilot-ai/requirements.lock.txt"
			;;
		malformed-continuation)
			printf '\n    this-is-not-a-lockfile-continuation\n' \
				>>"$fixture_repo/services/support-copilot-ai/requirements.lock.txt"
			;;
		unexpected-osv-package)
			failure_environment='CI_GATE_ADD_UNEXPECTED_PYTHON_PACKAGE=1'
			;;
		dependency-scanner-failure)
			failure_environment='CI_GATE_FAIL_PYTHON_OSV=1'
			;;
		*) fail "unknown dependency failure scenario: $scenario" ;;
	esac

	set +e
	if [[ -n "$failure_environment" ]]; then
		output="$(env PATH="$shim_dir:$PATH" CI_GATE_COMMAND_LOG="$command_log" TMPDIR="$scenario_tmpdir" \
			"$failure_environment" "$fixture_repo/scripts/verify-ci-gates.sh" --mode release 2>&1)"
	else
		output="$(env PATH="$shim_dir:$PATH" CI_GATE_COMMAND_LOG="$command_log" TMPDIR="$scenario_tmpdir" \
			"$fixture_repo/scripts/verify-ci-gates.sh" --mode release 2>&1)"
	fi
	status=$?
	set -e
	[[ $status -ne 0 ]] || record_dependency_failure \
		"$scenario expected dependency-vulnerabilities to fail with nonzero status"
	grep -q '^\[FAIL\] dependency-vulnerabilities$' <<<"$output" || \
		record_dependency_failure "$scenario missing stable dependency-vulnerabilities failure output"
	assert_dependency_failure_workspace_cleanup "$scenario" "$scenario_tmpdir"
}

for scenario in invalid-sha256 malformed-continuation unexpected-osv-package dependency-scanner-failure; do
	run_dependency_failure_case "$scenario"
done

[[ $dependency_failure_count -eq 0 ]] || exit 1

set +e
failure_output="$(PATH="$shim_dir:$PATH" CI_GATE_COMMAND_LOG="$command_log" CI_GATE_FAIL_FLYWAY=1 \
	"$fixture_repo/scripts/verify-ci-gates.sh" --mode java 2>&1)"
failure_status=$?
set -e
[[ $failure_status -ne 0 ]] || fail "a real failing Java gate did not propagate a nonzero status"
grep -q '^\[FAIL\] java-flyway-contracts$' <<<"$failure_output" || fail "real gate failure output is not stable"

deferred="$("$aggregate" --deferred)"
for capability in 'Docker images/runtime' 'Docker Compose' 'MySQL runtime' 'backup and restore' 'deployment rollback'; do
	grep -q "^\[DEFERRED\].*$capability" <<<"$deferred" || fail "$capability is not explicitly deferred"
done
if grep -q '^\[PASS\].*\(Docker\|Compose\|MySQL\|Testcontainers\|backup\|restore\|rollback\)' <<<"$deferred"; then
	fail "a deferred container capability was reported as PASS"
fi

for workflow in "$repo_root"/.github/workflows/*.yml; do
	configuration="$(grep -E '^[[:space:]]*uses:' "$workflow" | grep -Ev '@[0-9a-f]{40}[[:space:]]*$' || true)"
	[[ -z "$configuration" ]] || fail "workflow action is not SHA-pinned: ${workflow#$repo_root/}"
	grep -q '^permissions:' "$workflow" || fail "workflow permissions are not explicit: ${workflow#$repo_root/}"
	grep -q 'contents: read' "$workflow" || fail "workflow permissions are not least-privileged: ${workflow#$repo_root/}"
	grep -q 'scripts/verify-ci-gates.sh' "$workflow" || fail "workflow bypasses aggregate contract: ${workflow#$repo_root/}"
done

if rg -n 'check-live-rag|docker|compose|mysql|verify-(backup|restore|rollback)' \
	"$repo_root/.github/workflows" "$aggregate"; then
	fail "Task 15 or live behavior leaked into Task 13 execution"
fi

printf 'PASS: Task 13 aggregate behavioral contract\n'

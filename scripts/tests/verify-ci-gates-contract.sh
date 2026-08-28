#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
aggregate="$repo_root/scripts/verify-ci-gates.sh"
fixture_root="$(mktemp -d "${TMPDIR:-/tmp}/support-copilot-ci-contract.XXXXXX")"
fixture_repo="$fixture_root/repo"
shim_dir="$fixture_root/bin"
fallback_shim_dir="$fixture_root/fallback-bin"
bootstrap_bin_dir="$fixture_root/bootstrap-bin"
wrong_tool_dir="$fixture_root/wrong-tools"
command_log="$fixture_root/commands.log"
go_install_log="$fixture_root/go-install.log"
tool_provenance_log="$fixture_root/tool-provenance.log"
fixture_tmpdir="$fixture_root/tmp"
outer_evidence_dir="$fixture_root/outer-evidence"
outer_evidence_sentinel="$outer_evidence_dir/sentinel"
outer_evidence_sentinel_sha=''
scan_capture_root="$fixture_root/captured-scans"
venv_python="$fixture_repo/services/support-copilot-ai/.venv/bin/python"
override_python="$fixture_root/override-python"
concurrent_first_pid=''
concurrent_second_pid=''

cleanup() {
	for pid in "$concurrent_first_pid" "$concurrent_second_pid"; do
		if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
			kill "$pid" 2>/dev/null || true
			wait "$pid" 2>/dev/null || true
		fi
	done
	rm -rf "$fixture_root"
}
trap cleanup EXIT

fail() {
	printf 'FAIL: %s\n' "$*" >&2
	exit 1
}

[[ -x "$aggregate" ]] || fail "aggregate contract is missing or not executable: scripts/verify-ci-gates.sh"

# Fixture invocations must never inherit a release caller's evidence destination.
unset CI_GATE_SCAN_EVIDENCE_DIR

workflow="$repo_root/.github/workflows/release-gates-ci.yml"
/usr/bin/python3 - "$workflow" <<'PY'
import sys
from pathlib import Path

workflow_path = Path(sys.argv[1])
lines = workflow_path.read_text(encoding="utf-8").splitlines()

def find_line(value, start=0):
    for index in range(start, len(lines)):
        if lines[index] == value:
            return index
    raise SystemExit(f"workflow contract: missing line {value!r}")

job_env_starts = [index for index, line in enumerate(lines) if line == "    env:"]
if job_env_starts:
    job_env_start = job_env_starts[0]
    job_env_end = next(
        (index for index in range(job_env_start + 1, len(lines))
         if lines[index] and len(lines[index]) - len(lines[index].lstrip()) <= 4),
        len(lines),
    )
    if any("runner.temp" in line for line in lines[job_env_start + 1:job_env_end]):
        raise SystemExit("workflow contract: runner.temp must not be used in jobs.<job_id>.env")

release_step_start = find_line("      - name: Run non-container release gates")
step_env_start = find_line("        env:", release_step_start)
step_env_end = next(
    (index for index in range(step_env_start + 1, len(lines))
     if lines[index] and len(lines[index]) - len(lines[index].lstrip()) <= 8),
    len(lines),
)
actual = {}
for line in lines[step_env_start + 1:step_env_end]:
    stripped = line.strip()
    if stripped and ":" in stripped:
        key, value = stripped.split(":", 1)
        actual[key] = value.strip()
expected = {
    "TMPDIR": "${{ runner.temp }}",
    "SUPPORT_COPILOT_CI_TOOLS_DIR": "${{ runner.temp }}/support-copilot-ci-tools",
}
if actual != expected:
    raise SystemExit(f"workflow contract: release-step env is {actual!r}, expected {expected!r}")

runner_temp_lines = [
    index for index, line in enumerate(lines)
    if "runner.temp" in line
]
expected_runner_temp_lines = list(range(step_env_start + 1, step_env_end))
if runner_temp_lines != expected_runner_temp_lines:
    raise SystemExit("workflow contract: runner.temp must be scoped only to the release step env")
PY

mkdir -p "$fixture_repo" "$shim_dir" "$fallback_shim_dir" "$bootstrap_bin_dir" \
	"$wrong_tool_dir" "$fixture_tmpdir" \
	"$(dirname "$venv_python")"
git -C "$repo_root" ls-files -z | tar --null -T - -C "$repo_root" -cf - | tar -C "$fixture_repo" -xf -
cp "$repo_root/services/support-copilot-api/gradle.lockfile" \
	"$fixture_repo/services/support-copilot-api/gradle.lockfile"
git -C "$fixture_repo" init -q
git -C "$fixture_repo" add .

cat >"$shim_dir/python" <<'SHIM'
#!/usr/bin/env bash
set -euo pipefail
printf 'path-python %s\n' "$*" >>"$CI_GATE_COMMAND_LOG"
printf 'PATH python intentionally unavailable\n' >&2
exit 88
SHIM

cat >"$shim_dir/python3" <<'SHIM'
#!/usr/bin/env bash
set -euo pipefail
printf 'path-python3 %s\n' "$*" >>"$CI_GATE_COMMAND_LOG"
printf 'PATH python3 intentionally unavailable\n' >&2
exit 89
SHIM

cat >"$venv_python" <<'SHIM'
#!/usr/bin/env bash
set -euo pipefail
printf 'venv-python %s\n' "$*" >>"$CI_GATE_COMMAND_LOG"
if [[ "${1:-}" == "-" ]]; then
	exec /usr/bin/python3 "$@"
fi
SHIM

cat >"$fallback_shim_dir/python3" <<'SHIM'
#!/usr/bin/env bash
set -euo pipefail
printf 'fallback-python3 %s\n' "$*" >>"$CI_GATE_COMMAND_LOG"
if [[ "${1:-}" == "-" ]]; then
	exec /usr/bin/python3 "$@"
fi
SHIM

cat >"$override_python" <<'SHIM'
#!/usr/bin/env bash
set -euo pipefail
printf 'override-python %s\n' "$*" >>"$CI_GATE_COMMAND_LOG"
if [[ "${1:-}" == "-" ]]; then
	exec /usr/bin/python3 "$@"
fi
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

cat >"$bootstrap_bin_dir/go" <<'SHIM'
#!/usr/bin/env bash
set -euo pipefail
if [[ -n "${CI_GATE_FAKE_GO_FAIL_ON_INVOKE:-}" ]]; then
	printf 'UNEXPECTED_GO_INVOCATION %s\n' "$*" >>"$CI_GATE_FAKE_GO_LOG"
	exit 63
fi
if [[ "${1:-}" == "version" ]]; then
	printf 'go version go1.26.4 fixture/amd64\n'
	exit 0
fi
[[ "${1:-}" == "install" && $# -eq 2 ]] || exit 64
{
	printf 'BEGIN_GO_INSTALL\n'
	printf 'module=%s\n' "$2"
	printf 'GOBIN=%s\n' "${GOBIN:-}"
	printf 'GOSUMDB=%s\n' "${GOSUMDB:-}"
	printf 'GOPROXY=%s\n' "${GOPROXY:-}"
	printf 'GOPRIVATE=%s\n' "${GOPRIVATE:-}"
	printf 'GONOPROXY=%s\n' "${GONOPROXY:-}"
	printf 'GONOSUMDB=%s\n' "${GONOSUMDB:-}"
	printf 'GOINSECURE=%s\n' "${GOINSECURE:-}"
	printf 'GOFLAGS=%s\n' "${GOFLAGS:-}"
	printf 'END_GO_INSTALL\n'
} >>"$CI_GATE_FAKE_GO_LOG"
[[ -n "${GOBIN:-}" ]] || exit 65
if [[ "${CI_GATE_FAKE_GO_FAIL_MODULE:-}" == "$2" ]]; then
	exit 71
fi
case "$2" in
	github.com/rhysd/actionlint/cmd/actionlint@v1.7.7) binary=actionlint ;;
	github.com/google/osv-scanner/v2/cmd/osv-scanner@v2.2.4) binary=osv-scanner ;;
	github.com/gitleaks/gitleaks/v8@v8.30.1) binary=gitleaks ;;
	*) exit 66 ;;
esac
if [[ "$binary" == actionlint && -n "${CI_GATE_FAKE_GO_BARRIER_DIR:-}" ]]; then
	if mkdir "$CI_GATE_FAKE_GO_BARRIER_DIR/first-actionlint" 2>/dev/null; then
		: >"$CI_GATE_FAKE_GO_BARRIER_DIR/ready"
		deadline=$((SECONDS + 5))
		while [[ ! -f "$CI_GATE_FAKE_GO_BARRIER_DIR/release" && $SECONDS -lt $deadline ]]; do
			sleep 0.05
		done
		[[ -f "$CI_GATE_FAKE_GO_BARRIER_DIR/release" ]] || exit 74
	fi
fi
mkdir -p "$GOBIN"
if [[ "${CI_GATE_FAKE_GO_WRONG_BINARY:-}" == "$binary" ]]; then
	printf '#!/usr/bin/env bash\nprintf "fixture wrong version 0.0.0\\n"\n' >"$GOBIN/$binary"
else
	cp "$CI_GATE_FAKE_GO_TEMPLATE_DIR/$binary" "$GOBIN/$binary"
fi
chmod +x "$GOBIN/$binary"
SHIM

cat >"$bootstrap_bin_dir/mkdir" <<'SHIM'
#!/usr/bin/env bash
set -euo pipefail
if [[ -n "${CI_GATE_MKDIR_OBSERVE_LOCK:-}" ]]; then
	for argument in "$@"; do
		if [[ "$argument" == "$CI_GATE_MKDIR_OBSERVE_LOCK" ]]; then
			: >"$CI_GATE_CONCURRENT_SECOND_LOCK_ATTEMPT"
		fi
	done
fi
exec /bin/mkdir "$@"
SHIM

for command_name in java rg; do
	command_path="$(command -v "$command_name")"
	ln -s "$command_path" "$bootstrap_bin_dir/$command_name"
done

for tool_name in actionlint osv-scanner gitleaks; do
	cat >"$wrong_tool_dir/$tool_name" <<'SHIM'
#!/usr/bin/env bash
printf 'fixture wrong version 0.0.0\n'
SHIM
done
ln -s "$bootstrap_bin_dir/go" "$wrong_tool_dir/go"
ln -s "$bootstrap_bin_dir/java" "$wrong_tool_dir/java"
ln -s "$bootstrap_bin_dir/rg" "$wrong_tool_dir/rg"

cat >"$shim_dir/actionlint" <<'SHIM'
#!/usr/bin/env bash
set -euo pipefail
if [[ -n "${CI_GATE_TOOL_PROVENANCE_LOG:-}" ]]; then
	printf 'actionlint=%s\n' "$0" >>"$CI_GATE_TOOL_PROVENANCE_LOG"
fi
if [[ "${1:-}" == "-version" ]]; then
	printf 'actionlint 1.7.7\n'
	exit 0
fi
printf 'actionlint %s\n' "$*" >>"$CI_GATE_COMMAND_LOG"
SHIM

cat >"$shim_dir/gitleaks" <<'SHIM'
#!/usr/bin/env bash
set -euo pipefail
if [[ -n "${CI_GATE_TOOL_PROVENANCE_LOG:-}" ]]; then
	printf 'gitleaks=%s\n' "$0" >>"$CI_GATE_TOOL_PROVENANCE_LOG"
fi
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
if [[ -n "${CI_GATE_TOOL_PROVENANCE_LOG:-}" ]]; then
	printf 'osv-scanner=%s\n' "$0" >>"$CI_GATE_TOOL_PROVENANCE_LOG"
fi
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
		--output-file=*)
			printf 'flag provided but not defined: -output-file\n' >&2
			exit 127
			;;
		--lockfile=*) lockfile="${argument#--lockfile=}" ;;
	esac
done
[[ -n "$output" && -n "$lockfile" ]] || exit 64
inventory_path="${lockfile#*:}"
capture_fixture_scan() {
	[[ -n "${CI_GATE_OSV_CAPTURE_DIR:-}" ]] || return 0
	local label="${output##*/}"
	label="${label%-report.json}"
	mkdir -p "$CI_GATE_OSV_CAPTURE_DIR"
	cp "$inventory_path" "$CI_GATE_OSV_CAPTURE_DIR/$label.inventory"
	cp "$output" "$CI_GATE_OSV_CAPTURE_DIR/$label.report"
}
if [[ "${CI_GATE_OSV_OPERATIONAL_FAILURE:-}" == 1 && "$lockfile" == "osv-scanner:"*"python-production-osv.json" ]]; then
	printf '{"fixture":"operational"}\n' >"$output"
	capture_fixture_scan
	printf 'fixture-osv-operational-failure\n' >&2
	exit 129
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
            "vulnerabilities": (
                [{"id": "FIXTURE-OSV-1"}]
                if (
                    __import__("os").environ.get("CI_GATE_OSV_VULNERABILITY") == "1"
                    and lock_type == "osv-scanner"
                    and inventory.name == "python-production-osv.json"
                    and index == 0
                )
                else []
            ),
        } for index, (name, version, ecosystem) in enumerate(packages)],
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
capture_fixture_scan
if [[ "${CI_GATE_OSV_VULNERABILITY:-}" == 1 && "$lockfile" == "osv-scanner:"*"python-production-osv.json" ]]; then
	printf 'fixture-osv-vulnerability-exit-one\n' >&2
	exit 1
fi
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

chmod +x "$shim_dir"/* "$fallback_shim_dir"/* "$bootstrap_bin_dir/go" \
	"$bootstrap_bin_dir/mkdir" \
	"$wrong_tool_dir"/* "$venv_python" "$override_python" \
	"$fixture_repo/services/support-copilot-api/gradlew" \
	"$fixture_repo/scripts/tests/verify-ci-gates-contract.sh"

mkdir -p "$fixture_root/scans" "$scan_capture_root" "$outer_evidence_dir"
printf 'outer-evidence-sentinel\n' >"$outer_evidence_sentinel"
outer_evidence_sentinel_sha="$(shasum -a 256 "$outer_evidence_sentinel" | awk '{print $1}')"

run_fixture_mode() {
	local mode="$1"
	local output="$fixture_root/$mode.out"
	local evidence_dir="$fixture_root/scans/$mode"
	local capture_dir="$scan_capture_root/$mode"
	mkdir -p "$evidence_dir" "$capture_dir"
	if ! PATH="$shim_dir:$PATH" CI_GATE_COMMAND_LOG="$command_log" TMPDIR="$fixture_tmpdir" \
		CI_GATE_SCAN_EVIDENCE_DIR="$evidence_dir" CI_GATE_OSV_CAPTURE_DIR="$capture_dir" \
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
	ci-tooling workflow-syntax workflow-contract static-migration-profile static-security \
	dependency-vulnerabilities tracked-secrets; do
	grep -q "^\[RUN\] $gate$" "$all_output" || fail "all mode did not invoke gate: $gate"
	grep -q "^\[PASS\] $gate$" "$all_output" || fail "all mode did not complete gate: $gate"
done

grep -q '^venv-python -m scripts.check_dependency_locks$' "$command_log" || \
	fail "project venv did not run the Python lock gate"
grep -q '^venv-python -m pytest -q$' "$command_log" || \
	fail "project venv did not run the Python test gate"
grep -q '^venv-python -m evaluation.run_mock_evaluation$' "$command_log" || \
	fail "project venv did not run the Python mock evaluation gate"
grep -q '^venv-python - ' "$command_log" || \
	fail "project venv did not run inline Python inventory validation"
if grep -Eq '^path-python(3)? ' "$command_log"; then
	fail "aggregate mixed PATH Python with the selected project venv"
fi
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
if grep -Fq -- '--output-file=' "$command_log"; then
	fail "OSV scanner was invoked with unsupported --output-file"
fi
if grep '^osv-scanner scan source ' "$command_log" | grep -Ev -- '--output=[^[:space:]]+' >/dev/null; then
	fail "OSV scanner invocation omitted a nonempty --output path"
fi
for label in python-production python-development java node; do
	grep -Eq "^\[SCAN\] $label inventory-packages=[1-9][0-9]* scanned-packages=[1-9][0-9]* vulnerabilities=0$" \
		"$all_output" || fail "scan report was not validated against the $label inventory"
done

/usr/bin/python3 - "$fixture_root/scans/all" "$scan_capture_root/all" "$all_output" <<'PY'
import hashlib
import json
import re
import sys
from pathlib import Path

scan_dir = Path(sys.argv[1])
capture_dir = Path(sys.argv[2])
all_output = Path(sys.argv[3]).read_text(encoding="utf-8")
numpy_coordinates = {("numpy", "2.4.6", "PyPI"), ("numpy", "2.5.2", "PyPI")}

for label in ("python-production", "python-development", "java", "node"):
    artifact = scan_dir / label
    inventory_path = artifact / "inventory"
    report_path = artifact / "report"
    provenance_path = artifact / "provenance.json"
    if not all(path.is_file() for path in (inventory_path, report_path, provenance_path)):
        raise SystemExit(f"{label}: clean scan did not atomically persist inventory/report/provenance")
    if inventory_path.read_bytes() != (capture_dir / f"{label}.inventory").read_bytes():
        raise SystemExit(f"{label}: persisted inventory differs from scanner input")
    if report_path.read_bytes() != (capture_dir / f"{label}.report").read_bytes():
        raise SystemExit(f"{label}: persisted report differs from scanner output")
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    if provenance != {
        "schema_version": 1,
        "label": label,
        "lock_type": {
            "python-production": "osv-scanner",
            "python-development": "osv-scanner",
            "java": "gradle.lockfile",
            "node": "package-lock.json",
        }[label],
        "scanner_exit_status": 0,
        "report_present": True,
        "inventory_sha256": hashlib.sha256(inventory_path.read_bytes()).hexdigest(),
        "report_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
    }:
        raise SystemExit(f"{label}: clean scan provenance is not exact")

for label in ("python-production", "python-development"):
    inventory = json.loads((scan_dir / label / "inventory").read_text(encoding="utf-8"))
    report = json.loads((scan_dir / label / "report").read_text(encoding="utf-8"))
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

project_venv="$(dirname "$(dirname "$venv_python")")"
stashed_venv="$fixture_root/project-venv"
fallback_log="$fixture_root/fallback-commands.log"
fallback_output="$fixture_root/fallback.out"
mv "$project_venv" "$stashed_venv"
mkdir -p "$fixture_root/scans/fallback-all"
if ! PATH="$fallback_shim_dir:$shim_dir:$PATH" CI_GATE_COMMAND_LOG="$fallback_log" TMPDIR="$fixture_tmpdir" \
	CI_GATE_SCAN_EVIDENCE_DIR="$fixture_root/scans/fallback-all" \
	"$fixture_repo/scripts/verify-ci-gates.sh" --mode all >"$fallback_output" 2>&1; then
	cat "$fallback_output" >&2
	fail "all mode failed without a project venv despite python3 fallback"
fi
grep -q '^fallback-python3 -m scripts.check_dependency_locks$' "$fallback_log" || \
	fail "python3 fallback did not run the Python lock gate"
grep -q '^fallback-python3 - ' "$fallback_log" || \
	fail "python3 fallback did not run inline Python inventory validation"
if grep -Eq '^path-python(3)? ' "$fallback_log"; then
	fail "no-venv release mode mixed PATH Python interpreters"
fi
assert_no_dependency_workspaces "no-venv python3 fallback"
mv "$stashed_venv" "$project_venv"

override_log="$fixture_root/override-commands.log"
override_output="$fixture_root/override.out"
mkdir -p "$fixture_root/scans/override-all"
if ! PATH="$shim_dir:$PATH" CI_GATE_COMMAND_LOG="$override_log" TMPDIR="$fixture_tmpdir" \
	CI_GATE_SCAN_EVIDENCE_DIR="$fixture_root/scans/override-all" SUPPORT_COPILOT_CI_PYTHON="$override_python" \
	"$fixture_repo/scripts/verify-ci-gates.sh" --mode all >"$override_output" 2>&1; then
	cat "$override_output" >&2
	fail "all mode failed with an explicit Python override"
fi
grep -q '^override-python -m scripts.check_dependency_locks$' "$override_log" || \
	fail "explicit Python override did not run the Python lock gate"
grep -q '^override-python - ' "$override_log" || \
	fail "explicit Python override did not run inline Python inventory validation"
if grep -Eq '^(path-python(3)?|venv-python|fallback-python3) ' "$override_log"; then
	fail "explicit Python override mixed interpreters"
fi
assert_no_dependency_workspaces "explicit Python override"

invalid_override_output="$fixture_root/invalid-override.out"
if PATH="$shim_dir:$PATH" CI_GATE_COMMAND_LOG="$fixture_root/invalid-override-commands.log" \
	TMPDIR="$fixture_tmpdir" SUPPORT_COPILOT_CI_PYTHON="$fixture_root/missing-python" \
	"$fixture_repo/scripts/verify-ci-gates.sh" --mode python >"$invalid_override_output" 2>&1; then
	fail "an invalid explicit Python override unexpectedly succeeded"
fi
grep -q '^SUPPORT_COPILOT_CI_PYTHON must resolve to an executable:' "$invalid_override_output" || \
	fail "invalid explicit Python override did not fail clearly"

assert_no_tool_staging_dirs() {
	local scenario="$1"
	local tools_dir="$2"
	local leaked=''
	if [[ -d "$tools_dir" ]]; then
		leaked="$(find "$tools_dir" -type d \( -name '*.tmp.*' -o -name '*.partial.*' \) -print -quit)"
	fi
	[[ -z "$leaked" ]] || fail "$scenario left a tool staging directory: $leaked"
}

assert_exact_cached_tools() {
	local scenario="$1"
	local tools_dir="$2"
	local tool_name tool_version version_flag final_bin observed count
	while IFS='|' read -r tool_name tool_version version_flag; do
		final_bin="$tools_dir/$tool_name/$tool_version/$tool_name"
		[[ -x "$final_bin" ]] || fail "$scenario did not leave an executable $tool_name cache binary"
		observed="$("$final_bin" "$version_flag" 2>&1)" || fail "$scenario cached $tool_name binary did not report a version"
		grep -Eq "(^|[^0-9])v?${tool_version//./\\.}([^0-9A-Za-z]|$)" <<<"$observed" || \
			fail "$scenario cached $tool_name binary did not report exact version $tool_version"
		count="$(find "$tools_dir/$tool_name/$tool_version" -maxdepth 1 -type f -name "$tool_name" | wc -l | tr -d ' ')"
		[[ "$count" == 1 ]] || fail "$scenario left $count final $tool_name cache binaries"
	done <<'TOOL_SPECS'
actionlint|1.7.7|-version
osv-scanner|2.2.4|--version
gitleaks|8.30.1|version
TOOL_SPECS
	local leaked_lock
	leaked_lock="$(find "$tools_dir" -type d -name '*.installing' -print -quit)"
	[[ -z "$leaked_lock" ]] || fail "$scenario left a tool installation lock: $leaked_lock"
}

wait_for_path() {
	local expected_path="$1"
	local description="$2"
	local deadline=$((SECONDS + 5))
	while [[ ! -e "$expected_path" && $SECONDS -lt $deadline ]]; do
		sleep 0.05
	done
	[[ -e "$expected_path" ]] || fail "timed out waiting for $description"
}

run_tool_bootstrap() {
	local path_prefix="$1"
	local tools_dir="$2"
	shift 2
	env PATH="$path_prefix:/usr/bin:/bin" CI_GATE_COMMAND_LOG="$command_log" \
		CI_GATE_FAKE_GO_LOG="$go_install_log" CI_GATE_FAKE_GO_TEMPLATE_DIR="$shim_dir" \
		SUPPORT_COPILOT_CI_TOOLS_DIR="$tools_dir" TMPDIR="$fixture_tmpdir" "$@" \
		"$fixture_repo/scripts/verify-ci-gates.sh" --mode release
}

boundary_failure_count=0

record_boundary_failure() {
	printf 'FAIL: %s\n' "$*" >&2
	boundary_failure_count=$((boundary_failure_count + 1))
}

run_rejected_tools_root_case() {
	local scenario="$1"
	local tools_dir="$2"
	shift 2
	local output="$fixture_root/rejected-$scenario.out"
	local status
	set +e
	run_tool_bootstrap "$bootstrap_bin_dir" "$tools_dir" "$@" >"$output" 2>&1
	status=$?
	set -e
	[[ $status -ne 0 ]] || record_boundary_failure "$scenario tools root unexpectedly succeeded"
	grep -q '^CI tools root must be a dedicated descendant of canonical TMPDIR or XDG_CACHE_HOME:' \
		"$output" || record_boundary_failure "$scenario tools root lacked the stable boundary rejection"
}

run_rejected_tools_root_case filesystem-root /
run_rejected_tools_root_case tmp-base "$fixture_tmpdir"

fixture_cache_base="$fixture_root/cache-base"
mkdir -p "$fixture_cache_base"
run_rejected_tools_root_case cache-base "$fixture_cache_base" XDG_CACHE_HOME="$fixture_cache_base"

traversal_target="$fixture_root/traversal-target"
mkdir -p "$traversal_target"
printf 'preserve\n' >"$traversal_target/sentinel"
run_rejected_tools_root_case traversal-escape \
	"$fixture_tmpdir/dedicated/../../traversal-target"
[[ "$(<"$traversal_target/sentinel")" == preserve ]] || \
	record_boundary_failure "traversal escape modified its outside target"

symlink_target="$fixture_root/symlink-target"
mkdir -p "$symlink_target"
printf 'preserve\n' >"$symlink_target/sentinel"
ln -s "$symlink_target" "$fixture_tmpdir/tools-root-link"
run_rejected_tools_root_case symlink-root "$fixture_tmpdir/tools-root-link"
[[ "$(<"$symlink_target/sentinel")" == preserve ]] || \
	record_boundary_failure "symlink root modified its outside target"

ancestor_target="$fixture_root/ancestor-target"
mkdir -p "$ancestor_target"
printf 'preserve\n' >"$ancestor_target/sentinel"
ln -s "$ancestor_target" "$fixture_tmpdir/tools-ancestor-link"
run_rejected_tools_root_case symlink-ancestor "$fixture_tmpdir/tools-ancestor-link/ci-tools"
[[ "$(<"$ancestor_target/sentinel")" == preserve ]] || \
	record_boundary_failure "symlink ancestor modified its outside target"

sibling_cache_base="$fixture_root/canonical-cache"
sibling_tools_dir="$fixture_root/canonical-cache2/tools"
mkdir -p "$sibling_cache_base" "$(dirname "$sibling_tools_dir")"
printf 'preserve\n' >"$(dirname "$sibling_tools_dir")/sentinel"
: >"$go_install_log"
sibling_output="$fixture_root/sibling-prefix.out"
set +e
run_tool_bootstrap "$bootstrap_bin_dir" "$sibling_tools_dir" TMPDIR="$sibling_cache_base" \
	CI_GATE_FAKE_GO_FAIL_ON_INVOKE=1 >"$sibling_output" 2>&1
sibling_status=$?
set -e
[[ $sibling_status -ne 0 ]] || fail "sibling-prefix tools root unexpectedly succeeded"
grep -q '^CI tools root must be a dedicated descendant of canonical TMPDIR or XDG_CACHE_HOME:' \
	"$sibling_output" || fail "sibling-prefix tools root lacked the stable boundary rejection"
[[ ! -e "$sibling_tools_dir" ]] || fail "sibling-prefix rejection created an outside tools artifact"
[[ "$(<"$(dirname "$sibling_tools_dir")/sentinel")" == preserve ]] || \
	fail "sibling-prefix rejection modified its outside cache sibling"
[[ ! -s "$go_install_log" ]] || fail "sibling-prefix rejection invoked fake Go before failing closed"

missing_tools_dir="$fixture_tmpdir/tools path with spaces/missing"
missing_tools_output="$fixture_root/tools-missing.out"
: >"$go_install_log"
if ! run_tool_bootstrap "$bootstrap_bin_dir" "$missing_tools_dir" \
	GOPRIVATE=hostile.private.example GONOPROXY=hostile.noproxy.example \
	GONOSUMDB=hostile.nosumdb.example GOINSECURE=hostile.insecure.example \
	GOFLAGS=-mod=mod GOSUMDB=off GOPROXY=direct \
	>"$missing_tools_output" 2>&1; then
	cat "$missing_tools_output" >&2
	fail "missing tools were not bootstrapped through fake Go"
fi
for module in \
	github.com/rhysd/actionlint/cmd/actionlint@v1.7.7 \
	github.com/google/osv-scanner/v2/cmd/osv-scanner@v2.2.4 \
	github.com/gitleaks/gitleaks/v8@v8.30.1; do
	grep -Fxq "module=$module" "$go_install_log" || fail "exact Go install pin was not used: $module"
done
grep -Eq '^GOBIN=.*/tools path with spaces/missing/actionlint/1\.7\.7/\.actionlint-1\.7\.7\.tmp\.[^/]+$' \
	"$go_install_log" || fail "Go install did not preserve the staged GOBIN containing spaces"
for expected_go_environment in \
	'GOSUMDB=sum.golang.org' \
	'GOPROXY=https://proxy.golang.org,direct' \
	'GOPRIVATE=' \
	'GONOPROXY=' \
	'GONOSUMDB=' \
	'GOINSECURE=' \
	'GOFLAGS='; do
	grep -Fxq "$expected_go_environment" "$go_install_log" || \
		fail "fake Go did not observe exact public install environment: $expected_go_environment"
done
grep -q '^\[RUN\] ci-tooling$' "$missing_tools_output" || fail "ci-tooling gate was not explicit"
grep -q '^\[PASS\] ci-tooling$' "$missing_tools_output" || fail "ci-tooling gate did not pass"
ci_tooling_line="$(grep -n '^\[RUN\] ci-tooling$' "$missing_tools_output" | cut -d: -f1)"
workflow_line="$(grep -n '^\[RUN\] workflow-syntax$' "$missing_tools_output" | cut -d: -f1)"
[[ "$ci_tooling_line" -lt "$workflow_line" ]] || fail "ci-tooling did not precede workflow/scanner gates"
while IFS='|' read -r tool_name tool_version; do
	grep -Fqx "[TOOL] name=$tool_name version=$tool_version source=cache" "$missing_tools_output" || \
		fail "stable cache provenance missing for $tool_name"
done <<'TOOL_SPECS'
actionlint|1.7.7
osv-scanner|2.2.4
gitleaks|8.30.1
TOOL_SPECS
assert_no_tool_staging_dirs "successful missing-tool bootstrap" "$missing_tools_dir"

wrong_tools_dir="$fixture_tmpdir/tools-wrong"
wrong_tools_output="$fixture_root/tools-wrong.out"
wrong_tool_hash_before="$(shasum -a 256 "$wrong_tool_dir/gitleaks")"
if ! run_tool_bootstrap "$wrong_tool_dir" "$wrong_tools_dir" \
	>"$wrong_tools_output" 2>&1; then
	cat "$wrong_tools_output" >&2
	fail "wrong-version PATH tools were not replaced by cache-local exact tools"
fi
wrong_tool_hash_after="$(shasum -a 256 "$wrong_tool_dir/gitleaks")"
[[ "$wrong_tool_hash_before" == "$wrong_tool_hash_after" ]] || fail "unrelated wrong-version PATH binary was overwritten"
assert_no_tool_staging_dirs "successful wrong-version bootstrap" "$wrong_tools_dir"

validation_tools_dir="$fixture_tmpdir/tools-validation-failure"
validation_output="$fixture_root/tools-validation-failure.out"
set +e
run_tool_bootstrap "$bootstrap_bin_dir" "$validation_tools_dir" \
	CI_GATE_FAKE_GO_WRONG_BINARY=actionlint >"$validation_output" 2>&1
validation_status=$?
set -e
[[ $validation_status -ne 0 ]] || fail "wrong-version installed binary unexpectedly passed ci-tooling"
grep -q '^\[FAIL\] ci-tooling$' "$validation_output" || fail "installed version validation failure lacked stable ci-tooling failure"
if grep -q '^\[RUN\] workflow-syntax$' "$validation_output"; then
	fail "workflow/scanner gates ran after installed binary validation failed"
fi
assert_no_tool_staging_dirs "installed version validation failure" "$validation_tools_dir"

install_failure_tools_dir="$fixture_tmpdir/tools path with spaces/install-failure"
install_failure_output="$fixture_root/tools-install-failure.out"
set +e
run_tool_bootstrap "$bootstrap_bin_dir" "$install_failure_tools_dir" \
	CI_GATE_FAKE_GO_FAIL_MODULE=github.com/rhysd/actionlint/cmd/actionlint@v1.7.7 \
	>"$install_failure_output" 2>&1
install_failure_status=$?
set -e
[[ $install_failure_status -ne 0 ]] || fail "fake Go install failure unexpectedly passed"
grep -q '^\[FAIL\] ci-tooling$' "$install_failure_output" || fail "Go install failure lacked stable ci-tooling failure"
if grep -q '^\[RUN\] workflow-syntax$' "$install_failure_output"; then
	fail "workflow/scanner gates ran after Go install failed"
fi
assert_no_tool_staging_dirs "Go install failure" "$install_failure_tools_dir"

path_reuse_bin="$fixture_root/path-reuse-bin"
mkdir -p "$path_reuse_bin"
for command_name in actionlint osv-scanner gitleaks; do
	ln -s "$shim_dir/$command_name" "$path_reuse_bin/$command_name"
done
for command_name in go java rg mkdir; do
	ln -s "$bootstrap_bin_dir/$command_name" "$path_reuse_bin/$command_name"
done
path_reuse_bin_canonical="$(cd -P "$path_reuse_bin" && pwd)"
path_reuse_tools_dir="$fixture_tmpdir/tools-path-reuse"
path_reuse_output="$fixture_root/tools-path-reuse.out"
: >"$go_install_log"
: >"$tool_provenance_log"
if ! run_tool_bootstrap "$path_reuse_bin" "$path_reuse_tools_dir" \
	CI_GATE_FAKE_GO_FAIL_ON_INVOKE=1 CI_GATE_TOOL_PROVENANCE_LOG="$tool_provenance_log" \
	>"$path_reuse_output" 2>&1; then
	cat "$path_reuse_output" >&2
	fail "correct-version PATH tools did not complete release mode without Go"
fi
grep -q '^\[PASS\] ci-tooling$' "$path_reuse_output" || fail "correct-version PATH tools did not pass ci-tooling"
[[ ! -s "$go_install_log" ]] || fail "correct-version PATH reuse invoked fake Go"
while IFS='|' read -r tool_name tool_version; do
	grep -Fqx "[TOOL] name=$tool_name version=$tool_version source=path" "$path_reuse_output" || \
		fail "correct-version PATH reuse lacked path provenance for $tool_name"
	grep -Fqx "$tool_name=$path_reuse_bin_canonical/$tool_name" "$tool_provenance_log" || \
		fail "scanner gate did not invoke the resolved absolute $tool_name executable"
done <<'TOOL_SPECS'
actionlint|1.7.7
osv-scanner|2.2.4
gitleaks|8.30.1
TOOL_SPECS
[[ ! -e "$path_reuse_tools_dir" ]] || fail "correct-version PATH reuse created a cache artifact"

for partial_state in incomplete wrong-version non-executable; do
	partial_tools_dir="$fixture_tmpdir/tools-partial-$partial_state"
	partial_actionlint_dir="$partial_tools_dir/actionlint/1.7.7"
	partial_output="$fixture_root/tools-partial-$partial_state.out"
	mkdir -p "$partial_actionlint_dir"
	case "$partial_state" in
		incomplete)
			printf 'incomplete\n' >"$partial_actionlint_dir/incomplete-download"
			;;
		wrong-version)
			cp "$wrong_tool_dir/actionlint" "$partial_actionlint_dir/actionlint"
			chmod +x "$partial_actionlint_dir/actionlint"
			;;
		non-executable)
			cp "$shim_dir/actionlint" "$partial_actionlint_dir/actionlint"
			chmod 0644 "$partial_actionlint_dir/actionlint"
			;;
	esac
	: >"$go_install_log"
	if ! run_tool_bootstrap "$bootstrap_bin_dir" "$partial_tools_dir" >"$partial_output" 2>&1; then
		cat "$partial_output" >&2
		fail "partial cache state $partial_state did not repair fail-closed"
	fi
	grep -Fq 'module=github.com/rhysd/actionlint/cmd/actionlint@v1.7.7' "$go_install_log" || \
		fail "partial cache state $partial_state accepted its actionlint binary"
	assert_exact_cached_tools "partial cache state $partial_state" "$partial_tools_dir"
	assert_no_tool_staging_dirs "partial cache state $partial_state" "$partial_tools_dir"
done

concurrent_tools_dir="$fixture_tmpdir/tools-concurrent"
concurrent_tools_dir_canonical="$(cd -P "$fixture_tmpdir" && pwd)/tools-concurrent"
concurrent_barrier_dir="$fixture_root/concurrent-barrier"
concurrent_second_lock_attempt="$concurrent_barrier_dir/second-lock-attempt"
concurrent_lock_dir="$concurrent_tools_dir_canonical/actionlint/1.7.7.installing"
concurrent_first_output="$fixture_root/tools-concurrent-first.out"
concurrent_second_output="$fixture_root/tools-concurrent-second.out"
mkdir -p "$concurrent_barrier_dir"
: >"$go_install_log"
env PATH="$bootstrap_bin_dir:/usr/bin:/bin" CI_GATE_COMMAND_LOG="$command_log" \
	CI_GATE_FAKE_GO_LOG="$go_install_log" CI_GATE_FAKE_GO_TEMPLATE_DIR="$shim_dir" \
	SUPPORT_COPILOT_CI_TOOLS_DIR="$concurrent_tools_dir" TMPDIR="$fixture_tmpdir" \
	CI_GATE_FAKE_GO_BARRIER_DIR="$concurrent_barrier_dir" \
	"$fixture_repo/scripts/verify-ci-gates.sh" --mode release >"$concurrent_first_output" 2>&1 &
concurrent_first_pid=$!
wait_for_path "$concurrent_barrier_dir/ready" "the first concurrent fake Go install"
env PATH="$bootstrap_bin_dir:/usr/bin:/bin" CI_GATE_COMMAND_LOG="$command_log" \
	CI_GATE_FAKE_GO_LOG="$go_install_log" CI_GATE_FAKE_GO_TEMPLATE_DIR="$shim_dir" \
	SUPPORT_COPILOT_CI_TOOLS_DIR="$concurrent_tools_dir" TMPDIR="$fixture_tmpdir" \
	CI_GATE_MKDIR_OBSERVE_LOCK="$concurrent_lock_dir" \
	CI_GATE_CONCURRENT_SECOND_LOCK_ATTEMPT="$concurrent_second_lock_attempt" \
	"$fixture_repo/scripts/verify-ci-gates.sh" --mode release >"$concurrent_second_output" 2>&1 &
concurrent_second_pid=$!
wait_for_path "$concurrent_second_lock_attempt" "the second concurrent lock attempt"
: >"$concurrent_barrier_dir/release"
set +e
wait "$concurrent_first_pid"
concurrent_first_status=$?
wait "$concurrent_second_pid"
concurrent_second_status=$?
set -e
concurrent_first_pid=''
concurrent_second_pid=''
[[ $concurrent_first_status -eq 0 ]] || fail "first concurrent release fixture failed"
[[ $concurrent_second_status -eq 0 ]] || fail "second concurrent release fixture failed"
for concurrent_output in "$concurrent_first_output" "$concurrent_second_output"; do
	grep -q '^\[PASS\] ci-tooling$' "$concurrent_output" || fail "concurrent fixture did not pass ci-tooling"
	while IFS='|' read -r tool_name tool_version; do
		grep -Fqx "[TOOL] name=$tool_name version=$tool_version source=cache" "$concurrent_output" || \
			fail "concurrent fixture lacked cache provenance for $tool_name"
	done <<'TOOL_SPECS'
actionlint|1.7.7
osv-scanner|2.2.4
gitleaks|8.30.1
TOOL_SPECS
done
assert_exact_cached_tools "concurrent cache" "$concurrent_tools_dir"
assert_no_tool_staging_dirs "concurrent cache" "$concurrent_tools_dir"

[[ $boundary_failure_count -eq 0 ]] || exit 1

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

assert_persisted_scan_evidence() {
	local scenario="$1"
	local evidence_dir="$2"
	local capture_dir="$3"
	local expected_status="$4"
	local expected_report_present="$5"
	local artifact_dir="$evidence_dir/python-production"
	[[ -f "$artifact_dir/inventory" && -f "$artifact_dir/provenance.json" ]] || \
		record_dependency_failure "$scenario did not retain inventory and provenance"
	cmp -s "$capture_dir/python-production.inventory" "$artifact_dir/inventory" || \
		record_dependency_failure "$scenario did not retain the exact scanner inventory"
	if [[ "$expected_report_present" == true ]]; then
		[[ -f "$artifact_dir/report" ]] || \
			record_dependency_failure "$scenario did not retain the scanner report"
		cmp -s "$capture_dir/python-production.report" "$artifact_dir/report" || \
			record_dependency_failure "$scenario did not retain the exact scanner report"
	else
		[[ ! -e "$artifact_dir/report" ]] || \
			record_dependency_failure "$scenario retained an unexpected report"
	fi
	/usr/bin/python3 - "$artifact_dir/provenance.json" "$expected_status" "$expected_report_present" <<'PY' || \
		record_dependency_failure "$scenario provenance did not retain scanner status/report presence"
import hashlib
import json
import sys
from pathlib import Path

provenance_path = Path(sys.argv[1])
expected_status = int(sys.argv[2])
expected_report_present = sys.argv[3] == "true"
artifact_dir = provenance_path.parent
provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
if provenance["scanner_exit_status"] != expected_status:
    raise SystemExit("unexpected scanner status")
if provenance["report_present"] is not expected_report_present:
    raise SystemExit("unexpected report presence")
if provenance["inventory_sha256"] != hashlib.sha256((artifact_dir / "inventory").read_bytes()).hexdigest():
    raise SystemExit("inventory digest mismatch")
report_path = artifact_dir / "report"
if expected_report_present:
    if provenance["report_sha256"] != hashlib.sha256(report_path.read_bytes()).hexdigest():
        raise SystemExit("report digest mismatch")
elif provenance["report_sha256"] is not None:
    raise SystemExit("unexpected report digest")
PY
}

run_dependency_failure_case() {
	local scenario="$1"
	local failure_environment=''
	local output
	local scenario_tmpdir="$fixture_tmpdir/$scenario"
	local scenario_evidence_dir="$fixture_root/dependency-evidence/$scenario"
	local scenario_capture_dir="$scan_capture_root/$scenario"
	local status
	reset_python_production_lock
	mkdir -p "$scenario_tmpdir" "$scenario_evidence_dir" "$scenario_capture_dir"
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
		operational-scanner-failure)
			failure_environment='CI_GATE_OSV_OPERATIONAL_FAILURE=1'
			;;
		vulnerability-scanner-failure)
			failure_environment='CI_GATE_OSV_VULNERABILITY=1'
			;;
		*) fail "unknown dependency failure scenario: $scenario" ;;
	esac

	set +e
	if [[ -n "$failure_environment" ]]; then
		output="$(env PATH="$shim_dir:$PATH" CI_GATE_COMMAND_LOG="$command_log" TMPDIR="$scenario_tmpdir" \
			CI_GATE_SCAN_EVIDENCE_DIR="$scenario_evidence_dir" CI_GATE_OSV_CAPTURE_DIR="$scenario_capture_dir" \
			"$failure_environment" "$fixture_repo/scripts/verify-ci-gates.sh" --mode release 2>&1)"
	else
		output="$(env PATH="$shim_dir:$PATH" CI_GATE_COMMAND_LOG="$command_log" TMPDIR="$scenario_tmpdir" \
			CI_GATE_SCAN_EVIDENCE_DIR="$scenario_evidence_dir" CI_GATE_OSV_CAPTURE_DIR="$scenario_capture_dir" \
			"$fixture_repo/scripts/verify-ci-gates.sh" --mode release 2>&1)"
	fi
	status=$?
	set -e
	[[ $status -ne 0 ]] || record_dependency_failure \
		"$scenario expected dependency-vulnerabilities to fail with nonzero status"
	grep -q '^\[FAIL\] dependency-vulnerabilities$' <<<"$output" || \
		record_dependency_failure "$scenario missing stable dependency-vulnerabilities failure output"
	case "$scenario" in
		operational-scanner-failure)
			grep -Fq 'fixture-osv-operational-failure' <<<"$output" || \
				record_dependency_failure "$scenario did not preserve scanner stderr"
			grep -Fq 'OSV-Scanner operational error for python-production (exit 129).' <<<"$output" || \
				record_dependency_failure "$scenario did not identify the scanner operational error"
			if grep -q '^\[SCAN\] python-production ' <<<"$output"; then
				record_dependency_failure "$scenario reported a scan success"
			fi
			assert_persisted_scan_evidence "$scenario" "$scenario_evidence_dir" "$scenario_capture_dir" 129 true
			;;
		vulnerability-scanner-failure)
			grep -Fq 'fixture-osv-vulnerability-exit-one' <<<"$output" || \
				record_dependency_failure "$scenario did not preserve scanner stderr"
			grep -Fq 'python-production: OSV report contains 1 vulnerabilities' <<<"$output" || \
				record_dependency_failure "$scenario did not report the deterministic vulnerability count"
			if grep -Fq 'OSV-Scanner failed or found vulnerabilities' <<<"$output" || \
				grep -q '^\[SCAN\] python-production ' <<<"$output"; then
				record_dependency_failure "$scenario emitted a generic error or scan success"
			fi
			assert_persisted_scan_evidence "$scenario" "$scenario_evidence_dir" "$scenario_capture_dir" 1 true
			;;
	esac
	assert_dependency_failure_workspace_cleanup "$scenario" "$scenario_tmpdir"
}

for scenario in invalid-sha256 malformed-continuation unexpected-osv-package operational-scanner-failure vulnerability-scanner-failure; do
	run_dependency_failure_case "$scenario"
done

[[ $dependency_failure_count -eq 0 ]] || exit 1

[[ "$(shasum -a 256 "$outer_evidence_sentinel" | awk '{print $1}')" == "$outer_evidence_sentinel_sha" ]] || \
	fail "nested fixtures modified the outer scan evidence sentinel"
[[ "$(find "$outer_evidence_dir" -type f | wc -l | tr -d ' ')" == 1 ]] || \
	fail "nested fixtures created files in the outer scan evidence directory"

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

release_workflow="$repo_root/.github/workflows/release-gates-ci.yml"
grep -q 'SUPPORT_COPILOT_CI_TOOLS_DIR:' "$release_workflow" || \
	fail "release workflow does not declare the narrow shared tool cache"
grep -Fq 'TMPDIR: ${{ runner.temp }}' "$release_workflow" || \
	fail "release workflow does not align TMPDIR with canonical runner temp"
grep -Fq 'SUPPORT_COPILOT_CI_TOOLS_DIR: ${{ runner.temp }}/support-copilot-ci-tools' "$release_workflow" || \
	fail "release workflow tools root is not a dedicated runner temp descendant"
if grep -q 'go install ' "$release_workflow"; then
	fail "release workflow duplicates raw Go installs instead of relying on the aggregate"
fi

if rg -n 'check-live-rag|docker|compose|mysql|verify-(backup|restore|rollback)' \
	"$repo_root/.github/workflows" "$aggregate"; then
	fail "Task 15 or live behavior leaked into Task 13 execution"
fi

printf 'PASS: Task 13 aggregate behavioral contract\n'

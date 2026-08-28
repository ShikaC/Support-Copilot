#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly ACTIONLINT_VERSION="1.7.7"
readonly OSV_SCANNER_VERSION="2.2.4"
readonly GITLEAKS_VERSION="8.30.1"
readonly GO_VERSION="1.26.4"
readonly ACTIONLINT_MODULE="github.com/rhysd/actionlint/cmd/actionlint@v1.7.7"
readonly OSV_SCANNER_MODULE="github.com/google/osv-scanner/v2/cmd/osv-scanner@v2.2.4"
readonly GITLEAKS_MODULE="github.com/gitleaks/gitleaks/v8@v8.30.1"

actionlint_bin=''
osv_scanner_bin=''
gitleaks_bin=''

usage() {
	printf 'Usage: %s [--mode python|java|react|release|all | --deferred]\n' "$0"
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
  local gate_status
  local errexit_was_enabled=0
  shift
  printf '[RUN] %s\n' "$name"

  case $- in
    *e*) errexit_was_enabled=1 ;;
  esac
  set +e
  (
    set -Eeuo pipefail
    "$@"
  )
  gate_status=$?
  if [[ $errexit_was_enabled -eq 1 ]]; then
    set -e
  fi

  if [[ $gate_status -eq 0 ]]; then
    printf '[PASS] %s\n' "$name"
  else
    printf '[FAIL] %s\n' "$name" >&2
    return "$gate_status"
  fi
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || {
    printf 'Required command is missing: %s\n' "$1" >&2
    return 1
  }
}

absolute_executable() {
	local executable="$1"
	local executable_dir
	executable_dir="$(cd -P "$(dirname "$executable")" && pwd)"
	printf '%s/%s\n' "$executable_dir" "$(basename "$executable")"
}

version_matches() {
	local executable="$1"
	local expected="$2"
	local actual
	shift 2
	[[ -x "$executable" ]] || return 1
	actual="$("$executable" "$@" 2>&1)" || return 1
	grep -Eq "(^|[^0-9])v?${expected//./\\.}([^0-9A-Za-z]|$)" <<<"$actual"
}

canonical_existing_directory() {
	local path="$1"
	[[ "$path" == /* && -d "$path" ]] || return 1
	(cd -P "$path" && pwd)
}

canonical_lexical_path() {
	local path="$1"
	local remaining="${path#/}"
	local component normalized=''
	[[ "$path" == /* ]] || return 1
	while [[ -n "$remaining" ]]; do
		component="${remaining%%/*}"
		if [[ "$remaining" == */* ]]; then
			remaining="${remaining#*/}"
		else
			remaining=''
		fi
		[[ "$component" != . && "$component" != .. ]] || return 1
		[[ -n "$component" ]] || continue
		normalized="$normalized/$component"
	done
	printf '%s\n' "${normalized:-/}"
}

is_symlink_free_descendant() {
	local base="$1"
	local candidate="$2"
	local relative current component
	case "$candidate" in
		"$base"/*) ;;
		*) return 1 ;;
	esac
	relative="${candidate#"$base"/}"
	[[ -n "$relative" ]] || return 1
	current="$base"
	while [[ -n "$relative" ]]; do
		component="${relative%%/*}"
		if [[ "$relative" == */* ]]; then
			relative="${relative#*/}"
		else
			relative=''
		fi
		[[ -n "$component" ]] || continue
		current="$current/$component"
		[[ ! -L "$current" ]] || return 1
		[[ ! -e "$current" || -d "$current" ]] || return 1
	done
}

canonical_descendant_path() {
	local lexical_base="$1"
	local canonical_base="$2"
	local candidate="$3"
	local candidate_parent candidate_name relative_parent=''
	candidate_parent="$(canonical_lexical_path "$(dirname "$candidate")")" || return 1
	candidate_name="$(basename "$candidate")"
	case "$candidate_parent" in
		"$lexical_base") ;;
		"$lexical_base"/*) relative_parent="${candidate_parent#"$lexical_base"/}" ;;
		"$canonical_base") ;;
		"$canonical_base"/*) relative_parent="${candidate_parent#"$canonical_base"/}" ;;
		*) return 1 ;;
	esac
	if [[ -n "$relative_parent" ]]; then
		printf '%s/%s/%s\n' "$canonical_base" "$relative_parent" "$candidate_name"
	else
		printf '%s/%s\n' "$canonical_base" "$candidate_name"
	fi
}

ci_tools_root() {
	local tmp_lexical_base tmp_base xdg_lexical_base='' xdg_base='' candidate matched_base=''
	tmp_lexical_base="$(canonical_lexical_path "${TMPDIR:-/tmp}")" || {
		printf 'TMPDIR must resolve to an existing absolute directory.\n' >&2
		return 1
	}
	tmp_base="$(canonical_existing_directory "$tmp_lexical_base")" || {
		printf 'TMPDIR must resolve to an existing absolute directory.\n' >&2
		return 1
	}
	if [[ -n "${XDG_CACHE_HOME:-}" ]]; then
		xdg_lexical_base="$(canonical_lexical_path "$XDG_CACHE_HOME")" || {
			printf 'XDG_CACHE_HOME must resolve to an existing absolute directory.\n' >&2
			return 1
		}
		xdg_base="$(canonical_existing_directory "$xdg_lexical_base")" || {
			printf 'XDG_CACHE_HOME must resolve to an existing absolute directory.\n' >&2
			return 1
		}
	fi
	candidate="${SUPPORT_COPILOT_CI_TOOLS_DIR:-$tmp_base/support-copilot/ci-tools}"
	if ! candidate="$(canonical_lexical_path "$candidate")"; then
		printf 'CI tools root must be a dedicated descendant of canonical TMPDIR or XDG_CACHE_HOME: %q\n' \
			"$candidate" >&2
		return 1
	fi
	if candidate="$(canonical_descendant_path "$tmp_lexical_base" "$tmp_base" "$candidate")" && \
		is_symlink_free_descendant "$tmp_base" "$candidate"; then
		matched_base="$tmp_base"
	elif [[ -n "$xdg_base" ]] && \
		candidate="$(canonical_descendant_path "$xdg_lexical_base" "$xdg_base" "$candidate")" && \
		is_symlink_free_descendant "$xdg_base" "$candidate"; then
		matched_base="$xdg_base"
	else
		printf 'CI tools root must be a dedicated descendant of canonical TMPDIR or XDG_CACHE_HOME: %q\n' \
			"$candidate" >&2
		return 1
	fi
	printf '[TOOL] cache-root=%q base=%q\n' "$candidate" "$matched_base" >&2
	printf '%s\n' "$candidate"
}

cleanup_ci_tool_staging() {
	local staging_dir="$1"
	local tool_dir="$2"
	local name="$3"
	local expected="$4"
	local staging_parent tool_dir_canonical staging_name
	[[ -d "$staging_dir" && ! -L "$staging_dir" ]] || return 1
	staging_parent="$(canonical_existing_directory "$(dirname "$staging_dir")")" || return 1
	tool_dir_canonical="$(canonical_existing_directory "$tool_dir")" || return 1
	staging_name="$(basename "$staging_dir")"
	[[ "$staging_parent" == "$tool_dir_canonical" ]] || return 1
	case "$staging_name" in
		".${name}-${expected}.tmp."*) ;;
		*) return 1 ;;
	esac
	[[ ! -e "$staging_dir/$name" || -f "$staging_dir/$name" ]] || return 1
	rm -f -- "$staging_dir/$name"
	rmdir -- "$staging_dir"
}

install_ci_tool() {
	local name="$1"
	local expected="$2"
	local module="$3"
	shift 3
	local tools_root tool_dir final_bin lock_dir staging_dir go_bin lock_deadline lock_acquired=0
	tools_root="$(ci_tools_root)" || return 1
	tool_dir="$tools_root/$name/$expected"
	final_bin="$tool_dir/$name"
	lock_dir="$tool_dir.installing"
	is_symlink_free_descendant "$tools_root" "$tool_dir" || {
		printf 'CI tool cache contains a symlink or non-directory ancestor: %s\n' "$tool_dir" >&2
		return 1
	}

	if version_matches "$final_bin" "$expected" "$@"; then
		absolute_executable "$final_bin"
		return
	fi

	go_bin="$(command -v go || true)"
	[[ -n "$go_bin" ]] || {
		printf 'Go %s is required to install %s %s.\n' "$GO_VERSION" "$name" "$expected" >&2
		return 1
	}
	go_bin="$(absolute_executable "$go_bin")"
	version_matches "$go_bin" "$GO_VERSION" version || {
		printf 'Expected Go %s for CI tool installation.\n' "$GO_VERSION" >&2
		return 1
	}

	mkdir -p "$tool_dir"
	if mkdir "$lock_dir" 2>/dev/null; then
		lock_acquired=1
	else
		lock_deadline=$((SECONDS + 5))
		while [[ $SECONDS -lt $lock_deadline ]]; do
			if version_matches "$final_bin" "$expected" "$@"; then
				absolute_executable "$final_bin"
				return
			fi
			if mkdir "$lock_dir" 2>/dev/null; then
				lock_acquired=1
				break
			fi
			sleep 0.05
		done
	fi
	if [[ $lock_acquired -ne 1 ]]; then
		if version_matches "$final_bin" "$expected" "$@"; then
			absolute_executable "$final_bin"
			return
		fi
		printf 'CI tool cache is concurrently installing or partially locked: %s %s\n' \
			"$name" "$expected" >&2
		return 1
	fi

	staging_dir="$(mktemp -d "$tool_dir/.${name}-${expected}.tmp.XXXXXX")" || {
		rmdir "$lock_dir" 2>/dev/null || true
		return 1
	}
	printf '[TOOL] staging name=%s version=%s state=created\n' "$name" "$expected" >&2
	if ! env GOBIN="$staging_dir" GOENV=off GOTOOLCHAIN=local GOFLAGS= \
		GOSUMDB=sum.golang.org GOPROXY=https://proxy.golang.org,direct \
		GONOSUMDB= GOPRIVATE= GONOPROXY= GOINSECURE= \
		"$go_bin" install "$module"; then
		cleanup_ci_tool_staging "$staging_dir" "$tool_dir" "$name" "$expected" || true
		rmdir "$lock_dir" 2>/dev/null || true
		rmdir "$tool_dir" 2>/dev/null || true
		return 1
	fi
	if ! version_matches "$staging_dir/$name" "$expected" "$@"; then
		printf 'Installed %s binary did not match version %s.\n' "$name" "$expected" >&2
		cleanup_ci_tool_staging "$staging_dir" "$tool_dir" "$name" "$expected" || true
		rmdir "$lock_dir" 2>/dev/null || true
		rmdir "$tool_dir" 2>/dev/null || true
		return 1
	fi
	if ! mv -f "$staging_dir/$name" "$final_bin"; then
		cleanup_ci_tool_staging "$staging_dir" "$tool_dir" "$name" "$expected" || true
		rmdir "$lock_dir" 2>/dev/null || true
		rmdir "$tool_dir" 2>/dev/null || true
		return 1
	fi
	cleanup_ci_tool_staging "$staging_dir" "$tool_dir" "$name" "$expected" || return 1
	rmdir "$lock_dir" 2>/dev/null || true
	version_matches "$final_bin" "$expected" "$@" || {
		printf 'Promoted %s binary did not match version %s.\n' "$name" "$expected" >&2
		return 1
	}
	absolute_executable "$final_bin"
}

resolve_ci_tool() {
	local name="$1"
	local expected="$2"
	local module="$3"
	local destination="$4"
	local candidate resolved source
	shift 4
	candidate="$(command -v "$name" || true)"
	if [[ -n "$candidate" ]]; then
		candidate="$(absolute_executable "$candidate")"
	fi
	if [[ -n "$candidate" ]] && version_matches "$candidate" "$expected" "$@"; then
		resolved="$candidate"
		source=path
	else
		resolved="$(install_ci_tool "$name" "$expected" "$module" "$@")" || return 1
		source=cache
	fi
	[[ -x "$resolved" ]] || return 1
	case "$destination" in
		actionlint_bin) actionlint_bin="$resolved" ;;
		osv_scanner_bin) osv_scanner_bin="$resolved" ;;
		gitleaks_bin) gitleaks_bin="$resolved" ;;
		*) return 1 ;;
	esac
	printf '[TOOL] name=%s version=%s source=%s\n' "$name" "$expected" "$source"
}

resolve_ci_tooling() {
	resolve_ci_tool actionlint "$ACTIONLINT_VERSION" "$ACTIONLINT_MODULE" actionlint_bin -version || return
	resolve_ci_tool osv-scanner "$OSV_SCANNER_VERSION" "$OSV_SCANNER_MODULE" osv_scanner_bin --version || return
	resolve_ci_tool gitleaks "$GITLEAKS_VERSION" "$GITLEAKS_MODULE" gitleaks_bin version || return
}

run_ci_tooling_gate() {
	local gate_status
	printf '[RUN] ci-tooling\n'
	if resolve_ci_tooling; then
		printf '[PASS] ci-tooling\n'
		return
	else
		gate_status=$?
	fi
	printf '[FAIL] ci-tooling\n' >&2
	return "$gate_status"
}

ci_python=''

resolve_ci_python() {
  local candidate=''
  local project_venv="$repo_root/services/support-copilot-ai/.venv/bin/python"

  if [[ -n "${SUPPORT_COPILOT_CI_PYTHON:-}" ]]; then
    if [[ "$SUPPORT_COPILOT_CI_PYTHON" == */* ]]; then
      candidate="$SUPPORT_COPILOT_CI_PYTHON"
    else
      candidate="$(command -v "$SUPPORT_COPILOT_CI_PYTHON" || true)"
    fi
    [[ -n "$candidate" && -x "$candidate" ]] || {
      printf 'SUPPORT_COPILOT_CI_PYTHON must resolve to an executable: %s\n' \
        "$SUPPORT_COPILOT_CI_PYTHON" >&2
      return 1
    }
  elif [[ -x "$project_venv" ]]; then
    candidate="$project_venv"
  else
    candidate="$(command -v python3 || true)"
    [[ -n "$candidate" && -x "$candidate" ]] || {
      printf 'Python interpreter unavailable: expected %s or python3 from CI setup.\n' \
        "$project_venv" >&2
      return 1
    }
  fi

  ci_python="$candidate"
}

python_locks() {
  cd "$repo_root/services/support-copilot-ai"
  "$ci_python" -m scripts.check_dependency_locks
}

python_tests() {
  cd "$repo_root/services/support-copilot-ai"
  AI_MODE=mock OPENAI_API_KEY= OPENAI_EMBEDDING_API_KEY= "$ci_python" -m pytest -q
}

python_mock_evaluation() {
  cd "$repo_root/services/support-copilot-ai"
  AI_MODE=mock OPENAI_API_KEY= OPENAI_EMBEDDING_API_KEY= "$ci_python" -m evaluation.run_mock_evaluation
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
  "$actionlint_bin" "$repo_root"/.github/workflows/*.{yml,yaml} 2>/dev/null || \
    "$actionlint_bin" "$repo_root"/.github/workflows/*.yml
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

dependency_vulnerabilities() (
	set -Eeuo pipefail
	require_command java
	local tracked_snapshot=''
	local scan_workspace=''
	local java_project
	local evidence_dir="${CI_GATE_SCAN_EVIDENCE_DIR:-}"
	cleanup_dependency_workspaces() {
		local status=$?
		trap - EXIT
		[[ -z "$tracked_snapshot" ]] || rm -rf -- "$tracked_snapshot"
		[[ -z "$scan_workspace" ]] || rm -rf -- "$scan_workspace"
		return "$status"
	}
	trap cleanup_dependency_workspaces EXIT
	tracked_snapshot="$(mktemp -d "${TMPDIR:-/tmp}/support-copilot-dependencies.XXXXXX")"
	scan_workspace="$(mktemp -d "${TMPDIR:-/tmp}/support-copilot-scans.XXXXXX")"
	git -C "$repo_root" ls-files -z | tar --null -T - -C "$repo_root" -cf - | tar -C "$tracked_snapshot" -xf -
	java_project="$tracked_snapshot/services/support-copilot-api"
	cp "$java_project/gradle.lockfile" "$scan_workspace/committed-gradle.lockfile"
	(
		cd "$java_project"
		./gradlew dependencies --write-locks --no-daemon >/dev/null
	)
	cmp -s "$scan_workspace/committed-gradle.lockfile" "$java_project/gradle.lockfile" || {
		printf 'Generated Java dependency inventory differs from the committed gradle.lockfile.\n' >&2
		return 1
	}

	generate_python_osv_inventory \
		"$tracked_snapshot/services/support-copilot-ai/requirements.lock.txt" \
		"$scan_workspace/python-production-osv.json"
	generate_python_osv_inventory \
		"$tracked_snapshot/services/support-copilot-ai/requirements-dev.lock.txt" \
		"$scan_workspace/python-development-osv.json"
	: >"$scan_workspace/osv-scanner.toml"

	scan_resolved_inventory python-production osv-scanner \
		"$scan_workspace/python-production-osv.json" "$scan_workspace/python-production-report.json" \
		"$scan_workspace/osv-scanner.toml"
	scan_resolved_inventory python-development osv-scanner \
		"$scan_workspace/python-development-osv.json" "$scan_workspace/python-development-report.json" \
		"$scan_workspace/osv-scanner.toml"
	scan_resolved_inventory java gradle.lockfile \
		"$java_project/gradle.lockfile" "$scan_workspace/java-report.json" \
		"$scan_workspace/osv-scanner.toml"
	scan_resolved_inventory node package-lock.json \
		"$tracked_snapshot/apps/support-copilot-web/package-lock.json" "$scan_workspace/node-report.json" \
		"$scan_workspace/osv-scanner.toml"

	if [[ -n "$evidence_dir" ]]; then
		[[ -d "$evidence_dir" ]] || {
			printf 'CI_GATE_SCAN_EVIDENCE_DIR must name an existing directory.\n' >&2
			return 1
		}
		cp "$scan_workspace"/*-osv.json "$scan_workspace"/*-report.json \
			"$scan_workspace/committed-gradle.lockfile" "$evidence_dir/"
		cp "$tracked_snapshot/apps/support-copilot-web/package-lock.json" "$evidence_dir/node-package-lock.json"
	fi
)

generate_python_osv_inventory() {
	local lockfile="$1"
	local inventory="$2"
	"$ci_python" - "$lockfile" "$inventory" <<'PY'
import json
import re
import sys
from pathlib import Path

lock_path = Path(sys.argv[1])
inventory_path = Path(sys.argv[2])
lines = lock_path.read_text(encoding="utf-8").splitlines()
packages = []
current = None
hash_count = 0

def finish_package() -> None:
    global current, hash_count
    if current is not None:
        if hash_count == 0:
            raise SystemExit(f"{lock_path}: {current[0]} has no locked artifact hash")
        packages.append(current)
    current = None
    hash_count = 0

for line_number, line in enumerate(lines, 1):
    if not line.strip() or line.lstrip().startswith("#"):
        continue
    match = re.match(r"^([A-Za-z0-9_.-]+)==([^ ;\\\t]+)(?:[ \t]*;[^\\]*)?[ \t]*\\?$", line)
    if match:
        finish_package()
        current = (match.group(1).lower().replace("_", "-"), match.group(2))
        continue
    if re.match(r"^[ \t]+--hash=sha256:[0-9a-fA-F]{64}[ \t]*\\?$", line):
        if current is None:
            raise SystemExit(f"{lock_path}:{line_number}: hash without a package")
        hash_count += 1
        continue
    raise SystemExit(f"{lock_path}:{line_number}: unsupported lock entry")
finish_package()

if not packages:
    raise SystemExit(f"{lock_path}: no exact packages found")
if len(set(packages)) != len(packages):
    raise SystemExit(f"{lock_path}: duplicate normalized package coordinates are ambiguous")

document = {
    "results": [{
        "source": {"path": str(lock_path), "type": "lockfile"},
        "packages": [{
            "package": {"name": name, "version": version, "ecosystem": "PyPI"}
        } for name, version in packages],
    }]
}
inventory_path.write_text(json.dumps(document, sort_keys=True) + "\n", encoding="utf-8")
PY
}

scan_resolved_inventory() {
	local label="$1"
	local lock_type="$2"
	local inventory="$3"
	local report="$4"
	local config="$5"
	local scan_status
	set +e
	"$osv_scanner_bin" scan source --lockfile="$lock_type:$inventory" --all-packages \
		--format=json --output-file="$report" --config="$config"
	scan_status=$?
	set -e
	[[ -s "$report" ]] || {
		printf 'OSV-Scanner did not produce a report for %s.\n' "$label" >&2
		return 1
	}
	validate_osv_report "$label" "$lock_type" "$inventory" "$report"
	if [[ $scan_status -ne 0 ]]; then
		printf 'OSV-Scanner failed or found vulnerabilities in %s.\n' "$label" >&2
		return 1
	fi
}

validate_osv_report() {
	local label="$1"
	local lock_type="$2"
	local inventory="$3"
	local report="$4"
	"$ci_python" - "$label" "$lock_type" "$inventory" "$report" <<'PY'
import json
import sys
from pathlib import Path

label, lock_type, inventory_name, report_name = sys.argv[1:]
inventory_path = Path(inventory_name)
report_path = Path(report_name)

try:
    report = json.loads(report_path.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError) as error:
    raise SystemExit(f"{label}: invalid OSV JSON report: {error}")

if not isinstance(report, dict) or not isinstance(report.get("results"), list):
    raise SystemExit(f"{label}: OSV report has no results array")

def package_tuple(value: object) -> tuple[str, str, str]:
    if not isinstance(value, dict):
        raise SystemExit(f"{label}: malformed package entry")
    name = value.get("name")
    version = value.get("version")
    ecosystem = value.get("ecosystem")
    if not all(isinstance(item, str) and item for item in (name, version, ecosystem)):
        raise SystemExit(f"{label}: package entry is not exact")
    normalized_name = name.lower().replace("_", "-") if ecosystem == "PyPI" else name
    return normalized_name, version, ecosystem

if lock_type == "osv-scanner":
    try:
        source = json.loads(inventory_path.read_text(encoding="utf-8"))
        source_results = source["results"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as error:
        raise SystemExit(f"{label}: invalid generated inventory: {error}")
    expected = {
        package_tuple(item["package"])
        for result in source_results
        for item in result["packages"]
    }
elif lock_type == "gradle.lockfile":
    expected = set()
    for line in inventory_path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#") or line.startswith("empty="):
            continue
        coordinate = line.split("=", 1)[0].split(":")
        if len(coordinate) != 3 or not all(coordinate):
            raise SystemExit(f"{label}: malformed Gradle lock entry: {line}")
        expected.add((f"{coordinate[0]}:{coordinate[1]}", coordinate[2], "Maven"))
elif lock_type == "package-lock.json":
    try:
        lock = json.loads(inventory_path.read_text(encoding="utf-8"))
        package_entries = lock["packages"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as error:
        raise SystemExit(f"{label}: invalid package-lock inventory: {error}")
    expected = set()
    for path, package in package_entries.items():
        if not path or package.get("link"):
            continue
        name = package.get("name") or path.rsplit("node_modules/", 1)[-1]
        version = package.get("version")
        if not isinstance(name, str) or not isinstance(version, str):
            raise SystemExit(f"{label}: non-exact Node package at {path}")
        expected.add((name, version, "npm"))
else:
    raise SystemExit(f"{label}: unsupported inventory type {lock_type}")

if not expected:
    raise SystemExit(f"{label}: resolved inventory is empty")

scanned = set()
vulnerability_count = 0
for result in report["results"]:
    if not isinstance(result, dict) or not isinstance(result.get("packages"), list):
        raise SystemExit(f"{label}: malformed OSV result entry")
    for item in result["packages"]:
        if not isinstance(item, dict) or "package" not in item:
            raise SystemExit(f"{label}: malformed OSV package result")
        scanned.add(package_tuple(item["package"]))
        vulnerabilities = item.get("vulnerabilities", [])
        if not isinstance(vulnerabilities, list):
            raise SystemExit(f"{label}: malformed vulnerability list")
        vulnerability_count += len(vulnerabilities)

missing = expected - scanned
unexpected = scanned - expected
if missing or unexpected:
    raise SystemExit(
        f"{label}: OSV report tuple mismatch "
        f"missing={len(missing)} unexpected={len(unexpected)}"
    )
if vulnerability_count:
    raise SystemExit(f"{label}: OSV report contains {vulnerability_count} vulnerabilities")

print(
    f"[SCAN] {label} inventory-packages={len(expected)} "
    f"scanned-packages={len(scanned)} vulnerabilities=0"
)
PY
}

tracked_secrets() {
  local tracked_snapshot
  local scan_status=0
  tracked_snapshot="$(mktemp -d "${TMPDIR:-/tmp}/support-copilot-tracked.XXXXXX")"
  trap 'rm -rf "$tracked_snapshot"' RETURN
  git -C "$repo_root" ls-files -z | tar --null -T - -C "$repo_root" -cf - | tar -C "$tracked_snapshot" -xf -
  "$gitleaks_bin" dir "$tracked_snapshot" --no-banner --redact --exit-code 1 || scan_status=$?
  if [[ $scan_status -eq 0 ]]; then
    git -C "$repo_root" log -p --all | "$gitleaks_bin" stdin --no-banner --redact --exit-code 1 || scan_status=$?
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
  run_ci_tooling_gate
  run_gate workflow-syntax workflow_syntax
  run_gate workflow-contract "$repo_root/scripts/tests/verify-ci-gates-contract.sh"
  run_gate static-migration-profile static_migration_profile
  run_gate static-security static_security
  run_gate dependency-vulnerabilities dependency_vulnerabilities
  run_gate tracked-secrets tracked_secrets
}

mode="all"
case "${1:-}" in
	--deferred)
    print_deferred
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
	python|release|all) resolve_ci_python ;;
	java|react) ;;
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

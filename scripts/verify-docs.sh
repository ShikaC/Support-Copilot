#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
mode="${1:---full}"
fixture_root=''

usage() {
	printf 'Usage: %s [--full|--static]\n' "$0"
}

cleanup() {
	local exit_code=$?
	trap - EXIT INT TERM
	if [[ -n "$fixture_root" && -d "$fixture_root" ]]; then
		rm -rf "$fixture_root"
	fi
	exit "$exit_code"
}

run_gate() {
	local name="$1"
	shift
	printf '[RUN] %s\n' "$name"
	"$@"
	printf '[PASS] %s\n' "$name"
}

run_documented_gate() {
	run_gate "$@"
}

run_in_directory() {
	local directory="$1"
	shift
	(cd "$directory" && "$@")
}

resolve_python_311() {
	local candidate
	for candidate in \
		"${SUPPORT_COPILOT_DOCS_PYTHON:-}" \
		"$repo_root/services/support-copilot-ai/.venv/bin/python" \
		"$(command -v python3 || true)"; do
		[[ -n "$candidate" && -x "$candidate" ]] || continue
		if [[ "$("$candidate" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')" == 3.11 ]]; then
			(cd -P "$(dirname "$candidate")" && printf '%s/%s\n' "$PWD" "$(basename "$candidate")")
			return 0
		fi
	done
	printf 'Python 3.11 is required. Set SUPPORT_COPILOT_DOCS_PYTHON to its executable.\n' >&2
	return 1
}

copy_tracked_repository() {
	local destination="$1"
	local source_tree fixture_tree
	mkdir -p "$destination"
	git -C "$repo_root" archive --format=tar HEAD | tar -C "$destination" -xf -
	git -C "$destination" init -q
	git -C "$destination" add .
	git -C "$destination" \
		-c user.name='Support Copilot Docs Verifier' \
		-c user.email='docs-verifier@localhost.invalid' \
		commit -qm 'docs verification fixture'
	source_tree="$(git -C "$repo_root" rev-parse 'HEAD^{tree}')"
	fixture_tree="$(git -C "$destination" rev-parse 'HEAD^{tree}')"
	[[ "$source_tree" == "$fixture_tree" ]] || {
		printf 'Tracked fixture tree does not match source HEAD.\n' >&2
		return 1
	}
	printf 'Tracked fixture matches source tree: %s\n' "$source_tree"
}

install_locked_dependencies() {
	local fixture_repo="$1"
	local bootstrap_python="$2"
	"$bootstrap_python" -m venv "$fixture_repo/services/support-copilot-ai/.venv"
	"$fixture_repo/services/support-copilot-ai/.venv/bin/python" -m pip install \
		--disable-pip-version-check --require-hashes \
		-r "$fixture_repo/services/support-copilot-ai/requirements-dev.lock.txt"
	(cd "$fixture_repo/apps/support-copilot-web" && npm ci)
}

allocate_ports() {
	local python_bin="$1"
	"$python_bin" - <<'PY'
import socket

sockets = []
try:
    for _ in range(3):
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        sockets.append(sock)
    print(" ".join(str(sock.getsockname()[1]) for sock in sockets))
finally:
    for sock in sockets:
        sock.close()
PY
}

assert_ports_released() {
	local python_bin="$1"
	shift
	"$python_bin" - "$@" <<'PY'
import socket
import sys
import time

ports = [int(value) for value in sys.argv[1:]]
deadline = time.monotonic() + 10
while True:
    listening = []
    for port in ports:
        with socket.socket() as sock:
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                listening.append(port)
    if not listening:
        break
    if time.monotonic() >= deadline:
        raise SystemExit(f"smoke ports were not released: {listening}")
    time.sleep(0.1)
print("Smoke cleanup passed: all owned ports were released.")
PY
}

run_static_verification() {
	local fixture_repo="$1"
	local python_bin="$2"
	(cd "$fixture_repo" && "$python_bin" -m pytest -q scripts/tests/test_verify_docs.py)
	(cd "$fixture_repo" && "$python_bin" -m scripts.verify_docs --repo-root "$fixture_repo")
}

run_clean_tests_and_demo() {
	local fixture_repo="$1"
	local python_bin="$fixture_repo/services/support-copilot-ai/.venv/bin/python"
	local ports ai_port java_port web_port

	run_documented_gate verify-python-tests run_in_directory \
		"$fixture_repo/services/support-copilot-ai" "$python_bin" -m pytest -q
	run_documented_gate verify-mock-evaluation run_in_directory \
		"$fixture_repo/services/support-copilot-ai" env AI_MODE=mock \
		"$python_bin" -m evaluation.run_mock_evaluation
	run_documented_gate verify-java-tests run_in_directory \
		"$fixture_repo/services/support-copilot-api" ./gradlew test --no-daemon
	run_documented_gate verify-react-lint run_in_directory \
		"$fixture_repo/apps/support-copilot-web" npm run lint
	run_documented_gate verify-react-tests run_in_directory \
		"$fixture_repo/apps/support-copilot-web" npm test -- --run
	run_documented_gate verify-react-build-budget run_in_directory \
		"$fixture_repo/apps/support-copilot-web" npm run build:budget
	run_documented_gate verify-react-node-contracts run_in_directory \
		"$fixture_repo/apps/support-copilot-web" npm run test:node
	run_documented_gate verify-react-e2e run_in_directory \
		"$fixture_repo/apps/support-copilot-web" npm run test:e2e
	run_documented_gate verify-preflight \
		"$fixture_repo/scripts/check-local-startup.sh" --preflight

	ports="$(allocate_ports "$python_bin")"
	read -r ai_port java_port web_port <<<"$ports"
	run_documented_gate verify-smoke env \
		SUPPORT_COPILOT_SMOKE_AI_PORT="$ai_port" \
		SUPPORT_COPILOT_SMOKE_JAVA_PORT="$java_port" \
		SUPPORT_COPILOT_SMOKE_WEB_PORT="$web_port" \
		"$fixture_repo/scripts/run-local-smoke.sh"
	assert_ports_released "$python_bin" "$ai_port" "$java_port" "$web_port"
}

case "$mode" in
	--full|--static) ;;
	--help|-h)
		usage
		exit 0
		;;
	*)
		usage >&2
		exit 2
		;;
esac

for command_name in git tar java node npm curl; do
	command -v "$command_name" >/dev/null 2>&1 || {
		printf 'Required command is missing: %s\n' "$command_name" >&2
		exit 1
	}
done

bootstrap_python="$(resolve_python_311)"
unset AI_MODE OPENAI_API_KEY OPENAI_EMBEDDING_API_KEY OPENAI_BASE_URL \
	OPENAI_EMBEDDING_BASE_URL OPENAI_CHAT_MODEL OPENAI_CHAT_PROTOCOL \
	OPENAI_EMBEDDING_MODEL
fixture_root="$(mktemp -d "${TMPDIR:-/tmp}/support-copilot-docs.XXXXXX")"
fixture_repo="$fixture_root/repo"
trap cleanup EXIT INT TERM

run_gate tracked-copy copy_tracked_repository "$fixture_repo"

if [[ "$mode" == --full ]]; then
	run_gate locked-dependencies install_locked_dependencies "$fixture_repo" "$bootstrap_python"
	fixture_python="$fixture_repo/services/support-copilot-ai/.venv/bin/python"
else
	fixture_python="$bootstrap_python"
fi

run_gate documentation-contracts run_static_verification "$fixture_repo" "$fixture_python"

if [[ "$mode" == --full ]]; then
	run_gate documented-tests-and-demo run_clean_tests_and_demo "$fixture_repo"
fi

printf '[PASS] release documentation (%s)\n' "${mode#--}"

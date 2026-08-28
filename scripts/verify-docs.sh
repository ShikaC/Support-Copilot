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
	mkdir -p "$destination"
	git -C "$repo_root" ls-files -z | \
		tar --null -T - -C "$repo_root" -cf - | tar -C "$destination" -xf -
	git -C "$destination" init -q
	git -C "$destination" add .
	git -C "$destination" \
		-c user.name='Support Copilot Docs Verifier' \
		-c user.email='docs-verifier@localhost.invalid' \
		commit -qm 'docs verification fixture'
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

for value in sys.argv[1:]:
    with socket.socket() as sock:
        if sock.connect_ex(("127.0.0.1", int(value))) == 0:
            raise SystemExit(f"smoke port was not released: {value}")
print("Smoke cleanup passed: all owned ports were released.")
PY
}

run_static_verification() {
	local fixture_repo="$1"
	local python_bin="$2"
	(cd "$fixture_repo" && "$python_bin" -m pytest -q scripts/tests/test_verify_docs.py)
	"$python_bin" "$fixture_repo/scripts/verify_docs.py" --repo-root "$fixture_repo"
}

run_clean_tests_and_demo() {
	local fixture_repo="$1"
	local python_bin="$fixture_repo/services/support-copilot-ai/.venv/bin/python"
	local ports ai_port java_port web_port

	(cd "$fixture_repo/services/support-copilot-ai" && "$python_bin" -m pytest -q)
	(cd "$fixture_repo/services/support-copilot-ai" && AI_MODE=mock \
		"$python_bin" -m evaluation.run_mock_evaluation)
	(cd "$fixture_repo/services/support-copilot-api" && ./gradlew test --no-daemon)
	(cd "$fixture_repo/apps/support-copilot-web" && npm run lint)
	(cd "$fixture_repo/apps/support-copilot-web" && npm test -- --run)
	(cd "$fixture_repo/apps/support-copilot-web" && npm run build)
	(cd "$fixture_repo/apps/support-copilot-web" && npm run test:node)
	"$fixture_repo/scripts/check-local-startup.sh" --preflight

	ports="$(allocate_ports "$python_bin")"
	read -r ai_port java_port web_port <<<"$ports"
	env \
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
	OPENAI_EMBEDDING_BASE_URL OPENAI_CHAT_MODEL OPENAI_EMBEDDING_MODEL
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

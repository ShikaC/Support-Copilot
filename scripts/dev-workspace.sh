#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
WEB_PORT="${SUPPORT_WORKSPACE_WEB_PORT:-18173}"
API_PORT="${SUPPORT_WORKSPACE_API_PORT:-18080}"
AI_PORT="${SUPPORT_WORKSPACE_AI_PORT:-18000}"
WORKSPACE_AI_MODE="${AI_MODE:-mock}"
[[ "$WORKSPACE_AI_MODE" =~ ^(mock|live)$ ]] || { echo 'AI_MODE must be mock or live for the local workspace.' >&2; exit 1; }
RUNTIME_DIR="$PROJECT_ROOT/.local/workspace"
API_DIR="$PROJECT_ROOT/services/support-copilot-api"
AI_DIR="$PROJECT_ROOT/services/support-copilot-ai"
WEB_DIR="$PROJECT_ROOT/apps/support-copilot-web"
for program in node java curl openssl lsof; do
  command -v "$program" >/dev/null || { echo "Missing required program: $program" >&2; exit 1; }
done
[[ -x "$AI_DIR/.venv/bin/python" ]] || { echo "Install Python dependencies in services/support-copilot-ai/.venv first; see README.md." >&2; exit 1; }
[[ -f "$WEB_DIR/node_modules/vite/bin/vite.js" ]] || { echo "Run npm ci in apps/support-copilot-web first." >&2; exit 1; }
for port in "$WEB_PORT" "$API_PORT" "$AI_PORT"; do
  [[ "$port" =~ ^[0-9]+$ ]] && ((port >= 1024 && port <= 65535)) || { echo "Invalid unprivileged port: $port" >&2; exit 1; }
  if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then echo "Port $port is in use. Set SUPPORT_WORKSPACE_*_PORT to unused ports." >&2; exit 1; fi
done
[[ "$WEB_PORT" != "$API_PORT" && "$WEB_PORT" != "$AI_PORT" && "$API_PORT" != "$AI_PORT" ]] || { echo 'Three distinct ports are required.' >&2; exit 1; }
[[ "${SUPPORT_WORKSPACE_EPHEMERAL:-false}" =~ ^(true|false)$ ]] || { echo 'SUPPORT_WORKSPACE_EPHEMERAL must be true or false.' >&2; exit 1; }
[[ ! -L "$PROJECT_ROOT/.local" && ! -L "$RUNTIME_DIR" && ! -L "$RUNTIME_DIR/data" ]] || { echo 'Workspace data directories must not be symbolic links.' >&2; exit 1; }
mkdir -p "$RUNTIME_DIR/data"
chmod 700 "$RUNTIME_DIR" "$RUNTIME_DIR/data"
DATA_LOCK="$RUNTIME_DIR/.data-operation.lock"
mkdir "$DATA_LOCK" 2>/dev/null || { echo "Workspace data is in use. Stop its launcher or backup/restore operation. If a prior process crashed, inspect $DATA_LOCK before removing the stale directory." >&2; exit 1; }
printf '%s\n' "$$" > "$DATA_LOCK/pid"
children=()
cleanup() {
  trap - EXIT INT TERM
  for child in "${children[@]}"; do kill "$child" 2>/dev/null || true; done
  for child in "${children[@]}"; do wait "$child" 2>/dev/null || true; done
  rm -f "$DATA_LOCK/pid"
  rmdir "$DATA_LOCK"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
export SUPPORT_WORKSPACE_DB_PATH="$RUNTIME_DIR/data/support-copilot"
[[ ! -L "$SUPPORT_WORKSPACE_DB_PATH.mv.db" ]] || { echo 'Database file must not be a symbolic link.' >&2; exit 1; }
if [[ -f "$SUPPORT_WORKSPACE_DB_PATH.mv.db" ]] && lsof -t "$SUPPORT_WORKSPACE_DB_PATH.mv.db" >/dev/null 2>&1; then echo 'Workspace database is open in another process.' >&2; exit 1; fi
PROFILES=demo
STORAGE_LABEL="persistent H2 · $SUPPORT_WORKSPACE_DB_PATH.mv.db"
DATABASE_ARGUMENTS=(--spring.config.additional-location=classpath:workspace-defaults.properties "--spring.datasource.url=jdbc:h2:file:$SUPPORT_WORKSPACE_DB_PATH;MODE=MySQL;DB_CLOSE_ON_EXIT=FALSE" --spring.jpa.hibernate.ddl-auto=validate --spring.flyway.enabled=true)
if [[ "${SUPPORT_WORKSPACE_EPHEMERAL:-false}" == true ]]; then
  PROFILES=demo
  STORAGE_LABEL='ephemeral H2 · data resets on shutdown'
  DATABASE_ARGUMENTS=('--spring.datasource.url=jdbc:h2:mem:supportcopilot-demo;MODE=MySQL;DB_CLOSE_DELAY=-1;DB_CLOSE_ON_EXIT=FALSE' --spring.jpa.hibernate.ddl-auto=create-drop --spring.flyway.enabled=false)
fi
DATABASE_ARGUMENTS+=(--spring.datasource.driver-class-name=org.h2.Driver --spring.datasource.username=sa --spring.datasource.password= --spring.h2.console.enabled=false)
umask 077
(cd "$API_DIR" && ./gradlew bootJar --no-daemon --max-workers=1) > "$RUNTIME_DIR/build.log" 2>&1 || { cat "$RUNTIME_DIR/build.log"; exit 1; }
export SUPPORT_COPILOT_INTERNAL_SERVICE_TOKEN="$(openssl rand -hex 32)"
export AI_MODE="$WORKSPACE_AI_MODE"
export AI_SERVICE_BASE_URL="http://127.0.0.1:$AI_PORT"
export VITE_AUTH_MODE=demo
export VITE_DEV_API_TARGET="http://127.0.0.1:$API_PORT"
# A demo always uses the local proxy, regardless of an inherited frontend API URL.
export VITE_API_BASE_URL=''
(cd "$AI_DIR" && exec .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port "$AI_PORT") > "$RUNTIME_DIR/ai.log" 2>&1 &
children+=("$!")
(cd "$API_DIR" && exec java -jar build/libs/support-copilot-api-0.0.1-SNAPSHOT.jar --spring.profiles.active="$PROFILES" "${DATABASE_ARGUMENTS[@]}" --server.address=127.0.0.1 --server.port="$API_PORT") > "$RUNTIME_DIR/api.log" 2>&1 &
children+=("$!")
(cd "$WEB_DIR" && exec node node_modules/vite/bin/vite.js --host 127.0.0.1 --port "$WEB_PORT" --strictPort) > "$RUNTIME_DIR/web.log" 2>&1 &
children+=("$!")
ready=false
for ((attempt=0; attempt<60; attempt++)); do
  for child in "${children[@]}"; do kill -0 "$child" 2>/dev/null || { echo "A service exited; inspect $RUNTIME_DIR" >&2; exit 1; }; done
  if curl -fsS --max-time 2 "http://127.0.0.1:$API_PORT/actuator/health" >/dev/null 2>&1 && curl -fsS --max-time 2 "http://127.0.0.1:$AI_PORT/health" >/dev/null 2>&1 && curl -fsS --max-time 2 "http://127.0.0.1:$WEB_PORT" >/dev/null 2>&1; then ready=true; break; fi
  sleep 1
done
[[ "$ready" == true ]] || { echo "Startup timeout; inspect $RUNTIME_DIR" >&2; exit 1; }
printf '\nSupport Copilot: http://127.0.0.1:%s\nLocal anonymous workspace · AI mode: %s\nStorage: %s\nLogs: %s\nPress Ctrl+C to stop all three services.\n' "$WEB_PORT" "$AI_MODE" "$STORAGE_LABEL" "$RUNTIME_DIR"
while true; do
  for child in "${children[@]}"; do kill -0 "$child" 2>/dev/null || { echo "A service exited; stopping the workspace." >&2; exit 1; }; done
  sleep 2
done

#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
TEST_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/support-workspace-data-test.XXXXXXXX")"
trap 'rm -rf "$TEST_ROOT"' EXIT
mkdir -p "$TEST_ROOT/scripts" "$TEST_ROOT/.local/workspace/data"
cp "$PROJECT_ROOT/scripts/workspace-data.sh" "$PROJECT_ROOT/scripts/workspace_data.py" "$TEST_ROOT/scripts/"
TOOL="$TEST_ROOT/scripts/workspace-data.sh"
DB="$TEST_ROOT/.local/workspace/data/support-copilot.mv.db"
BACKUPS="$TEST_ROOT/.local/workspace/backups"
reject() {
  if "$@" > "$TEST_ROOT/rejection.log" 2>&1; then echo "Expected refusal: $*" >&2; exit 1; fi
}
reject "$TOOL" backup
printf 'first durable state\n' > "$DB"
FIRST="$("$TOOL" backup)"
[[ -f "$FIRST/SHA256SUMS" ]]
printf 'second durable state\n' > "$DB"
"$TOOL" restore "$FIRST" > "$TEST_ROOT/restore.log"
[[ "$(cat "$DB")" == 'first durable state' ]]
PRESERVED=("$BACKUPS"/before-restore-*/support-copilot.mv.db)
[[ ${#PRESERVED[@]} == 1 && "$(cat "${PRESERVED[0]}")" == 'second durable state' ]]
printf 'tampered backup\n' > "$FIRST/support-copilot.mv.db"
reject "$TOOL" restore "$FIRST"
[[ "$(cat "$DB")" == 'first durable state' ]]
mkdir "$TEST_ROOT/.local/workspace/.data-operation.lock"
reject "$TOOL" backup
reject "$TOOL" restore "$FIRST"
rmdir "$TEST_ROOT/.local/workspace/.data-operation.lock"
exec 3< "$DB"
reject "$TOOL" backup
reject "$TOOL" restore "$FIRST"
exec 3<&-
reject "$TOOL" restore "$TEST_ROOT"
ln -s "$FIRST" "$BACKUPS/symlink"
reject "$TOOL" restore "$BACKUPS/symlink"
SECOND="$("$TOOL" backup)"
rm "$SECOND/support-copilot.mv.db"
ln -s "$DB" "$SECOND/support-copilot.mv.db"
reject "$TOOL" restore "$SECOND"
printf 'invalid digest\n' > "$FIRST/SHA256SUMS"
reject "$TOOL" restore "$FIRST"
[[ "$(cat "$DB")" == 'first durable state' ]]
echo 'PASS: backup/restore, preserved prior data, checksum refusal, runtime lock, open database, outside path, symlink and manifest refusal.'

#!/usr/bin/env bash
set -euo pipefail
umask 077
PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="$PROJECT_ROOT/.local/workspace"
DATA_DIR="$RUNTIME_DIR/data"
DB_FILE="$DATA_DIR/support-copilot.mv.db"
BACKUP_ROOT="$RUNTIME_DIR/backups"
DATA_LOCK="$RUNTIME_DIR/.data-operation.lock"
fail() { echo "$*" >&2; exit 1; }
usage() { echo 'Usage: ./scripts/workspace-data.sh backup | restore <backup-directory>'; }
[[ $# -gt 0 ]] || { usage; exit 1; }
case "$1" in
  backup) [[ $# == 1 ]] || { usage; exit 1; } ;;
  restore) [[ $# == 2 ]] || { usage; exit 1; } ;;
  *) usage; exit 1 ;;
esac
for program in lsof shasum mktemp python3; do command -v "$program" >/dev/null || fail "Missing required program: $program"; done
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' || fail 'Python 3.11 or newer is required for database-safe file operations.'
for directory in "$PROJECT_ROOT/.local" "$RUNTIME_DIR" "$DATA_DIR" "$BACKUP_ROOT"; do
  [[ ! -L "$directory" ]] || fail "Data directories must not be symbolic links: $directory"
done
mkdir -p "$DATA_DIR" "$BACKUP_ROOT"
chmod 700 "$RUNTIME_DIR" "$DATA_DIR" "$BACKUP_ROOT"
mkdir "$DATA_LOCK" 2>/dev/null || fail "Workspace data is in use. Stop the workspace before backup/restore. Inspect $DATA_LOCK manually if a previous process crashed."
printf '%s\n' "$$" > "$DATA_LOCK/pid"
cleanup() {
  rm -f "$DATA_LOCK/pid"
  rmdir "$DATA_LOCK"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
[[ ! -L "$DB_FILE" ]] || fail 'Database file must not be a symbolic link.'
if [[ -e "$DB_FILE" ]]; then
  [[ -f "$DB_FILE" ]] || fail 'Database path is not a regular file.'
  lsof -t "$DB_FILE" >/dev/null 2>&1 && fail 'Database is open in another process. Stop it before backup/restore.'
fi
[[ ! -e "$DATA_DIR/support-copilot.lock.db" ]] || fail 'H2 lock file exists; investigate the owning process before continuing.'

if [[ "$1" == backup ]]; then
  [[ -s "$DB_FILE" ]] || fail 'No persistent workspace database exists yet.'
  python3 "$PROJECT_ROOT/scripts/workspace_data.py" backup "$DB_FILE" "$BACKUP_ROOT"
  exit 0
fi

[[ -d "$2" && ! -L "$2" ]] || fail 'Backup must be a real directory.'
SOURCE="$(cd -- "$2" && pwd -P)"
CANONICAL_BACKUPS="$(cd -- "$BACKUP_ROOT" && pwd -P)"
[[ "${SOURCE%/*}" == "$CANONICAL_BACKUPS" && "${SOURCE##*/}" != .pending-* ]] || fail 'Restore accepts only completed directories directly inside .local/workspace/backups.'
for name in support-copilot.mv.db SHA256SUMS; do
  [[ -f "$SOURCE/$name" && ! -L "$SOURCE/$name" ]] || fail "Backup is missing a regular $name file."
done
MANIFEST="$(cat "$SOURCE/SHA256SUMS")"
[[ "$MANIFEST" =~ ^[a-fA-F0-9]{64}'  support-copilot.mv.db'$ ]] || fail 'Invalid checksum manifest.'
(cd "$SOURCE" && shasum -a 256 -c SHA256SUMS) >/dev/null || fail 'Backup checksum does not match; database was not changed.'
[[ -s "$SOURCE/support-copilot.mv.db" ]] || fail 'Backup database is empty.'
python3 "$PROJECT_ROOT/scripts/workspace_data.py" restore "$DB_FILE" "$SOURCE/support-copilot.mv.db" "${MANIFEST%% *}"

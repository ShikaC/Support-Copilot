#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "INFO: verify-mysql-persistence.sh delegates to the authenticated pilot operations verifier." >&2
exec "$SCRIPT_DIR/verify-pilot-operations.sh" "$@"

#!/usr/bin/env bash
# setup.sh — Bootstrap/select the Python runtime for this skill.
#
# Usage:
#   bash ./setup.sh          # Use existing compatible Python, or create .venv
#   bash ./setup.sh --force  # Recreate .venv if no existing Python is ready

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

BOOTSTRAP_PYTHON="${PYTHON_BOOTSTRAP_BIN:-}"
if [[ -z "$BOOTSTRAP_PYTHON" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    BOOTSTRAP_PYTHON="python3"
  elif command -v python >/dev/null 2>&1; then
    BOOTSTRAP_PYTHON="python"
  else
    echo "ERROR: No Python interpreter found to run bootstrap_runtime.py." >&2
    exit 1
  fi
fi

exec "$BOOTSTRAP_PYTHON" "$SCRIPT_DIR/scripts/bootstrap_runtime.py" "$@"

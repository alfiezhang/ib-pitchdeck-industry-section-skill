#!/usr/bin/env bash
# setup.sh — Create/update the local Python runtime for this skill.
#
# Usage:
#   bash ./setup.sh          # Create/update .venv and install requirements
#   bash ./setup.sh --force  # Recreate .venv before installing
#   bash ./setup.sh --print-python  # Print the selected .venv Python

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
PYTHON_BIN="${PYTHON_BIN:-${PYTHON_BOOTSTRAP_BIN:-}}"
FORCE=0
PRINT_PYTHON=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --force)
      FORCE=1
      shift
      ;;
    --python)
      PYTHON_BIN="${2:-}"
      shift 2
      ;;
    --print-python)
      PRINT_PYTHON=1
      shift
      ;;
    --quiet|--ppt-only)
      shift
      ;;
    *)
      echo "ERROR: unsupported setup option: $1" >&2
      exit 1
      ;;
  esac
done

if [[ -z "$PYTHON_BIN" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
  elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
  else
    echo "ERROR: No Python interpreter found." >&2
    exit 1
  fi
fi

"$PYTHON_BIN" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)' || {
  echo "ERROR: Python 3.9+ is required." >&2
  exit 1
}

if [[ "$FORCE" == "1" && -d "$VENV_DIR" ]]; then
  rm -rf "$VENV_DIR"
fi

if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

"$VENV_DIR/bin/python" -m pip install --quiet --upgrade pip
"$VENV_DIR/bin/python" -m pip install --quiet -r "$SCRIPT_DIR/requirements.txt"

if [[ "$PRINT_PYTHON" == "1" ]]; then
  echo "$VENV_DIR/bin/python"
else
  "$VENV_DIR/bin/python" - <<'PY'
import json, sys
print(json.dumps({"selected_python": sys.executable, "source": "venv"}, ensure_ascii=False, indent=2))
PY
fi

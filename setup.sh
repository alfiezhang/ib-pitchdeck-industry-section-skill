#!/usr/bin/env bash
# setup.sh — Create venv and install all dependencies.
#
# Usage:
#   bash ./setup.sh          # Create .venv and install dependencies
#   bash ./setup.sh --force  # Recreate .venv from scratch

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
PYTHON_BIN="${PYTHON_BIN:-}"

detect_python() {
  if [[ -n "$PYTHON_BIN" ]]; then
    printf '%s\n' "$PYTHON_BIN"
    return 0
  fi

  if command -v python3 >/dev/null 2>&1; then
    printf '%s\n' "python3"
    return 0
  fi

  if command -v python >/dev/null 2>&1; then
    printf '%s\n' "python"
    return 0
  fi

  return 1
}

if [[ "${1:-}" == "--force" && -d "$VENV_DIR" ]]; then
  echo "Removing existing .venv..."
  rm -rf "$VENV_DIR"
fi

if [[ ! -d "$VENV_DIR" ]]; then
  PYTHON_BIN="$(detect_python)" || {
    echo "ERROR: No Python interpreter found. Install Python 3 first." >&2
    exit 1
  }
  "$PYTHON_BIN" -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" || {
    echo "ERROR: $PYTHON_BIN must be Python 3.9 or newer." >&2
    exit 1
  }
  echo "Creating .venv with $PYTHON_BIN..."
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

echo "Installing dependencies..."
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet -r "$SCRIPT_DIR/requirements.txt"

echo ""
echo "=== Setup complete ==="
echo "Python: $("$VENV_DIR/bin/python" --version)"
echo "Location: $VENV_DIR"
echo ""
echo "To activate manually:  source .venv/bin/activate"
echo "Pipeline default:      ./.venv/bin/python"
echo "Override if needed:    ./run_pipeline.sh --python /path/to/python ..."
echo "Recommended setup run: bash ./setup.sh"

#!/usr/bin/env bash
# Fast smoke checks for packaging and entrypoint regressions.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SKILL_DIR="$ROOT_DIR/runtime/ib-pitchdeck-agent-industry-section"
PYTHON_CMD="${PYTHON_CMD:-python3}"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

cd "$SKILL_DIR"

"$PYTHON_CMD" -m compileall -q scripts
bash -n setup.sh
if command -v shellcheck >/dev/null 2>&1; then
  shellcheck setup.sh "$ROOT_DIR/tests/run_smoke_tests.sh"
fi

if "$PYTHON_CMD" scripts/pipeline.py render --run-dir "$TMP_DIR/missing_attempt" >/dev/null 2>"$TMP_DIR/missing_run_dir.err"; then
  echo "pipeline.py render must reject a missing run directory" >&2
  exit 1
fi
if ! grep -q "run directory not found" "$TMP_DIR/missing_run_dir.err"; then
  echo "pipeline.py render rejection should identify the missing run directory" >&2
  exit 1
fi

"$PYTHON_CMD" "$ROOT_DIR/devtools/checks/check_json_files.py" --root . >/dev/null
"$PYTHON_CMD" "$ROOT_DIR/devtools/checks/check_artifact_manifest.py" >/dev/null
"$PYTHON_CMD" "$ROOT_DIR/devtools/checks/check_slide_registry.py" >/dev/null
"$PYTHON_CMD" "$ROOT_DIR/devtools/checks/check_registry_coverage.py" >/dev/null

echo "Smoke tests passed."

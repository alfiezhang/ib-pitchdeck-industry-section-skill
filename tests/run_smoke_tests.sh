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
bash -n run_pipeline.sh setup.sh "$ROOT_DIR/tests/run_contract_tests.sh"
if command -v shellcheck >/dev/null 2>&1; then
  shellcheck run_pipeline.sh setup.sh "$ROOT_DIR/tests/run_contract_tests.sh" "$ROOT_DIR/tests/run_smoke_tests.sh"
fi

if bash run_pipeline.sh --no-research-gate --renderer-spec "$TMP_DIR/missing_renderer_spec.json" >/dev/null 2>"$TMP_DIR/no_research_gate.err"; then
  echo "run_pipeline.sh must reject --no-research-gate without explicit debug authorization" >&2
  exit 1
fi
if ! grep -q "IB_SKILL_ALLOW_PPT_ONLY_DEBUG=1" "$TMP_DIR/no_research_gate.err"; then
  echo "run_pipeline.sh --no-research-gate rejection should explain required debug authorization" >&2
  exit 1
fi

if IB_SKILL_ALLOW_PPT_ONLY_DEBUG=1 bash run_pipeline.sh \
  --no-research-gate \
  --debug-reason "Research completed - generate PPT from validated renderer spec" \
  --renderer-spec "$TMP_DIR/missing_renderer_spec.json" >/dev/null 2>"$TMP_DIR/bad_debug_reason.err"; then
  echo "run_pipeline.sh must reject research/delivery shortcut debug reasons" >&2
  exit 1
fi
if ! grep -q "research/delivery shortcut" "$TMP_DIR/bad_debug_reason.err"; then
  echo "run_pipeline.sh bad debug-reason rejection should explain shortcut semantics" >&2
  exit 1
fi

if IB_SKILL_ALLOW_UNGATED_DEBUG=1 "$PYTHON_CMD" skills/output/scripts/fill_ppt_tokens.py \
  --allow-ungated-debug \
  --template "$TMP_DIR/missing_template.pptx" \
  --replacement-dict "$TMP_DIR/missing_replacement.json" \
  --output "$TMP_DIR/final_looking_name.pptx" >/dev/null 2>"$TMP_DIR/bad_debug_ppt_name.err"; then
  echo "ungated debug PPT output must reject final-looking filenames" >&2
  exit 1
fi
if ! grep -q "DEBUG_NOT_FOR_DELIVERY" "$TMP_DIR/bad_debug_ppt_name.err"; then
  echo "debug PPT filename rejection should mention DEBUG_NOT_FOR_DELIVERY" >&2
  exit 1
fi

"$PYTHON_CMD" skills/qc/scripts/check_json_files.py --root . >/dev/null
"$PYTHON_CMD" skills/qc/scripts/check_artifact_manifest.py >/dev/null
"$PYTHON_CMD" skills/template/scripts/check_slide_registry.py >/dev/null
"$PYTHON_CMD" skills/template/scripts/check_registry_coverage.py >/dev/null
"$PYTHON_CMD" skills/template/scripts/check_template_tokens.py \
  --template assets/industry_section_template_master.pptx \
  --ppt-mapping templates/ppt_mapping.json \
  --fail-on-diff \
  --output "$TMP_DIR/template_token_check.json" >/dev/null

echo "Smoke tests passed."

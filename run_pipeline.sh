#!/usr/bin/env bash
#
# run_pipeline.sh — Run the full fill-ppt script pipeline.
#
# Usage:
#   ./run_pipeline.sh [options] <ppt_copy.json> <storyboard.json>
#   ./run_pipeline.sh [options] --storyboard /path/to/industry_storyboard.json
#
# Options:
#   -o, --output-dir DIR   Output directory (overrides default work-root layout)
#   --ppt-copy FILE        Explicit path to industry_section_ppt_copy.json
#   --storyboard FILE      Explicit path to industry_storyboard.json
#   --work-root DIR        Working directory for default outputs (default: infer from inputs, else cwd)
#   --attempt-name NAME    Attempt name for default output layout; starts/switches active attempt
#   --python PATH          Python interpreter to test first; bootstrap selects one runtime for all scripts
#   --quality-gate         Enable content quality validation as a hard gate (fail on warnings)
#   --no-research-gate     Skip research artifact gate (PPT-only debug runs only)
#   -h, --help             Show this help
#
# Defaults:
#   ppt_copy   = industry_section_ppt_copy.json
#   storyboard = industry_storyboard.json
#
# All outputs are written to the output directory.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ── Parse arguments ──────────────────────────────────────────────
OUTPUT_DIR=""
PPT_COPY=""
STORYBOARD=""
PYTHON_CMD_ARG=""
WORK_ROOT_ARG=""
ATTEMPT_NAME_ARG=""
PPT_COPY_EXPLICIT=0
QUALITY_GATE=0
RESEARCH_GATE=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    -o|--output-dir)
      OUTPUT_DIR="$2"; shift 2 ;;
    --ppt-copy)
      PPT_COPY="$2"; PPT_COPY_EXPLICIT=1; shift 2 ;;
    --storyboard)
      STORYBOARD="$2"; shift 2 ;;
    --work-root)
      WORK_ROOT_ARG="$2"; shift 2 ;;
    --attempt-name)
      ATTEMPT_NAME_ARG="$2"; shift 2 ;;
    --python)
      PYTHON_CMD_ARG="$2"; shift 2 ;;
    --quality-gate)
      QUALITY_GATE=1; shift ;;
    --no-research-gate)
      RESEARCH_GATE=0; shift ;;
    -h|--help)
      sed -n '2,/^$/p' "$0" | sed 's/^# \?//'; exit 0 ;;
    -*)
      echo "Unknown option: $1" >&2; exit 1 ;;
    *)
      if [[ -z "$PPT_COPY" ]]; then
        PPT_COPY="$1"
      elif [[ -z "$STORYBOARD" ]]; then
        STORYBOARD="$1"
      else
        echo "Unexpected argument: $1" >&2; exit 1
      fi
      shift ;;
  esac
done

if [[ -n "$PPT_COPY" && -z "$STORYBOARD" ]]; then
  case "$(basename "$PPT_COPY")" in
    *storyboard*.json)
      STORYBOARD="$PPT_COPY"
      PPT_COPY=""
      PPT_COPY_EXPLICIT=0
      ;;
  esac
fi

PPT_COPY="${PPT_COPY:-industry_section_ppt_copy.json}"
STORYBOARD="${STORYBOARD:-industry_storyboard.json}"

# Resolve one Python interpreter for the whole pipeline. Do not mix system,
# managed, and .venv Python across steps.
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

BOOTSTRAP_ARGS=(--print-python)
if [[ -n "$PYTHON_CMD_ARG" ]]; then
  BOOTSTRAP_ARGS+=(--python "$PYTHON_CMD_ARG")
elif [[ -n "${PYTHON_CMD:-}" ]]; then
  BOOTSTRAP_ARGS+=(--python "$PYTHON_CMD")
fi
if ! PYTHON_CMD="$("$BOOTSTRAP_PYTHON" "$SCRIPT_DIR/scripts/bootstrap_runtime.py" "${BOOTSTRAP_ARGS[@]}")"; then
  echo "ERROR: Runtime bootstrap failed." >&2
  echo "Run 'python3 scripts/bootstrap_runtime.py' for details, or rerun with --python /path/to/python." >&2
  exit 1
fi
echo "[bootstrap] using Python: $PYTHON_CMD"

if [[ ! -f "$STORYBOARD" ]]; then
  echo "ERROR: storyboard file not found: $STORYBOARD" >&2
  exit 1
fi

# Resolve work root from explicit input, input file location, or cwd.
if [[ -n "$WORK_ROOT_ARG" ]]; then
  WORK_ROOT="$WORK_ROOT_ARG"
else
  if [[ -f "$STORYBOARD" ]]; then
    WORK_ROOT="$(cd "$(dirname "$STORYBOARD")" && pwd)"
  elif [[ -f "$PPT_COPY" ]]; then
    WORK_ROOT="$(cd "$(dirname "$PPT_COPY")" && pwd)"
  else
    WORK_ROOT="$(pwd)"
  fi
fi

if [[ -z "$OUTPUT_DIR" ]]; then
  if [[ "$(basename "$WORK_ROOT")" == attempt_* ]]; then
    OUTPUT_DIR="$WORK_ROOT"
  else
    RUNS_DIR="$WORK_ROOT/runs"
    ACTIVE_ATTEMPT_FILE="$RUNS_DIR/ACTIVE_ATTEMPT.txt"
    mkdir -p "$RUNS_DIR"
    if [[ -n "$ATTEMPT_NAME_ARG" ]]; then
      ATTEMPT_NAME="$ATTEMPT_NAME_ARG"
      printf '%s\n' "$ATTEMPT_NAME" > "$ACTIVE_ATTEMPT_FILE"
    elif [[ -f "$ACTIVE_ATTEMPT_FILE" ]] && [[ -n "$(tr -d '[:space:]' < "$ACTIVE_ATTEMPT_FILE")" ]]; then
      ATTEMPT_NAME="$(tr -d '[:space:]' < "$ACTIVE_ATTEMPT_FILE")"
    else
      ATTEMPT_NAME="attempt_$(date +%Y%m%d_%H%M%S)"
      printf '%s\n' "$ATTEMPT_NAME" > "$ACTIVE_ATTEMPT_FILE"
    fi
    OUTPUT_DIR="$RUNS_DIR/${ATTEMPT_NAME}"
  fi
fi

mkdir -p "$OUTPUT_DIR"
OUTPUT_DIR="$(cd "$OUTPUT_DIR" && pwd)"
RUN_ROOT="$(dirname "$OUTPUT_DIR")"

TEMPLATE="assets/industry_section_template_master.pptx"
PPT_MAPPING="templates/ppt_mapping.json"

mkdir -p "$OUTPUT_DIR/artifacts"

# ── Step 0: Stage inputs into the run directory ──────────────────
PPT_COPY_BASENAME="$(basename "$PPT_COPY")"
STORYBOARD_BASENAME="$(basename "$STORYBOARD")"
STAGED_PPT_COPY="$OUTPUT_DIR/$PPT_COPY_BASENAME"
STAGED_STORYBOARD="$OUTPUT_DIR/$STORYBOARD_BASENAME"
AUTO_GENERATED_PPT_COPY=0

stage_file() {
  local src="$1"
  local dest="$2"
  local src_abs dest_abs
  src_abs="$(cd "$(dirname "$src")" && pwd)/$(basename "$src")"
  dest_abs="$(cd "$(dirname "$dest")" && pwd)/$(basename "$dest")"
  if [[ "$src_abs" != "$dest_abs" ]]; then
    cp "$src" "$dest"
  fi
}

require_research_artifact() {
  local src_dir="$1"
  local rel="$2"
  if [[ ! -f "$src_dir/$rel" ]]; then
    echo "ERROR: missing mandatory research artifact before PPT pipeline: $src_dir/$rel" >&2
    echo "Create and validate research_plan.json, write search_log.md, then rerun. Use --no-research-gate only for PPT-only debug runs." >&2
    exit 1
  fi
}

stage_optional_artifact() {
  local src_dir="$1"
  local rel="$2"
  if [[ -f "$src_dir/$rel" ]]; then
    mkdir -p "$OUTPUT_DIR/$(dirname "$rel")"
    stage_file "$src_dir/$rel" "$OUTPUT_DIR/$rel"
  fi
}

stage_optional_artifact_from_any() {
  local rel="$1"
  shift
  local src_dir
  for src_dir in "$@"; do
    if [[ -n "$src_dir" && -f "$src_dir/$rel" ]]; then
      mkdir -p "$OUTPUT_DIR/$(dirname "$rel")"
      stage_file "$src_dir/$rel" "$OUTPUT_DIR/$rel"
      return
    fi
  done
}

stage_file "$STORYBOARD" "$STAGED_STORYBOARD"

INPUT_DIR="$(cd "$(dirname "$STORYBOARD")" && pwd)"
WORK_ROOT_ABS="$(cd "$WORK_ROOT" && pwd)"
if [[ $RESEARCH_GATE -eq 1 ]]; then
  require_research_artifact "$INPUT_DIR" "artifacts/research_plan.json"
  require_research_artifact "$INPUT_DIR" "artifacts/research_plan_validation.json"
  require_research_artifact "$INPUT_DIR" "artifacts/search_log.md"
  require_research_artifact "$INPUT_DIR" "industry_input_memo.md"
fi
stage_optional_artifact_from_any "input_card.json" "$INPUT_DIR" "$WORK_ROOT_ABS"
stage_optional_artifact_from_any "artifacts/input_card_validation.json" "$INPUT_DIR" "$WORK_ROOT_ABS"
stage_optional_artifact "$INPUT_DIR" "artifacts/research_plan.json"
stage_optional_artifact "$INPUT_DIR" "artifacts/research_plan_validation.json"
stage_optional_artifact "$INPUT_DIR" "artifacts/search_log.md"

if [[ $RESEARCH_GATE -eq 1 ]]; then
  echo "[bootstrap] validating formal research plan..."
  "$PYTHON_CMD" "$SCRIPT_DIR/scripts/validate_research_plan.py" \
    --plan "$OUTPUT_DIR/artifacts/research_plan.json" \
    --source-registry "$SCRIPT_DIR/templates/source_registry.json" \
    --stage formal \
    --output "$OUTPUT_DIR/artifacts/research_plan_validation.json"

  echo "[bootstrap] validating research memo..."
  "$PYTHON_CMD" "$SCRIPT_DIR/scripts/validate_memo.py" \
    --memo "$INPUT_DIR/industry_input_memo.md" \
    --run-dir "$INPUT_DIR" \
    --output "$OUTPUT_DIR/artifacts/memo_validation.json"
fi

echo "[bootstrap] validating storyboard contract..."
"$PYTHON_CMD" "$SCRIPT_DIR/scripts/validate_storyboard.py" \
  --storyboard "$STAGED_STORYBOARD" \
  --schema "$SCRIPT_DIR/templates/storyboard_schema.json" \
  --text-fit-rules "$SCRIPT_DIR/templates/text_fit_rules.json" \
  --output "$OUTPUT_DIR/artifacts/storyboard_validation.json"

# ── Step 0b: Content quality validation ──────────────────────────
# Density warnings are advisory; source_warnings are blocking unless
# validate_content_quality.py is run with --allow-source-warnings.
MEMO_FILE=""
for memo_candidate in \
  "$(dirname "$STORYBOARD")/industry_input_memo.md" \
  "$(dirname "$PPT_COPY")/industry_input_memo.md" \
  "$OUTPUT_DIR/industry_input_memo.md"
do
  if [[ -f "$memo_candidate" ]]; then
    MEMO_FILE="$memo_candidate"
    break
  fi
done

echo "[bootstrap] validating content quality..."
QUALITY_ARGS=(
  --storyboard "$STAGED_STORYBOARD"
  --rules "$SCRIPT_DIR/templates/content_quality_rules.json"
  --output "$OUTPUT_DIR/artifacts/content_quality_validation.json"
)
if [[ -n "$MEMO_FILE" ]]; then
  QUALITY_ARGS+=(--memo "$MEMO_FILE")
fi
if [[ $QUALITY_GATE -eq 1 ]]; then
  QUALITY_ARGS+=(--quality-gate)
fi
"$PYTHON_CMD" "$SCRIPT_DIR/scripts/validate_content_quality.py" "${QUALITY_ARGS[@]}"

if [[ -f "$PPT_COPY" ]]; then
  stage_file "$PPT_COPY" "$STAGED_PPT_COPY"
else
  if [[ $PPT_COPY_EXPLICIT -eq 1 ]]; then
    echo "ERROR: explicit ppt_copy file not found: $PPT_COPY" >&2
    exit 1
  fi
  echo "[bootstrap] ppt_copy not found; generating from storyboard..."
  "$PYTHON_CMD" "$SCRIPT_DIR/scripts/convert_storyboard_to_ppt_copy.py" \
    --storyboard "$STAGED_STORYBOARD" \
    --output "$STAGED_PPT_COPY" \
    --strict-content
  AUTO_GENERATED_PPT_COPY=1
fi

for memo_candidate in \
  "$(dirname "$STORYBOARD")/industry_input_memo.md" \
  "$(dirname "$PPT_COPY")/industry_input_memo.md"
do
  if [[ -f "$memo_candidate" ]]; then
    stage_file "$memo_candidate" "$OUTPUT_DIR/industry_input_memo.md"
    break
  fi
done

echo "=== IB Industry Section PPT Pipeline ==="
if [[ $AUTO_GENERATED_PPT_COPY -eq 1 ]]; then
  echo "PPT copy:    $STAGED_PPT_COPY (auto-generated from storyboard)"
else
  echo "PPT copy:    $PPT_COPY"
fi
echo "Storyboard:  $STORYBOARD"
echo "Work root:   $WORK_ROOT"
echo "Run root:    $RUN_ROOT"
echo "Output dir:  $OUTPUT_DIR"
echo "Python:      $PYTHON_CMD"
echo ""

# ── Step 1: Check template tokens ────────────────────────────────
echo "[1/7] Checking template tokens..."
"$PYTHON_CMD" "$SCRIPT_DIR/scripts/check_template_tokens.py" \
  --template "$TEMPLATE" \
  --ppt-mapping "$PPT_MAPPING" \
  --output "$OUTPUT_DIR/artifacts/template_token_check.json" \
  --fail-on-diff

# ── Step 2: Generate replacement dictionary ──────────────────────
echo "[2/7] Generating replacement dictionary..."
"$PYTHON_CMD" "$SCRIPT_DIR/scripts/generate_replacement_dict.py" \
  --ppt-copy "$STAGED_PPT_COPY" \
  --ppt-mapping "$PPT_MAPPING" \
  --output "$OUTPUT_DIR/replacement_dict.json"

# ── Step 3: Fill PPT tokens ─────────────────────────────────────
echo "[3/7] Filling PPT tokens..."
"$PYTHON_CMD" "$SCRIPT_DIR/scripts/fill_ppt_tokens.py" \
  --template "$TEMPLATE" \
  --replacement-dict "$OUTPUT_DIR/replacement_dict.json" \
  --output "$OUTPUT_DIR/industry_section_filled.pptx" \
  --log "$OUTPUT_DIR/artifacts/fill_ppt_tokens.log.json"

# ── Step 4: Clean inactive variant slides ────────────────────────
echo "[4/7] Cleaning inactive variant slides..."
"$PYTHON_CMD" "$SCRIPT_DIR/scripts/clean_filled_ppt.py" \
  --input "$OUTPUT_DIR/industry_section_filled.pptx" \
  --control-file "$STAGED_STORYBOARD" \
  --output "$OUTPUT_DIR/industry_section_filled_clean.pptx" \
  --log "$OUTPUT_DIR/artifacts/clean_filled_ppt.log.json"

# ── Step 5: Post-process visuals ─────────────────────────────────
echo "[5/7] Post-processing visuals..."
"$PYTHON_CMD" "$SCRIPT_DIR/scripts/postprocess_ppt_visuals.py" \
  --input-ppt "$OUTPUT_DIR/industry_section_filled_clean.pptx" \
  --storyboard "$STAGED_STORYBOARD" \
  --output "$OUTPUT_DIR/industry_section_filled_clean.pptx" \
  --render-layouts "$SCRIPT_DIR/templates/render_layouts.json" \
  --log "$OUTPUT_DIR/artifacts/postprocess_ppt_visuals.log.json" \
  --fail-on-unrendered

# ── Step 6: Validate final output ────────────────────────────────
echo "[6/7] Validating filled PPT..."
"$PYTHON_CMD" "$SCRIPT_DIR/scripts/validate_filled_ppt.py" \
  --filled-ppt "$OUTPUT_DIR/industry_section_filled.pptx" \
  --clean-ppt "$OUTPUT_DIR/industry_section_filled_clean.pptx" \
  --control-file "$STAGED_STORYBOARD" \
  --replacement-dict "$OUTPUT_DIR/replacement_dict.json" \
  --ppt-mapping "$PPT_MAPPING" \
  --output "$OUTPUT_DIR/filled_ppt_validation.json" \
  --fail-on-issue

# ── Step 7: Final delivery gate and quality summary ──────────────
echo "[7/7] Running final delivery gate..."
"$PYTHON_CMD" "$SCRIPT_DIR/scripts/validate_final_delivery.py" \
  --run-dir "$OUTPUT_DIR" \
  --source-registry "$SCRIPT_DIR/templates/source_registry.json" \
  --output "$OUTPUT_DIR/artifacts/final_delivery_validation.json"

"$PYTHON_CMD" "$SCRIPT_DIR/scripts/generate_run_quality_summary.py" \
  --run-dir "$OUTPUT_DIR"

if [[ "$(basename "$(dirname "$OUTPUT_DIR")")" == "runs" ]]; then
  printf '%s\n' "$(basename "$OUTPUT_DIR")" > "$(dirname "$OUTPUT_DIR")/ACTIVE_ATTEMPT.txt"
  "$PYTHON_CMD" "$SCRIPT_DIR/scripts/update_runs_index.py" \
    --runs-dir "$(dirname "$OUTPUT_DIR")"
fi

echo "Run directory ready."
echo "Staged inputs:"
echo "  - $STAGED_PPT_COPY"
echo "  - $STAGED_STORYBOARD"
if [[ -f "$OUTPUT_DIR/industry_input_memo.md" ]]; then
  echo "  - $OUTPUT_DIR/industry_input_memo.md"
fi

echo ""
echo "=== Pipeline complete ==="
echo "Output dir:  $OUTPUT_DIR"
echo "Clean PPT:   $OUTPUT_DIR/industry_section_filled_clean.pptx"
echo "Validation:  $OUTPUT_DIR/filled_ppt_validation.json"
echo "Final gate:  $OUTPUT_DIR/artifacts/final_delivery_validation.json"
echo "Quality:     $OUTPUT_DIR/artifacts/run_quality_summary.md"

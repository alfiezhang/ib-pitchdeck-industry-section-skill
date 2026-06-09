#!/usr/bin/env bash
#
# run_pipeline.sh — Run the full fill-ppt script pipeline for an already validated run package.
#
# This is not a brief-to-PPT generator. Starting from a project brief requires
# industry scope pack/search plan, formal_research_execution_report, research pack, issue analysis, deck blueprint,
# compiled page evidence contract, compiled renderer spec,
# content-quality validation, and stage gates before this script is used.
#
# Usage:
#   ./run_pipeline.sh [options] --deck-blueprint /path/to/deck_blueprint.json
#
# Options:
#   -o, --output-dir DIR   Output directory (overrides default work-root layout)
#   --deck-blueprint FILE  Explicit path to deck_blueprint.json for formal runs
#   --renderer-spec FILE   PPT-only debug input; formal runs compile renderer_spec from deck_blueprint
#   --work-root DIR        Working directory for default outputs (default: infer from inputs, else cwd)
#   --case-name NAME       Case/project name for grouping runs under work-root/runs/<case_slug>/
#   --attempt-name NAME    Attempt name for default output layout; starts/switches active attempt
#   --resume-active        Reuse ACTIVE_ATTEMPT.txt for the case; default creates a fresh attempt
#   --new-attempt          Explicitly allow creating a new attempt from an existing attempt package
#   --python PATH          Python interpreter to test first; bootstrap selects one runtime for all scripts
#   --quality-gate         Enable content quality validation as a hard gate (fail on warnings)
#   --no-research-gate     Skip research artifact gate and search-provider bootstrap (PPT-only debug runs only)
#   --debug-reason TEXT    Required with --no-research-gate; must explain the local PPT-only diagnostic purpose
#   -h, --help             Show this help
#
# Default:
#   deck_blueprint = deck_blueprint.json in formal mode; renderer_spec = renderer_spec.json in debug mode
#
# All outputs are written to the output directory.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ── Parse arguments ──────────────────────────────────────────────
OUTPUT_DIR=""
RENDERER_SPEC=""
DECK_BLUEPRINT=""
PYTHON_CMD_ARG=""
WORK_ROOT_ARG=""
CASE_NAME_ARG=""
ATTEMPT_NAME_ARG=""
QUALITY_GATE=0
RESEARCH_GATE=1
RESUME_ACTIVE=0
NEW_ATTEMPT=0
DEBUG_REASON=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    -o|--output-dir)
      OUTPUT_DIR="$2"; shift 2 ;;
    --renderer-spec)
      RENDERER_SPEC="$2"; shift 2 ;;
    --deck-blueprint)
      DECK_BLUEPRINT="$2"; shift 2 ;;
    --work-root)
      WORK_ROOT_ARG="$2"; shift 2 ;;
    --case-name)
      CASE_NAME_ARG="$2"; shift 2 ;;
    --attempt-name)
      ATTEMPT_NAME_ARG="$2"; shift 2 ;;
    --resume-active)
      RESUME_ACTIVE=1; shift ;;
    --new-attempt)
      NEW_ATTEMPT=1; shift ;;
    --python)
      PYTHON_CMD_ARG="$2"; shift 2 ;;
    --quality-gate)
      QUALITY_GATE=1; shift ;;
    --debug-reason|--debug-ppt-only-reason)
      DEBUG_REASON="$2"; shift 2 ;;
    --no-research-gate)
      RESEARCH_GATE=0; shift ;;
    -h|--help)
      sed -n '2,/^$/p' "$0" | sed 's/^# \?//'; exit 0 ;;
    -*)
      echo "Unknown option: $1" >&2; exit 1 ;;
    *)
      if [[ -z "$DECK_BLUEPRINT" && $RESEARCH_GATE -eq 1 ]]; then
        DECK_BLUEPRINT="$1"
      elif [[ -z "$RENDERER_SPEC" ]]; then
        RENDERER_SPEC="$1"
      else
        echo "Unexpected argument: $1" >&2; exit 1
      fi
      shift ;;
  esac
done

if [[ $RESEARCH_GATE -eq 1 ]]; then
  if [[ -n "$RENDERER_SPEC" && -z "$DECK_BLUEPRINT" ]]; then
    cat >&2 <<'EOF'
ERROR: formal runs no longer accept renderer_spec as the authored input.

Write and validate deck_blueprint.json, then rerun with:
  ./run_pipeline.sh --deck-blueprint /path/to/deck_blueprint.json

renderer_spec.json is compiled by scripts/compile_deck_blueprint.py and must not be hand-authored for formal delivery.
EOF
    exit 2
  fi
  DECK_BLUEPRINT="${DECK_BLUEPRINT:-deck_blueprint.json}"
  RENDERER_SPEC="renderer_spec.json"
else
  RENDERER_SPEC="${RENDERER_SPEC:-renderer_spec.json}"
fi

if [[ $RESEARCH_GATE -eq 0 ]]; then
  if [[ "${IB_SKILL_ALLOW_PPT_ONLY_DEBUG:-}" != "1" ]]; then
    cat >&2 <<'EOF'
ERROR: --no-research-gate is disabled by default.

For a user request like "use ib-industry-section-skill to generate PPT from this project brief",
the required path is the formal issue-analysis-driven workflow:
industry_scope_pack/search plan -> formal_research_execution_report -> research pack -> issue_analysis -> deck_blueprint -> compiled page_evidence_contract/renderer_spec -> final delivery gate.

Use --no-research-gate only for local PPT-template/rendering diagnostics, never to satisfy a
research-backed PPT generation request. To run PPT-only diagnostics, explicitly set:
  IB_SKILL_ALLOW_PPT_ONLY_DEBUG=1
and pass:
  --debug-reason "local template/rendering diagnostic: <what you are testing>"
EOF
    exit 2
  fi
  if [[ -z "${DEBUG_REASON//[[:space:]]/}" ]]; then
    cat >&2 <<'EOF'
ERROR: --no-research-gate requires --debug-reason.

The reason must state the local PPT-only diagnostic purpose. A missing reason usually means
the operator is trying to shortcut the research and issue-analysis gates, which is not allowed.
EOF
    exit 2
  fi
  if printf '%s' "$DEBUG_REASON" | grep -Eiq 'research|memo|source|evidence|renderer|formal|delivery|client|generate[[:space:]-]*ppt|generat[[:space:]-]*ppt|validated|completed|研究|备忘录|来源|证据|渲染规格|正式|交付|生成[[:space:]]*ppt|已完成|通过'; then
    cat >&2 <<'EOF'
ERROR: --debug-reason indicates an attempted research/delivery shortcut.

--no-research-gate cannot be used because research, research pack, source, evidence,
renderer spec, schema, or delivery gates are failing. Fix the upstream gate instead.
EOF
    exit 2
  fi
  if ! printf '%s' "$DEBUG_REASON" | grep -Eiq 'template|render|rendering|layout|postprocess|post-processing|token|visual|chart|table|diagnostic|diagnostics|模板|渲染|版式|后处理|占位符|图表|表格|诊断'; then
    cat >&2 <<'EOF'
ERROR: --debug-reason must describe a local template/rendering diagnostic.

Valid examples:
  --debug-reason "local template/rendering diagnostic: chart rendering smoke test"
  --debug-reason "local template/rendering diagnostic: placeholder cleanup test"
EOF
    exit 2
  fi
fi

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

BOOTSTRAP_ARGS=(--print-python --ppt-only)
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

if [[ $RESEARCH_GATE -eq 1 ]]; then
  if [[ ! -f "$DECK_BLUEPRINT" ]]; then
    echo "ERROR: deck blueprint file not found: $DECK_BLUEPRINT" >&2
    exit 1
  fi
else
  if [[ ! -f "$RENDERER_SPEC" ]]; then
    echo "ERROR: renderer spec file not found: $RENDERER_SPEC" >&2
    exit 1
  fi
fi

# Resolve work root from explicit input, input file location, or cwd.
if [[ -n "$WORK_ROOT_ARG" ]]; then
  WORK_ROOT="$WORK_ROOT_ARG"
else
  if [[ $RESEARCH_GATE -eq 1 && -f "$DECK_BLUEPRINT" ]]; then
    WORK_ROOT="$(cd "$(dirname "$DECK_BLUEPRINT")" && pwd)"
  elif [[ -f "$RENDERER_SPEC" ]]; then
    WORK_ROOT="$(cd "$(dirname "$RENDERER_SPEC")" && pwd)"
  else
    WORK_ROOT="$(pwd)"
  fi
fi

WORK_ROOT_ABS_EARLY="$(cd "$WORK_ROOT" && pwd)"
if [[ "$(basename "$WORK_ROOT_ABS_EARLY")" == "runs" && -z "$OUTPUT_DIR" ]]; then
  echo "ERROR: --work-root points to a runs directory: $WORK_ROOT_ABS_EARLY" >&2
  echo "Pass the parent workspace (for example /Users/.../workbuddy), or pass --output-dir for an existing attempt." >&2
  exit 1
fi

if [[ $RESEARCH_GATE -eq 1 ]]; then
  INPUT_ARTIFACT="$DECK_BLUEPRINT"
else
  INPUT_ARTIFACT="$RENDERER_SPEC"
fi
INPUT_ARTIFACT_DIR_ABS="$(cd "$(dirname "$INPUT_ARTIFACT")" && pwd)"
INPUT_ARTIFACT_ABS="$INPUT_ARTIFACT_DIR_ABS/$(basename "$INPUT_ARTIFACT")"
SOURCE_RUN_DIR=""
SOURCE_SCAN_DIR="$INPUT_ARTIFACT_DIR_ABS"
while [[ "$SOURCE_SCAN_DIR" != "/" && -n "$SOURCE_SCAN_DIR" ]]; do
  if [[ "$(basename "$SOURCE_SCAN_DIR")" == attempt_* ]]; then
    SOURCE_RUN_DIR="$SOURCE_SCAN_DIR"
    break
  fi
  SOURCE_SCAN_DIR="$(dirname "$SOURCE_SCAN_DIR")"
done

if [[ -z "$OUTPUT_DIR" ]]; then
  if [[ -n "$SOURCE_RUN_DIR" && $NEW_ATTEMPT -eq 0 && -z "$ATTEMPT_NAME_ARG" ]]; then
    OUTPUT_DIR="$SOURCE_RUN_DIR"
  elif [[ "$(basename "$WORK_ROOT")" == attempt_* ]]; then
    OUTPUT_DIR="$WORK_ROOT"
  else
    INPUT_CARD_FOR_CASE=""
    for input_card_candidate in \
      "$INPUT_ARTIFACT_DIR_ABS/input_card.json" \
      "$WORK_ROOT/input_card.json"
    do
      if [[ -f "$input_card_candidate" ]]; then
        INPUT_CARD_FOR_CASE="$input_card_candidate"
        break
      fi
    done
    CASE_SLUG="$("$PYTHON_CMD" "$SCRIPT_DIR/scripts/resolve_case_slug.py" \
      --case-name "$CASE_NAME_ARG" \
      --input-card "$INPUT_CARD_FOR_CASE" \
      --renderer-spec "$INPUT_ARTIFACT_ABS")"
    RUNS_DIR="$WORK_ROOT/runs/$CASE_SLUG"
    ACTIVE_ATTEMPT_FILE="$RUNS_DIR/ACTIVE_ATTEMPT.txt"
    mkdir -p "$RUNS_DIR"
    if [[ -n "$ATTEMPT_NAME_ARG" ]]; then
      ATTEMPT_NAME="$ATTEMPT_NAME_ARG"
      printf '%s\n' "$ATTEMPT_NAME" > "$ACTIVE_ATTEMPT_FILE"
    elif [[ $RESUME_ACTIVE -eq 1 && -f "$ACTIVE_ATTEMPT_FILE" && -n "$(tr -d '[:space:]' < "$ACTIVE_ATTEMPT_FILE")" ]]; then
      ATTEMPT_NAME="$(tr -d '[:space:]' < "$ACTIVE_ATTEMPT_FILE")"
    else
      ATTEMPT_NAME="attempt_$(date +%Y%m%d_%H%M%S)"
    fi
    OUTPUT_DIR="$RUNS_DIR/${ATTEMPT_NAME}"
  fi
fi

mkdir -p "$OUTPUT_DIR"
OUTPUT_DIR="$(cd "$OUTPUT_DIR" && pwd)"
RUN_ROOT="$(dirname "$OUTPUT_DIR")"
RENDERER_SPEC_ABS="$OUTPUT_DIR/renderer_spec.json"

TEMPLATE="$SCRIPT_DIR/assets/industry_section_template_master.pptx"
PPT_MAPPING="$SCRIPT_DIR/templates/ppt_mapping.json"

mkdir -p "$OUTPUT_DIR/artifacts"
export IB_SKILL_DEBUG_REASON="$DEBUG_REASON"
DEBUG_REASON_JSON="$("$PYTHON_CMD" -c 'import json, os; print(json.dumps(os.environ.get("IB_SKILL_DEBUG_REASON", ""), ensure_ascii=False))')"
RENDERER_SPEC_ABS_JSON="$("$PYTHON_CMD" -c 'import json, sys; print(json.dumps(sys.argv[1], ensure_ascii=False))' "$RENDERER_SPEC_ABS")"
if [[ $RESEARCH_GATE -eq 1 ]]; then
  DECK_BLUEPRINT_ABS_JSON="$("$PYTHON_CMD" -c 'import json, sys; print(json.dumps(sys.argv[1], ensure_ascii=False))' "${INPUT_ARTIFACT_ABS}")"
else
  DECK_BLUEPRINT_ABS_JSON='""'
fi
SOURCE_RUN_DIR_JSON="$("$PYTHON_CMD" -c 'import json, sys; print(json.dumps(sys.argv[1], ensure_ascii=False))' "$SOURCE_RUN_DIR")"
OUTPUT_DIR_JSON="$("$PYTHON_CMD" -c 'import json, sys; print(json.dumps(sys.argv[1], ensure_ascii=False))' "$OUTPUT_DIR")"
PACKAGE_OF_RECORD_JSON="$OUTPUT_DIR_JSON"

cat > "$OUTPUT_DIR/artifacts/run_flags.json" <<EOF
{
  "schema_version": "run_flags_v1",
  "research_gate": $RESEARCH_GATE,
  "issue_analysis_layer": 1,
  "quality_gate": $QUALITY_GATE,
  "resume_active": $RESUME_ACTIVE,
  "new_attempt_explicit": $([[ $NEW_ATTEMPT -eq 1 ]] && echo true || echo false),
  "source_run_dir": $SOURCE_RUN_DIR_JSON,
  "output_run_dir": $OUTPUT_DIR_JSON,
  "package_of_record": $PACKAGE_OF_RECORD_JSON,
  "debug_output_only": $([[ $RESEARCH_GATE -eq 0 ]] && echo true || echo false),
  "debug_reason": $DEBUG_REASON_JSON
}
EOF

cat > "$OUTPUT_DIR/artifacts/run_package.json" <<EOF
{
  "schema_version": "run_package_v1",
  "deck_blueprint": $DECK_BLUEPRINT_ABS_JSON,
  "renderer_spec": $RENDERER_SPEC_ABS_JSON,
  "source_run_dir": $SOURCE_RUN_DIR_JSON,
  "output_run_dir": $OUTPUT_DIR_JSON,
  "package_of_record": $PACKAGE_OF_RECORD_JSON,
  "new_attempt_explicit": $([[ $NEW_ATTEMPT -eq 1 ]] && echo true || echo false)
}
EOF

MAX_REPAIR_CYCLES="${IB_SKILL_MAX_REPAIR_CYCLES:-3}"

check_gate_retry_state() {
  local gate="$1"
  "$PYTHON_CMD" "$SCRIPT_DIR/scripts/gate_retry_state.py" check \
    --run-dir "$OUTPUT_DIR" \
    --gate "$gate" \
    --max-repair-cycles "$MAX_REPAIR_CYCLES" >/dev/null
}

record_gate_retry_state() {
  local gate="$1"
  local result="$2"
  "$PYTHON_CMD" "$SCRIPT_DIR/scripts/gate_retry_state.py" record \
    --run-dir "$OUTPUT_DIR" \
    --gate "$gate" \
    --result "$result" \
    --max-repair-cycles "$MAX_REPAIR_CYCLES" >/dev/null || true
}

run_validation_gate() {
  local gate="$1"
  local result="$2"
  shift 2
  check_gate_retry_state "$gate"
  if "$@"; then
    record_gate_retry_state "$gate" "$result"
  else
    local status=$?
    record_gate_retry_state "$gate" "$result"
    return "$status"
  fi
}

# ── Step 0: Stage inputs into the run directory ──────────────────
STAGED_RENDERER_SPEC="$OUTPUT_DIR/renderer_spec.json"
STAGED_DECK_BLUEPRINT="$OUTPUT_DIR/deck_blueprint.json"
STAGED_RESEARCH_PACK="$OUTPUT_DIR/industry_research_pack.md"
STAGED_ISSUE_ANALYSIS="$OUTPUT_DIR/industry_issue_analysis.json"
STAGED_TEMPLATE_REGISTRY="$OUTPUT_DIR/template_registry.json"
STAGED_PAGE_CONTRACT="$OUTPUT_DIR/page_evidence_contract.json"

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
    echo "Create the full issue-analysis-driven research package, then rerun. Use --no-research-gate only for PPT-only debug runs." >&2
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

stage_optional_dir() {
  local src_dir="$1"
  local rel="$2"
  if [[ -d "$src_dir/$rel" ]]; then
    mkdir -p "$OUTPUT_DIR/$rel"
    cp -R "$src_dir/$rel/." "$OUTPUT_DIR/$rel/"
  fi
}

require_artifact_from_any() {
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
  echo "ERROR: missing mandatory formal artifact before PPT pipeline: $rel" >&2
  echo "Checked source directories: $*" >&2
  exit 1
}

if [[ $RESEARCH_GATE -eq 1 ]]; then
  stage_file "$DECK_BLUEPRINT" "$STAGED_DECK_BLUEPRINT"
else
  stage_file "$RENDERER_SPEC" "$STAGED_RENDERER_SPEC"
fi

INPUT_DIR="$INPUT_ARTIFACT_DIR_ABS"
WORK_ROOT_ABS="$(cd "$WORK_ROOT" && pwd)"
if [[ $RESEARCH_GATE -eq 1 ]]; then
  require_artifact_from_any "input_card.json" "$INPUT_DIR" "$WORK_ROOT_ABS"
  require_artifact_from_any "artifacts/input_card_validation.json" "$INPUT_DIR" "$WORK_ROOT_ABS"
  require_research_artifact "$INPUT_DIR" "artifacts/industry_scope_pack.json"
  require_research_artifact "$INPUT_DIR" "artifacts/industry_scope_pack_validation.json"
  require_research_artifact "$INPUT_DIR" "artifacts/formal_search_plan.json"
  require_research_artifact "$INPUT_DIR" "artifacts/search_log.md"
  require_research_artifact "$INPUT_DIR" "artifacts/source_reviews.json"
  require_research_artifact "$INPUT_DIR" "artifacts/source_archive/source_archive_index.json"
  require_research_artifact "$INPUT_DIR" "artifacts/formal_research_execution_report.json"
  require_research_artifact "$INPUT_DIR" "artifacts/formal_research_execution_validation.json"
  require_research_artifact "$INPUT_DIR" "industry_research_pack.md"
  require_research_artifact "$INPUT_DIR" "industry_issue_analysis.json"
  require_research_artifact "$INPUT_DIR" "deck_blueprint.json"
fi
if [[ $RESEARCH_GATE -eq 0 ]]; then
  stage_optional_artifact_from_any "input_card.json" "$INPUT_DIR" "$WORK_ROOT_ABS"
  stage_optional_artifact_from_any "artifacts/input_card_validation.json" "$INPUT_DIR" "$WORK_ROOT_ABS"
fi
stage_optional_artifact "$INPUT_DIR" "artifacts/industry_scope_pack.json"
stage_optional_artifact "$INPUT_DIR" "artifacts/industry_scope_pack_validation.json"
stage_optional_artifact "$INPUT_DIR" "artifacts/formal_search_plan.json"
stage_optional_artifact "$INPUT_DIR" "artifacts/formal_search_plan_validation.json"
stage_optional_artifact "$INPUT_DIR" "artifacts/search_log.md"
stage_optional_artifact "$INPUT_DIR" "artifacts/source_reviews.json"
stage_optional_artifact "$INPUT_DIR" "artifacts/source_reviews_validation.json"
stage_optional_dir "$INPUT_DIR" "artifacts/source_archive"
stage_optional_artifact "$INPUT_DIR" "artifacts/source_archive_validation.json"
stage_optional_artifact "$INPUT_DIR" "artifacts/formal_research_execution_report.json"
stage_optional_artifact "$INPUT_DIR" "artifacts/formal_research_execution_validation.json"
stage_optional_artifact "$INPUT_DIR" "industry_issue_analysis.json"
stage_optional_artifact "$INPUT_DIR" "deck_blueprint.json"
stage_optional_artifact_from_any "industry_research_pack.md" \
  "$INPUT_DIR" \
  "$INPUT_ARTIFACT_DIR_ABS" \
  "$WORK_ROOT_ABS"

if [[ $RESEARCH_GATE -eq 1 && ! -f "$STAGED_RESEARCH_PACK" ]]; then
  echo "ERROR: mandatory research pack was not staged into current attempt: $STAGED_RESEARCH_PACK" >&2
  exit 1
fi

echo "[bootstrap] extracting template registry..."
"$PYTHON_CMD" "$SCRIPT_DIR/scripts/extract_template_registry.py" \
  --template "$TEMPLATE" \
  --slide-registry "$SCRIPT_DIR/templates/slide_registry.json" \
  --page-type-rules "$SCRIPT_DIR/templates/page_type_rules.json" \
  --ppt-mapping "$PPT_MAPPING" \
  --layout-budget "$SCRIPT_DIR/templates/layout_budget.json" \
  --text-fit-rules "$SCRIPT_DIR/templates/text_fit_rules.json" \
  --output "$STAGED_TEMPLATE_REGISTRY" >/dev/null

if [[ $RESEARCH_GATE -eq 1 ]]; then
  echo "[bootstrap] validating input card..."
  run_validation_gate "input_card" "$OUTPUT_DIR/artifacts/input_card_validation.json" \
  "$PYTHON_CMD" "$SCRIPT_DIR/scripts/validate_input_card.py" \
    --input-card "$OUTPUT_DIR/input_card.json" \
    --output "$OUTPUT_DIR/artifacts/input_card_validation.json"

  echo "[bootstrap] validating industry scope pack..."
  run_validation_gate "industry_scope_pack" "$OUTPUT_DIR/artifacts/industry_scope_pack_validation.json" \
  "$PYTHON_CMD" "$SCRIPT_DIR/scripts/validate_industry_scope_pack.py" \
    --scope-pack "$OUTPUT_DIR/artifacts/industry_scope_pack.json" \
    --output "$OUTPUT_DIR/artifacts/industry_scope_pack_validation.json"

  echo "[bootstrap] validating formal search plan..."
  run_validation_gate "formal_search_plan" "$OUTPUT_DIR/artifacts/formal_search_plan_validation.json" \
  "$PYTHON_CMD" "$SCRIPT_DIR/scripts/validate_formal_search_plan.py" \
    --formal-search-plan "$OUTPUT_DIR/artifacts/formal_search_plan.json" \
    --output "$OUTPUT_DIR/artifacts/formal_search_plan_validation.json"

  echo "[bootstrap] validating source reviews..."
  run_validation_gate "source_reviews" "$OUTPUT_DIR/artifacts/source_reviews_validation.json" \
  "$PYTHON_CMD" "$SCRIPT_DIR/scripts/validate_source_reviews.py" \
    --source-reviews "$OUTPUT_DIR/artifacts/source_reviews.json" \
    --search-log "$OUTPUT_DIR/artifacts/search_log.md" \
    --output "$OUTPUT_DIR/artifacts/source_reviews_validation.json"

  echo "[bootstrap] validating source archive..."
  run_validation_gate "source_archive" "$OUTPUT_DIR/artifacts/source_archive_validation.json" \
  "$PYTHON_CMD" "$SCRIPT_DIR/scripts/validate_source_archive.py" \
    --source-reviews "$OUTPUT_DIR/artifacts/source_reviews.json" \
    --source-archive-index "$OUTPUT_DIR/artifacts/source_archive/source_archive_index.json" \
    --run-dir "$OUTPUT_DIR" \
    --output "$OUTPUT_DIR/artifacts/source_archive_validation.json"

  echo "[bootstrap] validating formal research execution..."
  run_validation_gate "formal_research_execution" "$OUTPUT_DIR/artifacts/formal_research_execution_validation.json" \
  "$PYTHON_CMD" "$SCRIPT_DIR/scripts/validate_formal_research_execution.py" \
    --report "$OUTPUT_DIR/artifacts/formal_research_execution_report.json" \
    --formal-search-plan "$OUTPUT_DIR/artifacts/formal_search_plan.json" \
    --search-log "$OUTPUT_DIR/artifacts/search_log.md" \
    --output "$OUTPUT_DIR/artifacts/formal_research_execution_validation.json"

  echo "[bootstrap] validating pre-research pack stage gate..."
  run_validation_gate "pre_research_pack" "$OUTPUT_DIR/artifacts/stage_gate_pre_research_pack_validation.json" \
  "$PYTHON_CMD" "$SCRIPT_DIR/scripts/validate_stage_gate.py" \
    --stage pre_research_pack \
    --run-dir "$OUTPUT_DIR" \
    --source-registry "$SCRIPT_DIR/templates/source_registry.json" \
    --output "$OUTPUT_DIR/artifacts/stage_gate_pre_research_pack_validation.json"

  echo "[bootstrap] validating research pack..."
  run_validation_gate "research_pack" "$OUTPUT_DIR/artifacts/research_pack_validation.json" \
  "$PYTHON_CMD" "$SCRIPT_DIR/scripts/validate_research_pack.py" \
    --research-pack "$STAGED_RESEARCH_PACK" \
    --run-dir "$OUTPUT_DIR" \
    --source-registry "$SCRIPT_DIR/templates/source_registry.json" \
    --output "$OUTPUT_DIR/artifacts/research_pack_validation.json"

  echo "[bootstrap] validating source reviews against research pack evidence ledger..."
  run_validation_gate "source_reviews" "$OUTPUT_DIR/artifacts/source_reviews_validation.json" \
  "$PYTHON_CMD" "$SCRIPT_DIR/scripts/validate_source_reviews.py" \
    --source-reviews "$OUTPUT_DIR/artifacts/source_reviews.json" \
    --search-log "$OUTPUT_DIR/artifacts/search_log.md" \
    --formal-research-execution-report "$OUTPUT_DIR/artifacts/formal_research_execution_report.json" \
    --research-pack "$STAGED_RESEARCH_PACK" \
    --source-archive-index "$OUTPUT_DIR/artifacts/source_archive/source_archive_index.json" \
    --run-dir "$OUTPUT_DIR" \
    --output "$OUTPUT_DIR/artifacts/source_reviews_validation.json"

  echo "[bootstrap] validating issue analysis..."
  run_validation_gate "issue_analysis" "$OUTPUT_DIR/artifacts/issue_analysis_validation.json" \
  "$PYTHON_CMD" "$SCRIPT_DIR/scripts/validate_issue_analysis.py" \
    --issue-analysis "$STAGED_ISSUE_ANALYSIS" \
    --research-pack "$STAGED_RESEARCH_PACK" \
    --output "$OUTPUT_DIR/artifacts/issue_analysis_validation.json"

  echo "[bootstrap] validating template registry..."
  run_validation_gate "template_registry" "$OUTPUT_DIR/artifacts/template_registry_validation.json" \
  "$PYTHON_CMD" "$SCRIPT_DIR/scripts/validate_template_registry.py" \
    --template-registry "$STAGED_TEMPLATE_REGISTRY" \
    --slide-registry "$SCRIPT_DIR/templates/slide_registry.json" \
    --output "$OUTPUT_DIR/artifacts/template_registry_validation.json"

  echo "[bootstrap] validating deck blueprint..."
  run_validation_gate "deck_blueprint" "$OUTPUT_DIR/artifacts/deck_blueprint_validation.json" \
  "$PYTHON_CMD" "$SCRIPT_DIR/scripts/validate_deck_blueprint.py" \
    --issue-analysis "$STAGED_ISSUE_ANALYSIS" \
    --template-registry "$STAGED_TEMPLATE_REGISTRY" \
    --deck-blueprint "$STAGED_DECK_BLUEPRINT" \
    --output "$OUTPUT_DIR/artifacts/deck_blueprint_validation.json"

  echo "[bootstrap] compiling deck blueprint into page evidence contract and renderer spec..."
  "$PYTHON_CMD" "$SCRIPT_DIR/scripts/compile_deck_blueprint.py" \
    --issue-analysis "$STAGED_ISSUE_ANALYSIS" \
    --deck-blueprint "$STAGED_DECK_BLUEPRINT" \
    --template-registry "$STAGED_TEMPLATE_REGISTRY" \
    --page-contract-output "$STAGED_PAGE_CONTRACT" \
    --renderer-spec-output "$STAGED_RENDERER_SPEC" >/dev/null

  echo "[bootstrap] validating page evidence contract..."
  run_validation_gate "page_evidence_contract" "$OUTPUT_DIR/artifacts/page_evidence_contract_validation.json" \
  "$PYTHON_CMD" "$SCRIPT_DIR/scripts/validate_page_evidence_contract.py" \
    --issue-analysis "$STAGED_ISSUE_ANALYSIS" \
    --deck-blueprint "$STAGED_DECK_BLUEPRINT" \
    --page-contract "$STAGED_PAGE_CONTRACT" \
    --output "$OUTPUT_DIR/artifacts/page_evidence_contract_validation.json"
fi

if [[ $RESEARCH_GATE -eq 1 ]]; then
  echo "[bootstrap] validating renderer spec..."
  run_validation_gate "renderer_spec" "$OUTPUT_DIR/artifacts/renderer_spec_validation.json" \
  "$PYTHON_CMD" "$SCRIPT_DIR/scripts/validate_renderer_spec.py" \
    --renderer-spec "$STAGED_RENDERER_SPEC" \
    --template-registry "$STAGED_TEMPLATE_REGISTRY" \
    --deck-blueprint "$STAGED_DECK_BLUEPRINT" \
    --page-contract "$STAGED_PAGE_CONTRACT" \
    --output "$OUTPUT_DIR/artifacts/renderer_spec_validation.json"
fi

RESEARCH_PACK_FILE=""
if [[ -f "$STAGED_RESEARCH_PACK" ]]; then
  RESEARCH_PACK_FILE="$STAGED_RESEARCH_PACK"
fi

if [[ $RESEARCH_GATE -eq 1 ]]; then
  echo "[bootstrap] validating chart metric binding..."
  CHART_BINDING_ARGS=(
    --renderer-spec "$STAGED_RENDERER_SPEC"
    --research-pack "$STAGED_RESEARCH_PACK"
    --page-contract "$STAGED_PAGE_CONTRACT"
    --output "$OUTPUT_DIR/artifacts/chart_metric_binding_validation.json"
  )
  run_validation_gate "chart_metric_binding" "$OUTPUT_DIR/artifacts/chart_metric_binding_validation.json" \
  "$PYTHON_CMD" "$SCRIPT_DIR/scripts/validate_chart_metric_binding.py" "${CHART_BINDING_ARGS[@]}"
fi

# ── Step 0b: Content quality validation ──────────────────────────
# Density warnings are advisory; source_warnings are blocking unless
# validate_content_quality.py is run with --allow-source-warnings.

echo "[bootstrap] validating content quality..."
QUALITY_ARGS=(
  --renderer-spec "$STAGED_RENDERER_SPEC"
  --rules "$SCRIPT_DIR/templates/content_quality_rules.json"
  --text-fit-rules "$SCRIPT_DIR/templates/text_fit_rules.json"
  --layout-budget "$SCRIPT_DIR/templates/layout_budget.json"
  --output "$OUTPUT_DIR/artifacts/content_quality_validation.json"
)
if [[ -n "$RESEARCH_PACK_FILE" ]]; then
  QUALITY_ARGS+=(--research-pack "$RESEARCH_PACK_FILE")
fi
if [[ $QUALITY_GATE -eq 1 ]]; then
  QUALITY_ARGS+=(--quality-gate)
fi
run_validation_gate "content_quality" "$OUTPUT_DIR/artifacts/content_quality_validation.json" \
"$PYTHON_CMD" "$SCRIPT_DIR/scripts/validate_content_quality.py" "${QUALITY_ARGS[@]}"

if [[ $RESEARCH_GATE -eq 1 ]]; then
  echo "[bootstrap] validating pre-PPT stage gate..."
  run_validation_gate "pre_ppt" "$OUTPUT_DIR/artifacts/stage_gate_pre_ppt_validation.json" \
  "$PYTHON_CMD" "$SCRIPT_DIR/scripts/validate_stage_gate.py" \
    --stage pre_ppt \
    --run-dir "$OUTPUT_DIR" \
    --source-registry "$SCRIPT_DIR/templates/source_registry.json" \
    --output "$OUTPUT_DIR/artifacts/stage_gate_pre_ppt_validation.json"
fi

PPT_SCRIPT_GATE_ARGS_STRING=""
FILLED_PPT_NAME="industry_section_filled.pptx"
CLEAN_PPT_NAME="industry_section_filled_clean.pptx"

mark_not_client_ready_outputs_on_failure() {
  local status=$?
  if [[ $status -ne 0 && "${RESEARCH_GATE:-1}" -eq 1 && -n "${OUTPUT_DIR:-}" && -d "${OUTPUT_DIR:-}" ]]; then
    for ppt_name in "${CLEAN_PPT_NAME:-}" "${FILLED_PPT_NAME:-}"; do
      if [[ -n "$ppt_name" && -f "$OUTPUT_DIR/$ppt_name" && ! "$ppt_name" == NOT_CLIENT_READY_* ]]; then
        mv "$OUTPUT_DIR/$ppt_name" "$OUTPUT_DIR/NOT_CLIENT_READY_$ppt_name" 2>/dev/null || true
      fi
    done
    if [[ ! -f "$OUTPUT_DIR/NOT_CLIENT_READY_OUTPUT.txt" ]]; then
      cat > "$OUTPUT_DIR/NOT_CLIENT_READY_OUTPUT.txt" <<'EOF'
Formal PPT pipeline failed before client-ready final delivery.
Any generated PPT was renamed with NOT_CLIENT_READY_ and must not be described as a final deliverable.
Fix the upstream pipeline blocker and rerun run_pipeline.sh.
EOF
    fi
  fi
}
trap mark_not_client_ready_outputs_on_failure EXIT

if [[ $RESEARCH_GATE -eq 0 ]]; then
  PPT_SCRIPT_GATE_ARGS_STRING="--allow-ungated-debug"
  export IB_SKILL_ALLOW_UNGATED_DEBUG=1
  FILLED_PPT_NAME="DEBUG_NOT_FOR_DELIVERY_industry_section_raw.pptx"
  CLEAN_PPT_NAME="DEBUG_NOT_FOR_DELIVERY_industry_section.pptx"
  cat > "$OUTPUT_DIR/DEBUG_OUTPUT_ONLY.txt" <<'EOF'
This run was generated with --no-research-gate / ungated debug mode.
It is not a final delivery package. Do not copy this PPT to a final-looking
filename, do not update LATEST_FINAL_PPT.txt, and do not describe it as client-ready.
EOF
  {
    printf '\nDebug reason:\n'
    printf '%s\n' "$DEBUG_REASON"
  } >> "$OUTPUT_DIR/DEBUG_OUTPUT_ONLY.txt"
fi

echo "=== IB Industry Section PPT Pipeline ==="
if [[ $RESEARCH_GATE -eq 1 ]]; then
  echo "Deck blueprint: $DECK_BLUEPRINT"
  echo "Renderer:       $STAGED_RENDERER_SPEC (compiled)"
else
  echo "Renderer:    $RENDERER_SPEC"
fi
echo "Source dir:  $INPUT_DIR"
echo "Source run:  ${SOURCE_RUN_DIR:-<none>}"
echo "Work root:   $WORK_ROOT"
echo "Run root:    $RUN_ROOT"
echo "Output dir:  $OUTPUT_DIR"
echo "Package of record: $OUTPUT_DIR"
if [[ -n "$SOURCE_RUN_DIR" && "$SOURCE_RUN_DIR" != "$OUTPUT_DIR" ]]; then
  echo "NOTE: source run and output run differ because --new-attempt/--attempt-name/--output-dir was explicit."
fi
if [[ $RESEARCH_GATE -eq 0 ]]; then
  echo "Run mode:    DEBUG_NOT_FOR_DELIVERY"
fi
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
  --renderer-spec "$STAGED_RENDERER_SPEC" \
  --ppt-mapping "$PPT_MAPPING" \
  --output "$OUTPUT_DIR/replacement_dict.json" \
  ${PPT_SCRIPT_GATE_ARGS_STRING:+"$PPT_SCRIPT_GATE_ARGS_STRING"}

echo "[2b/7] Validating replacement dictionary..."
run_validation_gate "replacement_dict" "$OUTPUT_DIR/artifacts/replacement_dict_validation.json" \
"$PYTHON_CMD" "$SCRIPT_DIR/scripts/validate_replacement_dict.py" \
  --replacement-dict "$OUTPUT_DIR/replacement_dict.json" \
  --renderer-spec "$STAGED_RENDERER_SPEC" \
  --ppt-mapping "$PPT_MAPPING" \
  --output "$OUTPUT_DIR/artifacts/replacement_dict_validation.json"

# ── Step 3: Fill PPT tokens ─────────────────────────────────────
echo "[3/7] Filling PPT tokens..."
"$PYTHON_CMD" "$SCRIPT_DIR/scripts/fill_ppt_tokens.py" \
  --template "$TEMPLATE" \
  --replacement-dict "$OUTPUT_DIR/replacement_dict.json" \
  --output "$OUTPUT_DIR/$FILLED_PPT_NAME" \
  --log "$OUTPUT_DIR/artifacts/fill_ppt_tokens.log.json" \
  ${PPT_SCRIPT_GATE_ARGS_STRING:+"$PPT_SCRIPT_GATE_ARGS_STRING"}

# ── Step 4: Clean inactive variant slides ────────────────────────
echo "[4/7] Cleaning inactive variant slides..."
"$PYTHON_CMD" "$SCRIPT_DIR/scripts/clean_filled_ppt.py" \
  --input "$OUTPUT_DIR/$FILLED_PPT_NAME" \
  --control-file "$STAGED_RENDERER_SPEC" \
  --output "$OUTPUT_DIR/$CLEAN_PPT_NAME" \
  --log "$OUTPUT_DIR/artifacts/clean_filled_ppt.log.json" \
  ${PPT_SCRIPT_GATE_ARGS_STRING:+"$PPT_SCRIPT_GATE_ARGS_STRING"}

# ── Step 5: Post-process visuals ─────────────────────────────────
echo "[5/7] Post-processing visuals..."
"$PYTHON_CMD" "$SCRIPT_DIR/scripts/postprocess_ppt_visuals.py" \
  --input-ppt "$OUTPUT_DIR/$CLEAN_PPT_NAME" \
  --renderer-spec "$STAGED_RENDERER_SPEC" \
  --output "$OUTPUT_DIR/$CLEAN_PPT_NAME" \
  --render-layouts "$SCRIPT_DIR/templates/render_layouts.json" \
  --log "$OUTPUT_DIR/artifacts/postprocess_ppt_visuals.log.json" \
  ${PPT_SCRIPT_GATE_ARGS_STRING:+"$PPT_SCRIPT_GATE_ARGS_STRING"} \
  --fail-on-unrendered

# ── Step 6: Validate final output ────────────────────────────────
echo "[6/7] Validating filled PPT..."
run_validation_gate "filled_ppt" "$OUTPUT_DIR/filled_ppt_validation.json" \
"$PYTHON_CMD" "$SCRIPT_DIR/scripts/validate_filled_ppt.py" \
  --filled-ppt "$OUTPUT_DIR/$FILLED_PPT_NAME" \
  --clean-ppt "$OUTPUT_DIR/$CLEAN_PPT_NAME" \
  --control-file "$STAGED_RENDERER_SPEC" \
  --replacement-dict "$OUTPUT_DIR/replacement_dict.json" \
  --ppt-mapping "$PPT_MAPPING" \
  --output "$OUTPUT_DIR/filled_ppt_validation.json" \
  --fail-on-issue

# ── Step 7: Final delivery gate and quality summary ──────────────
echo "[7/7] Running final delivery gate..."
if [[ $RESEARCH_GATE -eq 0 ]]; then
  echo "Debug mode: skipping final delivery gate and latest-final pointer update."
  echo "Debug PPT:   $OUTPUT_DIR/$CLEAN_PPT_NAME"
  echo "Validation:  $OUTPUT_DIR/filled_ppt_validation.json"
  exit 0
fi
if ! run_validation_gate "final_delivery" "$OUTPUT_DIR/artifacts/final_delivery_validation.json" \
"$PYTHON_CMD" "$SCRIPT_DIR/scripts/validate_final_delivery.py" \
  --run-dir "$OUTPUT_DIR" \
  --source-registry "$SCRIPT_DIR/templates/source_registry.json" \
  --output "$OUTPUT_DIR/artifacts/final_delivery_validation.json" \
  --require-client-ready
then
  echo "ERROR: final delivery gate failed; renaming any generated PPT to NOT_CLIENT_READY names." >&2
  if [[ -f "$OUTPUT_DIR/$CLEAN_PPT_NAME" ]]; then
    mv "$OUTPUT_DIR/$CLEAN_PPT_NAME" "$OUTPUT_DIR/NOT_CLIENT_READY_$CLEAN_PPT_NAME"
  fi
  if [[ -f "$OUTPUT_DIR/$FILLED_PPT_NAME" ]]; then
    mv "$OUTPUT_DIR/$FILLED_PPT_NAME" "$OUTPUT_DIR/NOT_CLIENT_READY_$FILLED_PPT_NAME"
  fi
  cat > "$OUTPUT_DIR/NOT_CLIENT_READY_OUTPUT.txt" <<'EOF'
Final delivery validation failed.
Any generated PPT was renamed with NOT_CLIENT_READY_ and must not be described as a final deliverable.
Fix the upstream page-editor, renderer, replacement, PPT validation, or final delivery blocker and rerun the formal pipeline.
EOF
  exit 1
fi

rm -f "$OUTPUT_DIR/NOT_CLIENT_READY_$CLEAN_PPT_NAME" \
      "$OUTPUT_DIR/NOT_CLIENT_READY_$FILLED_PPT_NAME" \
      "$OUTPUT_DIR/NOT_CLIENT_READY_OUTPUT.txt"

"$PYTHON_CMD" "$SCRIPT_DIR/scripts/generate_run_quality_summary.py" \
  --run-dir "$OUTPUT_DIR"

if [[ "$(basename "$OUTPUT_DIR")" == attempt_* ]]; then
  printf '%s\n' "$(basename "$OUTPUT_DIR")" > "$(dirname "$OUTPUT_DIR")/ACTIVE_ATTEMPT.txt"
  "$PYTHON_CMD" "$SCRIPT_DIR/scripts/update_runs_index.py" \
    --runs-dir "$(dirname "$OUTPUT_DIR")"
fi

LATEST_FINAL_POINTER=""
if [[ "$(basename "$OUTPUT_DIR")" == attempt_* ]]; then
  LATEST_FINAL_POINTER="$(dirname "$OUTPUT_DIR")/LATEST_FINAL_PPT.txt"
fi

if [[ -z "$LATEST_FINAL_POINTER" || ! -s "$LATEST_FINAL_POINTER" ]]; then
  echo "ERROR: final delivery passed but latest-final pointer was not written." >&2
  echo "Expected pointer: ${LATEST_FINAL_POINTER:-<not in attempt layout>}" >&2
  exit 1
fi

FINAL_PPT_PATH="$(cat "$LATEST_FINAL_POINTER")"
if [[ -z "$FINAL_PPT_PATH" || ! -f "$FINAL_PPT_PATH" ]]; then
  echo "ERROR: latest-final pointer does not reference an existing PPTX: $LATEST_FINAL_POINTER" >&2
  exit 1
fi

echo "Run directory ready."
echo "Staged inputs:"
echo "  - $STAGED_RENDERER_SPEC"
if [[ -f "$OUTPUT_DIR/industry_research_pack.md" ]]; then
  echo "  - $OUTPUT_DIR/industry_research_pack.md"
fi

echo ""
echo "=== Pipeline complete ==="
echo "Output dir:  $OUTPUT_DIR"
echo "Final PPT:   $FINAL_PPT_PATH"
echo "Validation:  $OUTPUT_DIR/filled_ppt_validation.json"
echo "Final gate:  $OUTPUT_DIR/artifacts/final_delivery_validation.json"
echo "Quality:     $OUTPUT_DIR/artifacts/run_quality_summary.md"

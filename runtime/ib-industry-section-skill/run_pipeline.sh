#!/usr/bin/env bash
#
# run_pipeline.sh — legacy compatibility wrapper.
#
# Public entrypoint for formal delivery is now:
#   "$PYTHON_CMD" scripts/pipeline.py render --run-dir /path/to/attempt
#
# This wrapper exists for older automation. It does not create attempts, stage
# artifacts, repair validators, or run research. It resolves an existing attempt
# directory and delegates to scripts/pipeline.py render.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

usage() {
  cat <<'EOF'
Usage:
  ./run_pipeline.sh --run-dir /path/to/runs/<case>/attempt_<timestamp>
  ./run_pipeline.sh --deck-blueprint /path/to/attempt/deck_blueprint.json

Compatibility options accepted:
  --run-dir DIR             Existing package-of-record attempt directory
  --deck-blueprint FILE     Used only to infer the attempt directory
  --renderer-spec FILE      Formal mode rejects renderer_spec-only input
  -o, --output-dir DIR      Legacy alias; must point to an existing attempt
  --work-root DIR           Used only if DIR itself is an existing attempt
  --case-name NAME          Accepted for old callers; not used to create runs
  --attempt-name NAME       Accepted for old callers; not used to create runs
  --resume-active           Accepted for old callers; no effect
  --new-attempt             Rejected; create attempts explicitly before render
  --python PATH             Python interpreter hint for bootstrap
  --quality-gate            Accepted; pipeline.py owns formal quality gates
  --no-research-gate        Debug-only compatibility path; never formal delivery
  --debug-reason TEXT       Required with --no-research-gate
  -h, --help                Show this help

Formal delivery command:
  "$PYTHON_CMD" scripts/pipeline.py render --run-dir "$RUN_DIR"

This wrapper never generates a client-ready PPT unless final delivery validation
inside scripts/pipeline.py succeeds.
EOF
}

RUN_DIR=""
OUTPUT_DIR=""
DECK_BLUEPRINT=""
RENDERER_SPEC=""
WORK_ROOT_ARG=""
PYTHON_CMD_ARG=""
RESEARCH_GATE=1
DEBUG_REASON=""
NEW_ATTEMPT=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --run-dir)
      RUN_DIR="$2"; shift 2 ;;
    -o|--output-dir)
      OUTPUT_DIR="$2"; shift 2 ;;
    --deck-blueprint)
      DECK_BLUEPRINT="$2"; shift 2 ;;
    --renderer-spec)
      RENDERER_SPEC="$2"; shift 2 ;;
    --work-root)
      WORK_ROOT_ARG="$2"; shift 2 ;;
    --case-name|--attempt-name)
      shift 2 ;;
    --resume-active|--quality-gate)
      shift ;;
    --new-attempt)
      NEW_ATTEMPT=1; shift ;;
    --python)
      PYTHON_CMD_ARG="$2"; shift 2 ;;
    --no-research-gate)
      RESEARCH_GATE=0; shift ;;
    --debug-reason|--debug-ppt-only-reason)
      DEBUG_REASON="$2"; shift 2 ;;
    -h|--help)
      usage; exit 0 ;;
    -*)
      echo "ERROR: unknown option: $1" >&2
      usage >&2
      exit 2 ;;
    *)
      if [[ -z "$DECK_BLUEPRINT" && $RESEARCH_GATE -eq 1 ]]; then
        DECK_BLUEPRINT="$1"
      elif [[ -z "$RENDERER_SPEC" ]]; then
        RENDERER_SPEC="$1"
      else
        echo "ERROR: unexpected argument: $1" >&2
        usage >&2
        exit 2
      fi
      shift ;;
  esac
done

reject_debug_shortcut() {
  if [[ "${IB_SKILL_ALLOW_PPT_ONLY_DEBUG:-}" != "1" ]]; then
    cat >&2 <<'EOF'
ERROR: --no-research-gate is disabled by default.

For a project brief, use the formal workflow and final delivery gate. Debug mode
is only for local template/rendering diagnostics. To acknowledge that, set:
  IB_SKILL_ALLOW_PPT_ONLY_DEBUG=1
and pass:
  --debug-reason "local template/rendering diagnostic: <what you are testing>"
EOF
    exit 2
  fi
  if [[ -z "${DEBUG_REASON//[[:space:]]/}" ]]; then
    echo "ERROR: --no-research-gate requires --debug-reason." >&2
    exit 2
  fi
  if printf '%s' "$DEBUG_REASON" | grep -Eiq 'research|memo|source|evidence|renderer|formal|delivery|client|generate[[:space:]-]*ppt|validated|completed|研究|备忘录|来源|证据|渲染规格|正式|交付|生成[[:space:]]*ppt|已完成|通过'; then
    cat >&2 <<'EOF'
ERROR: --debug-reason indicates an attempted research/delivery shortcut.

--no-research-gate cannot be used because research, source, evidence, renderer,
schema, or delivery gates are failing. Fix the upstream gate instead.
EOF
    exit 2
  fi
  if ! printf '%s' "$DEBUG_REASON" | grep -Eiq 'template|render|rendering|layout|postprocess|post-processing|token|visual|chart|table|diagnostic|diagnostics|模板|渲染|版式|后处理|占位符|图表|表格|诊断'; then
    echo "ERROR: --debug-reason must describe a local template/rendering diagnostic." >&2
    exit 2
  fi
  cat >&2 <<'EOF'
ERROR: run_pipeline.sh no longer runs PPT-only debug rendering.

Use the specific low-level diagnostic script for the template/rendering behavior
you are testing. Formal delivery must use:
  "$PYTHON_CMD" scripts/pipeline.py render --run-dir "$RUN_DIR"
EOF
  exit 2
}

if [[ $RESEARCH_GATE -eq 0 ]]; then
  reject_debug_shortcut
fi

if [[ $NEW_ATTEMPT -eq 1 ]]; then
  cat >&2 <<'EOF'
ERROR: run_pipeline.sh no longer creates new attempts.

Create the attempt directory and formal authoring artifacts explicitly, then run:
  "$PYTHON_CMD" scripts/pipeline.py render --run-dir "$RUN_DIR"
EOF
  exit 2
fi

if [[ -n "$RENDERER_SPEC" && -z "$DECK_BLUEPRINT" && -z "$RUN_DIR" ]]; then
  cat >&2 <<'EOF'
ERROR: formal runs no longer accept renderer_spec as the authored input.

Write and validate deck_blueprint.json, compile deterministic artifacts, then run:
  "$PYTHON_CMD" scripts/pipeline.py render --run-dir "$RUN_DIR"
EOF
  exit 2
fi

abs_dir() {
  local path="$1"
  (cd "$path" && pwd)
}

infer_attempt_from_path() {
  local path="$1"
  local dir
  if [[ -z "$path" ]]; then
    return 1
  fi
  if [[ -f "$path" ]]; then
    dir="$(dirname "$path")"
  else
    dir="$path"
  fi
  dir="$(abs_dir "$dir" 2>/dev/null || true)"
  while [[ -n "$dir" && "$dir" != "/" ]]; do
    if [[ "$(basename "$dir")" == attempt_* ]]; then
      printf '%s\n' "$dir"
      return 0
    fi
    dir="$(dirname "$dir")"
  done
  return 1
}

if [[ -z "$RUN_DIR" && -n "$OUTPUT_DIR" ]]; then
  if [[ -d "$OUTPUT_DIR" && "$(basename "$(abs_dir "$OUTPUT_DIR")")" == attempt_* ]]; then
    RUN_DIR="$(abs_dir "$OUTPUT_DIR")"
  else
    echo "ERROR: --output-dir is legacy compatibility only and must point to an existing attempt directory." >&2
    exit 2
  fi
fi

if [[ -z "$RUN_DIR" && -n "$DECK_BLUEPRINT" ]]; then
  RUN_DIR="$(infer_attempt_from_path "$DECK_BLUEPRINT" || true)"
fi

if [[ -z "$RUN_DIR" && -n "$WORK_ROOT_ARG" ]]; then
  if [[ -d "$WORK_ROOT_ARG" && "$(basename "$(abs_dir "$WORK_ROOT_ARG")")" == attempt_* ]]; then
    RUN_DIR="$(abs_dir "$WORK_ROOT_ARG")"
  fi
fi

if [[ -z "$RUN_DIR" ]]; then
  cat >&2 <<'EOF'
ERROR: could not infer an existing attempt directory.

Use the public command directly:
  "$PYTHON_CMD" scripts/pipeline.py render --run-dir /path/to/runs/<case>/attempt_<timestamp>

This wrapper intentionally does not create attempts or stage artifacts.
EOF
  exit 2
fi

RUN_DIR="$(abs_dir "$RUN_DIR")"
if [[ ! -d "$RUN_DIR" || "$(basename "$RUN_DIR")" != attempt_* ]]; then
  echo "ERROR: --run-dir must be an existing attempt directory: $RUN_DIR" >&2
  exit 2
fi

BOOTSTRAP_PYTHON="${PYTHON_BOOTSTRAP_BIN:-}"
if [[ -z "$BOOTSTRAP_PYTHON" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    BOOTSTRAP_PYTHON="python3"
  elif command -v python >/dev/null 2>&1; then
    BOOTSTRAP_PYTHON="python"
  else
    echo "ERROR: no Python interpreter found to run bootstrap_runtime.py." >&2
    exit 1
  fi
fi

BOOTSTRAP_ARGS=(--print-python --ppt-only)
if [[ -n "$PYTHON_CMD_ARG" ]]; then
  BOOTSTRAP_ARGS+=(--python "$PYTHON_CMD_ARG")
elif [[ -n "${PYTHON_CMD:-}" ]]; then
  BOOTSTRAP_ARGS+=(--python "$PYTHON_CMD")
fi

if ! PYTHON_CMD_RESOLVED="$("$BOOTSTRAP_PYTHON" "$SCRIPT_DIR/scripts/bootstrap_runtime.py" "${BOOTSTRAP_ARGS[@]}")"; then
  echo "ERROR: runtime bootstrap failed." >&2
  exit 1
fi

echo "[run_pipeline] compatibility wrapper; delegating to scripts/pipeline.py render"
echo "[run_pipeline] run_dir: $RUN_DIR"
exec "$PYTHON_CMD_RESOLVED" "$SCRIPT_DIR/scripts/pipeline.py" --python "$PYTHON_CMD_RESOLVED" render --run-dir "$RUN_DIR"

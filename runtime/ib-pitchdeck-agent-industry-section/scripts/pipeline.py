#!/usr/bin/env python3
"""Python orchestrator for deterministic IB industry-section run steps.

This CLI operates on one existing run directory. It does not perform research,
does not write page judgments, and does not create a new attempt unless the
caller explicitly creates one outside this script. Its purpose is to keep
attempt management, validation orchestration, PPT rendering, final delivery,
and quality summary in one predictable Python entrypoint.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from json import JSONDecodeError
from pathlib import Path
from typing import Any

from layout_config import layout_config_paths
from validate_run_state import validate_run_state


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent

# --- Tool integrity: do not modify this file during a run ---
_TOOL_SOURCE_REPO = ROOT_DIR.parent.parent  # expected: <repo>/runtime/ib-pitchdeck-agent-industry-section
_INTEGRITY_SENTINEL = "pipeline.py is a read-only tool file; repair upstream artifacts, not this script."  # noqa: E501
TEMPLATE = ROOT_DIR / "assets" / "industry_section_template_master.pptx"
SOURCE_REGISTRY = ROOT_DIR / "templates" / "source_registry.json"
CONTENT_RULES = ROOT_DIR / "templates" / "content_quality_rules.json"
LAYOUT_PATHS = layout_config_paths()
PPT_MAPPING = LAYOUT_PATHS["ppt_mapping"]
RENDER_LAYOUTS = LAYOUT_PATHS["render_layouts"]
TEXT_FIT_RULES = LAYOUT_PATHS["text_fit_rules"]
LAYOUT_BUDGET = LAYOUT_PATHS["layout_budget"]
TEMPLATE_PROFILE = LAYOUT_PATHS["template_profile"]

FILLED_PPT = "industry_section_filled.pptx"
CLEAN_PPT = "industry_section_filled_clean.pptx"
FAILURE_MEMORY = "artifacts/failure_memory.jsonl"


class PipelineError(RuntimeError):
    pass


def _json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        raise PipelineError(f"Failed to decode JSON file as UTF-8: {path}. {exc}") from exc
    except OSError as exc:
        raise PipelineError(f"Failed to read JSON file: {path}. {exc}") from exc
    except JSONDecodeError as exc:
        raise PipelineError(f"Invalid JSON in file: {path}. {exc}") from exc


def _run(cmd: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    printable = " ".join(str(part) for part in cmd)
    print(f"[pipeline] {printable}")
    subprocess.run([str(part) for part in cmd], cwd=str(cwd or ROOT_DIR), env=env, check=True)


def _run_returncode(cmd: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> int:
    printable = " ".join(str(part) for part in cmd)
    print(f"[pipeline] {printable}")
    completed = subprocess.run([str(part) for part in cmd], cwd=str(cwd or ROOT_DIR), env=env, check=False)
    return completed.returncode


def _append_failure_memory(run_dir: Path, event: str, *, outcome: str, command: str = "", details: dict[str, Any] | None = None) -> None:
    if not run_dir:
        return
    path = run_dir / FAILURE_MEMORY
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "run_dir": str(run_dir),
        "event": event,
        "outcome": outcome,
        "command": command,
    }
    if details:
        payload["details"] = details
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _ensure_run_dir(run_dir: Path) -> Path:
    run_dir = run_dir.resolve()
    if not run_dir.exists() or not run_dir.is_dir():
        raise PipelineError(f"run directory not found: {run_dir}")
    if run_dir.name == "runs":
        raise PipelineError("run-dir points to a runs/ directory; pass the concrete attempt directory")
    return run_dir


def _preflight(run_dir: Path) -> None:
    state = validate_run_state(run_dir)
    if state["current_stage"] not in {
        "TEMPLATE_PROFILE_MISSING_OR_FAILED",
        "TEMPLATE_FIT_FAILED",
        "CHART_METRIC_BINDING_FAILED",
        "CONTENT_QUALITY_FAILED",
        "PRE_PPT_GATE_FAILED",
        "REPLACEMENT_DICT_MISSING_OR_FAILED",
        "FILLED_PPT_VALIDATION_FAILED",
        "FINAL_DELIVERY_NOT_READY",
        "CLIENT_READY",
    }:
        raise PipelineError(
            "run is not ready for deterministic PPT rendering. "
            f"current_stage={state['current_stage']} status={state['status']}. "
            "Run scripts/workflow.py next --run-dir <run_dir> and repair the listed upstream gate first."
        )
    if state.get("debug_only"):
        raise PipelineError("debug-only runs cannot be rendered/finalized by the formal Python pipeline")


def _mark_not_client_ready(run_dir: Path) -> None:
    for name in (CLEAN_PPT, FILLED_PPT):
        source = run_dir / name
        dest = run_dir / f"NOT_CLIENT_READY_{name}"
        if source.exists() and not dest.exists():
            source.rename(dest)
    marker = run_dir / "NOT_CLIENT_READY_OUTPUT.txt"
    if not marker.exists():
        marker.write_text(
            "Formal PPT pipeline failed before client-ready final delivery.\n"
            "Any generated PPT was renamed with NOT_CLIENT_READY_ and must not be described as a final deliverable.\n"
            "Fix the current workflow gate and rerun scripts/pipeline.py render.\n",
            encoding="utf-8",
        )


def _clear_not_client_ready(run_dir: Path) -> None:
    for name in (CLEAN_PPT, FILLED_PPT):
        not_ready = run_dir / f"NOT_CLIENT_READY_{name}"
        if not_ready.exists():
            not_ready.unlink()
    marker = run_dir / "NOT_CLIENT_READY_OUTPUT.txt"
    if marker.exists():
        marker.unlink()


def _write_run_flags(run_dir: Path, *, entrypoint: str, preflight_skipped: bool = False) -> None:
    """Record formal pipeline mode for final delivery.

    The legacy shell wrapper used to own this artifact. The Python pipeline is
    now the formal controller, so it must write the package-of-record flags
    itself. Existing debug flags are preserved so a debug run cannot be
    accidentally promoted by calling finalize.
    """

    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    path = artifacts / "run_flags.json"
    existing = _json(path)
    if existing.get("debug_output_only") is True:
        return
    payload = {
        "schema_version": "run_flags_v1",
        "research_gate": 1,
        "issue_analysis_layer": 1,
        "quality_gate": 1,
        "source_run_dir": str(run_dir),
        "output_run_dir": str(run_dir),
        "package_of_record": str(run_dir),
        "debug_output_only": False,
        "debug_reason": "",
        "pipeline_entrypoint": entrypoint,
        "preflight_skipped": preflight_skipped,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate_pre_ppt(run_dir: Path, python_cmd: str) -> None:
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(exist_ok=True)
    template_profile_path = artifacts / "template_profile.json"
    _run(
        [
            python_cmd,
            SCRIPT_DIR / "validate_chart_metric_binding.py",
            "--renderer-spec",
            run_dir / "renderer_spec.json",
            "--research-pack",
            run_dir / "industry_research_pack.md",
            "--page-contract",
            run_dir / "page_evidence_contract.json",
            "--output",
            artifacts / "chart_metric_binding_validation.json",
        ]
    )
    _run(
        [
            python_cmd,
            SCRIPT_DIR / "validate_content_quality.py",
            "--renderer-spec",
            run_dir / "renderer_spec.json",
            "--research-pack",
            run_dir / "industry_research_pack.md",
            "--rules",
            CONTENT_RULES,
            "--text-fit-rules",
            TEXT_FIT_RULES,
            "--layout-budget",
            LAYOUT_BUDGET,
            "--output",
            artifacts / "content_quality_validation.json",
        ]
    )
    _run(
        [
            python_cmd,
            SCRIPT_DIR / "template_analyzer.py",
            "--template",
            TEMPLATE,
            "--layout-config",
            ROOT_DIR / "templates" / "layout_config.json",
            "--output",
            template_profile_path,
        ]
    )
    _run(
        [
            python_cmd,
            SCRIPT_DIR / "template_fit.py",
            "--renderer-spec",
            run_dir / "renderer_spec.json",
            "--template-profile",
            template_profile_path,
            "--output",
            artifacts / "template_fit_validation.json",
            "--fit-plan-output",
            artifacts / "template_fit_plan.json",
        ]
    )
    _run(
        [
            python_cmd,
            SCRIPT_DIR / "validate_stage_gate.py",
            "--stage",
            "pre_ppt",
            "--run-dir",
            run_dir,
            "--source-registry",
            SOURCE_REGISTRY,
            "--output",
            artifacts / "stage_gate_pre_ppt_validation.json",
        ]
    )


def render(run_dir: Path, python_cmd: str, *, skip_preflight: bool = False) -> None:
    _append_failure_memory(run_dir, "pipeline_render", outcome="start", command=f"{python_cmd} {Path('scripts/pipeline.py')} render --run-dir {run_dir}")
    run_dir = _ensure_run_dir(run_dir)
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(exist_ok=True)
    if not skip_preflight:
        _preflight(run_dir)
    _write_run_flags(run_dir, entrypoint="scripts/pipeline.py render", preflight_skipped=skip_preflight)

    try:
        validate_pre_ppt(run_dir, python_cmd)
        _run(
            [
                python_cmd,
                SCRIPT_DIR / "check_template_tokens.py",
                "--template",
                TEMPLATE,
                "--ppt-mapping",
                PPT_MAPPING,
                "--output",
                artifacts / "template_token_check.json",
                "--fail-on-diff",
            ]
        )
        _run(
            [
                python_cmd,
                SCRIPT_DIR / "generate_replacement_dict.py",
                "--renderer-spec",
                run_dir / "renderer_spec.json",
                "--ppt-mapping",
                PPT_MAPPING,
                "--output",
                run_dir / "replacement_dict.json",
            ]
        )
        _run(
            [
                python_cmd,
                SCRIPT_DIR / "validate_replacement_dict.py",
                "--replacement-dict",
                run_dir / "replacement_dict.json",
                "--renderer-spec",
                run_dir / "renderer_spec.json",
                "--ppt-mapping",
                PPT_MAPPING,
                "--output",
                artifacts / "replacement_dict_validation.json",
            ]
        )
        _run(
            [
                python_cmd,
                SCRIPT_DIR / "fill_ppt_tokens.py",
                "--template",
                TEMPLATE,
                "--replacement-dict",
                run_dir / "replacement_dict.json",
                "--output",
                run_dir / FILLED_PPT,
                "--log",
                artifacts / "fill_ppt_tokens.log.json",
            ]
        )
        _run(
            [
                python_cmd,
                SCRIPT_DIR / "clean_filled_ppt.py",
                "--input",
                run_dir / FILLED_PPT,
                "--control-file",
                run_dir / "renderer_spec.json",
                "--output",
                run_dir / CLEAN_PPT,
                "--log",
                artifacts / "clean_filled_ppt.log.json",
            ]
        )
        _run(
            [
                python_cmd,
                SCRIPT_DIR / "postprocess_ppt_visuals.py",
                "--input-ppt",
                run_dir / CLEAN_PPT,
                "--renderer-spec",
                run_dir / "renderer_spec.json",
                "--output",
                run_dir / CLEAN_PPT,
                "--template-profile",
                artifacts / "template_profile.json",
                "--render-layouts",
                RENDER_LAYOUTS,
                "--log",
                artifacts / "postprocess_ppt_visuals.log.json",
                "--fail-on-unrendered",
            ]
        )
        _run(
            [
                python_cmd,
                SCRIPT_DIR / "validate_filled_ppt.py",
                "--filled-ppt",
                run_dir / FILLED_PPT,
                "--clean-ppt",
                run_dir / CLEAN_PPT,
                "--control-file",
                run_dir / "renderer_spec.json",
                "--replacement-dict",
                run_dir / "replacement_dict.json",
                "--ppt-mapping",
                PPT_MAPPING,
                "--output",
                run_dir / "filled_ppt_validation.json",
                "--fail-on-issue",
            ]
        )
        finalize(run_dir, python_cmd, require_client_ready=True)
        _clear_not_client_ready(run_dir)
    except Exception:
        _append_failure_memory(
            run_dir,
            "pipeline_render",
            outcome="failure",
            command=f"{python_cmd} {Path('scripts/pipeline.py')} render --run-dir {run_dir}",
            details={"skip_preflight": skip_preflight},
        )
        _mark_not_client_ready(run_dir)
        raise
    else:
        _append_failure_memory(
            run_dir,
            "pipeline_render",
            outcome="success",
            command=f"{python_cmd} {Path('scripts/pipeline.py')} render --run-dir {run_dir}",
            details={"skip_preflight": skip_preflight},
        )


def finalize(run_dir: Path, python_cmd: str, *, require_client_ready: bool) -> None:
    run_dir = _ensure_run_dir(run_dir)
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(exist_ok=True)
    _write_run_flags(run_dir, entrypoint="scripts/pipeline.py finalize")
    cmd = [
        python_cmd,
        SCRIPT_DIR / "validate_final_delivery.py",
        "--run-dir",
        run_dir,
        "--source-registry",
        SOURCE_REGISTRY,
        "--output",
        artifacts / "final_delivery_validation.json",
    ]
    if require_client_ready:
        cmd.append("--require-client-ready")
    final_returncode = _run_returncode(cmd)
    if final_returncode != 0:
        _append_failure_memory(
            run_dir,
            "pipeline_finalize",
            outcome="failure",
            command=" ".join(str(part) for part in cmd),
            details={"require_client_ready": require_client_ready, "return_code": final_returncode},
        )
        _mark_not_client_ready(run_dir)
        raise PipelineError(
            "final delivery gate failed; see artifacts/final_delivery_validation.json "
            "and artifacts/run_quality_summary.json for repair targets"
        )
    _append_failure_memory(
        run_dir,
        "pipeline_finalize",
        outcome="success",
        command=" ".join(str(part) for part in cmd),
        details={"require_client_ready": require_client_ready, "return_code": final_returncode},
    )
    _run([python_cmd, SCRIPT_DIR / "generate_run_quality_summary.py", "--run-dir", run_dir])
    if run_dir.name.startswith("attempt_"):
        runs_dir = run_dir.parent
        (runs_dir / "ACTIVE_ATTEMPT.txt").write_text(run_dir.name + "\n", encoding="utf-8")
        _run([python_cmd, SCRIPT_DIR / "update_runs_index.py", "--runs-dir", runs_dir])


def status(run_dir: Path) -> None:
    print(json.dumps(validate_run_state(_ensure_run_dir(run_dir)), ensure_ascii=False, indent=2))


def next_action(run_dir: Path) -> None:
    from workflow import next_payload

    print(json.dumps(next_payload(_ensure_run_dir(run_dir)), ensure_ascii=False, indent=2))


def _check_tool_integrity() -> None:
    """Verify critical pipeline functions have not been patched at runtime.

    This is a lightweight behavioral check: it inspects the source of key
    functions for markers that would be lost if an agent replaced them with
    stubs (e.g., forcing is_valid=True, swallowing exceptions). If tampering
    is detected, the pipeline refuses to run.
    """
    import inspect

    checks = {
        "_preflight": "PipelineError",
        "finalize": "PipelineError",
        "validate_pre_ppt": "_run(",
        "render": "_mark_not_client_ready",
    }
    for func_name, marker in checks.items():
        func = globals().get(func_name)
        if func is None:
            raise PipelineError(f"tool integrity: {func_name} is missing; do not modify pipeline.py")
        src = inspect.getsource(func)
        if marker not in src:
            raise PipelineError(
                f"tool integrity: {func_name} appears to have been modified "
                f"(expected marker '{marker}' not found). "
                "Do not patch pipeline.py to bypass gates. "
                "Repair the upstream artifact instead."
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", default=sys.executable, help="Python interpreter used for child scripts.")
    sub = parser.add_subparsers(dest="command", required=True)
    render_parser = None
    finalize_parser = None
    for name in ("status", "next", "validate-pre-ppt", "render", "finalize"):
        p = sub.add_parser(name)
        p.add_argument("--run-dir", required=True)
        if name == "render":
            render_parser = p
        elif name == "finalize":
            finalize_parser = p

    if render_parser is None or finalize_parser is None:
        raise RuntimeError("failed to construct parser for render/finalize commands")

    render_parser.add_argument(
        "--skip-preflight",
        action="store_true",
        help="Only for repairing a run whose workflow status is stale but the operator has verified pre-PPT readiness.",
    )
    finalize_parser.add_argument("--require-client-ready", action="store_true")
    args = parser.parse_args()

    try:
        _check_tool_integrity()
        run_dir = Path(args.run_dir)
        if args.command == "status":
            status(run_dir)
        elif args.command == "next":
            next_action(run_dir)
        elif args.command == "validate-pre-ppt":
            validate_pre_ppt(_ensure_run_dir(run_dir), args.python)
        elif args.command == "render":
            render(_ensure_run_dir(run_dir), args.python, skip_preflight=args.skip_preflight)
        elif args.command == "finalize":
            finalize(_ensure_run_dir(run_dir), args.python, require_client_ready=args.require_client_ready)
    except subprocess.CalledProcessError as exc:
        return exc.returncode or 1
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

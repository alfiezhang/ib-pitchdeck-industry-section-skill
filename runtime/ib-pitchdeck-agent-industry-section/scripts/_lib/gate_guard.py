#!/usr/bin/env python3
"""Shared deterministic gate guard for PPT-producing scripts."""

from __future__ import annotations

import os
from typing import Any
from pathlib import Path

from json_utils import load_json_file


DEBUG_MARKER = "DEBUG_OUTPUT_ONLY.txt"


def _runtime_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "configs").is_dir() and (parent / "scripts").is_dir():
            return parent
    raise RuntimeError("Cannot locate runtime root for workflow policy")


def _default_max_repair_cycles() -> int:
    path = _runtime_root() / "configs" / "workflow_policy.json"
    try:
        payload = load_json_file(path)
        gate_retry = payload.get("gate_retry") if isinstance(payload, dict) else {}
        return int(gate_retry.get("default_max_repair_cycles") or 3) if isinstance(gate_retry, dict) else 3
    except Exception:
        return 3


DEFAULT_MAX_REPAIR_CYCLES = _default_max_repair_cycles()


def _gate_state_path(run_dir: Path) -> Path:
    return run_dir / "artifacts" / "gate_retry_state.json"


def load_state(run_dir: Path) -> dict[str, Any]:
    path = _gate_state_path(run_dir)
    if not path.exists():
        return {"schema_version": "gate_retry_state_v1", "gates": {}}
    data = load_json_file(path)
    if not isinstance(data, dict):
        return {"schema_version": "gate_retry_state_v1", "gates": {}}
    data.setdefault("schema_version", "gate_retry_state_v1")
    data.setdefault("gates", {})
    return data


def check_gate(
    run_dir: Path,
    gate: str,
    *,
    max_repair_cycles: int = DEFAULT_MAX_REPAIR_CYCLES,
) -> dict[str, Any]:
    state = load_state(run_dir)
    gate_state = (state.get("gates") or {}).get(gate) or {}
    failed_count = int(gate_state.get("failed_validation_count") or 0)
    blocked = gate_state.get("status") == "blocked" or failed_count > max_repair_cycles
    return {
        "is_blocked": blocked,
        "gate": gate,
        "run_dir": str(run_dir),
        "failed_validation_count": failed_count,
        "max_repair_cycles": max_repair_cycles,
        "state": gate_state,
    }


def mark_ungated_debug_run(run_dir: Path) -> None:
    """Record that a run used an ungated PPT debug bypass."""
    run_dir.mkdir(parents=True, exist_ok=True)
    marker = run_dir / DEBUG_MARKER
    if not marker.exists():
        marker.write_text(
            "This run used --allow-ungated-debug / IB_SKILL_ALLOW_UNGATED_DEBUG=1.\n"
            "It is not a formal delivery package. Do not copy generated PPTX files to final-looking names,\n"
            "do not update LATEST_FINAL_PPT.txt, and do not describe it as client-ready.\n",
            encoding="utf-8",
        )


def require_debug_output_name(output_path: Path) -> None:
    """Prevent ungated debug PPTs from looking like deliverables."""
    if output_path.suffix.lower() != ".pptx":
        return
    if "DEBUG_NOT_FOR_DELIVERY" not in output_path.name:
        raise RuntimeError(
            "ungated PPT output must include 'DEBUG_NOT_FOR_DELIVERY' in the filename. "
            "Debug PPTs must not use final-looking names."
        )


def _looks_like_formal_run(run_dir: Path) -> bool:
    """Return true when a directory contains formal-run artifacts.

    Ungated debug is meant for isolated template/render diagnostics. Once a
    directory contains the formal package of record, generation must be governed
    by the formal gates and retry state.
    """
    formal_foundation_markers = (
        run_dir / "input_card.json",
        run_dir / "artifacts/research_evidence_db.json",
        run_dir / "industry_research_pack.md",
        run_dir / "banker_page_pack.json",
        run_dir / "industry_section_filled.pptx",
        run_dir / "artifacts/run_flags.json",
    )
    formal_core_artifacts = (
        run_dir / "artifacts/research_evidence_db.json",
        run_dir / "industry_research_pack.md",
        run_dir / "banker_page_pack.json",
        run_dir / "deck_blueprint.json",
        run_dir / "template_registry.json",
        run_dir / "renderer_spec.json",
        run_dir / "replacement_dict.json",
        run_dir / "artifacts/industry_scope_pack.json",
    )
    evidence_chain = (
        run_dir / "artifacts/formal_search_plan.json",
        run_dir / "artifacts/source_archive/source_archive_index.json",
        run_dir / "artifacts/formal_research_execution_report.json",
    )

    # A formal package should look like a coherent pipeline state, not a
    # one-off diagnostic directory. Require both a baseline input marker and at
    # least one core evidence/deck artifact.
    foundation = any(path.exists() for path in formal_foundation_markers)
    core = any(path.exists() for path in formal_core_artifacts)
    if not (foundation and core):
        return False

    optional_checks = sum(path.exists() for path in evidence_chain)
    return optional_checks >= 1


def _blocked_retry_gates(run_dir: Path) -> list[str]:
    state = load_state(run_dir)
    gates = state.get("gates") if isinstance(state, dict) else {}
    if not isinstance(gates, dict):
        return []
    return [
        str(gate)
        for gate, gate_state in gates.items()
        if isinstance(gate_state, dict) and gate_state.get("status") == "blocked"
    ]


def _pre_ppt_gate_is_passing(run_dir: Path) -> bool:
    gate_path = run_dir / "artifacts" / "stage_gate_pre_ppt_validation.json"
    if not gate_path.exists():
        return False
    try:
        gate = load_json_file(gate_path)
    except Exception:
        return False
    return isinstance(gate, dict) and gate.get("is_valid") is True


def _reject_debug_on_formal_run_if_needed(run_dir: Path) -> None:
    if not _looks_like_formal_run(run_dir):
        return
    blocked = _blocked_retry_gates(run_dir)
    if blocked:
        raise RuntimeError(
            "ungated debug output is not allowed for this formal run package because "
            f"gate(s) are blocked after repeated failures: {', '.join(blocked)}. "
            "Run scripts/pipeline.py next and report the blocker instead of generating downstream artifacts."
        )
    if not _pre_ppt_gate_is_passing(run_dir):
        raise RuntimeError(
            "ungated debug output is not allowed for a formal run package without a passing pre-PPT gate. "
            "Use an isolated temporary directory for template/render diagnostics, or fix the formal package first."
        )


def require_pre_ppt_gate(run_dir: Path, *, allow_ungated_debug: bool = False) -> None:
    """Block PPT output when the deterministic pre-PPT gate is missing or failing."""
    if allow_ungated_debug:
        if os.environ.get("IB_SKILL_ALLOW_UNGATED_DEBUG") == "1":
            _reject_debug_on_formal_run_if_needed(run_dir)
            mark_ungated_debug_run(run_dir)
            return
        raise RuntimeError(
            "--allow-ungated-debug was requested, but IB_SKILL_ALLOW_UNGATED_DEBUG=1 is not set. "
            "This bypass is reserved for explicit local diagnostics and must not be used for delivery."
        )

    retry_state = check_gate(run_dir, "pre_ppt", max_repair_cycles=DEFAULT_MAX_REPAIR_CYCLES)
    if retry_state.get("is_blocked"):
        failed_count = retry_state.get("failed_validation_count", 0)
        max_cycles = retry_state.get("max_repair_cycles", DEFAULT_MAX_REPAIR_CYCLES)
        raise RuntimeError(
            "pre-PPT gate is blocked after repeated failures; refusing PPT output. "
            f"failed_validation_count={failed_count}, max_repair_cycles={max_cycles}. "
            f"State: {run_dir / 'artifacts' / 'gate_retry_state.json'}"
        )

    gate_path = run_dir / "artifacts" / "stage_gate_pre_ppt_validation.json"
    if not gate_path.exists():
        raise RuntimeError(
            f"missing required pre-PPT gate artifact: {gate_path}. "
            "Run scripts/pipeline.py validate --artifact pre_ppt first, or use --allow-ungated-debug only for local diagnostics."
        )

    try:
        gate = load_json_file(gate_path)
    except Exception as exc:
        raise RuntimeError(f"cannot read pre-PPT gate artifact {gate_path}: {exc}") from exc

    if not isinstance(gate, dict) or gate.get("is_valid") is not True:
        errors = gate.get("errors", []) if isinstance(gate, dict) else []
        preview = "; ".join(str(item) for item in errors[:5])
        if len(errors) > 5:
            preview += f"; plus {len(errors) - 5} more"
        raise RuntimeError(
            "pre-PPT gate is not passing; refusing to generate or mutate PPT output. "
            f"Gate: {gate_path}. {preview}"
        )

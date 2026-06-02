#!/usr/bin/env python3
"""Shared hard gate guard for PPT-producing scripts."""

from __future__ import annotations

import os
from pathlib import Path

from json_utils import load_json_file


def require_pre_ppt_gate(run_dir: Path, *, allow_ungated_debug: bool = False) -> None:
    """Block PPT output when the deterministic pre-PPT gate is missing or failing."""
    if allow_ungated_debug:
        if os.environ.get("IB_SKILL_ALLOW_UNGATED_DEBUG") == "1":
            return
        raise RuntimeError(
            "--allow-ungated-debug was requested, but IB_SKILL_ALLOW_UNGATED_DEBUG=1 is not set. "
            "This bypass is reserved for explicit local diagnostics and must not be used for delivery."
        )

    gate_path = run_dir / "artifacts" / "stage_gate_pre_ppt_validation.json"
    if not gate_path.exists():
        raise RuntimeError(
            f"missing required pre-PPT gate artifact: {gate_path}. "
            "Run scripts/validate_stage_gate.py --stage pre_ppt first, or use --allow-ungated-debug only for local diagnostics."
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

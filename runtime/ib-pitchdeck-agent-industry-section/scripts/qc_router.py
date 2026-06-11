#!/usr/bin/env python3
"""Route current run-state/QC failures to the correct repair role."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from qc_normalize_report import normalize_report
from validate_run_state import validate_run_state


ROLE_ACTIONS = {
    "material-intake": "Repair user material classification, extracted facts, or input_card transcription.",
    "knowledge-repository": "Repair research_evidence_db.json and regenerate derived research pack.",
    "industry-scoping": "Repair industry boundary, excluded scope, data hierarchy, or unvalidated leads.",
    "research-external-evidence": "Repair search/source/archive/formal execution accounting using actual reviewed sources only.",
    "reasoning": "Repair issue analysis, hypothesis resolution, allowed deck usage, or research request queue.",
    "generation": "Repair page arguments, deck_blueprint, evidence contract, or renderer spec by editing upstream page design.",
    "template": "Repair template profile/fit or return to generation when capacity is insufficient.",
    "qc": "Rerun or inspect gate validation and route the underlying upstream artifact.",
    "output": "Rerun deterministic output pipeline after upstream gates are current.",
    "orchestrator": "Stop downstream work, report blocker, and resume from workflow.py next.",
}


def payload_for_run(run_dir: Path) -> dict[str, Any]:
    state = validate_run_state(run_dir)
    role = str(state.get("repair_target_role") or state.get("owner_role") or "orchestrator")
    blocking_gate = str(state.get("blocking_gate") or "")
    payload = {
        "schema_version": "qc_router_report_v1",
        "run_dir": str(run_dir),
        "current_stage": state.get("current_stage"),
        "status": state.get("status"),
        "blocking_gate": blocking_gate,
        "issue_type": "workflow_gate_blocker" if state.get("status") != "passed" else "none",
        "severity": "blocking" if state.get("status") in {"missing", "failed", "stale", "blocked"} else "none",
        "repair_target_role": role,
        "repair_target_skill": state.get("owner_skill", ""),
        "repair_target_artifact": (state.get("missing_artifacts") or [""])[0]
        if state.get("missing_artifacts")
        else blocking_gate,
        "recommended_action": ROLE_ACTIONS.get(role, ROLE_ACTIONS["orchestrator"]),
        "forbidden_action": state.get("forbidden_actions", []),
        "state_message": state.get("message", ""),
        "missing_artifacts": state.get("missing_artifacts", []),
        "failed_validations": state.get("failed_validations", []),
        "stale_validations": state.get("stale_validations", []),
    }
    normalized = normalize_report(
        payload,
        default_layer=role,
        default_artifact=str(payload.get("repair_target_artifact") or blocking_gate),
        rerun_command=f"$PYTHON_CMD scripts/workflow.py next --run-dir {run_dir}",
    )
    payload["repair_schema_version"] = normalized["schema_version"]
    payload["is_valid"] = normalized["is_valid"]
    payload["blocking_issue_count"] = normalized["blocking_issue_count"]
    payload["issues"] = normalized["issues"]
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    payload = payload_for_run(Path(args.run_dir))
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

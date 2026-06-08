#!/usr/bin/env python3
"""Lightweight workflow harness for formal run state and next actions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from validate_run_state import validate_run_state


def status_payload(run_dir: Path) -> dict[str, Any]:
    return validate_run_state(run_dir)


def next_payload(run_dir: Path) -> dict[str, Any]:
    state = validate_run_state(run_dir)
    payload = {
        "schema_version": "workflow_next_v1",
        "run_dir": state["run_dir"],
        "source_run_dir": state.get("source_run_dir", ""),
        "output_run_dir": state.get("output_run_dir", state["run_dir"]),
        "package_of_record": state.get("package_of_record", state["run_dir"]),
        "current_stage": state["current_stage"],
        "status": state["status"],
        "blocking_gate": state["blocking_gate"],
        "missing_artifacts": state.get("missing_artifacts", []),
        "failed_validations": state.get("failed_validations", []),
        "stale_validations": state.get("stale_validations", []),
        "retry_state": state.get("retry_state", {}),
        "allowed_next_actions": state["allowed_next_actions"],
        "forbidden_actions": state["forbidden_actions"],
        "debug_only": state["debug_only"],
        "final_delivery_valid": state["final_delivery_valid"],
        "message": state["message"],
    }
    if state["status"] in {"missing", "failed", "stale"}:
        payload["gate_policy"] = {
            "must_not_proceed_to_downstream": True,
            "must_fix_current_gate_first": True,
            "must_not_call_validator_failure_a_parsing_edge_case": True,
            "forbidden_until_gate_passes": state["forbidden_actions"],
        }
    if state["current_stage"] == "STOP_AND_REPORT":
        payload["repair_policy"] = {
            "must_stop_downstream_generation": True,
            "must_report_blocker_to_user": True,
            "must_audit_recent_edits": [
                "changed Opened/Reviewed to yes without source review",
                "removed broad_discovery search IDs instead of creating formal_research_execution searches",
                "cleared source_pack fields only to reduce domain count",
                "replaced official/filing domains with lower-authority media domains",
                "removed evidence or metric IDs only to pass validators",
            ],
        }
    return payload


def write_or_print(payload: dict[str, Any], output: str | None) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if output:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text + "\n", encoding="utf-8")
    print(text)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Report formal workflow status and allowed next actions for a run directory."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name in ("status", "next"):
        sub = subparsers.add_parser(name)
        sub.add_argument("--run-dir", required=True)
        sub.add_argument("--output")

    args = parser.parse_args()
    run_dir = Path(args.run_dir)
    if args.command == "status":
        payload = status_payload(run_dir)
    else:
        payload = next_payload(run_dir)
    write_or_print(payload, args.output)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Compatibility wrapper for the legacy workflow.py entrypoint.

The public state dashboard is now ``scripts/state_report.py``.  This wrapper
exists so older commands and tests do not fail, but it should not be treated as
a workflow controller.  The main LLM agent drives the engagement and uses state
reports only as an instrument panel.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import state_report as _state_report
from state_report import recommended_commands, status_payload
from state_report import next_payload as _state_next_payload


validate_run_state = _state_report.validate_run_state


def _with_legacy_fields(payload: dict[str, Any]) -> dict[str, Any]:
    """Expose old field names for existing callers while preserving new semantics."""
    compat = dict(payload)
    compat.setdefault("schema_version", "workflow_next_compat_v1")
    if "candidate_next_actions" in compat:
        compat.setdefault("allowed_next_actions", compat["candidate_next_actions"])
    if "downstream_risks" in compat:
        compat.setdefault("forbidden_actions", compat["downstream_risks"])
    compat.setdefault("workflow_role", "legacy_alias_for_state_report")
    compat.setdefault(
        "workflow_policy",
        {
            "script_authority": "observed_state_and_suggested_actions_only",
            "main_agent_is_driver": True,
            "prefer": "scripts/state_report.py next",
        },
    )
    return compat


def next_payload(run_dir: Path) -> dict[str, Any]:
    previous = _state_report.validate_run_state
    _state_report.validate_run_state = validate_run_state
    try:
        return _with_legacy_fields(_state_next_payload(run_dir))
    finally:
        _state_report.validate_run_state = previous


def write_or_print(payload: dict[str, Any], output: str | None) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if output:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text + "\n", encoding="utf-8")
    print(text)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Legacy alias for scripts/state_report.py. Prefer state_report.py for new runs."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name in ("status", "next"):
        sub = subparsers.add_parser(name)
        sub.add_argument("--run-dir", required=True)
        sub.add_argument("--output")

    args = parser.parse_args()
    run_dir = Path(args.run_dir)
    if args.command == "status":
        payload = _with_legacy_fields(status_payload(run_dir))
    else:
        payload = next_payload(run_dir)
    write_or_print(payload, args.output)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Track repeated validation-gate failures for one run attempt.

The workflow intentionally does not auto-repair artifacts. This state file gives
orchestrators a deterministic stop condition: after the same gate fails too many
times, further repair attempts should stop and human review is required.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from json_utils import load_json_file


DEFAULT_MAX_REPAIR_CYCLES = 3


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def state_path(run_dir: Path) -> Path:
    return run_dir / "artifacts" / "gate_retry_state.json"


def load_state(run_dir: Path) -> dict[str, Any]:
    path = state_path(run_dir)
    if not path.exists():
        return {"schema_version": "gate_retry_state_v1", "gates": {}}
    data = load_json_file(path)
    if not isinstance(data, dict):
        return {"schema_version": "gate_retry_state_v1", "gates": {}}
    data.setdefault("schema_version", "gate_retry_state_v1")
    data.setdefault("gates", {})
    return data


def write_state(run_dir: Path, state: dict[str, Any]) -> None:
    path = state_path(run_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _messages_from_result(result: dict[str, Any]) -> list[str]:
    messages: list[str] = []
    for key in ("errors", "blocking_issues"):
        values = result.get(key)
        if isinstance(values, list):
            messages.extend(str(item) for item in values)
    root_causes = result.get("root_causes")
    if isinstance(root_causes, list):
        for item in root_causes:
            if not isinstance(item, dict):
                messages.append(str(item))
                continue
            code = str(item.get("code") or "").strip()
            slide_no = str(item.get("slide_no") or "").strip()
            message = str(item.get("message") or "").strip()
            repair_hint = str(item.get("repair_hint") or "").strip()
            parts = [part for part in (code, f"slide {slide_no}" if slide_no else "", message, repair_hint) if part]
            if parts:
                messages.append(" | ".join(parts))
    return messages


def _fingerprint(messages: list[str]) -> str:
    normalized = "\n".join(sorted(message.strip() for message in messages if message.strip()))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest() if normalized else ""


def record_gate(
    run_dir: Path,
    gate: str,
    result_path: Path,
    *,
    max_repair_cycles: int = DEFAULT_MAX_REPAIR_CYCLES,
) -> dict[str, Any]:
    state = load_state(run_dir)
    gates = state.setdefault("gates", {})
    gate_state = gates.setdefault(
        gate,
        {
            "failed_validation_count": 0,
            "max_repair_cycles": max_repair_cycles,
            "status": "not_run",
            "history": [],
        },
    )
    gate_state["max_repair_cycles"] = max_repair_cycles

    if result_path.exists():
        result = load_json_file(result_path)
        if not isinstance(result, dict):
            result = {"is_valid": False, "errors": [f"{result_path} did not contain a JSON object"]}
    else:
        result = {"is_valid": False, "errors": [f"missing gate result: {result_path}"]}

    is_valid = result.get("is_valid") is True
    messages = _messages_from_result(result)
    fingerprint = _fingerprint(messages)
    timestamp = now_iso()

    if is_valid:
        gate_state.update(
            {
                "status": "passed",
                "failed_validation_count": 0,
                "last_error_fingerprint": "",
                "last_errors": [],
                "updated_at": timestamp,
            }
        )
    else:
        failed_count = int(gate_state.get("failed_validation_count") or 0) + 1
        blocked = failed_count > max_repair_cycles
        gate_state.update(
            {
                "status": "blocked" if blocked else "failed",
                "failed_validation_count": failed_count,
                "last_error_fingerprint": fingerprint,
                "last_errors": messages[:20],
                "updated_at": timestamp,
                "blocked_reason": (
                    f"Gate '{gate}' failed {failed_count} time(s), exceeding max_repair_cycles={max_repair_cycles}."
                    if blocked
                    else ""
                ),
            }
        )

    history = gate_state.setdefault("history", [])
    history.append(
        {
            "timestamp": timestamp,
            "is_valid": is_valid,
            "error_fingerprint": fingerprint,
            "error_count": len(messages),
            "result_path": str(result_path),
        }
    )
    if len(history) > 20:
        del history[:-20]

    write_state(run_dir, state)
    return gate_state


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Track validation-gate retry state.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    record_parser = subparsers.add_parser("record", help="Record one gate validation result.")
    record_parser.add_argument("--run-dir", required=True)
    record_parser.add_argument("--gate", required=True)
    record_parser.add_argument("--result", required=True)
    record_parser.add_argument("--max-repair-cycles", type=int, default=DEFAULT_MAX_REPAIR_CYCLES)

    check_parser = subparsers.add_parser("check", help="Check whether a gate is blocked.")
    check_parser.add_argument("--run-dir", required=True)
    check_parser.add_argument("--gate", required=True)
    check_parser.add_argument("--max-repair-cycles", type=int, default=DEFAULT_MAX_REPAIR_CYCLES)

    args = parser.parse_args()
    run_dir = Path(args.run_dir)
    if args.command == "record":
        result = record_gate(
            run_dir,
            args.gate,
            Path(args.result),
            max_repair_cycles=args.max_repair_cycles,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if result.get("status") == "blocked":
            raise SystemExit(2)
    else:
        result = check_gate(run_dir, args.gate, max_repair_cycles=args.max_repair_cycles)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if result["is_blocked"]:
            raise SystemExit(2)


if __name__ == "__main__":
    main()

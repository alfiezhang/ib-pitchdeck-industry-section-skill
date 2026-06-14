#!/usr/bin/env python3
"""Emit a delivery-safe run status summary for agents to quote."""

from __future__ import annotations

# Runtime scripts can be run directly. Shared helpers remain in runtime
# `scripts/`; production tools live under role scripts; validators live under QC.
import sys as _ib_sys
from pathlib import Path as _IbPath
_IB_ROLE_SCRIPT_DIR = _IbPath(__file__).resolve().parent
_IB_RUNTIME_ROOT = next(
    _p for _p in _IbPath(__file__).resolve().parents
    if (_p / 'configs').is_dir() and (_p / 'scripts').is_dir()
)
_IB_SHARED_SCRIPT_DIR = _IB_RUNTIME_ROOT / "scripts"
_IB_ROLE_SCRIPT_DIRS = sorted(_p for _p in (_IB_RUNTIME_ROOT / 'scripts').iterdir() if _p.is_dir())
_IB_QC_VALIDATOR_DIRS = sorted((_IB_RUNTIME_ROOT / 'scripts' / 'qc' / 'validators').glob('*'))
_IB_IMPORT_PATHS = [str(_IB_ROLE_SCRIPT_DIR)]
for _ib_dir in [*_IB_ROLE_SCRIPT_DIRS, *_IB_QC_VALIDATOR_DIRS]:
    _ib_text = str(_ib_dir)
    if _ib_text not in _IB_IMPORT_PATHS:
        _IB_IMPORT_PATHS.append(_ib_text)
_IB_IMPORT_PATHS.append(str(_IB_SHARED_SCRIPT_DIR))
for _ib_path in list(_IB_IMPORT_PATHS):
    if _ib_path in _ib_sys.path:
        _ib_sys.path.remove(_ib_path)
for _ib_path in reversed(_IB_IMPORT_PATHS):
    _ib_sys.path.insert(0, _ib_path)

import argparse
import json
from pathlib import Path
from typing import Any

from validate_run_state import validate_run_state


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def build_report(run_dir: Path) -> dict[str, Any]:
    state = validate_run_state(run_dir)
    final_gate = _load_json(run_dir / "artifacts" / "final_delivery_validation.json")
    content_gate = _load_json(run_dir / "artifacts" / "content_quality_validation.json")
    chart_gate = _load_json(run_dir / "artifacts" / "chart_metric_binding_validation.json")
    deck_blueprint_gate = _load_json(run_dir / "artifacts" / "deck_blueprint_validation.json")
    replacement_gate = _load_json(run_dir / "artifacts" / "replacement_dict_validation.json")
    filled_gate = _load_json(run_dir / "filled_ppt_validation.json")

    debug_ppts = sorted(path.name for path in run_dir.glob("*DEBUG_NOT_FOR_DELIVERY*.pptx"))
    not_client_ready_ppts = sorted(path.name for path in run_dir.glob("*NOT_CLIENT_READY*.pptx"))
    final_pointer = run_dir.parent / "LATEST_FINAL_PPT.txt"
    final_pointer_text = final_pointer.read_text(encoding="utf-8").strip() if final_pointer.exists() else ""
    pointed_ppt = Path(final_pointer_text).expanduser() if final_pointer_text else None
    latest_final_pointer_valid = bool(pointed_ppt and pointed_ppt.exists())
    final_gate_ready_without_pointer = bool(state.get("final_delivery_valid"))
    client_ready = final_gate_ready_without_pointer and latest_final_pointer_valid

    return {
        "schema_version": "run_status_report_v1",
        "run_dir": str(run_dir),
        "current_stage": state.get("current_stage"),
        "blocking_gate": state.get("blocking_gate"),
        "status": state.get("status"),
        "client_ready": client_ready,
        "debug_only": state.get("debug_only"),
        "formal_delivery_ppt": final_pointer_text if client_ready else "",
        "debug_ppts": debug_ppts,
        "not_client_ready_ppts": not_client_ready_ppts,
        "latest_final_pointer": final_pointer_text,
        "latest_final_pointer_valid": latest_final_pointer_valid,
        "final_gate_ready_without_pointer": final_gate_ready_without_pointer,
        "candidate_next_actions": state.get("allowed_next_actions", []),
        "downstream_risks": state.get("forbidden_actions", []),
        "failed_validations": state.get("failed_validations", []),
        "chart_metric_binding": {
            "is_valid": chart_gate.get("is_valid"),
            "root_causes": chart_gate.get("root_causes", []),
            "errors": chart_gate.get("errors", []),
        },
        "deck_blueprint": {
            "is_valid": deck_blueprint_gate.get("is_valid"),
            "errors": deck_blueprint_gate.get("errors", []),
        },
        "replacement_dict": {
            "is_valid": replacement_gate.get("is_valid"),
            "errors": replacement_gate.get("errors", []),
        },
        "content_quality": {
            "is_valid": content_gate.get("is_valid"),
            "blocking_issue_count": content_gate.get("blocking_issue_count", 0),
            "root_causes": content_gate.get("root_causes", []),
        },
        "filled_ppt_validation": {
            "is_valid": filled_gate.get("is_valid"),
            "errors": filled_gate.get("errors", []),
        },
        "final_delivery_validation": {
            "is_valid": final_gate.get("is_valid"),
            "client_ready": final_gate.get("client_ready"),
            "errors": final_gate.get("errors", []),
            "warnings": final_gate.get("warnings", []),
        },
        "message": (
            "Formal delivery is complete only when client_ready=true and formal_delivery_ppt is populated."
            if client_ready
            else "Not a formal delivery. Do not describe debug PPTs or pointer-less runs as final or client-ready."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Report run delivery status without optimistic language.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--output", help="Optional JSON output path.")
    args = parser.parse_args()

    report = build_report(Path(args.run_dir))
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

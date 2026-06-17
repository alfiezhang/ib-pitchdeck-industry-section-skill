#!/usr/bin/env python3
"""Build page_argument_pack.json from issue analysis and hypothesis handling."""

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
_IB_SHARED_SCRIPT_DIR = _IB_RUNTIME_ROOT / "scripts" / "_lib"
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

from json_utils import load_json_file


def text(value: Any) -> str:
    return str(value or "").strip()


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _analyses(issue_analysis: dict[str, Any]) -> list[dict[str, Any]]:
    raw = issue_analysis.get("issue_analyses")
    if raw is None:
        raw = issue_analysis.get("analyses")
    return [item for item in as_list(raw) if isinstance(item, dict)]


def _analysis_id(item: dict[str, Any], idx: int) -> str:
    return text(item.get("analysis_id") or item.get("issue_analysis_id") or item.get("id") or f"IA-{idx:03d}")


def build_pack(issue_analysis: dict[str, Any], hypothesis_store: dict[str, Any]) -> dict[str, Any]:
    hypotheses = {
        text(item.get("issue_analysis_id")): item
        for item in as_list(hypothesis_store.get("hypotheses"))
        if isinstance(item, dict) and text(item.get("issue_analysis_id"))
    }
    page_arguments: list[dict[str, Any]] = []
    for idx, item in enumerate(_analyses(issue_analysis), start=1):
        analysis_id = _analysis_id(item, idx)
        permission = text(item.get("downstream_permission") or item.get("allowed_deck_usage"))
        evidence_status = text(item.get("evidence_status") or item.get("status") or item.get("support_status"))
        if permission in {"not_allowed", "research_backlog_only"} or evidence_status in {"not_researched", "rejected"}:
            continue
        hypothesis = hypotheses.get(analysis_id, {})
        resolution = text(hypothesis.get("resolution_status"))
        allowed_usage = text(item.get("allowed_deck_usage") or hypothesis.get("allowed_use_before_resolution") or "body_only")
        page_arguments.append(
            {
                "page_argument_id": f"PA-{len(page_arguments) + 1:03d}",
                "source_issue_analysis_id": analysis_id,
                "issue_area": text(item.get("issue_area")),
                "subissue": text(item.get("subissue")),
                "client_question": text(item.get("client_question") or item.get("research_question")),
                "page_argument": text(item.get("page_argument") or item.get("judgment") or item.get("finding") or item.get("summary")),
                "evidence_status": evidence_status or "directional",
                "allowed_deck_usage": allowed_usage,
                "hypothesis_resolution_status": resolution,
                "evidence_ids": as_list(item.get("evidence_ids")),
                "metric_ids": as_list(item.get("metric_ids")),
                "caveat_or_diligence_question": text(hypothesis.get("caveat_text")),
                "generation_instruction": "Use as page thesis only if allowed_deck_usage permits; otherwise use as body/caveat/open question.",
            }
        )
    return {
        "schema_version": "page_argument_pack_v1",
        "policy_context": "pre_mandate_client_pitch",
        "page_arguments": page_arguments,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--issue-analysis", required=True)
    parser.add_argument("--hypothesis-store")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    issue_analysis = load_json_file(Path(args.issue_analysis))
    hypothesis_store = load_json_file(Path(args.hypothesis_store)) if args.hypothesis_store and Path(args.hypothesis_store).exists() else {}
    payload = build_pack(issue_analysis, hypothesis_store)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"is_valid": True, "output": str(output), "page_argument_count": len(payload["page_arguments"])}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

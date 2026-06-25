#!/usr/bin/env python3
"""Build artifacts/research_evidence_db.json skeleton from formal research artifacts."""

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

from research_evidence_db import build_db, load_optional_json


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-card", required=True)
    parser.add_argument("--scope-pack", required=True)
    parser.add_argument("--formal-search-plan", required=True)
    parser.add_argument("--formal-research-execution-report", required=True)
    parser.add_argument("--source-archive-index", required=True)
    parser.add_argument("--research-graph-state", required=True)
    parser.add_argument("--material-manifest")
    parser.add_argument("--material-extracts")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    payload = build_db(
        input_card=load_optional_json(args.input_card),
        scope_pack=load_optional_json(args.scope_pack),
        formal_search_plan=load_optional_json(args.formal_search_plan),
        execution_report=load_optional_json(args.formal_research_execution_report),
        source_reviews={},
        source_archive_index=load_optional_json(args.source_archive_index),
        research_graph_state=load_optional_json(args.research_graph_state),
        material_manifest=load_optional_json(args.material_manifest),
        material_extracts=load_optional_json(args.material_extracts),
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "is_valid": True,
                "output": str(output_path),
                "source_material_count": len(payload.get("source_materials") or []),
                "formal_extract_count": len(payload.get("formal_research_extracts") or []),
                "evidence_skeleton_count": len(payload.get("evidence_ledger") or []),
                "metric_skeleton_count": len(payload.get("metric_reconciliation") or []),
                "note": "Skeleton contains TODO markers. LLM must edit research_evidence_db.json, then validate and export industry_research_pack.md.",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

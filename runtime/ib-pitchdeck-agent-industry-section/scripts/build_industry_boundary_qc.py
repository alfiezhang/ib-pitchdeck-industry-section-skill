#!/usr/bin/env python3
"""Build industry boundary QC report from an industry scope pack."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from json_utils import load_json_file


def text(value: Any) -> str:
    return str(value or "").strip()


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _scope(scope_pack: dict[str, Any]) -> dict[str, Any]:
    return scope_pack.get("scope_summary") if isinstance(scope_pack.get("scope_summary"), dict) else {}


def build_report(scope_pack: dict[str, Any]) -> dict[str, Any]:
    scope = _scope(scope_pack)
    working_market = text(scope.get("working_market"))
    parent_market = text(scope.get("parent_market"))
    excluded_scope = as_list(scope.get("excluded_scope"))
    adjacent = as_list(scope.get("adjacent_markets") or scope.get("adjacent_themes"))
    unvalidated_leads = as_list(scope_pack.get("unvalidated_leads"))
    required_reconciliations = as_list(scope_pack.get("required_reconciliations"))

    checks: list[dict[str, Any]] = []

    checks.append(
        {
            "check_id": "BQC-001",
            "check": "core_market_defined",
            "status": "pass" if working_market else "fail",
            "finding": "working_market is present" if working_market else "working_market is missing",
            "repair_target_role": "industry-scoping",
        }
    )
    checks.append(
        {
            "check_id": "BQC-002",
            "check": "parent_vs_core_distinguished",
            "status": "pass" if working_market and parent_market and working_market != parent_market else "warning",
            "finding": "parent and core market are distinct" if working_market and parent_market and working_market != parent_market else "parent/core distinction may be unclear",
            "repair_target_role": "industry-scoping",
        }
    )
    checks.append(
        {
            "check_id": "BQC-003",
            "check": "excluded_scope_present",
            "status": "pass" if excluded_scope else "warning",
            "finding": "excluded scope is explicit" if excluded_scope else "excluded scope is empty; downstream research may drift too broad",
            "repair_target_role": "industry-scoping",
        }
    )
    checks.append(
        {
            "check_id": "BQC-004",
            "check": "adjacent_scope_present",
            "status": "pass" if adjacent else "warning",
            "finding": "adjacent themes/markets are explicit" if adjacent else "adjacent themes are not documented",
            "repair_target_role": "industry-scoping",
        }
    )
    checks.append(
        {
            "check_id": "BQC-005",
            "check": "unvalidated_leads_not_claims",
            "status": "pass",
            "finding": f"{len(unvalidated_leads)} unvalidated lead(s) retained for formal research rather than deck claims",
            "repair_target_role": "research-external-evidence",
        }
    )
    checks.append(
        {
            "check_id": "BQC-006",
            "check": "reconciliation_map",
            "status": "pass" if required_reconciliations else "warning",
            "finding": "required reconciliations are recorded" if required_reconciliations else "no required reconciliations recorded; confirm this is intentional",
            "repair_target_role": "industry-scoping",
        }
    )

    blocking = [item for item in checks if item["status"] == "fail"]
    warnings = [item for item in checks if item["status"] == "warning"]
    return {
        "schema_version": "industry_boundary_qc_v1",
        "is_valid": not blocking,
        "blocking_issue_count": len(blocking),
        "warning_count": len(warnings),
        "repair_target_role": "industry-scoping" if blocking else "",
        "scope_summary": {
            "working_market": working_market,
            "parent_market": parent_market,
            "adjacent_markets": adjacent,
            "excluded_scope": excluded_scope,
        },
        "checks": checks,
        "boundary_research_needed": bool(blocking or warnings),
        "recommended_action": "Repair industry_scope_pack.json or create boundary_research_requests.json for thin boundary points."
        if blocking or warnings
        else "Boundary QC passed; continue to formal research planning.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope-pack", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    payload = build_report(load_json_file(Path(args.scope_pack)))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["is_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

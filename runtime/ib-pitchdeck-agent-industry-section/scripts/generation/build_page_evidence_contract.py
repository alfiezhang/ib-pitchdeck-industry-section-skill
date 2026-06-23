#!/usr/bin/env python3
"""Build page_evidence_contract.json from page_argument_pack and a page plan.

The contract is authorized by selected page_argument_ids on each deck slide.
Issue-analysis IDs remain lineage fields and are not the contract source.
"""

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

from deck_blueprint_utils import normalize_deck_blueprint_for_page_plan, page_argument_pool_from_pack, selected_page_argument_ids
from json_utils import load_json_file


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _analysis_index(pool: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("analysis_id")): item
        for item in pool.get("issue_analyses") or []
        if isinstance(item, dict) and item.get("analysis_id")
    }


def _is_page_argument_pack(payload: dict[str, Any]) -> bool:
    return isinstance(payload.get("page_arguments"), list)


def _page_argument_index(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("page_argument_id") or "").strip(): item
        for item in _as_list(payload.get("page_arguments"))
        if isinstance(item, dict) and str(item.get("page_argument_id") or "").strip()
    }


def _analyses_for_slide(source: dict[str, Any], strategy_slide: dict[str, Any], global_analyses: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    if not _is_page_argument_pack(source):
        return global_analyses
    selected_ids = selected_page_argument_ids(strategy_slide)
    return _analysis_index(page_argument_pool_from_pack(source, selected_ids))


def _usage(analysis: dict[str, Any]) -> dict[str, Any]:
    usage = analysis.get("downstream_permission")
    return usage if isinstance(usage, dict) else {}


def _analysis_metric_ids(analysis: dict[str, Any]) -> set[str]:
    values = {str(item).strip() for item in _as_list(analysis.get("metric_ids")) if str(item).strip()}
    for point in _as_list(analysis.get("supporting_points")):
        if isinstance(point, dict):
            values.update(str(item).strip() for item in _as_list(point.get("metric_ids")) if str(item).strip())
    return values


def _analysis_evidence_ids(analysis: dict[str, Any]) -> set[str]:
    values = {str(item).strip() for item in _as_list(analysis.get("evidence_ids")) if str(item).strip()}
    for point in _as_list(analysis.get("supporting_points")):
        if isinstance(point, dict):
            values.update(str(item).strip() for item in _as_list(point.get("evidence_ids")) if str(item).strip())
    return values


VALID_EVIDENCE_STATUS = {
    "supported",
    "thin",
    "insufficient",
    "not_applicable",
    "unavailable_after_research",
    "not_researched",
    "caveat_only",
}


def _analysis_evidence_status(analysis: dict[str, Any]) -> str:
    raw_status = str(analysis.get("evidence_status") or "").strip()
    if raw_status in VALID_EVIDENCE_STATUS:
        return raw_status

    raw_evidence = str(analysis.get("evidence_sufficiency") or "").strip()
    if raw_evidence == "sufficient":
        return "supported"
    if raw_evidence in VALID_EVIDENCE_STATUS:
        return raw_evidence
    if str(analysis.get("status") or "").strip() == "rejected":
        return "not_researched"
    if not raw_status and not raw_evidence:
        return "not_researched"
    return raw_evidence if raw_evidence else "not_researched"


def _analysis_downstream_permission(analysis: dict[str, Any]) -> dict[str, bool]:
    allowed = analysis.get("allowed_deck_usage")
    if isinstance(allowed, dict):
        return {
            "headline_allowed": bool(allowed.get("headline") is True),
            "main_message_allowed": bool(allowed.get("main_message") is True),
            "chart_allowed": bool(allowed.get("chart") is True),
            "body_copy_allowed": bool(allowed.get("body_copy") is True),
        }
    usage = _usage(analysis)
    return {
        "headline_allowed": bool(usage.get("headline_allowed") is True),
        "main_message_allowed": bool(usage.get("headline_allowed") is True),
        "chart_allowed": bool(usage.get("chart_allowed") is True),
        "body_copy_allowed": bool(usage.get("body_copy_allowed") is True),
    }


def _page_argument_downstream_permission(argument: dict[str, Any]) -> dict[str, bool]:
    permission = argument.get("downstream_permission")
    if isinstance(permission, dict):
        return {
            "headline_allowed": permission.get("headline_allowed") is True,
            "main_message_allowed": permission.get("main_message_allowed") is True or permission.get("headline_allowed") is True,
            "chart_allowed": permission.get("chart_allowed") is True,
            "body_copy_allowed": permission.get("body_copy_allowed") is True,
        }
    usage = str(argument.get("allowed_deck_usage") or "").strip()
    return {
        "headline_allowed": usage == "headline_allowed",
        "main_message_allowed": usage == "headline_allowed",
        "chart_allowed": usage in {"headline_allowed", "body_only"},
        "body_copy_allowed": usage in {"headline_allowed", "body_only", "supporting_context", "context_only", "caveat_only"},
    }


def _selected_page_argument_permission_entries(source: dict[str, Any], strategy_slide: dict[str, Any]) -> list[dict[str, Any]]:
    if not _is_page_argument_pack(source):
        return []
    index = _page_argument_index(source)
    entries: list[dict[str, Any]] = []
    for argument_id in selected_page_argument_ids(strategy_slide):
        argument = index.get(argument_id)
        if not argument:
            continue
        permission = _page_argument_downstream_permission(argument)
        evidence_ids = _unique([str(item).strip() for item in _as_list(argument.get("evidence_ids")) if str(item).strip()])
        metric_ids = _unique([str(item).strip() for item in _as_list(argument.get("metric_ids")) if str(item).strip()])
        entries.append(
            {
                "page_argument_id": argument_id,
                "source_issue_analysis_id": str(argument.get("source_issue_analysis_id") or "").strip(),
                "evidence_status": _analysis_evidence_status(argument),
                "allowed_deck_usage": str(argument.get("allowed_deck_usage") or "").strip(),
                "downstream_permission": permission,
                "evidence_ids": evidence_ids,
                "metric_ids": metric_ids,
                "body_evidence_ids": evidence_ids if permission["body_copy_allowed"] else [],
                "body_metric_ids": metric_ids if permission["body_copy_allowed"] else [],
                "visual_metric_ids": metric_ids if permission["chart_allowed"] else [],
            }
        )
    return entries


EVIDENCE_STATUS_RANK = {
    "supported": 0,
    "thin": 1,
    "caveat_only": 2,
    "insufficient": 3,
    "unavailable_after_research": 4,
    "not_researched": 5,
}


def _aggregate_evidence_status(analysis_ids: list[str], analyses_by_id: dict[str, dict[str, Any]]) -> str:
    if not analysis_ids:
        return "insufficient"
    statuses = [_analysis_evidence_status(analyses_by_id.get(analysis_id) or {}) for analysis_id in analysis_ids if analysis_id]
    if not statuses:
        return "insufficient"
    unique = {status for status in statuses if status}
    if not unique:
        return "insufficient"
    if unique == {"not_applicable"}:
        return "not_applicable"
    usable = [status for status in unique if status != "not_applicable"]
    if not usable:
        return "not_applicable"
    return max(usable, key=lambda item: EVIDENCE_STATUS_RANK.get(item, -1))


def _union_permission(perms: list[dict[str, bool]]) -> dict[str, bool]:
    union: dict[str, bool] = {
        "headline_allowed": False,
        "main_message_allowed": False,
        "chart_allowed": False,
        "body_copy_allowed": False,
    }
    for perm in perms:
        for key in union:
            if perm.get(key) is True:
                union[key] = True
    return union


def _entry_ids(entries: list[dict[str, Any]], field: str) -> list[str]:
    return _unique(
        [
            str(item).strip()
            for entry in entries
            for item in _as_list(entry.get(field))
            if str(item).strip()
        ]
    )


def _aggregate_entry_evidence_status(entries: list[dict[str, Any]]) -> str:
    if not entries:
        return "insufficient"
    statuses = [str(entry.get("evidence_status") or "").strip() for entry in entries if str(entry.get("evidence_status") or "").strip()]
    if not statuses:
        return "insufficient"
    unique = {status for status in statuses if status}
    if unique == {"not_applicable"}:
        return "not_applicable"
    usable = [status for status in unique if status != "not_applicable"]
    if not usable:
        return "not_applicable"
    return max(usable, key=lambda item: EVIDENCE_STATUS_RANK.get(item, -1))


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        text = str(item or "").strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def _selected_analysis_ids(slide: dict[str, Any]) -> list[str]:
    primary = str(slide.get("primary_issue_analysis_id") or "").strip()
    supporting = [str(item).strip() for item in _as_list(slide.get("supporting_issue_analysis_ids")) if str(item).strip()]
    return ([primary] if primary else []) + supporting


def _proof_metric_ids(slide: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for point in _as_list(slide.get("proof_points")):
        if isinstance(point, dict):
            values.extend(str(item).strip() for item in _as_list(point.get("metric_ids")) if str(item).strip())
    return _unique(values)


def _visual_metric_ids(slide: dict[str, Any], fallback_metric_ids: list[str]) -> list[str]:
    visual_plan = slide.get("visual_plan") if isinstance(slide.get("visual_plan"), dict) else {}
    if isinstance(visual_plan.get("visual_metric_ids"), list):
        return _unique([str(item).strip() for item in visual_plan.get("visual_metric_ids") if str(item).strip()])
    return fallback_metric_ids


def _proof_evidence_ids(slide: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for point in _as_list(slide.get("proof_points")):
        if isinstance(point, dict):
            values.extend(str(item).strip() for item in _as_list(point.get("evidence_ids")) if str(item).strip())
    return _unique(values)


def _proof_points(slide: dict[str, Any]) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    for point in _as_list(slide.get("proof_points")):
        if not isinstance(point, dict):
            continue
        item = {
            "point": str(point.get("point") or "").strip(),
            "source_analysis_ids": _unique(
                [str(value).strip() for value in _as_list(point.get("source_analysis_ids")) if str(value).strip()]
            ),
            "evidence_ids": _unique(
                [str(value).strip() for value in _as_list(point.get("evidence_ids")) if str(value).strip()]
            ),
            "metric_ids": _unique(
                [str(value).strip() for value in _as_list(point.get("metric_ids")) if str(value).strip()]
            ),
            "claim_strength": str(point.get("claim_strength") or "").strip(),
        }
        visual_role = str(point.get("visual_role") or "").strip()
        if visual_role:
            item["visual_role"] = visual_role
        caveat = str(point.get("caveat") or "").strip()
        if caveat:
            item["caveat"] = caveat
        points.append(item)
    return points


def _permitted_proof_ids(
    slide: dict[str, Any],
    analyses_by_id: dict[str, dict[str, Any]],
    *,
    id_field: str,
    permission_field: str,
) -> list[str]:
    values: list[str] = []
    for point in _as_list(slide.get("proof_points")):
        if not isinstance(point, dict):
            continue
        point_ids = [str(item).strip() for item in _as_list(point.get(id_field)) if str(item).strip()]
        if not point_ids:
            continue
        source_ids = [str(item).strip() for item in _as_list(point.get("source_analysis_ids")) if str(item).strip()]
        permitted: set[str] = set()
        for analysis_id in source_ids:
            analysis = analyses_by_id.get(analysis_id) or {}
            if _usage(analysis).get(permission_field) is not True:
                continue
            if id_field == "metric_ids":
                permitted.update(_analysis_metric_ids(analysis))
            elif id_field == "evidence_ids":
                permitted.update(_analysis_evidence_ids(analysis))
        values.extend(item for item in point_ids if item in permitted)
    return _unique(values)


def build_page_evidence_contract(source_permissions: dict[str, Any], page_plan: dict[str, Any]) -> dict[str, Any]:
    global_analyses_by_id = _analysis_index(source_permissions)
    slides = []
    for strategy_slide in page_plan.get("slides") or []:
        if not isinstance(strategy_slide, dict):
            continue
        analyses_by_id = _analyses_for_slide(source_permissions, strategy_slide, global_analyses_by_id)
        page_argument_permissions = _selected_page_argument_permission_entries(source_permissions, strategy_slide)
        slide_no = strategy_slide.get("slide_no")
        primary_id = str(strategy_slide.get("primary_issue_analysis_id") or "").strip()
        primary = analyses_by_id.get(primary_id, {})
        visual_plan = strategy_slide.get("visual_plan") if isinstance(strategy_slide.get("visual_plan"), dict) else {}
        capability = str(visual_plan.get("required_capability") or "").strip()
        issue_ids = _selected_analysis_ids(strategy_slide)
        issue_permissions = [_analysis_downstream_permission(analyses_by_id.get(analysis_id) or {}) for analysis_id in issue_ids]
        evidence_status = (
            _aggregate_entry_evidence_status(page_argument_permissions)
            if _is_page_argument_pack(source_permissions)
            else _aggregate_evidence_status(issue_ids, analyses_by_id)
        )
        permission_union = (
            _union_permission(
                [
                    entry.get("downstream_permission") or {}
                    for entry in page_argument_permissions
                    if isinstance(entry.get("downstream_permission"), dict)
                ]
            )
            if _is_page_argument_pack(source_permissions)
            else _union_permission(issue_permissions)
        )
        metric_ids = _proof_metric_ids(strategy_slide)
        requested_visual_metric_ids = _visual_metric_ids(strategy_slide, metric_ids)
        visual_metric_ids = (
            _entry_ids(page_argument_permissions, "visual_metric_ids")
            if _is_page_argument_pack(source_permissions)
            else _permitted_proof_ids(
                strategy_slide,
                analyses_by_id,
                id_field="metric_ids",
                permission_field="chart_allowed",
            )
        )
        visual_metric_ids = [met_id for met_id in requested_visual_metric_ids if met_id in set(visual_metric_ids)]
        body_evidence_ids = (
            [ev_id for ev_id in _proof_evidence_ids(strategy_slide) if ev_id in set(_entry_ids(page_argument_permissions, "body_evidence_ids"))]
            if _is_page_argument_pack(source_permissions)
            else _permitted_proof_ids(
                strategy_slide,
                analyses_by_id,
                id_field="evidence_ids",
                permission_field="body_copy_allowed",
            )
        )
        body_metric_ids = (
            [met_id for met_id in metric_ids if met_id in set(_entry_ids(page_argument_permissions, "body_metric_ids"))]
            if _is_page_argument_pack(source_permissions)
            else _permitted_proof_ids(
                strategy_slide,
                analyses_by_id,
                id_field="metric_ids",
                permission_field="body_copy_allowed",
            )
        )
        chart_allowed = (
            capability == "chart"
            and bool(requested_visual_metric_ids)
            and set(requested_visual_metric_ids) <= set(visual_metric_ids)
        )
        visual_metric_allowed = (
            capability in {"chart", "table", "matrix", "cards"}
            and bool(requested_visual_metric_ids)
            and set(requested_visual_metric_ids) <= set(visual_metric_ids)
        )
        proof_points = _proof_points(strategy_slide)
        claim_strength = str(strategy_slide.get("claim_strength") or "").strip()
        headline_allowed = permission_union.get("headline_allowed") is True and claim_strength not in {"hypothesis", "open_question"}
        main_message_allowed = permission_union.get("main_message_allowed") is True and claim_strength not in {"hypothesis", "open_question"}
        slides.append(
            {
                "slide_no": slide_no,
                "page_role": strategy_slide.get("fixed_page_role", ""),
                "page_question": strategy_slide.get("investor_question", ""),
                "page_argument_ids": [
                    str(item).strip()
                    for item in _as_list(strategy_slide.get("page_argument_ids"))
                    if str(item).strip()
                ],
                "primary_issue_analysis_id": primary_id,
                "supporting_issue_analysis_ids": [
                    str(item).strip()
                    for item in _as_list(strategy_slide.get("supporting_issue_analysis_ids"))
                    if str(item).strip()
                ],
                "headline_claim": strategy_slide.get("page_answer", ""),
                "proof_standard": (
                    "Use only deck_blueprint proof_points and selected page_argument_ids EV/MET IDs permitted by downstream_permission; "
                    "downgrade or caveat any claim outside this boundary."
                ),
                "headline_allowed": headline_allowed,
                "main_message_allowed": main_message_allowed,
                "downstream_permission": permission_union,
                "evidence_status": evidence_status,
                "selected_issue_downstream_permissions": [
                    {
                        "analysis_id": str(analysis_id),
                        "evidence_status": _analysis_evidence_status(analyses_by_id.get(analysis_id) or {}),
                        "downstream_permission": _analysis_downstream_permission(analyses_by_id.get(analysis_id) or {}),
                    }
                    for analysis_id in issue_ids
                    if str(analysis_id).strip()
                ],
                "selected_page_argument_permissions": page_argument_permissions,
                "chart_allowed": chart_allowed,
                "visual_metric_allowed": visual_metric_allowed,
                "chart_metric_ids": requested_visual_metric_ids if chart_allowed else [],
                "allowed_visual_metric_ids": visual_metric_ids if visual_metric_allowed else [],
                "body_evidence_ids": body_evidence_ids,
                "body_metric_ids": body_metric_ids,
                "proof_points": proof_points,
                "claim_strength": claim_strength,
                "evidence_gap_handling": visual_plan.get("fallback_if_data_insufficient", ""),
                "dependency_note": "; ".join(
                    f"{item.get('analysis_id')}: {item.get('use_as')}"
                    for item in _as_list(strategy_slide.get("analysis_use"))
                    if isinstance(item, dict) and item.get("analysis_id")
                ),
                "caveats": [str(item).strip() for item in _as_list(strategy_slide.get("caveats")) if str(item).strip()],
                "open_questions": [
                    str(item).strip()
                    for item in _as_list(strategy_slide.get("open_questions"))
                    if str(item).strip()
                ],
            }
        )
    return {"slides": sorted(slides, key=lambda item: int(item.get("slide_no") or 0))}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--page-argument-pack", required=True)
    parser.add_argument("--issue-analysis", help="Optional lineage cross-check artifact; page_argument_pack is the contract source.")
    parser.add_argument("--deck-blueprint", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    contract = build_page_evidence_contract(
        load_json_file(Path(args.page_argument_pack)),
        normalize_deck_blueprint_for_page_plan(load_json_file(Path(args.deck_blueprint))),
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"is_valid": True, "output": str(output_path)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

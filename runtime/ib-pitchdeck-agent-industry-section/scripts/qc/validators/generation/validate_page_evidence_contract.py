#!/usr/bin/env python3
"""Validate page_evidence_contract.json against issue analysis and page-plan artifacts."""

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
import sys
from pathlib import Path
from typing import Any

from deck_blueprint_utils import normalize_deck_blueprint_for_page_plan
from json_utils import load_json_file
from upstream_validation import COMPILE_UPSTREAM_VALIDATIONS, assert_formal_upstream_valid


VALID_CLAIM_STRENGTHS = {
    "hard_fact",
    "supported_inference",
    "directional_inference",
    "management_claim",
    "hypothesis",
    "open_question",
}
METRIC_VISUAL_CAPABILITIES = {"chart", "table", "matrix", "cards"}
VALID_EVIDENCE_STATUS = {
    "supported",
    "thin",
    "insufficient",
    "not_applicable",
    "unavailable_after_research",
    "not_researched",
    "caveat_only",
}
EVIDENCE_STATUS_RANK = {
    "supported": 0,
    "thin": 1,
    "caveat_only": 2,
    "insufficient": 3,
    "unavailable_after_research": 4,
    "not_researched": 5,
}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _non_empty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _analysis_index(pool: dict[str, Any]) -> dict[str, dict[str, Any]]:
    analyses = pool.get("issue_analyses") if isinstance(pool, dict) else []
    if not isinstance(analyses, list):
        return {}
    return {str(item.get("analysis_id")): item for item in analyses if isinstance(item, dict) and item.get("analysis_id")}


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
    return "not_researched"


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


def _union_permission(perms: list[dict[str, bool]]) -> dict[str, bool]:
    union = {
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


def _aggregate_evidence_status(analysis_ids: set[str], analyses_by_id: dict[str, dict[str, Any]]) -> str:
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


def _analysis_permission_matrix_entry(entry: dict[str, Any], idx: int) -> tuple[str, dict[str, Any]]:
    if not isinstance(entry, dict):
        raise TypeError("selected_issue_downstream_permissions entries must be objects")
    analysis_id = str(entry.get("analysis_id") or "").strip()
    if not (analysis_id.startswith("IA-") and len(analysis_id) == 6 and analysis_id[3:].isdigit()):
        raise ValueError(f"selected_issue_downstream_permissions[{idx}] invalid analysis_id '{analysis_id}'")
    evidence_status = str(entry.get("evidence_status") or "").strip()
    if evidence_status not in VALID_EVIDENCE_STATUS:
        raise ValueError(f"selected_issue_downstream_permissions[{idx}] evidence_status invalid '{evidence_status}'")
    perm = entry.get("downstream_permission")
    if not isinstance(perm, dict):
        raise ValueError(f"selected_issue_downstream_permissions[{idx}] downstream_permission must be object")
    required = ("headline_allowed", "main_message_allowed", "chart_allowed", "body_copy_allowed")
    missing = [name for name in required if perm.get(name) is None]
    if missing:
        raise ValueError(f"selected_issue_downstream_permissions[{idx}] missing downstream_permission fields: {', '.join(missing)}")
    if any(not isinstance(perm.get(name), bool) for name in required):
        raise ValueError(f"selected_issue_downstream_permissions[{idx}] downstream_permission fields must be boolean")
    return analysis_id, {
        "analysis_status": evidence_status,
        "downstream_permission": {
            "headline_allowed": bool(perm.get("headline_allowed") is True),
            "main_message_allowed": bool(perm.get("main_message_allowed") is True),
            "chart_allowed": bool(perm.get("chart_allowed") is True),
            "body_copy_allowed": bool(perm.get("body_copy_allowed") is True),
        },
    }


def _page_plan_index(page_plan: dict[str, Any]) -> dict[int, dict[str, Any]]:
    slides = page_plan.get("slides") if isinstance(page_plan, dict) else []
    if not isinstance(slides, list):
        return {}
    return {int(item.get("slide_no")): item for item in slides if isinstance(item, dict) and isinstance(item.get("slide_no"), int)}


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


def _selected_analysis_ids(strategy_entry: dict[str, Any]) -> set[str]:
    values = {str(item).strip() for item in _as_list(strategy_entry.get("supporting_issue_analysis_ids")) if str(item).strip()}
    primary = str(strategy_entry.get("primary_issue_analysis_id") or "").strip()
    if primary:
        values.add(primary)
    return values


def _proof_metric_ids(strategy_entry: dict[str, Any]) -> set[str]:
    values: set[str] = set()
    for point in _as_list(strategy_entry.get("proof_points")):
        if isinstance(point, dict):
            values.update(str(item).strip() for item in _as_list(point.get("metric_ids")) if str(item).strip())
    return values


def _strategy_visual_metric_ids(strategy_entry: dict[str, Any], fallback_metric_ids: set[str]) -> set[str]:
    visual_plan = strategy_entry.get("visual_plan") if isinstance(strategy_entry.get("visual_plan"), dict) else {}
    if isinstance(visual_plan.get("visual_metric_ids"), list):
        return {str(item).strip() for item in visual_plan.get("visual_metric_ids") if str(item).strip()}
    return set(fallback_metric_ids)


def _proof_evidence_ids(strategy_entry: dict[str, Any]) -> set[str]:
    values: set[str] = set()
    for point in _as_list(strategy_entry.get("proof_points")):
        if isinstance(point, dict):
            values.update(str(item).strip() for item in _as_list(point.get("evidence_ids")) if str(item).strip())
    return values


def _normalized_proof_points(entry: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for point in _as_list(entry.get("proof_points")):
        if not isinstance(point, dict):
            continue
        normalized = {
            "point": str(point.get("point") or "").strip(),
            "source_analysis_ids": [
                str(item).strip()
                for item in _as_list(point.get("source_analysis_ids"))
                if str(item).strip()
            ],
            "evidence_ids": [
                str(item).strip()
                for item in _as_list(point.get("evidence_ids"))
                if str(item).strip()
            ],
            "metric_ids": [
                str(item).strip()
                for item in _as_list(point.get("metric_ids"))
                if str(item).strip()
            ],
            "claim_strength": str(point.get("claim_strength") or "").strip(),
        }
        visual_role = str(point.get("visual_role") or "").strip()
        if visual_role:
            normalized["visual_role"] = visual_role
        caveat = str(point.get("caveat") or "").strip()
        if caveat:
            normalized["caveat"] = caveat
        result.append(normalized)
    return result


def _proof_ids_with_permission(
    strategy_entry: dict[str, Any],
    analyses_by_id: dict[str, dict[str, Any]],
    *,
    id_field: str,
    permission_field: str,
) -> set[str]:
    values: set[str] = set()
    for point in _as_list(strategy_entry.get("proof_points")):
        if not isinstance(point, dict):
            continue
        point_ids = {str(item).strip() for item in _as_list(point.get(id_field)) if str(item).strip()}
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
        values.update(point_ids & permitted)
    return values


def _proof_ids_without_permission(
    strategy_entry: dict[str, Any],
    analyses_by_id: dict[str, dict[str, Any]],
    *,
    id_field: str,
    permission_field: str,
) -> set[str]:
    all_ids: set[str] = set()
    for point in _as_list(strategy_entry.get("proof_points")):
        if isinstance(point, dict):
            all_ids.update(str(item).strip() for item in _as_list(point.get(id_field)) if str(item).strip())
    return all_ids - _proof_ids_with_permission(
        strategy_entry,
        analyses_by_id,
        id_field=id_field,
        permission_field=permission_field,
    )


def _mapped_metric_ids(analyses_by_id: dict[str, dict[str, Any]], analysis_ids: set[str]) -> set[str]:
    values: set[str] = set()
    for analysis_id in analysis_ids:
        analysis = analyses_by_id.get(analysis_id) or {}
        values.update(str(item).strip() for item in _as_list(analysis.get("metric_ids")) if str(item).strip())
        for point in _as_list(analysis.get("supporting_points")):
            if isinstance(point, dict):
                values.update(str(item).strip() for item in _as_list(point.get("metric_ids")) if str(item).strip())
    return values


def _mapped_evidence_ids(analyses_by_id: dict[str, dict[str, Any]], analysis_ids: set[str]) -> set[str]:
    values: set[str] = set()
    for analysis_id in analysis_ids:
        analysis = analyses_by_id.get(analysis_id) or {}
        values.update(str(item).strip() for item in _as_list(analysis.get("evidence_ids")) if str(item).strip())
        for point in _as_list(analysis.get("supporting_points")):
            if isinstance(point, dict):
                values.update(str(item).strip() for item in _as_list(point.get("evidence_ids")) if str(item).strip())
    return values


def _strength_rank(value: str) -> int:
    order = {
        "open_question": 0,
        "hypothesis": 1,
        "management_claim": 2,
        "directional_inference": 3,
        "supported_inference": 4,
        "hard_fact": 5,
    }
    return order.get(value, -1)


def validate(pool: dict[str, Any], page_plan: dict[str, Any], page_contract: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    analyses_by_id = _analysis_index(pool)
    strategy_by_no = _page_plan_index(page_plan)

    slides = page_contract.get("slides") if isinstance(page_contract, dict) else None
    if not isinstance(slides, list):
        return ["slides must be an array"], warnings
    expected_slide_numbers = set(strategy_by_no)
    if expected_slide_numbers and len(slides) != len(expected_slide_numbers):
        errors.append(f"slides must contain exactly {len(expected_slide_numbers)} entries; found {len(slides)}")

    seen_slide_numbers: set[int] = set()
    for idx, slide in enumerate(slides, start=1):
        if not isinstance(slide, dict):
            errors.append(f"slides[{idx}] must be an object")
            continue
        slide_no = slide.get("slide_no")
        prefix = f"slide {slide_no or idx}"
        if not isinstance(slide_no, int):
            errors.append(f"{prefix}: slide_no must be an integer")
            continue
        if slide_no in seen_slide_numbers:
            errors.append(f"{prefix}: duplicate slide_no")
        seen_slide_numbers.add(slide_no)

        expected_role = str((strategy_by_no.get(slide_no) or {}).get("fixed_page_role") or "").strip()
        page_role = str(slide.get("page_role") or "").strip()
        if expected_role and page_role != expected_role:
            errors.append(f"{prefix}: page_role must be '{expected_role}', found '{page_role}'")

        for field in ("page_question", "proof_standard", "evidence_gap_handling", "headline_claim"):
            if not _non_empty_text(slide.get(field)):
                errors.append(f"{prefix}: {field} is required")
        for field in ("headline_allowed", "main_message_allowed", "chart_allowed", "visual_metric_allowed"):
            if not isinstance(slide.get(field), bool):
                errors.append(f"{prefix}: {field} must be boolean")
        downstream_permission = slide.get("downstream_permission")
        if not isinstance(downstream_permission, dict):
            errors.append(f"{prefix}: downstream_permission must be object")
        else:
            for field in ("headline_allowed", "main_message_allowed", "chart_allowed", "body_copy_allowed"):
                if not isinstance(downstream_permission.get(field), bool):
                    errors.append(f"{prefix}: downstream_permission.{field} must be boolean")
        evidence_status = str(slide.get("evidence_status") or "").strip()
        if evidence_status not in VALID_EVIDENCE_STATUS:
            errors.append(f"{prefix}: evidence_status must be one of {sorted(VALID_EVIDENCE_STATUS)}")

        selected_issue_permissions: dict[str, dict[str, Any]] = {}
        contract_issue_status: dict[str, str] = {}
        for entry_idx, item in enumerate(_as_list(slide.get("selected_issue_downstream_permissions")), start=1):
            if not isinstance(item, dict):
                errors.append(f"{prefix}: selected_issue_downstream_permissions[{entry_idx}] must be object")
                continue
            try:
                analysis_id, parsed = _analysis_permission_matrix_entry(item, entry_idx)
            except (TypeError, ValueError) as exc:
                errors.append(f"{prefix}: {exc}")
                continue
            if analysis_id in selected_issue_permissions:
                errors.append(f"{prefix}: selected_issue_downstream_permissions has duplicate analysis_id '{analysis_id}'")
                continue
            selected_issue_permissions[analysis_id] = parsed["downstream_permission"]
            contract_issue_status[analysis_id] = parsed["analysis_status"]

        strategy_entry = strategy_by_no.get(slide_no)
        if not strategy_entry:
            errors.append(f"{prefix}: missing matching slide in page plan")
            mapped_ids: set[str] = set()
            proof_metric_ids: set[str] = set()
            proof_evidence_ids: set[str] = set()
            expected_proof_points: list[dict[str, Any]] = []
            strategy_visual_plan: dict[str, Any] = {}
            expected_downstream_permission = {}
            expected_evidence_status = ""
        else:
            if page_role != str(strategy_entry.get("fixed_page_role") or "").strip():
                errors.append(f"{prefix}: page_role does not match page plan fixed_page_role")
            if str(slide.get("page_question") or "").strip() != str(strategy_entry.get("investor_question") or "").strip():
                errors.append(f"{prefix}: page_question must match page plan investor_question")
            if str(slide.get("headline_claim") or "").strip() != str(strategy_entry.get("page_answer") or "").strip():
                errors.append(f"{prefix}: headline_claim must match page plan page_answer/page_thesis")
            mapped_ids = _selected_analysis_ids(strategy_entry)
            proof_metric_ids = _proof_metric_ids(strategy_entry)
            strategy_visual_metric_ids = _strategy_visual_metric_ids(strategy_entry, proof_metric_ids)
            proof_evidence_ids = _proof_evidence_ids(strategy_entry)
            expected_proof_points = _normalized_proof_points(strategy_entry)
            strategy_visual_plan = strategy_entry.get("visual_plan") if isinstance(strategy_entry.get("visual_plan"), dict) else {}
            expected_downstream_permission = _union_permission(
                [_analysis_downstream_permission(analyses_by_id.get(analysis_id) or {}) for analysis_id in mapped_ids]
            )
            expected_evidence_status = _aggregate_evidence_status(mapped_ids, analyses_by_id)

        primary_id = str(slide.get("primary_issue_analysis_id") or "").strip()
        if strategy_entry and primary_id != str(strategy_entry.get("primary_issue_analysis_id") or "").strip():
            errors.append(f"{prefix}: primary_issue_analysis_id must match page plan primary_issue_analysis_id")
        primary = analyses_by_id.get(primary_id)
        if not primary:
            errors.append(f"{prefix}: primary_issue_analysis_id {primary_id or '<blank>'} not found in issue analysis")

        supporting_ids = {str(item).strip() for item in _as_list(slide.get("supporting_issue_analysis_ids")) if str(item).strip()}
        invalid_supporting = sorted(supporting_ids - mapped_ids)
        if invalid_supporting:
            errors.append(f"{prefix}: supporting_issue_analysis_ids not selected in page plan: {', '.join(invalid_supporting)}")
        selected_ids = set(selected_issue_permissions)
        if mapped_ids != selected_ids:
            missing = sorted(mapped_ids - selected_ids)
            extra = sorted(selected_ids - mapped_ids)
            if missing:
                errors.append(f"{prefix}: selected_issue_downstream_permissions missing analysis ids: {', '.join(missing)}")
            if extra:
                errors.append(f"{prefix}: selected_issue_downstream_permissions has extra analysis ids: {', '.join(extra)}")
        if strategy_entry:
            if evidence_status != expected_evidence_status:
                errors.append(f"{prefix}: evidence_status must equal aggregate evidence status of selected issue analyses")
            if isinstance(downstream_permission, dict):
                contract_union = _union_permission(list(selected_issue_permissions.values()))
                if contract_union != expected_downstream_permission:
                    errors.append(f"{prefix}: downstream_permission must equal union of selected_issue_downstream_permissions")
            for analysis_id in mapped_ids:
                if analysis_id not in selected_issue_permissions:
                    continue
                issue = analyses_by_id.get(analysis_id) or {}
                expected_issue_status = _analysis_evidence_status(issue)
                if expected_issue_status != contract_issue_status.get(analysis_id):
                    errors.append(
                        f"{prefix}: selected_issue_downstream_permissions[{analysis_id}].evidence_status "
                        f"must match issue_analysis evidence_status '{expected_issue_status}'"
                    )
                expected_issue_perm = _analysis_downstream_permission(issue)
                if expected_issue_perm != selected_issue_permissions[analysis_id]:
                    errors.append(
                        f"{prefix}: selected_issue_downstream_permissions[{analysis_id}].downstream_permission "
                        f"must match issue_analysis allowed permissions"
                    )

        claim_strength = str(slide.get("claim_strength") or "").strip()
        if claim_strength not in VALID_CLAIM_STRENGTHS:
            errors.append(f"{prefix}: claim_strength must be one of {sorted(VALID_CLAIM_STRENGTHS)}")
        strategy_strength = str((strategy_entry or {}).get("claim_strength") or "").strip()
        if strategy_strength in VALID_CLAIM_STRENGTHS and claim_strength in VALID_CLAIM_STRENGTHS:
            if _strength_rank(claim_strength) > _strength_rank(strategy_strength):
                errors.append(f"{prefix}: page contract claim_strength cannot be stronger than page plan claim_strength")

        headline_allowed = slide.get("headline_allowed") is True
        main_message_allowed = slide.get("main_message_allowed") is True
        chart_allowed = slide.get("chart_allowed") is True
        visual_metric_allowed = slide.get("visual_metric_allowed") is True
        if strategy_entry and isinstance(downstream_permission, dict):
            expected_headline_allowed = (
                bool(expected_downstream_permission.get("headline_allowed"))
                and claim_strength not in {"hypothesis", "open_question"}
            )
            if expected_headline_allowed is False:
                expected_headline_allowed = False
            if headline_allowed != expected_headline_allowed:
                errors.append(f"{prefix}: headline_allowed does not match generated headline permissions from page plan and issue analyses")
            expected_main_message_allowed = (
                bool(expected_downstream_permission.get("main_message_allowed"))
                and claim_strength not in {"hypothesis", "open_question"}
            )
            if expected_main_message_allowed is False:
                expected_main_message_allowed = False
            if main_message_allowed != expected_main_message_allowed:
                errors.append(f"{prefix}: main_message_allowed does not match generated permissions from page plan and issue analyses")
        elif headline_allowed:
            errors.append(f"{prefix}: headline_allowed=true but cannot validate against page plan")
        capability = str(strategy_visual_plan.get("required_capability") or "")
        visual_permitted_metrics = (
            _proof_ids_with_permission(
                strategy_entry or {},
                analyses_by_id,
                id_field="metric_ids",
                permission_field="chart_allowed",
            )
            if strategy_entry
            else set()
        )
        if not strategy_entry:
            strategy_visual_metric_ids = set()
        chart_permission_failures = set(strategy_visual_metric_ids) - visual_permitted_metrics
        expected_visual_metric_allowed = (
            capability in METRIC_VISUAL_CAPABILITIES
            and bool(strategy_visual_metric_ids)
            and not chart_permission_failures
        )
        body_permission_failures = (
            _proof_ids_without_permission(
                strategy_entry or {},
                analyses_by_id,
                id_field="evidence_ids",
                permission_field="body_copy_allowed",
            )
            if strategy_entry
            else set()
        )
        if capability in METRIC_VISUAL_CAPABILITIES and chart_permission_failures:
            errors.append(
                f"{prefix}: visual_plan.visual_metric_ids require downstream_permission.chart_allowed=true: "
                + ", ".join(sorted(chart_permission_failures))
            )
        if body_permission_failures:
            errors.append(
                f"{prefix}: body evidence proof_points require downstream_permission.body_copy_allowed=true: "
                + ", ".join(sorted(body_permission_failures))
            )
        if strategy_entry and visual_metric_allowed != expected_visual_metric_allowed:
            errors.append(
                f"{prefix}: visual_metric_allowed must match page plan visual required_capability "
                f"in {sorted(METRIC_VISUAL_CAPABILITIES)}"
            )
        allowed_visual_metric_ids = {
            str(item).strip()
            for item in _as_list(slide.get("allowed_visual_metric_ids"))
            if str(item).strip()
        }
        if visual_metric_allowed:
            outside_visual_permission = sorted(allowed_visual_metric_ids - visual_permitted_metrics)
            if outside_visual_permission:
                errors.append(
                    f"{prefix}: allowed_visual_metric_ids not permitted by source issue analyses: "
                    + ", ".join(outside_visual_permission)
                )
            missing_visual_metrics = sorted(strategy_visual_metric_ids - allowed_visual_metric_ids)
            if missing_visual_metrics:
                errors.append(
                    f"{prefix}: allowed_visual_metric_ids must include page plan visual_metric_ids: "
                    + ", ".join(missing_visual_metrics)
                )
        elif allowed_visual_metric_ids:
            errors.append(f"{prefix}: allowed_visual_metric_ids must be empty when visual_metric_allowed=false")
        if chart_allowed:
            chart_metric_ids = {str(item).strip() for item in _as_list(slide.get("chart_metric_ids")) if str(item).strip()}
            if not chart_metric_ids:
                errors.append(f"{prefix}: chart_allowed=true requires non-empty chart_metric_ids")
            chart_permitted_metrics = _proof_ids_with_permission(
                strategy_entry or {},
                analyses_by_id,
                id_field="metric_ids",
                permission_field="chart_allowed",
            )
            outside_chart_permission = sorted(chart_metric_ids - chart_permitted_metrics)
            if outside_chart_permission:
                errors.append(
                    f"{prefix}: chart_metric_ids not permitted by source issue analyses: "
                    + ", ".join(outside_chart_permission)
                )
            mapped_metrics = _mapped_metric_ids(analyses_by_id, mapped_ids)
            missing_metrics = sorted(chart_metric_ids - mapped_metrics)
            if missing_metrics:
                errors.append(f"{prefix}: chart_metric_ids not present in mapped issue analyses: {', '.join(missing_metrics)}")
            metrics_outside_proof = sorted(chart_metric_ids - proof_metric_ids)
            if metrics_outside_proof:
                errors.append(f"{prefix}: chart_metric_ids not present in page plan proof_points: {', '.join(metrics_outside_proof)}")
            missing_proof_metrics = sorted(strategy_visual_metric_ids - chart_metric_ids)
            if str(strategy_visual_plan.get("required_capability") or "") == "chart" and missing_proof_metrics:
                errors.append(f"{prefix}: chart_metric_ids must include page plan visual_metric_ids: {', '.join(missing_proof_metrics)}")
        if strategy_entry:
            expected_chart_allowed = capability == "chart" and bool(strategy_visual_metric_ids) and not chart_permission_failures
            if chart_allowed != expected_chart_allowed:
                errors.append(f"{prefix}: chart_allowed must match chart capability plus downstream_permission.chart_allowed")
        actual_proof_points = _normalized_proof_points(slide)
        if actual_proof_points != expected_proof_points:
            errors.append(f"{prefix}: proof_points must match page plan proof_points exactly")

        body_evidence_ids = {str(item).strip() for item in _as_list(slide.get("body_evidence_ids")) if str(item).strip()}
        body_permitted_evidence = _proof_ids_with_permission(
            strategy_entry or {},
            analyses_by_id,
            id_field="evidence_ids",
            permission_field="body_copy_allowed",
        )
        outside_body_permission = sorted(body_evidence_ids - body_permitted_evidence)
        if outside_body_permission:
            errors.append(
                f"{prefix}: body_evidence_ids not permitted by source issue analyses: "
                + ", ".join(outside_body_permission)
            )
        mapped_evidence = _mapped_evidence_ids(analyses_by_id, mapped_ids)
        missing_evidence = sorted(body_evidence_ids - mapped_evidence)
        if missing_evidence:
            errors.append(f"{prefix}: body_evidence_ids not present in mapped issue analyses: {', '.join(missing_evidence)}")
        evidence_outside_proof = sorted(body_evidence_ids - proof_evidence_ids)
        if evidence_outside_proof:
            errors.append(f"{prefix}: body_evidence_ids not present in page plan proof_points: {', '.join(evidence_outside_proof)}")
        missing_proof_evidence = sorted(proof_evidence_ids - body_evidence_ids)
        if missing_proof_evidence:
            errors.append(f"{prefix}: body_evidence_ids must include all evidence_ids from page plan proof_points: {', '.join(missing_proof_evidence)}")

        if claim_strength == "hard_fact" and not (body_evidence_ids or _as_list(slide.get("chart_metric_ids"))):
            errors.append(f"{prefix}: hard_fact requires body_evidence_ids or chart_metric_ids")
        if claim_strength in {"hypothesis", "open_question"} and headline_allowed:
            errors.append(f"{prefix}: hypothesis/open_question cannot be a confident headline")
        if not body_evidence_ids and not _as_list(slide.get("chart_metric_ids")) and not _as_list(slide.get("open_questions")):
            errors.append(f"{prefix}: slide has no evidence, metrics, or open_questions")

    missing_slide_numbers = expected_slide_numbers - seen_slide_numbers
    if missing_slide_numbers:
        errors.append("missing slide_no entries: " + ", ".join(str(num) for num in sorted(missing_slide_numbers)))

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--issue-analysis", required=True)
    parser.add_argument("--deck-blueprint", required=True)
    parser.add_argument("--page-contract", required=True)
    parser.add_argument("--output", help="Optional path to write validation report JSON")
    args = parser.parse_args()

    pool_path = Path(args.issue_analysis)
    page_plan_path = Path(args.deck_blueprint)
    contract_path = Path(args.page_contract)
    try:
        pool = load_json_file(pool_path)
        page_plan = normalize_deck_blueprint_for_page_plan(load_json_file(page_plan_path))
        page_contract = load_json_file(contract_path)
        errors, warnings = validate(pool, page_plan, page_contract)
        errors.extend(
            assert_formal_upstream_valid(
                [pool_path, page_plan_path, contract_path],
                expected_names={"industry_issue_analysis.json", "deck_blueprint.json", "page_evidence_contract.json"},
                validation_rels=COMPILE_UPSTREAM_VALIDATIONS,
                stage_name="page_evidence_contract",
            )
        )
    except Exception as exc:
        errors, warnings = [str(exc)], []

    result = {
        "is_valid": not errors,
        "issue_analysis": str(pool_path),
        "page_plan": str(page_plan_path),
        "page_plan_kind": "deck_blueprint",
        "page_contract": str(contract_path),
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
    }
    result_json = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(result_json + "\n", encoding="utf-8")
    print(result_json)
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())

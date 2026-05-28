#!/usr/bin/env python3
"""Validate artifacts/research_plan.json for the research phase.

This is a lightweight harness check. It catches missing broad discovery,
unexplained source selection, and accidental all-default-pack fanout before
the memo is written.
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any, Optional

from json_utils import load_json_file


EXPECTED_DIMENSIONS = {
    "industry_definition_scope",
    "market_size_growth",
    "segmentation",
    "demand_drivers",
    "value_chain_profit_pool",
    "barriers_value_drivers",
    "competitive_landscape_peer_set",
    "trends_regulation_technology",
    "target_specific_implications",
}

YEAR_RE = re.compile(r"\b(20\d{2})\b")
FRESHNESS_TERMS = (
    "latest",
    "current",
    "recent",
    "newest",
    "updated",
    "most recent",
    "最新",
    "当前",
    "近期",
    "近年",
    "今年",
    "去年",
    "近6个月",
    "近三年",
)


def load_json(path: Path) -> dict[str, Any]:
    return load_json_file(path)


def text_present(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def non_empty_strings(values: list[Any]) -> list[str]:
    return [str(v).strip() for v in values if str(v).strip()]


def default_source_packs(registry: dict[str, Any]) -> set[str]:
    packs = registry.get("default_packs", [])
    if isinstance(packs, list):
        return {str(pack) for pack in packs if str(pack).strip()}
    return set()


def pack_domains(registry: dict[str, Any], pack_name: str) -> list[str]:
    packs = registry.get("source_packs", {})
    if not isinstance(packs, dict):
        return []
    pack = packs.get(pack_name, {})
    if not isinstance(pack, dict):
        return []
    domains = pack.get("domains", [])
    if not isinstance(domains, list):
        return []
    return non_empty_strings(domains)


def extract_years(text: str) -> set[int]:
    return {int(match) for match in YEAR_RE.findall(text)}


def has_freshness_cue(text: str, current_year: int) -> bool:
    lowered = text.lower()
    if str(current_year) in lowered or str(current_year - 1) in lowered:
        return True
    return any(term.lower() in lowered for term in FRESHNESS_TERMS)


def check_freshness_metadata(plan: dict[str, Any], warnings: list[str]) -> None:
    meta = plan.get("meta", {})
    if not isinstance(meta, dict):
        return
    if not text_present(meta.get("research_as_of_date")):
        warnings.append("meta.research_as_of_date should be populated with the run date before search")
    if not text_present(meta.get("user_material_data_cutoff")):
        warnings.append(
            "meta.user_material_data_cutoff should state the latest period found in user-provided materials, "
            "or 'not specified'"
        )


def check_query_freshness(
    dimension: str,
    field_name: str,
    query: str,
    current_year: int,
    errors: list[str],
    warnings: list[str],
) -> None:
    years = extract_years(query)
    stale_years = sorted(year for year in years if year <= current_year - 2)
    fresh_years = sorted(year for year in years if year >= current_year - 1)

    if field_name == "latest_query" and not has_freshness_cue(query, current_year):
        warnings.append(
            f"dimension '{dimension}' latest_query has no freshness cue; include 'latest/current/recent' "
            f"or {current_year}/{current_year - 1}"
        )

    if stale_years and not fresh_years:
        message = (
            f"dimension '{dimension}' {field_name} appears anchored to stale year(s) {stale_years}. "
            f"Do not treat user-material years as the current research period; use latest/current or "
            f"{current_year}/{current_year - 1} for freshness checks, and put old-year verification in targeted queries."
        )
        if field_name == "latest_query":
            errors.append(message)
        else:
            warnings.append(message)


def validate(
    plan: dict[str, Any],
    registry: Optional[dict[str, Any]] = None,
    current_year: Optional[int] = None,
    stage: str = "formal",
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    blocking_warnings: list[str] = []
    current_year = current_year or date.today().year
    formal_stage = stage == "formal"

    check_freshness_metadata(plan, warnings)

    source_registry = plan.get("source_registry", {})
    if not isinstance(source_registry, dict):
        errors.append("source_registry must be an object")
        source_registry = {}

    if source_registry.get("default_packs_auto_run") is True:
        errors.append("source_registry.default_packs_auto_run must be false")

    if source_registry.get("read_as_menu_before_search") is not True:
        warnings.append("source_registry.read_as_menu_before_search should be true")

    research_emphasis = plan.get("research_emphasis", {})
    if formal_stage:
        if not isinstance(research_emphasis, dict):
            blocking_warnings.append("research_emphasis must be an object after broad discovery")
        else:
            classification = research_emphasis.get("project_classification", {})
            if not isinstance(classification, dict) or not text_present(classification.get("key_transaction_question")):
                blocking_warnings.append("research_emphasis.project_classification.key_transaction_question is required in formal plans")
            priority_angles = research_emphasis.get("priority_research_angles", [])
            if not isinstance(priority_angles, list):
                blocking_warnings.append("research_emphasis.priority_research_angles must be an array")
            else:
                filled_angles = [
                    item for item in priority_angles
                    if isinstance(item, dict) and text_present(item.get("angle")) and text_present(item.get("why_it_matters_for_pitch"))
                ]
                if len(filled_angles) < 3:
                    blocking_warnings.append("research_emphasis should include at least 3 priority research angles with pitch relevance")
            slide_implications = research_emphasis.get("fixed_8_slide_implications", [])
            if not isinstance(slide_implications, list) or len(slide_implications) < 8:
                blocking_warnings.append("research_emphasis.fixed_8_slide_implications should map emphasis to all 8 fixed slides")

    broad = plan.get("broad_discovery", {})
    broad_queries = broad.get("queries", []) if isinstance(broad, dict) else []
    if not isinstance(broad_queries, list):
        errors.append("broad_discovery.queries must be an array")
        broad_queries = []

    filled_broad_queries = [
        item for item in broad_queries
        if isinstance(item, dict) and text_present(item.get("query"))
    ]
    if len(filled_broad_queries) < 3:
        message = "broad_discovery should include at least 3 filled unrestricted queries"
        warnings.append(message)
        if formal_stage:
            blocking_warnings.append(message)

    for idx, item in enumerate(broad_queries, start=1):
        if not isinstance(item, dict):
            errors.append(f"broad_discovery query {idx} must be an object")
            continue
        if item.get("mode") not in ("unrestricted", None, ""):
            errors.append(f"broad_discovery query {idx} must use mode='unrestricted'")
        if text_present(item.get("query")):
            check_query_freshness(
                str(item.get("dimension") or idx),
                "broad_discovery.query",
                str(item.get("query")),
                current_year,
                errors,
                warnings,
            )

    source_selection = plan.get("source_selection", {})
    selected_packs = source_selection.get("selected_source_packs", []) if isinstance(source_selection, dict) else []
    selected_domains = source_selection.get("selected_domains", []) if isinstance(source_selection, dict) else []

    if not isinstance(selected_packs, list):
        errors.append("source_selection.selected_source_packs must be an array")
        selected_packs = []
    if not isinstance(selected_domains, list):
        errors.append("source_selection.selected_domains must be an array")
        selected_domains = []

    pack_names = set()
    explicit_domains = set()

    for idx, item in enumerate(selected_packs, start=1):
        if not isinstance(item, dict):
            errors.append(f"selected_source_packs item {idx} must be an object")
            continue
        pack_name = str(item.get("source_pack", "")).strip()
        if pack_name:
            pack_names.add(pack_name)
        if pack_name and not text_present(item.get("reason")):
            warnings.append(f"selected source pack '{pack_name}' has no reason")

    for idx, item in enumerate(selected_domains, start=1):
        if not isinstance(item, dict):
            errors.append(f"selected_domains item {idx} must be an object")
            continue
        domain = str(item.get("domain", "")).strip()
        if domain:
            explicit_domains.add(domain)
        if domain and not text_present(item.get("reason")):
            warnings.append(f"selected domain '{domain}' has no reason")

    dimension_plan = plan.get("dimension_plan", [])
    if not isinstance(dimension_plan, list):
        errors.append("dimension_plan must be an array")
        dimension_plan = []

    seen_dimensions = set()
    targeted_query_count = 0
    dimensions_with_targeted = 0

    for idx, dim in enumerate(dimension_plan, start=1):
        if not isinstance(dim, dict):
            errors.append(f"dimension_plan item {idx} must be an object")
            continue

        dimension = str(dim.get("dimension", "")).strip()
        if dimension:
            seen_dimensions.add(dimension)

        if not text_present(dim.get("broad_query")):
            message = f"dimension '{dimension or idx}' has no broad_query"
            warnings.append(message)
            if formal_stage:
                blocking_warnings.append(message)
        latest_query = dim.get("latest_query")
        if not text_present(latest_query):
            message = f"dimension '{dimension or idx}' has no latest_query"
            warnings.append(message)
            if formal_stage:
                blocking_warnings.append(message)
        else:
            check_query_freshness(
                dimension or str(idx),
                "latest_query",
                str(latest_query),
                current_year,
                errors,
                warnings,
            )

        targeted = dim.get("targeted_validation_queries", [])
        if not isinstance(targeted, list):
            errors.append(f"dimension '{dimension or idx}' targeted_validation_queries must be an array")
            continue

        filled_targeted = 0
        for t_idx, query in enumerate(targeted, start=1):
            if not isinstance(query, dict):
                errors.append(f"dimension '{dimension or idx}' targeted query {t_idx} must be an object")
                continue
            if text_present(query.get("query")):
                targeted_query_count += 1
                filled_targeted += 1
                check_query_freshness(
                    dimension or str(idx),
                    f"targeted query {t_idx}",
                    str(query.get("query")),
                    current_year,
                    errors,
                    warnings,
                )
            pack = str(query.get("source_pack", "")).strip()
            if pack:
                pack_names.add(pack)
            domains = query.get("domains", [])
            query_domains: list[str] = []
            if isinstance(domains, list):
                query_domains = non_empty_strings(domains)
                explicit_domains.update(query_domains)
            if text_present(query.get("query")) and not (pack or query_domains) and not text_present(query.get("reason")):
                warnings.append(f"dimension '{dimension or idx}' targeted query {t_idx} lacks source and reason")
        if filled_targeted:
            dimensions_with_targeted += 1

    missing_dimensions = EXPECTED_DIMENSIONS - seen_dimensions
    if missing_dimensions:
        message = "dimension_plan missing dimensions: " + ", ".join(sorted(missing_dimensions))
        warnings.append(message)
        if formal_stage:
            blocking_warnings.append(message)

    if targeted_query_count == 0:
        message = "no filled targeted_validation_queries found"
        warnings.append(message)
        if formal_stage:
            blocking_warnings.append(message)
    if dimensions_with_targeted < 6:
        message = "fewer than 6 dimensions have targeted validation queries"
        warnings.append(message)
        if formal_stage:
            blocking_warnings.append(message)

    default_packs = default_source_packs(registry or {})
    if default_packs and default_packs.issubset(pack_names):
        warnings.append("all default source packs are selected; confirm this is intentional and not automatic fanout")

    resolved_domains = set(explicit_domains)
    if registry:
        for pack in pack_names:
            resolved_domains.update(pack_domains(registry, pack))

    if len(resolved_domains) < 6:
        message = "fewer than 6 distinct high-priority domains selected across the plan"
        warnings.append(message)
        if formal_stage:
            blocking_warnings.append(message)
    if len(resolved_domains) > 20:
        message = "more than 20 distinct high-priority domains selected; narrow per query to 6-15 domains"
        warnings.append(message)
        if formal_stage:
            blocking_warnings.append(message)

    return {
        "is_valid": not errors and not blocking_warnings,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "blocking_warning_count": len(blocking_warnings),
        "blocking_warnings": blocking_warnings,
        "stage": stage,
        "metrics": {
            "broad_discovery_query_count": len(filled_broad_queries),
            "targeted_validation_query_count": targeted_query_count,
            "dimensions_planned": len(seen_dimensions),
            "dimensions_with_targeted_validation": dimensions_with_targeted,
            "selected_source_pack_count": len(pack_names),
            "resolved_high_priority_domain_count": len(resolved_domains),
            "freshness_current_year": current_year,
        }
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate an industry research_plan.json artifact.")
    parser.add_argument("--plan", required=True, help="Path to artifacts/research_plan.json")
    parser.add_argument("--source-registry", help="Path to templates/source_registry.json")
    parser.add_argument("--output", help="Optional path to write validation report JSON")
    parser.add_argument("--quality-gate", action="store_true", help="Treat warnings as errors")
    parser.add_argument(
        "--stage",
        choices=["discovery", "formal"],
        default="formal",
        help=(
            "discovery allows a lightweight pre-search plan; formal is the pre-memo/pre-delivery "
            "gate and requires targeted validation queries plus source selection."
        ),
    )
    parser.add_argument(
        "--current-year",
        type=int,
        default=date.today().year,
        help="Current year used to detect stale year-anchored latest queries.",
    )
    args = parser.parse_args()

    try:
        plan = load_json(Path(args.plan))
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        result = {
            "is_valid": False,
            "error_count": 1,
            "warning_count": 0,
            "errors": [f"cannot load plan: {exc}"],
            "warnings": [],
            "metrics": {}
        }
    else:
        registry = None
        if args.source_registry:
            try:
                registry = load_json(Path(args.source_registry))
            except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
                registry = None
                result = {
                    "is_valid": False,
                    "error_count": 1,
                    "warning_count": 0,
                    "errors": [f"cannot load source registry: {exc}"],
                    "warnings": [],
                    "metrics": {}
                }
            else:
                result = validate(plan, registry, current_year=args.current_year, stage=args.stage)
        else:
            result = validate(plan, registry, current_year=args.current_year, stage=args.stage)

    if args.quality_gate and result.get("warning_count", 0) > 0:
        result["is_valid"] = False

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result.get("is_valid"):
        sys.exit(1)


if __name__ == "__main__":
    main()

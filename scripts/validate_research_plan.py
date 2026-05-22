#!/usr/bin/env python3
"""Validate artifacts/research_plan.json for the research phase.

This is a lightweight harness check. It catches missing broad discovery,
unexplained source selection, and accidental all-default-pack fanout before
the memo is written.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

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


def validate(plan: dict[str, Any], registry: dict[str, Any] | None = None) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    source_registry = plan.get("source_registry", {})
    if not isinstance(source_registry, dict):
        errors.append("source_registry must be an object")
        source_registry = {}

    if source_registry.get("default_packs_auto_run") is True:
        errors.append("source_registry.default_packs_auto_run must be false")

    if source_registry.get("read_as_menu_before_search") is not True:
        warnings.append("source_registry.read_as_menu_before_search should be true")

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
        warnings.append("broad_discovery should include at least 3 filled unrestricted queries")

    for idx, item in enumerate(broad_queries, start=1):
        if not isinstance(item, dict):
            errors.append(f"broad_discovery query {idx} must be an object")
            continue
        if item.get("mode") not in ("unrestricted", None, ""):
            errors.append(f"broad_discovery query {idx} must use mode='unrestricted'")

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
            warnings.append(f"dimension '{dimension or idx}' has no broad_query")
        if not text_present(dim.get("latest_query")):
            warnings.append(f"dimension '{dimension or idx}' has no latest_query")

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
        warnings.append("dimension_plan missing dimensions: " + ", ".join(sorted(missing_dimensions)))

    if targeted_query_count == 0:
        warnings.append("no filled targeted_validation_queries found")
    if dimensions_with_targeted < 6:
        warnings.append("fewer than 6 dimensions have targeted validation queries")

    default_packs = default_source_packs(registry or {})
    if default_packs and default_packs.issubset(pack_names):
        warnings.append("all default source packs are selected; confirm this is intentional and not automatic fanout")

    resolved_domains = set(explicit_domains)
    if registry:
        for pack in pack_names:
            resolved_domains.update(pack_domains(registry, pack))

    if len(resolved_domains) < 6:
        warnings.append("fewer than 6 distinct high-priority domains selected across the plan")
    if len(resolved_domains) > 20:
        warnings.append("more than 20 distinct high-priority domains selected; consider narrowing per query")

    return {
        "is_valid": not errors,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "metrics": {
            "broad_discovery_query_count": len(filled_broad_queries),
            "targeted_validation_query_count": targeted_query_count,
            "dimensions_planned": len(seen_dimensions),
            "dimensions_with_targeted_validation": dimensions_with_targeted,
            "selected_source_pack_count": len(pack_names),
            "resolved_high_priority_domain_count": len(resolved_domains)
        }
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate an industry research_plan.json artifact.")
    parser.add_argument("--plan", required=True, help="Path to artifacts/research_plan.json")
    parser.add_argument("--source-registry", help="Path to templates/source_registry.json")
    parser.add_argument("--output", help="Optional path to write validation report JSON")
    parser.add_argument("--quality-gate", action="store_true", help="Treat warnings as errors")
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
                result = validate(plan, registry)
        else:
            result = validate(plan, registry)

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

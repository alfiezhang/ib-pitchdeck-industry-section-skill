#!/usr/bin/env python3
"""Generate a concise markdown quality summary for an industry-section run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from json_utils import load_json_file
from validate_final_delivery import validate as validate_final_delivery_current


def load_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = load_json_file(path)
    except Exception as exc:
        return {"_load_error": str(exc)}
    return data if isinstance(data, dict) else {}


def count_search_attempts(path: Path) -> int:
    if not path.exists():
        return 0
    text = path.read_text(encoding="utf-8")
    return sum(1 for line in text.splitlines() if line.lstrip().startswith("### Search"))


def yes_no(value: bool) -> str:
    return "yes" if value else "no"


def build_summary(run_dir: Path) -> str:
    artifacts = run_dir / "artifacts"
    input_card = load_optional_json(artifacts / "input_card_validation.json")
    research_plan = load_optional_json(artifacts / "research_plan_validation.json")
    content = load_optional_json(artifacts / "content_quality_validation.json")
    storyboard = load_optional_json(artifacts / "storyboard_validation.json")
    final_delivery = load_optional_json(artifacts / "final_delivery_validation.json")
    ppt = load_optional_json(run_dir / "filled_ppt_validation.json")
    current_final = validate_final_delivery_current(run_dir, Path("templates/source_registry.json"))

    rp_metrics = research_plan.get("metrics", {}) if isinstance(research_plan.get("metrics"), dict) else {}
    ppt_summary = ppt.get("summary", {}) if isinstance(ppt.get("summary"), dict) else {}

    lines = [
        "# Run Quality Summary",
        "",
        f"Run Dir: `{run_dir}`",
        "",
        "## Gates",
        "",
        f"- Input card valid: {yes_no(input_card.get('is_valid') is True)}",
        f"- Research plan valid: {yes_no(research_plan.get('is_valid') is True)}",
        f"- Storyboard valid: {yes_no(storyboard.get('is_valid') is True)}",
        f"- Content quality valid: {yes_no(content.get('is_valid') is True)}",
        f"- PPT validation valid: {yes_no(ppt_summary.get('is_valid') is True)}",
        f"- Final delivery artifact valid: {yes_no(final_delivery.get('is_valid') is True)}",
        f"- Current final delivery gate valid: {yes_no(current_final.get('is_valid') is True)}",
        "",
        "## Research Audit",
        "",
        f"- Search attempts logged: {count_search_attempts(artifacts / 'search_log.md')}",
        f"- Broad discovery queries in plan: {rp_metrics.get('broad_discovery_query_count', 0)}",
        f"- Targeted validation queries in plan: {rp_metrics.get('targeted_validation_query_count', 0)}",
        f"- Dimensions with targeted validation: {rp_metrics.get('dimensions_with_targeted_validation', 0)}",
        f"- Selected source packs: {rp_metrics.get('selected_source_pack_count', 0)}",
        f"- Resolved high-priority domains: {rp_metrics.get('resolved_high_priority_domain_count', 0)}",
        f"- Research plan warnings: {research_plan.get('warning_count', 0)}",
        f"- Research plan blocking warnings: {research_plan.get('blocking_warning_count', 0)}",
        "",
        "## Source And Copy Quality",
        "",
        f"- Source warnings: {len(content.get('source_warnings', []) or [])}",
        f"- Blocking content warnings: {content.get('blocking_warning_count', 0)}",
        f"- Density warnings: {len(content.get('density_warnings', []) or [])}",
        f"- Layout warnings: {len(content.get('layout_warnings', []) or [])}",
        f"- Chart data warnings: {len(content.get('chart_data_warnings', []) or [])}",
        "",
        "## PPT Integrity",
        "",
        f"- Remaining placeholders: {ppt_summary.get('remaining_placeholder_count', 'n/a')}",
        f"- Visible scaffold labels: {ppt_summary.get('visible_scaffold_label_count', 'n/a')}",
        f"- Page number issues: {ppt_summary.get('page_number_issue_count', 'n/a')}",
        f"- Actual kept slides: {ppt_summary.get('actual_kept_slide_count', 'n/a')}",
        "",
    ]

    notable: list[str] = []
    for key, source in [
        ("Research plan", research_plan),
        ("Content quality", content),
        ("Final delivery artifact", final_delivery),
        ("Current final delivery", current_final),
    ]:
        for item in (source.get("errors") or [])[:5]:
            notable.append(f"- {key} error: {item}")
        for item in (source.get("blocking_warnings") or [])[:5]:
            notable.append(f"- {key} blocking warning: {item}")

    if notable:
        lines.extend(["## Notable Issues", "", *notable, ""])
    else:
        lines.extend(["## Notable Issues", "", "- None reported by deterministic gates.", ""])

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate artifacts/run_quality_summary.md for a run.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--output", help="Defaults to <run-dir>/artifacts/run_quality_summary.md")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    output = Path(args.output) if args.output else run_dir / "artifacts/run_quality_summary.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_summary(run_dir), encoding="utf-8")
    print(str(output))


if __name__ == "__main__":
    main()

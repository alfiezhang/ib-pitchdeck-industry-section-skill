#!/usr/bin/env python3
"""Validate industry_input_memo.md before storyboard generation."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Optional


REQUIRED_SECTIONS = [
    "Project Meta",
    "Research Plan",
    "Deal Context",
    "Target Business Summary",
    "Industry Definition",
    "Source Materials",
    "Evidence Ledger",
]

WEAK_SOURCE_MARKERS = (
    "zhihu",
    "知乎",
    "baijiahao",
    "百家号",
    "docin",
    "豆丁",
    "aiqicha",
    "爱企查",
    "chinairn",
    "中研普华",
    "training_data",
    "数据聚合平台",
    "行业数据聚合",
)

WEAK_SOURCE_ALLOWED_CONTEXT = (
    "rejected",
    "lead-only",
    "lead only",
    "excluded",
    "排除",
    "线索",
    "未采用",
)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def has_section(text: str, section_name: str) -> bool:
    pattern = rf"^##\s+{re.escape(section_name)}\b"
    return bool(re.search(pattern, text, flags=re.MULTILINE | re.IGNORECASE))


def evidence_ids(text: str) -> set[str]:
    return set(re.findall(r"\bEV-\d{3}\b", text))


def ledger_rows(text: str) -> list[str]:
    in_ledger = False
    rows: list[str] = []
    for line in text.splitlines():
        if re.match(r"^##\s+Evidence Ledger\b", line, flags=re.IGNORECASE):
            in_ledger = True
            continue
        if in_ledger and re.match(r"^##\s+", line):
            break
        if in_ledger and re.match(r"^\|\s*EV-\d{3}\s*\|", line):
            rows.append(line)
    return rows


def page_note_count(text: str) -> int:
    patterns = [
        r"^###\s+Page\s+\d+\b",
        r"^###\s+Slide\s+\d+\b",
        r"^##\s+Page\s+\d+\b",
        r"^##\s+Slide\s+\d+\b",
    ]
    return max(len(re.findall(pattern, text, flags=re.MULTILINE | re.IGNORECASE)) for pattern in patterns)


def page_sections(text: str) -> dict[int, str]:
    """Return memo text grouped by Page/Slide N headings."""
    heading_re = re.compile(r"^(#{2,3})\s+(?:Page|Slide)\s+(\d+)\b.*$", flags=re.MULTILINE | re.IGNORECASE)
    matches = list(heading_re.finditer(text))
    sections: dict[int, str] = {}
    for idx, match in enumerate(matches):
        page_no = int(match.group(2))
        if page_no < 1 or page_no > 8:
            continue
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        sections[page_no] = text[start:end]
    return sections


def page_evidence_pack_issues(text: str) -> tuple[list[str], dict[str, Any]]:
    """Validate that each page has enough evidence and argument material."""
    errors: list[str] = []
    metrics: dict[str, Any] = {}
    sections = page_sections(text)
    for page_no in range(1, 9):
        section = sections.get(page_no, "")
        page_metric: dict[str, Any] = {}
        if not section:
            errors.append(f"page {page_no}: missing page section")
            metrics[str(page_no)] = page_metric
            continue

        ids = evidence_ids(section)
        page_metric["evidence_id_count"] = len(ids)
        if len(ids) < 2:
            errors.append(f"page {page_no}: only {len(ids)} distinct Evidence IDs; expected at least 2")

        has_pack = bool(re.search(r"Page Evidence Pack|Evidence Pack|论据包|证据包", section, flags=re.IGNORECASE))
        page_metric["has_page_evidence_pack"] = has_pack
        if not has_pack:
            errors.append(f"page {page_no}: missing Page Evidence Pack")

        argument_count = len(
            re.findall(
                r"^\s*-\s*(?:Argument|论据)\s*\d+\s*:",
                section,
                flags=re.MULTILINE | re.IGNORECASE,
            )
        )
        if argument_count == 0:
            # Fallback for free-form memos: count argument-like labels under the pack.
            argument_count = len(re.findall(r"^\s*(?:Fact / data|So what|Target relevance|事实|含义|标的)", section, flags=re.MULTILINE | re.IGNORECASE))
            argument_count = argument_count // 3
        page_metric["argument_count"] = argument_count
        if argument_count < 3:
            errors.append(f"page {page_no}: Page Evidence Pack has {argument_count} argument(s); expected at least 3")

        target_relevance_count = len(re.findall(r"Target relevance\s*:|标的", section, flags=re.IGNORECASE))
        page_metric["target_relevance_count"] = target_relevance_count
        if target_relevance_count < 1:
            errors.append(f"page {page_no}: evidence pack lacks target relevance")

        metrics[str(page_no)] = page_metric
    return errors, metrics


def line_has_allowed_weak_context(line: str) -> bool:
    lowered = line.lower()
    return any(marker in lowered for marker in WEAK_SOURCE_ALLOWED_CONTEXT)


def weak_source_issues(text: str) -> list[str]:
    issues: list[str] = []
    formal_context_patterns = (
        "source name",
        "online research sources",
        "evidence ledger",
        "| ev-",
        "selected sources",
        "source:",
        "来源",
    )
    for line_no, line in enumerate(text.splitlines(), start=1):
        lowered = line.lower()
        if not any(marker.lower() in lowered for marker in WEAK_SOURCE_MARKERS):
            continue
        if line_has_allowed_weak_context(line):
            continue
        if any(pattern in lowered for pattern in formal_context_patterns):
            issues.append(
                f"line {line_no}: weak source marker appears in formal memo source/evidence context: {line.strip()[:160]}"
            )
    return issues


def evidence_strength_issues(text: str) -> list[str]:
    issues: list[str] = []
    weak_evidence_terms = ("数据聚合平台", "行业数据聚合", "聚合源", "百度", "爱企查", "中研普华")
    for line_no, line in enumerate(text.splitlines(), start=1):
        if not re.match(r"^\|\s*EV-\d{3}\s*\|", line):
            continue
        lowered = line.lower()
        if not any(term.lower() in lowered for term in weak_evidence_terms):
            continue
        if re.search(r"\|\s*verified\s*\|?\s*$", lowered) or "| verified |" in lowered:
            issues.append(
                f"line {line_no}: weak/data-aggregated evidence row is marked verified; downgrade confidence or add independent validation: {line.strip()[:160]}"
            )
    return issues


def validate(memo_path: Path, run_dir: Optional[Path] = None) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    if not memo_path.exists():
        return {
            "is_valid": False,
            "error_count": 1,
            "warning_count": 0,
            "errors": [f"memo file not found: {memo_path}"],
            "warnings": [],
            "memo": str(memo_path),
        }

    text = read_text(memo_path)
    if len(text.strip()) < 2000:
        errors.append("memo appears incomplete: fewer than 2,000 characters")

    missing_sections = [section for section in REQUIRED_SECTIONS if not has_section(text, section)]
    if missing_sections:
        errors.append("memo missing required section(s): " + ", ".join(missing_sections))

    rows = ledger_rows(text)
    if len(rows) < 5:
        errors.append(f"Evidence Ledger has only {len(rows)} populated EV rows; expected at least 5")

    ids = evidence_ids(text)
    if len(ids) < 8:
        warnings.append(f"memo references only {len(ids)} distinct Evidence IDs; richer runs should use more")

    pages = page_note_count(text)
    if pages < 8:
        errors.append(f"memo has page/slide notes for only {pages} page(s); expected 8")

    page_pack_errors, page_pack_metrics = page_evidence_pack_issues(text)
    errors.extend(page_pack_errors)

    if "chart_ready" not in text:
        warnings.append("memo has no chart_ready flags; quantitative visuals may be under-specified")

    if "HIGH PRIORITY GAP: online research not completed" in text:
        errors.append("memo records mandatory online research failure")

    for issue in weak_source_issues(text):
        errors.append(issue)
    for issue in evidence_strength_issues(text):
        errors.append(issue)

    if run_dir:
        required_artifacts = [
            "artifacts/research_plan.json",
            "artifacts/research_plan_validation.json",
            "artifacts/search_log.md",
        ]
        for rel in required_artifacts:
            if not (run_dir / rel).exists():
                errors.append(f"missing research artifact required before storyboard: {rel}")

    return {
        "is_valid": not errors,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "memo": str(memo_path),
        "run_dir": str(run_dir) if run_dir else "",
        "metrics": {
            "char_count": len(text),
            "evidence_id_count": len(ids),
            "evidence_ledger_row_count": len(rows),
            "page_note_count": pages,
            "page_evidence_pack": page_pack_metrics,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate industry_input_memo.md completeness and source hygiene.")
    parser.add_argument("--memo", required=True, help="Path to industry_input_memo.md")
    parser.add_argument("--run-dir", default="", help="Run directory containing artifacts/")
    parser.add_argument("--output", help="Optional JSON report path")
    args = parser.parse_args()

    result = validate(Path(args.memo), Path(args.run_dir) if args.run_dir else None)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["is_valid"]:
        sys.exit(1)


if __name__ == "__main__":
    main()

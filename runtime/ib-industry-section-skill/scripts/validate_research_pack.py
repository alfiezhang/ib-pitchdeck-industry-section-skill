#!/usr/bin/env python3
"""Validate industry_research_pack.md before issue analysis and deck blueprint generation."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Optional

from metric_scope_utils import compare_metric_scopes
from validate_issue_analysis import ISSUE_TOPICS_BY_AREA as VALID_ISSUE_TOPICS_BY_AREA


REQUIRED_SECTIONS = [
    "Project Meta",
    "search plan",
    "Scope Boundary",
    "Scope Pack And Formal Research Execution Summary",
    "Formal Research Extracts",
    "Deal Context",
    "Target Business Summary",
    "Industry Definition",
    "Source Materials",
    "Evidence Ledger",
    "Metric Reconciliation",
    "IB Issue Fact Inventory",
    "Research Gap Audit",
]

def load_lead_only_domains(registry_path: Optional[Path] = None) -> tuple[str, ...]:
    """Load lead-only domains from source_registry.json."""
    if not registry_path or not registry_path.exists():
        return ()
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        packs = registry.get("source_packs", {})
        domains: list[str] = []
        for pack_name, pack in packs.items():
            if not isinstance(pack, dict):
                continue
            if pack.get("evidence_policy") == "lead_only":
                domains.extend(str(d) for d in pack.get("domains", []))
        return tuple(domains)
    except (json.JSONDecodeError, OSError):
        return ()

WEAK_SOURCE_ALLOWED_CONTEXT = (
    "rejected",
    "lead-only",
    "lead only",
    "excluded",
    "排除",
    "线索",
    "未采用",
)

GENERIC_SOURCE_LOCATORS = {
    "正文",
    "正文段落",
    "官网",
    "官网正文",
    "报告正文",
    "白皮书正文",
    "source",
    "website",
    "webpage",
    "article",
    "report",
    "n/a",
    "na",
    "-",
    "—",
}

REQUIRED_METRIC_FIELDS = (
    "Metric Type",
    "Market Definition",
    "Channel Scope",
    "Geography",
    "Data Period",
    "Value",
    "Unit",
    "Conflict Status",
)

VALID_ISSUE_AREAS = set(VALID_ISSUE_TOPICS_BY_AREA)
VALID_ISSUE_TOPICS = set().union(*VALID_ISSUE_TOPICS_BY_AREA.values())
VALID_FACT_STATUS = {"sufficient", "thin", "insufficient", "not_applicable", "unavailable_after_research"}


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


def evidence_ledger_rows(text: str) -> list[dict[str, str]]:
    """Parse Evidence Ledger table rows into dictionaries."""
    rows: list[dict[str, str]] = []
    in_ledger = False
    header: list[str] = []
    for line in text.splitlines():
        if re.match(r"^##\s+Evidence Ledger\b", line, flags=re.IGNORECASE):
            in_ledger = True
            continue
        if in_ledger and re.match(r"^##\s+", line):
            break
        if not in_ledger or not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.split("|")[1:-1]]
        if not cells:
            continue
        if cells[0] == "Evidence ID":
            header = cells
            continue
        if all(set(c) <= {"-", ":"} for c in cells):
            continue
        if not re.match(r"^EV-\d{3}$", cells[0] if cells else ""):
            continue
        row: dict[str, str] = {}
        for i, cell in enumerate(cells):
            key = header[i] if i < len(header) else f"col_{i}"
            row[key] = cell
        rows.append(row)
    return rows


def section_text(text: str, heading: str, level: int = 2) -> str:
    heading_re = re.compile(
        rf"^#{{{level}}}\s+{re.escape(heading)}\b.*$",
        flags=re.MULTILINE | re.IGNORECASE,
    )
    match = heading_re.search(text)
    if not match:
        return ""
    next_re = re.compile(rf"^#{{1,{level}}}\s+", flags=re.MULTILINE)
    next_match = next_re.search(text, match.end())
    return text[match.end() : next_match.start() if next_match else len(text)]


def subsection_text(parent_text: str, heading: str, level: int = 3) -> str:
    heading_re = re.compile(
        rf"^#{{{level}}}\s+{re.escape(heading)}\b.*$",
        flags=re.MULTILINE | re.IGNORECASE,
    )
    match = heading_re.search(parent_text)
    if not match:
        return ""
    next_re = re.compile(rf"^#{{1,{level}}}\s+", flags=re.MULTILINE)
    next_match = next_re.search(parent_text, match.end())
    return parent_text[match.end() : next_match.start() if next_match else len(parent_text)]


def meaningful_gap_lines(text: str) -> list[str]:
    lines: list[str] = []
    none_markers = {
        "none",
        "no critical gaps",
        "n/a",
        "na",
        "not applicable",
        "无",
        "无重大缺口",
        "不适用",
    }
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line in {"-", "—"} or line.startswith(">"):
            continue
        lowered = line.lower().strip("-: ")
        normalized = lowered.rstrip(".。;；").strip()
        if normalized in none_markers:
            continue
        lines.append(line)
    return lines


def critical_gap_audit_issues(critical_gap_text: str) -> tuple[list[str], list[str]]:
    """Return unresolved critical gap lines and hidden-gap audit errors."""
    errors: list[str] = []
    critical_gaps = meaningful_gap_lines(critical_gap_text)
    lowered_gap_text = critical_gap_text.lower()
    hidden_gap_markers = (
        "unavailable",
        "unresolved",
        "data gap",
        "缺失",
        "无法获取",
        "未验证",
        "需尽调",
        "尽调确认",
        "management due diligence",
        "management interview",
    )
    none_prefixed_hidden_lines = []
    for line in critical_gaps:
        normalized = line.lower().strip("-: ")
        if normalized.startswith(("none ", "none—", "none-", "none:")) and any(
            marker in normalized for marker in hidden_gap_markers
        ):
            none_prefixed_hidden_lines.append(line)
    if none_prefixed_hidden_lines:
        errors.append(
            "Research Gap Audit Critical Gaps uses 'None' while describing unavailable or diligence-only items. "
            "Move non-public target facts to Open DD Questions, keep evidence conflicts as Blocking Evidence Gaps, "
            "and do not hide gaps under 'None'."
        )
        critical_gaps = [line for line in critical_gaps if line not in none_prefixed_hidden_lines]

    if critical_gap_text.strip() and not critical_gaps and not errors:
        if any(marker in lowered_gap_text for marker in hidden_gap_markers):
            errors.append(
                "Research Gap Audit Critical Gaps appears to mark gaps as resolved/None while still describing "
                "unavailable or diligence-only items. Move non-public target facts to Open DD Questions, keep "
                "evidence conflicts as Blocking Evidence Gaps, and do not hide gaps under 'None'."
            )
    return critical_gaps, errors


def line_has_allowed_weak_context(line: str) -> bool:
    lowered = line.lower()
    return any(marker in lowered for marker in WEAK_SOURCE_ALLOWED_CONTEXT)


def metric_reconciliation_rows(text: str) -> list[dict[str, str]]:
    """Parse Metric Reconciliation table rows."""
    rows: list[dict[str, str]] = []
    in_section = False
    header: list[str] = []
    for line in text.splitlines():
        if re.match(r"^##\s+Metric Reconciliation\b", line, flags=re.IGNORECASE):
            in_section = True
            continue
        if in_section and re.match(r"^##\s+", line):
            break
        if not in_section or not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.split("|")[1:-1]]
        if not cells:
            continue
        # Header row: first cell is "Metric Group"
        if cells[0] == "Metric Group":
            header = cells
            continue
        # Skip separator rows (---|---|---)
        if all(set(c) <= {"-", ":"} for c in cells):
            continue
        # Data row: MET-ID is in column 1
        if len(cells) >= 13 and re.match(r"^MET-\d{3}$", cells[1]):
            row: dict[str, str] = {}
            for i, cell in enumerate(cells):
                key = header[i] if i < len(header) else f"col_{i}"
                row[key] = cell
            rows.append(row)
    return rows


def metric_reconciliation_id_set(text: str) -> set[str]:
    return {row.get("Metric ID", "").strip() for row in metric_reconciliation_rows(text) if row.get("Metric ID")}


def issue_fact_inventory_rows(text: str) -> list[dict[str, str]]:
    """Parse the IB Issue Fact Inventory table."""
    rows: list[dict[str, str]] = []
    section = section_text(text, "IB Issue Fact Inventory")
    if not section:
        return rows
    header: list[str] = []
    for line in section.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.split("|")[1:-1]]
        if not cells:
            continue
        if cells[0] == "Issue Area":
            header = cells
            continue
        if all(set(c) <= {"-", ":"} for c in cells):
            continue
        row: dict[str, str] = {}
        for idx, cell in enumerate(cells):
            key = header[idx] if idx < len(header) else f"col_{idx}"
            row[key] = cell
        rows.append(row)
    return rows


def issue_fact_inventory_issues(text: str) -> tuple[list[str], list[str], dict[str, Any]]:
    errors: list[str] = []
    warnings: list[str] = []
    rows = issue_fact_inventory_rows(text)
    metrics = {
        "row_count": len(rows),
        "sufficient_count": 0,
        "thin_count": 0,
        "insufficient_count": 0,
        "not_applicable_count": 0,
    }
    if not rows:
        errors.append("IB Issue Fact Inventory has no populated rows")
        return errors, warnings, metrics

    ledger_ids = {row.get("Evidence ID", "").strip() for row in evidence_ledger_rows(text) if row.get("Evidence ID")}
    metric_ids = metric_reconciliation_id_set(text)
    seen: set[tuple[str, str]] = set()
    for idx, row in enumerate(rows, start=1):
        prefix = f"IB Issue Fact Inventory row {idx}"
        area = (row.get("Issue Area") or "").strip()
        topic = (row.get("Subissue") or row.get("Issue Topic") or "").strip()
        status = (row.get("Fact Status") or "").strip()
        evidence_refs = re.findall(r"\bEV-\d{3}\b", row.get("Evidence IDs", ""))
        metric_refs = re.findall(r"\bMET-\d{3}\b", row.get("Metric IDs", ""))

        if area not in VALID_ISSUE_AREAS:
            errors.append(f"{prefix}: invalid Issue Area '{area}'")
        if topic not in VALID_ISSUE_TOPICS:
            errors.append(f"{prefix}: invalid Subissue '{topic}'")
        elif area and topic not in VALID_ISSUE_TOPICS_BY_AREA.get(area, set()):
            errors.append(f"{prefix}: Subissue '{topic}' does not belong to Issue Area '{area}'")
        if status not in VALID_FACT_STATUS:
            errors.append(f"{prefix}: Fact Status must be one of {sorted(VALID_FACT_STATUS)}")
        else:
            metrics[f"{status}_count"] = int(metrics.get(f"{status}_count", 0)) + 1
        if area and topic:
            key = (area, topic)
            if key in seen:
                warnings.append(f"{prefix}: duplicate issue topic {area}/{topic}")
            seen.add(key)
        if status in {"sufficient", "thin"} and not (evidence_refs or metric_refs):
            errors.append(f"{prefix}: {status} fact status requires Evidence IDs or Metric IDs")
        missing_ev = sorted(set(evidence_refs) - ledger_ids)
        if missing_ev:
            errors.append(f"{prefix}: Evidence IDs not found in Evidence Ledger: {', '.join(missing_ev)}")
        missing_met = sorted(set(metric_refs) - metric_ids)
        if missing_met:
            errors.append(f"{prefix}: Metric IDs not found in Metric Reconciliation: {', '.join(missing_met)}")
    if metrics["sufficient_count"] + metrics["thin_count"] == 0:
        warnings.append("IB Issue Fact Inventory has no sufficient/thin issue topics; issue analysis will likely produce only backlog")
    return errors, warnings, metrics


def metric_reference_issues(text: str) -> list[str]:
    """Require every research pack MET-ID reference to be defined in Metric Reconciliation."""
    reconciled = metric_reconciliation_id_set(text)
    referenced = set(re.findall(r"\bMET-\d{3}\b", text))
    missing = sorted(referenced - reconciled)
    if not missing:
        return []
    if not reconciled:
        return [
            "Metric Reconciliation is empty but research pack references MET-IDs elsewhere: "
            + ", ".join(missing[:12])
            + ". Define all slide/chart Key Data Point MET-IDs in Metric Reconciliation before renderer spec."
        ]
    return [
        "MET-ID(s) referenced outside Metric Reconciliation are not defined in the Metric Reconciliation table: "
        + ", ".join(missing[:12])
        + ". Key Data Points, chart-ready data, page evidence contract, and renderer spec metrics must reuse defined MET-IDs."
    ]


def approx_equal(a: float, b: float, tolerance: float = 0.03) -> bool:
    """Check approximate equality within tolerance."""
    if b == 0:
        return abs(a) < 0.01
    return abs(a - b) <= tolerance * max(abs(a), abs(b), 1.0)


def calculate_cagr(beginning: float, ending: float, years: float) -> float:
    """Calculate CAGR from beginning and ending values."""
    if beginning <= 0 or years <= 0:
        return 0.0
    return (ending / beginning) ** (1.0 / years) - 1.0


_PARSE_NUM = re.compile(r"([\d,]+(?:\.\d+)?)")
_YEARS_RE = re.compile(r"(\d{4})")
_STANDARD_MET_ID_RE = re.compile(r"\bMET-\d{3}\b")
_MET_LIKE_RE = re.compile(r"\bMET[-_]?[A-Za-z0-9]+\b")


def _parse_number(raw: str) -> Optional[float]:
    """Extract a numeric value from a string."""
    if not raw:
        return None
    clean = raw.replace(",", "").replace(" ", "")
    # Handle ranges: take average
    parts = _PARSE_NUM.findall(clean)
    if not parts:
        return None
    values = []
    for p in parts:
        try:
            values.append(float(p))
        except ValueError:
            continue
    if not values:
        return None
    return sum(values) / len(values)


def _parse_years(raw: str) -> float:
    """Parse a year range into number of years."""
    years = _YEARS_RE.findall(str(raw))
    if len(years) >= 2:
        begin = int(years[0])
        end = int(years[-1])
        return float(max(1, end - begin))
    return 0.0


def parse_percent_value(raw: str) -> Optional[float]:
    """Return decimal value: 4.3% -> 0.043; 0.043 -> 0.043."""
    value = _parse_number(str(raw or ""))
    if value is None:
        return None
    return value / 100.0 if value > 1 else value


def parse_period_endpoint(raw: str) -> tuple[Optional[int], Optional[int]]:
    """Parse ordered year endpoints from a period string."""
    years = [int(year) for year in _YEARS_RE.findall(str(raw or ""))]
    if len(years) >= 2:
        return years[0], years[-1]
    if len(years) == 1:
        return years[0], years[0]
    return None, None


def parse_single_period_year(raw: str) -> Optional[int]:
    begin, end = parse_period_endpoint(raw)
    if begin is None:
        return None
    return end if end is not None else begin


def validate_cagr_metric(cagr_id: str, cagr_row: dict[str, Any], rows_by_id: dict[str, dict[str, Any]]) -> list[str]:
    """Validate a CAGR row using ordered CAGR Endpoint IDs."""
    issues: list[str] = []
    endpoint_raw = str(cagr_row.get("CAGR Endpoint IDs", "") or "")
    endpoint_ids = _STANDARD_MET_ID_RE.findall(endpoint_raw)
    if len(endpoint_ids) != 2:
        comparable_ids = _STANDARD_MET_ID_RE.findall(str(cagr_row.get("Comparable With", "") or ""))
        met_like_ids = _MET_LIKE_RE.findall(endpoint_raw)
        nonstandard_ids = sorted(set(item for item in met_like_ids if not _STANDARD_MET_ID_RE.fullmatch(item)))
        detail = ""
        if nonstandard_ids:
            detail = (
                f" Non-standard endpoint ID(s) found: {', '.join(nonstandard_ids)}. "
                "Endpoint rows must use existing numeric Metric IDs matching MET-###, e.g. MET-021 and MET-022; "
                "do not rename endpoints to MET-BGN, MET-END, METBGN, or METEND."
            )
        elif comparable_ids and not endpoint_ids:
            detail = (
                f" Comparable With currently contains {', '.join(comparable_ids)}; move the two ordered begin/end IDs "
                "into CAGR Endpoint IDs instead of relying on Comparable With."
            )
        elif endpoint_raw.strip():
            detail = f" Current CAGR Endpoint IDs value: {endpoint_raw!r}."
        return [
            f"{cagr_id}: CAGR row must define exactly two ordered CAGR Endpoint IDs "
            "(beginning MET-ID, ending MET-ID). Comparable With cannot replace CAGR Endpoint IDs."
            + detail
        ]
    begin_id, end_id = endpoint_ids
    if begin_id not in rows_by_id or end_id not in rows_by_id:
        missing = [met_id for met_id in endpoint_ids if met_id not in rows_by_id]
        return [f"{cagr_id}: CAGR Endpoint IDs reference missing metric(s): {', '.join(missing)}"]

    begin_row = rows_by_id[begin_id]
    end_row = rows_by_id[end_id]
    scope = compare_metric_scopes(begin_row, end_row)
    if not scope["comparable"]:
        issues.append(
            f"{cagr_id}: CAGR endpoints are not comparable: {begin_id} vs {end_id}; {scope['reason']}"
        )

    begin_value = _parse_number(begin_row.get("Value", ""))
    end_value = _parse_number(end_row.get("Value", ""))
    stated = parse_percent_value(cagr_row.get("Value", ""))
    if begin_value is None or begin_value <= 0:
        issues.append(f"{cagr_id}: beginning endpoint {begin_id} has invalid value {begin_row.get('Value', '')!r}")
    if end_value is None or end_value <= 0:
        issues.append(f"{cagr_id}: ending endpoint {end_id} has invalid value {end_row.get('Value', '')!r}")
    if stated is None:
        issues.append(f"{cagr_id}: CAGR value is missing or not numeric")

    begin_year = parse_single_period_year(begin_row.get("Data Period", ""))
    end_year = parse_single_period_year(end_row.get("Data Period", ""))
    if begin_year is None or end_year is None:
        issues.append(
            f"{cagr_id}: CAGR endpoint periods must parse to years; "
            f"{begin_id}={begin_row.get('Data Period', '')!r}, {end_id}={end_row.get('Data Period', '')!r}"
        )
    elif end_year <= begin_year:
        issues.append(
            f"{cagr_id}: CAGR endpoint years must be ordered beginning→ending; "
            f"{begin_id}={begin_year}, {end_id}={end_year}"
        )

    if issues or begin_value is None or end_value is None or stated is None or begin_year is None or end_year is None:
        return issues

    years = end_year - begin_year
    calculated = calculate_cagr(begin_value, end_value, years)
    if abs(stated - calculated) > 0.002:
        issues.append(
            f"{cagr_id}: CAGR mismatch. Stated {stated * 100:.2f}%, calculated {calculated * 100:.2f}% from "
            f"{begin_id}={begin_value:,.2f} ({begin_row.get('Data Period', '')}) to "
            f"{end_id}={end_value:,.2f} ({end_row.get('Data Period', '')}), {years} years. "
            "Fix Metric Reconciliation or visible slide copy before renderer spec."
        )
    return issues


def lead_only_domain_issues(text: str, lead_only_domains: tuple[str, ...] = ()) -> list[str]:
    """Flag lead-only domains appearing in Evidence Ledger or formal sources."""
    if not lead_only_domains:
        lead_only_domains = load_lead_only_domains()
    issues: list[str] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        lowered = line.lower()
        if not re.match(r"^\|\s*EV-\d{3}\s*\|", line):
            continue
        for domain in lead_only_domains:
            if domain in lowered:
                # Check if marked as primary-reviewed
                if "primary-reviewed" in lowered:
                    issues.append(
                        f"line {line_no}: lead-only domain '{domain}' in evidence row is marked primary-reviewed. "
                        "Move this source out of the formal Evidence Ledger and keep it in search_log.md or "
                        "supplementary lead notes until the original methodology/report context is confirmed. "
                        "Do not merely relabel a lead-only source as formal evidence."
                    )
                else:
                    issues.append(
                        f"line {line_no}: lead-only domain '{domain}' in evidence row. "
                        "Move this source out of the formal Evidence Ledger and keep it in search_log.md or "
                        "supplementary lead notes until the original methodology/report context is confirmed."
                    )
                break
    return issues


def evidence_promotion_issues(text: str) -> list[str]:
    """Validate Evidence Ledger promotion fields."""
    issues: list[str] = []
    allowed_scopes = {"industry-level", "target-level", "transaction-inference"}
    allowed_statuses = {"primary-reviewed", "secondary-reviewed", "lead-only"}

    for row in evidence_ledger_rows(text):
        ev_id = row.get("Evidence ID", "EV-???")
        scope = row.get("Claim Scope", "").strip().lower()
        status = row.get("Evidence Status", "").strip().lower()
        locator = row.get("Source Locator", "").strip()
        excerpt = row.get("Raw Excerpt", "").strip()
        source_name = row.get("Source Name", "").strip()
        source_url = row.get("Source URL", "").strip()
        source_type = row.get("Source Type", "").strip().lower()

        if not row.get("Claim / Metric", "").strip():
            issues.append(f"{ev_id}: Claim / Metric is required")
        if scope not in allowed_scopes:
            issues.append(f"{ev_id}: Claim Scope must be one of {sorted(allowed_scopes)}")
        if status not in allowed_statuses:
            issues.append(f"{ev_id}: Evidence Status must be one of {sorted(allowed_statuses)}")
        if not source_name and not source_url:
            issues.append(f"{ev_id}: Source Name or Source URL is required")
        if status in {"primary-reviewed", "secondary-reviewed"}:
            is_user_material = any(token in source_type for token in ("user", "client", "management", "provided", "用户", "客户", "管理层"))
            if not is_user_material:
                if not source_url:
                    issues.append(f"{ev_id}: formal external evidence requires a full Source URL")
                elif not re.match(r"^https?://[^\s/$.?#][^\s]*$", source_url, flags=re.IGNORECASE):
                    issues.append(
                        f"{ev_id}: Source URL '{source_url}' is not a full URL; use the exact article/report/PDF URL"
                    )

        if status == "lead-only":
            issues.append(
                f"{ev_id}: lead-only evidence must stay in search_log.md or supplementary lead notes, not formal "
                "Evidence Ledger. Move the row out; do not merely relabel it as lead-only."
            )
        if status == "primary-reviewed":
            if not locator:
                issues.append(f"{ev_id}: primary-reviewed evidence requires Source Locator")
            elif locator.lower() in GENERIC_SOURCE_LOCATORS:
                issues.append(
                    f"{ev_id}: Source Locator '{locator}' is too generic; use page, section, table, paragraph, or URL anchor"
                )
            if not excerpt:
                issues.append(f"{ev_id}: primary-reviewed evidence requires Raw Excerpt")
        elif status == "secondary-reviewed":
            if not locator:
                issues.append(
                    f"{ev_id}: secondary-reviewed evidence should still record Source Locator or explain the limitation"
                )
            if not excerpt:
                issues.append(
                    f"{ev_id}: secondary-reviewed evidence should include Raw Excerpt or a limitation note"
                )
    return issues


def metric_required_field_issues(text: str) -> list[str]:
    """Require slide-bound metrics to carry enough scope metadata."""
    issues: list[str] = []
    for row in metric_reconciliation_rows(text):
        met_id = row.get("Metric ID", "MET-???")
        missing = [field for field in REQUIRED_METRIC_FIELDS if not row.get(field, "").strip()]
        if missing:
            issues.append(f"{met_id}: missing required Metric Reconciliation field(s): {', '.join(missing)}")
        conflict = row.get("Conflict Status", "").strip().lower()
        if conflict in {"conflicting", "not_comparable", "unresolved"} and not row.get("Resolution", "").strip():
            issues.append(f"{met_id}: Conflict Status is '{conflict}' but Resolution is blank")
    return issues


def math_consistency_checks(text: str) -> list[str]:
    """Check mathematical consistency in research pack metrics."""
    issues: list[str] = []

    rows = metric_reconciliation_rows(text)
    if len(rows) < 2:
        return issues  # Not enough structured metric data to check

    parsed: dict[str, dict[str, Any]] = {}
    for row in rows:
        met_id = row.get("Metric ID", "")
        if not met_id or not met_id.startswith("MET-"):
            continue
        value = _parse_number(row.get("Value", ""))
        conflict = row.get("Conflict Status", "").strip().lower()
        metric_type = row.get("Metric Type", "").strip().lower()
        channel = row.get("Channel Scope", "").strip()
        market_def = row.get("Market Definition", "").strip()
        comparable_raw = row.get("Comparable With", "")
        comparable = set(re.findall(r"MET-\d{3}", comparable_raw)) if comparable_raw else set()
        endpoint_raw = row.get("CAGR Endpoint IDs", "")
        cagr_endpoint_ids = re.findall(r"MET-\d{3}", endpoint_raw)

        parent_metric_id = row.get("Parent Metric ID", "").strip()
        is_share_metric = "share" in metric_type or any(token in metric_type for token in ("份额", "占比", "比例"))
        # Normalize share values: 51.2 → 0.512
        if is_share_metric and value is not None and value > 1:
            value = value / 100.0
        parsed[met_id] = {
            "name": row.get("Metric Name", ""),
            "value": value,
            "conflict": conflict,
            "metric_type": metric_type,
            "is_share_metric": is_share_metric,
            "channel": channel,
            "market_def": market_def,
            "data_period": row.get("Data Period", "").strip(),
            "unit": row.get("Unit", "").strip(),
            "comparable": comparable,
            "parent_metric_id": parent_metric_id,
            "cagr_endpoint_ids": cagr_endpoint_ids,
            "raw": row,
        }
        metric_name_lc = str(row.get("Metric Name", "")).lower()
        if is_share_metric and re.search(r"(growth|cagr|yoy|增速|增长|同比|复合增长)", metric_name_lc):
            issues.append(
                f"{met_id} ({row.get('Metric Name', '')}): Metric Type is '{metric_type}' but the metric appears to be a growth/rate claim. "
                "Use Metric Type 'growth' or 'cagr' for growth rates; reserve 'share' for part-of-whole percentages with a clear denominator."
            )

    # Check 1: Subset ≤ parent set (via Parent Metric ID)
    for met_id, m in parsed.items():
        if m["value"] is None:
            continue
        parent_id = m.get("parent_metric_id", "")
        if not parent_id or parent_id not in parsed:
            continue
        parent = parsed[parent_id]
        if parent["value"] is None:
            continue
        if m.get("is_share_metric") or parent.get("is_share_metric"):
            continue
        if m["value"] > parent["value"] * (1.0 + 0.05):
            issues.append(
                f"{met_id} ({m['name']}): value {m['value']:.2f} exceeds parent "
                f"{parent_id} ({parent['name']}) value {parent['value']:.2f}. "
                f"A subset metric should not be larger than its parent metric."
            )
        elif m["value"] > parent["value"]:
            issues.append(
                f"{met_id} ({m['name']}): value {m['value']:.2f} slightly exceeds "
                f"{parent_id} ({parent['name']}) value {parent['value']:.2f}. "
                f"Check if definitions are genuinely comparable or differ in scope."
            )

    # Check 2: Share sums ≈ 100% (group by same metric_type and channel_scope)
    share_groups: dict[tuple[str, str], list[tuple[str, float]]] = {}
    for met_id, m in parsed.items():
        if m["value"] is None or not m.get("is_share_metric"):
            continue
        group_anchor = str(m.get("parent_metric_id") or m.get("market_def", "")).strip()
        if group_anchor in {"", "-", "n/a", "N/A"}:
            continue
        group_key = (group_anchor, m.get("channel", ""))
        share_groups.setdefault(group_key, []).append((met_id, abs(m["value"])))

    for group_key, shares in share_groups.items():
        if len(shares) < 3:
            continue  # Need at least 3 shares for a meaningfull check on sum
        total = sum(s for _, s in shares)
        if total < 0.1:
            continue
        if not approx_equal(total, 1.0, 0.05):
            ids = ", ".join(f"{mid}({val:.1%})" for mid, val in shares[:6])
            issues.append(
                f"Share group ({group_key[0]} / {group_key[1]}): sum is {total:.2%}, expected ~100%. "
                f"Shares: {ids}"
            )

    # Check 3: CAGR matches ordered endpoint IDs
    cagr_rows = [(met_id, m) for met_id, m in parsed.items() if m["metric_type"] == "cagr" and m["value"] is not None]
    raw_rows_by_id = {met_id: m["raw"] for met_id, m in parsed.items()}
    for cagr_id, cagr_m in cagr_rows:
        issues.extend(validate_cagr_metric(cagr_id, cagr_m["raw"], raw_rows_by_id))

    # Check 4: No conflicting values for same metric (same metric_type + market_def + channel_scope + data_period)
    key_groups: dict[tuple[str, str, str, str], list[tuple[str, float]]] = {}
    for met_id, m in parsed.items():
        if m["value"] is None:
            continue
        if m.get("is_share_metric"):
            continue
        key = (m.get("metric_type", ""), m.get("market_def", ""), m.get("channel", ""), m.get("data_period", ""))
        key_groups.setdefault(key, []).append((met_id, m["value"]))

    for key, values in key_groups.items():
        if len(values) < 2:
            continue
        unique_values = set(round(v, 4) for _, v in values)
        if len(unique_values) > 1:
            ids = ", ".join(f"{mid}({val:.2f})" for mid, val in values)
            issues.append(
                f"Conflicting metric values for ({key[0]}/{key[1]}/{key[2]}): {ids}"
            )

    return issues


def validate(memo_path: Path, run_dir: Optional[Path] = None, source_registry_path: Optional[Path] = None) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    lead_only_domains = load_lead_only_domains(source_registry_path)

    if not memo_path.exists():
        return {
            "is_valid": False,
            "error_count": 1,
            "warning_count": 0,
            "errors": [f"research pack file not found: {memo_path}"],
            "warnings": [],
            "research_pack": str(memo_path),
        }

    text = read_text(memo_path)
    if len(text.strip()) < 2000:
        errors.append("research pack appears incomplete: fewer than 2,000 characters")

    missing_sections = [section for section in REQUIRED_SECTIONS if not has_section(text, section)]
    if missing_sections:
        errors.append("research pack missing required section(s): " + ", ".join(missing_sections))

    rows = ledger_rows(text)
    if len(rows) == 0:
        errors.append("Evidence Ledger has no populated EV rows")
    elif len(rows) < 5:
        warnings.append(
            f"Evidence Ledger has only {len(rows)} populated EV rows; focused runs can be valid, "
            "but every material slide conclusion must be defensible."
        )

    metric_rows = metric_reconciliation_rows(text)
    if len(metric_rows) == 0:
        warnings.append(
            "Metric Reconciliation has no populated MET rows. This is acceptable only if the renderer spec avoids "
            "material quantitative claims and chart-ready numeric visuals."
        )
    elif len(metric_rows) < 2:
        warnings.append(
            f"Metric Reconciliation has only {len(metric_rows)} populated MET row; make sure every material "
            "numeric claim and chart datapoint can be traced."
        )

    ids = evidence_ids(text)
    if len(ids) < 8:
        warnings.append(f"research pack references only {len(ids)} distinct Evidence IDs; richer runs should use more")

    scope_execution_summary = section_text(text, "Scope Pack And Formal Research Execution Summary")
    if scope_execution_summary and "Formal Research Execution Results" not in scope_execution_summary:
        warnings.append(
            "Scope Pack And Formal Research Execution Summary does not include Formal Research Execution Results; "
            "issue analysis should still rely on formal_research_execution_report.json as the machine-readable control record."
        )

    inventory_errors, inventory_warnings, inventory_metrics = issue_fact_inventory_issues(text)
    errors.extend(inventory_errors)
    warnings.extend(inventory_warnings)

    if "chart_ready" not in text:
        warnings.append("research pack has no chart_ready flags; quantitative visuals may be under-specified")

    if "HIGH PRIORITY GAP: online research not completed" in text:
        errors.append("research pack records mandatory online research failure")

    gap_audit = section_text(text, "Research Gap Audit")
    if gap_audit:
        critical_gap_text = subsection_text(gap_audit, "Critical Gaps")
        critical_gaps, critical_gap_errors = critical_gap_audit_issues(critical_gap_text)
        errors.extend(critical_gap_errors)
        if critical_gaps:
            errors.append(
                "Research Gap Audit has unresolved Critical Gaps; run focused supplemental research before deck blueprint / renderer spec: "
                + "; ".join(critical_gaps[:3])
            )
        metric_check = subsection_text(gap_audit, "Metric Consistency Check")
        if not metric_check or len(meaningful_gap_lines(metric_check)) < 4:
            errors.append("Research Gap Audit missing a populated Metric Consistency Check")
        else:
            required_metric_labels = [
                "GMV vs revenue",
                "Cross-slide repeated metric consistency",
                "Target financials consistency",
                "User-provided vs external-source discrepancy",
                "Chart number consistency",
            ]
            missing_metric_labels = [
                label for label in required_metric_labels
                if label.lower() not in metric_check.lower()
            ]
            if missing_metric_labels:
                errors.append(
                    "Research Gap Audit Metric Consistency Check missing required item(s): "
                    + ", ".join(missing_metric_labels)
                )

    for issue in lead_only_domain_issues(text, lead_only_domains):
        errors.append(issue)
    for issue in evidence_promotion_issues(text):
        errors.append(issue)
    for issue in metric_required_field_issues(text):
        errors.append(issue)
    for issue in metric_reference_issues(text):
        errors.append(issue)

    math_issues = math_consistency_checks(text)
    for issue in math_issues:
        errors.append(issue)

    if run_dir:
        required_artifacts = [
            "artifacts/industry_scope_pack.json",
            "artifacts/industry_scope_pack_validation.json",
            "artifacts/formal_search_plan.json",
            "artifacts/formal_search_plan_validation.json",
            "artifacts/search_log.md",
            "artifacts/source_reviews.json",
            "artifacts/source_archive/source_archive_index.json",
            "artifacts/source_archive_validation.json",
            "artifacts/source_reviews_validation.json",
            "artifacts/formal_research_execution_report.json",
            "artifacts/formal_research_execution_validation.json",
            "artifacts/stage_gate_pre_research_pack_validation.json",
        ]
        for rel in required_artifacts:
            artifact_path = run_dir / rel
            if not artifact_path.exists():
                errors.append(f"missing research artifact required before deck blueprint / renderer spec: {rel}")
                continue
            if rel.endswith("_validation.json"):
                try:
                    validation = json.loads(artifact_path.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError) as exc:
                    errors.append(f"cannot read research artifact validation {rel}: {exc}")
                    continue
                if validation.get("is_valid") is False:
                    errors.append(f"{rel} is_valid=false; fix upstream research/source review gate before validating research pack")

    return {
        "is_valid": not errors,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "research_pack": str(memo_path),
        "run_dir": str(run_dir) if run_dir else "",
        "metrics": {
            "char_count": len(text),
            "evidence_id_count": len(ids),
            "evidence_ledger_row_count": len(rows),
            "issue_fact_inventory": inventory_metrics,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate industry_research_pack.md completeness and source hygiene.")
    parser.add_argument("--research-pack", dest="research_pack", required=True, help="Path to industry_research_pack.md")
    parser.add_argument("--run-dir", default="", help="Run directory containing artifacts/")
    parser.add_argument("--source-registry", default="", help="Path to templates/source_registry.json for dynamic lead-only domain loading")
    parser.add_argument("--output", help="Optional JSON report path")
    args = parser.parse_args()

    result = validate(
        Path(args.research_pack),
        Path(args.run_dir) if args.run_dir else None,
        Path(args.source_registry) if args.source_registry else None,
    )
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["is_valid"]:
        sys.exit(1)


if __name__ == "__main__":
    main()

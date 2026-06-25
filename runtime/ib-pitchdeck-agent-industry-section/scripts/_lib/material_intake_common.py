#!/usr/bin/env python3
"""Shared helpers for deterministic material extraction scripts."""

from __future__ import annotations

from pathlib import Path
import hashlib
from typing import Any

CANONICAL_SOURCE_TYPES = (
    "project_specific_material",
    "user_curated_industry_report",
    "web_search_result",
    "company_material",
    "market_data_source",
    "manual_url_ingestion",
    "ppt_template",
    "official_filing",
    "company_disclosure",
    "industry_report",
    "regulator",
    "business_media",
    "database",
    "other",
)


SOURCE_TYPE_ALIASES = {
    "user_provided": "project_specific_material",
    "user provided": "project_specific_material",
    "input_card": "project_specific_material",
    "management": "project_specific_material",
    "company/user-provided": "project_specific_material",
    "company user": "company_material",
    "search_result": "web_search_result",
    "search result": "web_search_result",
    "web_search": "web_search_result",
    "web search": "web_search_result",
    "manual_url": "manual_url_ingestion",
    "manual url": "manual_url_ingestion",
    "url_ingestion": "manual_url_ingestion",
    "market_data": "market_data_source",
    "market data": "market_data_source",
    "financial_data": "market_data_source",
    "ppt_template": "ppt_template",
    "ppt template": "ppt_template",
    "powerpoint_template": "ppt_template",
    "powerpoint template": "ppt_template",
    "template_ppt": "ppt_template",
    "template ppt": "ppt_template",
    "presentation_template": "ppt_template",
    "presentation template": "ppt_template",
    "模板": "ppt_template",
}


USER_MATERIAL_SOURCE_TYPES = {
    "project_specific_material",
    "user_curated_industry_report",
    "company_material",
    "manual_url_ingestion",
    "ppt_template",
}


def normalize_source_type(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return "other"
    if raw in CANONICAL_SOURCE_TYPES:
        return raw
    if raw in SOURCE_TYPE_ALIASES:
        return SOURCE_TYPE_ALIASES[raw]
    for token, canonical in SOURCE_TYPE_ALIASES.items():
        if token in raw:
            return canonical
    return "other"


def is_material_type(source_type: str) -> bool:
    return normalize_source_type(source_type) in USER_MATERIAL_SOURCE_TYPES


def is_web_search_type(source_type: str) -> bool:
    return normalize_source_type(source_type) == "web_search_result"


def text(value: Any) -> str:
    return str(value or "").strip()


def as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "y", "yes", "on"}


def is_url(value: str) -> bool:
    lowered = text(value).lower()
    return lowered.startswith(("http://", "https://", "mailto:", "ftp://"))


def infer_material_kind(source_path: str, source_type: str) -> str:
    """Classify source kind without inferring facts from file names.

    `source_type` controls whether this is a curated or user-provided URL/file;
    this helper only normalizes shape so validators have stable values.
    """

    source_path = text(source_path)
    if normalize_source_type(source_type) == "ppt_template":
        return "ppt_template"
    if source_path == "inline_user_text":
        return "text"
    if is_url(source_path):
        return "url"
    return "file"


def normalize_source_type_hint(path_or_url: str, provided_type: str | None) -> str:
    value = text(path_or_url)
    if provided_type:
        return normalize_source_type(provided_type)
    if is_url(value):
        return normalize_source_type("manual_url_ingestion")
    return normalize_source_type("project_specific_material")


def classify_access(source_type: str, source_path: str | None = None) -> str:
    normalized = normalize_source_type(source_type)
    if is_url(source_path or "") or normalized == "web_search_result":
        return "public_search"
    return "user_provided"


def file_fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        digest.update(path.read_bytes())
        return digest.hexdigest()
    except Exception:
        return ""


def read_text_file(path: str | Path) -> str:
    p = Path(path)
    try:
        raw = p.read_bytes()
    except Exception:
        return ""
    try:
        return raw.decode("utf-8")
    except Exception:
        try:
            return raw.decode("latin1")
        except Exception:
            return ""


def clean_text_block(value: str) -> str:
    text_value = value or ""
    lines = [line.strip() for line in text_value.replace("\x00", "").splitlines()]
    filtered = [line for line in lines if line and "BT" not in line and "ET" not in line]
    return "\n".join(filtered)

"""Source classification helpers for Material / Source metadata lineage."""

from __future__ import annotations

from typing import Any


CANONICAL_SOURCE_TYPES = (
    # New material taxonomy
    "project_specific_material",
    "user_curated_industry_report",
    "web_search_result",
    "company_material",
    "market_data_source",
    "repository_retrieval",
    "manual_url_ingestion",
    # Legacy + compatibility values used in existing artifacts
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
    "repository": "repository_retrieval",
    "repository_retrieval": "repository_retrieval",
    "repo_retrieval": "repository_retrieval",
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
}


USER_MATERIAL_SOURCE_TYPES = {
    "project_specific_material",
    "user_curated_industry_report",
    "company_material",
    "repository_retrieval",
    "manual_url_ingestion",
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

"""Source classification helpers for Material / Source metadata lineage."""

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
_IB_SHARED_SCRIPT_DIR = _IB_RUNTIME_ROOT / "scripts"
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
    "ppt_template",
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
    "repository_retrieval",
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

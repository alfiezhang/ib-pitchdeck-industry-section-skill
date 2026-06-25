#!/usr/bin/env python3
"""Config-backed industry issue taxonomy shared by research and analysis tools."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _runtime_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "configs").is_dir() and (parent / "scripts").is_dir():
            return parent
    raise RuntimeError("Cannot locate runtime root for issue taxonomy")


def _load_issue_topics_by_area() -> dict[str, set[str]]:
    path = _runtime_root() / "configs" / "research_issue_taxonomy.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw = payload.get("issue_topics_by_area") if isinstance(payload, dict) else None
    if not isinstance(raw, dict) or not raw:
        raise ValueError(f"{path} must contain non-empty issue_topics_by_area")
    result: dict[str, set[str]] = {}
    for issue_area, subissues in raw.items():
        if not isinstance(issue_area, str) or not issue_area.strip():
            raise ValueError(f"{path} contains an invalid issue area")
        if not isinstance(subissues, list) or not subissues:
            raise ValueError(f"{path} issue area {issue_area!r} must contain a non-empty subissue list")
        clean = {str(item).strip() for item in subissues if str(item).strip()}
        if not clean:
            raise ValueError(f"{path} issue area {issue_area!r} has no usable subissues")
        result[issue_area.strip()] = clean
    return result


ISSUE_TOPICS_BY_AREA = _load_issue_topics_by_area()
VALID_ISSUE_AREAS = set(ISSUE_TOPICS_BY_AREA)
VALID_SUBISSUES = set().union(*ISSUE_TOPICS_BY_AREA.values()) if ISSUE_TOPICS_BY_AREA else set()


def is_valid_issue_pair(issue_area: str, subissue: str) -> bool:
    return subissue in ISSUE_TOPICS_BY_AREA.get(issue_area, set())


def configured_issue_taxonomy() -> dict[str, Any]:
    return {area: sorted(subissues) for area, subissues in ISSUE_TOPICS_BY_AREA.items()}

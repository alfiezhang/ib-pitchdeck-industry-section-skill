#!/usr/bin/env python3
"""Resolve a stable case slug for run directory grouping."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def first_text(*values: Any) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[\\/:*?\"<>|]+", "_", text)
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^0-9a-zA-Z_\-\u4e00-\u9fff]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_-.")
    return text[:80] or "case_unspecified"


def resolve_from_input_card(path: Path) -> str:
    data = load_json(path)
    if not data:
        return ""
    meta = data.get("project_meta", {}) if isinstance(data.get("project_meta"), dict) else {}
    target = first_text(
        data.get("target_company"),
        data.get("target_name"),
        meta.get("target_company"),
        meta.get("target_name"),
    )
    industry = first_text(data.get("industry"), meta.get("industry"), data.get("subsector"), meta.get("subsector"))
    if target and industry:
        return f"{target}_{industry}"
    return target or industry


def resolve_from_renderer_spec(path: Path) -> str:
    data = load_json(path)
    if not data:
        return ""
    meta = data.get("section_meta", {}) if isinstance(data.get("section_meta"), dict) else {}
    target = first_text(meta.get("target_company"), meta.get("target_name"), data.get("target_company"))
    industry = first_text(meta.get("industry"), meta.get("subsector"), data.get("industry"))
    if target and industry:
        return f"{target}_{industry}"
    return target or industry


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve a case slug from explicit name or project artifacts.")
    parser.add_argument("--case-name", default="")
    parser.add_argument("--input-card", default="")
    parser.add_argument("--renderer-spec", default="")
    parser.add_argument("--fallback", default="case_unspecified")
    args = parser.parse_args()

    resolved = args.case_name.strip()
    if not resolved and args.input_card:
        resolved = resolve_from_input_card(Path(args.input_card))
    if not resolved and args.renderer_spec:
        resolved = resolve_from_renderer_spec(Path(args.renderer_spec))
    if not resolved:
        resolved = args.fallback
    print(slugify(resolved))


if __name__ == "__main__":
    main()

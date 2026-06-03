#!/usr/bin/env python3
"""Helpers for comparing memo Metric Reconciliation scope."""

from __future__ import annotations

import re
from typing import Any


SCOPE_FIELDS = (
    "Metric Type",
    "Market Definition",
    "Channel Scope",
    "Geography",
    "Unit",
)


def normalize_scope_value(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"\s+", "", text)
    return text


def metric_scope_signature(metric_row: dict[str, Any]) -> tuple[str, ...]:
    return tuple(normalize_scope_value(metric_row.get(field, "")) for field in SCOPE_FIELDS)


def compare_metric_scopes(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    differences: list[str] = []
    for field in SCOPE_FIELDS:
        av = normalize_scope_value(a.get(field, ""))
        bv = normalize_scope_value(b.get(field, ""))
        if av and bv and av != bv:
            differences.append(field)
    return {
        "comparable": not differences,
        "differences": differences,
        "reason": ", ".join(
            f"{field}: {a.get(field, '')!r} vs {b.get(field, '')!r}"
            for field in differences
        ),
    }

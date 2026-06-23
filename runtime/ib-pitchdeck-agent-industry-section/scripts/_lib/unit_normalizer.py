"""Normalize common metric units before chart/evidence export."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any


NUMBER_RE = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?")
PERCENT_UNITS = {"%", "percent", "percentage", "pct", "bps"}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _parse_decimal(value: Any) -> Decimal | None:
    if isinstance(value, (int, float, Decimal)):
        try:
            return Decimal(str(value))
        except InvalidOperation:
            return None
    match = NUMBER_RE.search(_text(value).replace(",", ""))
    if not match:
        return None
    try:
        return Decimal(match.group(0))
    except InvalidOperation:
        return None


def _unit_from_value(value: Any) -> str:
    text = _text(value)
    match = NUMBER_RE.search(text)
    if not match:
        return ""
    return text[match.end() :].strip()


def _is_percent(unit: str) -> bool:
    lowered = unit.strip().lower()
    return lowered in PERCENT_UNITS or lowered.endswith("%")


def _rmb_to_bn_factor(unit: str) -> Decimal | None:
    normalized = unit.strip().lower().replace(" ", "")
    if not normalized:
        return None
    if _is_percent(normalized):
        return None
    if normalized in {"rmbbn", "rmbbillion", "cnybn", "cnybillion", "billionrmb", "billioncny", "十亿元"}:
        return Decimal("1")
    if normalized in {"rmbmn", "rmbm", "rmbmillion", "cnymn", "cnym", "cnymillion", "millionrmb", "millioncny", "百万元"}:
        return Decimal("0.001")
    if normalized in {"万亿元", "万亿"}:
        return Decimal("1000")
    if normalized in {"亿元", "亿", "亿人民币", "亿rmb", "亿cny"}:
        return Decimal("0.1")
    if normalized in {"万元", "万人民币", "万rmb", "万cny"}:
        return Decimal("0.00001")
    if normalized in {"元", "人民币", "rmb", "cny", "¥", "￥"}:
        return Decimal("0.000000001")
    return None


def _format_decimal(value: Decimal) -> str:
    quantized = value.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
    text = format(quantized, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def normalize_metric_row(
    row: dict[str, Any],
    *,
    default_currency_target: str = "RMB bn",
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return a metric row with Chinese/RMB money units converted to RMB bn.

    Percentages and unknown units are left unchanged. Original value/unit fields
    are preserved so reviewers can audit the conversion.
    """

    normalized = dict(row)
    original_value = row.get("value")
    original_unit = _text(row.get("unit")) or _unit_from_value(original_value)
    normalized["original_value"] = _text(original_value)
    normalized["original_unit"] = original_unit

    if _is_percent(original_unit):
        normalized.setdefault("unit_conversion_note", "Percent metric left unchanged.")
        return normalized, {"converted": False, "reason": "percent_unit"}

    value = _parse_decimal(original_value)
    factor = _rmb_to_bn_factor(original_unit)
    if value is None or factor is None or default_currency_target != "RMB bn":
        normalized.setdefault("unit_conversion_note", "No recognized RMB monetary unit conversion applied.")
        return normalized, {"converted": False, "reason": "unrecognized_or_not_numeric"}

    converted = value * factor
    normalized["value"] = _format_decimal(converted)
    normalized["unit"] = "RMB bn"
    normalized["unit_conversion_note"] = (
        f"Converted from {normalized['original_value']} {original_unit} to RMB bn using factor {factor}."
    )
    return normalized, {
        "converted": True,
        "from_value": normalized["original_value"],
        "from_unit": original_unit,
        "to_value": normalized["value"],
        "to_unit": "RMB bn",
        "factor": str(factor),
    }

#!/usr/bin/env python3
"""Common helpers for normalized repair-target issue summaries."""

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

from typing import Any, Iterable


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return text


def _as_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value:
        text = _as_text(item)
        if text:
            items.append(text)
    return items


def _forbidden_value(item: Any) -> str:
    if item is None:
        return ""
    if isinstance(item, list):
        return "; ".join(_as_text(value) for value in item if _as_text(value))
    return _as_text(item)


def normalize_repair_issue(
    item: Any,
    *,
    default_layer: str = "",
    default_artifact: str = "",
    default_recommended_action: str = "",
) -> dict[str, str] | None:
    """Return a normalized repair issue record from mixed legacy/new validator shapes."""
    if not isinstance(item, dict):
        return None

    issue_type = _as_text(
        item.get("issue_type")
        or item.get("code")
        or item.get("type")
        or item.get("category")
        or item.get("error_type")
    )
    if not issue_type:
        return None

    severity = _as_text(item.get("severity") or "error")

    repair_target_layer = _as_text(
        item.get("repair_target_layer")
        or item.get("owner_stage")
        or item.get("layer")
        or item.get("source_layer")
        or item.get("target_layer")
        or default_layer
    )
    if not repair_target_layer:
        repair_target_layer = default_layer

    repair_target_artifact = _as_text(
        item.get("repair_target_artifact")
        or item.get("repair_target")
        or item.get("artifact")
        or item.get("target_artifact")
        or default_artifact
    )

    recommended_action = _as_text(
        item.get("recommended_action")
        or item.get("repair_hint")
        or item.get("hint")
        or item.get("message")
        or item.get("recommendation")
        or default_recommended_action
    )
    forbidden_action = _as_text(
        item.get("forbidden_action")
        or item.get("forbidden")
        or item.get("do_not_edit")
        or item.get("do_not")
    )
    if not forbidden_action:
        forbidden_action = _forbidden_value(item.get("do_not_edit"))
    if not forbidden_action:
        forbidden_action = _as_text(item.get("do_not"))

    return {
        "issue_type": issue_type,
        "severity": severity or "error",
        "repair_target_layer": repair_target_layer,
        "repair_target_artifact": repair_target_artifact,
        "recommended_action": recommended_action,
        "forbidden_action": forbidden_action,
    }


def collect_repair_targets(
    report: dict[str, Any],
    *,
    default_layer: str = "",
    default_artifact: str = "",
) -> list[dict[str, str]]:
    """Collect normalized repair issue records from a validator JSON report."""
    if not isinstance(report, dict):
        return []

    found: list[dict[str, str]] = []

    def add(item: Any) -> None:
        normalized = normalize_repair_issue(
            item,
            default_layer=default_layer,
            default_artifact=default_artifact,
        )
        if normalized and normalized not in found:
            found.append(normalized)

    for key in ("repair_issues", "repair_targets"):
        for item in _as_list_of_dicts(report.get(key)):
            add(item)

    repair_plan = report.get("repair_plan")
    if isinstance(repair_plan, dict):
        for item in _as_list_of_dicts(repair_plan.get("targets")):
            add(item)
        for artifact in _as_list(repair_plan.get("primary_repair_targets")):
            add(
                {
                    "issue_type": "REPAIR_PLAN",
                    "repair_target_artifact": artifact,
                    "repair_target_layer": default_layer or "unknown",
                    "recommended_action": "Follow the repair plan targets in order.",
                }
            )

    for item in _as_list_of_dicts(report.get("root_causes")):
        if "issue_type" not in item and item.get("code"):
            item = dict(item)
            item["issue_type"] = str(item["code"])
        add(item)

    if report.get("is_valid") is False and not found:
        for error in _as_list(report.get("errors"))[:3]:
            if not error:
                continue
            add(
                {
                    "issue_type": "VALIDATION_FAILED",
                    "severity": "error",
                    "repair_target_layer": default_layer or "unknown",
                    "repair_target_artifact": default_artifact,
                    "recommended_action": (
                        "Rerun the validator for this stage and repair the upstream artifact "
                        f"before downstream generation."
                    ),
                    "forbidden_action": "Do not edit later-stage outputs until this stage passes.",
                    "message": error,
                }
            )

    return found


def _as_list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def unique_repair_targets(
    issues: Iterable[dict[str, str]],
) -> list[dict[str, str]]:
    """Deduplicate repair issues with stable order."""
    seen: set[tuple[str, str, str, str, str]] = set()
    unique: list[dict[str, str]] = []
    for issue in issues:
        key = tuple(issue.get(k, "") for k in (
            "issue_type",
            "repair_target_layer",
            "repair_target_artifact",
            "severity",
            issue.get("recommended_action", ""),
        ))
        if key in seen:
            continue
        seen.add(key)
        unique.append(issue)
    return unique

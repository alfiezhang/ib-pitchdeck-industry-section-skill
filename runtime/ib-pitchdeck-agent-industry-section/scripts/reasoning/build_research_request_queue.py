#!/usr/bin/env python3
"""Build a public research request queue from banker_page_pack research gaps."""

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
_IB_SHARED_SCRIPT_DIR = _IB_RUNTIME_ROOT / "scripts" / "_lib"
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

import argparse
import json
from pathlib import Path
from typing import Any

from json_utils import load_json_file


def text(value: Any) -> str:
    return str(value or "").strip()


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _research_request_policy() -> dict[str, Any]:
    path = _IB_RUNTIME_ROOT / "configs" / "research_planning_policy.json"
    payload = load_json_file(path)
    if not isinstance(payload, dict) or not isinstance(payload.get("research_request_queue"), dict):
        raise ValueError("configs/research_planning_policy.json must define research_request_queue")
    return payload["research_request_queue"]


def _policy_list(key: str) -> list[str]:
    values = _research_request_policy().get(key)
    if not isinstance(values, list) or not values:
        raise ValueError(f"research_request_queue.{key} must be a non-empty list")
    return [text(item) for item in values if text(item)]


def _policy_text(key: str) -> str:
    value = text(_research_request_policy().get(key))
    if not value:
        raise ValueError(f"research_request_queue.{key} must be a non-empty string")
    return value


def _policy_dict(key: str) -> dict[str, Any]:
    value = _research_request_policy().get(key)
    if not isinstance(value, dict) or not value:
        raise ValueError(f"research_request_queue.{key} must be a non-empty object")
    return value


def _clamp_source_type(value: str) -> str:
    candidate = text(value)
    allowed_source_types = set(_policy_list("allowed_source_types"))
    if candidate in allowed_source_types:
        return candidate
    lowered = candidate.lower()
    for source_type, terms in _policy_dict("source_type_alias_terms").items():
        if source_type not in allowed_source_types or not isinstance(terms, list):
            continue
        if candidate and any(text(term).lower() in lowered for term in terms if text(term)):
            return source_type
    return _policy_text("default_source_type")


def _downstream_permission(candidate: str) -> str:
    value = text(candidate)
    if value in set(_policy_list("headline_aliases")):
        return _policy_text("headline_alias_downgrade_permission")
    if value in set(_policy_list("downstream_permissions")):
        return value
    return _policy_text("default_permission_if_unresolved")


def _minimum_searches(candidate: Any) -> int:
    if isinstance(candidate, int) and candidate >= 0:
        return candidate
    try:
        return int(_research_request_policy().get("default_minimum_actual_searches"))
    except (TypeError, ValueError):
        raise ValueError("research_request_queue.default_minimum_actual_searches must be an integer")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--banker-page-pack", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    banker_page_pack = load_json_file(Path(args.banker_page_pack))
    requests: list[dict[str, Any]] = []
    for item in as_list(banker_page_pack.get("research_requests")):
        if not isinstance(item, dict):
            continue
        request_id = f"RQ-{len(requests) + 1:03d}"
        requests.append(
            {
                "request_id": request_id,
                "origin_issue_id": text(item.get("origin_page_argument_id") or item.get("origin_slide_no")),
                "hypothesis_id": text(item.get("origin_page_argument_id") or item.get("origin_slide_no")),
                "research_question": text(item.get("research_question") or item.get("question")),
                "required_source_type": _clamp_source_type(text(item.get("required_source_type") or item.get("source_type"))),
                "minimum_actual_searches": _minimum_searches(item.get("minimum_actual_searches")),
                "downstream_permission_if_unresolved": _downstream_permission(text(item.get("allowed_use_before_resolution"))),
                # compatibility aliases for existing downstream scripts/notes
                "research_request_id": request_id,
                "allowed_source_types": _policy_list("allowed_source_types"),
                "status": _policy_text("default_status"),
                "downstream_permission_until_resolved": _downstream_permission(text(item.get("allowed_use_before_resolution"))),
                "required_source_type_hint": text(item.get("source_type")),
                "origin_issue_area": text(item.get("page_role") or item.get("origin_page_role")),
                "origin_issue_subissue": text(item.get("subissue") or item.get("research_thread")),
                "allowed_use_before_resolution": text(item.get("allowed_use_before_resolution"))
                or _policy_text("default_allowed_use_before_resolution"),
            }
        )
    for slide in as_list(banker_page_pack.get("slides")):
        if not isinstance(slide, dict):
            continue
        for question in as_list(slide.get("open_questions")):
            question_text = text(question)
            if not question_text:
                continue
            request_id = f"RQ-{len(requests) + 1:03d}"
            slide_no = text(slide.get("slide_no"))
            requests.append(
                {
                    "request_id": request_id,
                    "origin_issue_id": f"slide_{slide_no}" if slide_no else "",
                    "hypothesis_id": f"slide_{slide_no}" if slide_no else "",
                    "research_question": question_text,
                    "required_source_type": _policy_text("default_source_type"),
                    "minimum_actual_searches": _minimum_searches(None),
                    "downstream_permission_if_unresolved": _policy_text("default_permission_if_unresolved"),
                    "research_request_id": request_id,
                    "allowed_source_types": _policy_list("allowed_source_types"),
                    "status": _policy_text("default_status"),
                    "downstream_permission_until_resolved": _policy_text("default_permission_if_unresolved"),
                    "required_source_type_hint": _policy_text("default_source_type"),
                    "origin_issue_area": text(slide.get("fixed_page_role")),
                    "origin_issue_subissue": text(slide.get("client_question")),
                    "allowed_use_before_resolution": _policy_text("default_allowed_use_before_resolution"),
                }
            )
    payload = {
        "schema_version": "research_request_queue_v1",
        "policy_context": "pre_mandate_client_pitch",
        "requests": requests,
        "build_rule": _policy_text("build_rule"),
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"is_valid": True, "output": str(out), "request_count": len(requests)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

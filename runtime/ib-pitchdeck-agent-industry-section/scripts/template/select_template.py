#!/usr/bin/env python3
"""Select the PPT template for Template/Output.

Policy:
- explicit user template wins;
- otherwise use a user-provided material classified as `ppt_template`;
- otherwise use the bundled template.

This script does not decide page content. It only records which PPTX/POTX file
Template and Output should analyze/render against.
"""

from __future__ import annotations

import sys as _ib_sys
from pathlib import Path as _IbPath

_IB_ROLE_SCRIPT_DIR = _IbPath(__file__).resolve().parent
_IB_RUNTIME_ROOT = next(
    _p for _p in _IbPath(__file__).resolve().parents
    if (_p / "configs").is_dir() and (_p / "scripts").is_dir()
)
_IB_SHARED_SCRIPT_DIR = _IB_RUNTIME_ROOT / "scripts"
_IB_ROLE_SCRIPT_DIRS = sorted(_p for _p in (_IB_RUNTIME_ROOT / "scripts").iterdir() if _p.is_dir())
_IB_QC_VALIDATOR_DIRS = sorted((_IB_RUNTIME_ROOT / "scripts" / "qc" / "validators").glob("*"))
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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from check_template_tokens import build_report, collect_mapping_tokens, collect_template_tokens
from json_utils import load_json_file
from source_classification import normalize_source_type


ROOT = _IB_RUNTIME_ROOT
DEFAULT_BUNDLED_TEMPLATE = ROOT / "assets" / "industry_section_template_master.pptx"
DEFAULT_PPT_MAPPING = ROOT / "configs" / "ppt_mapping.json"


def _load_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = load_json_file(path)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _is_template_suffix(path_text: str) -> bool:
    return path_text.lower().endswith((".pptx", ".potx", ".ppt"))


def _resolve_path(path_text: str, run_dir: Path) -> Path:
    path = Path(path_text).expanduser()
    if path.is_absolute():
        return path
    candidate = (run_dir / path).resolve()
    if candidate.exists():
        return candidate
    if path.exists():
        return path.resolve()
    return (ROOT / path).resolve()


def _template_candidates(material_manifest: dict[str, Any], run_dir: Path) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for item in material_manifest.get("materials") or []:
        if not isinstance(item, dict):
            continue
        source_type = normalize_source_type(item.get("source_type"))
        material_kind = str(item.get("material_kind") or "").strip().lower()
        path_text = str(item.get("file_path_or_url") or "").strip()
        if not path_text or not _is_template_suffix(path_text):
            continue
        if source_type == "ppt_template" or material_kind == "ppt_template":
            path = _resolve_path(path_text, run_dir)
            candidates.append(
                {
                    "material_id": item.get("material_id", ""),
                    "path": str(path),
                    "source_type": source_type,
                    "material_kind": material_kind,
                    "exists": path.exists(),
                }
            )
    return candidates


def _token_compatibility(template_path: Path, ppt_mapping: Path) -> dict[str, Any]:
    try:
        template_tokens = collect_template_tokens(template_path)
        mapping_tokens = collect_mapping_tokens(_load_object(ppt_mapping))
        report = build_report(template_tokens, mapping_tokens)
        summary = report.get("summary") or {}
        return {
            "checked": True,
            "is_token_fill_compatible": bool(summary.get("is_consistent")),
            "template_token_count": summary.get("template_token_count", 0),
            "mapping_token_count": summary.get("mapping_token_count", 0),
            "missing_in_template_count": summary.get("missing_in_template_count", 0),
            "missing_in_mapping_count": summary.get("missing_in_mapping_count", 0),
        }
    except Exception as exc:
        return {
            "checked": False,
            "is_token_fill_compatible": False,
            "error": str(exc),
        }


def select_template(
    *,
    run_dir: Path,
    explicit_template: str = "",
    material_manifest_path: Path | None = None,
    bundled_template: Path = DEFAULT_BUNDLED_TEMPLATE,
    ppt_mapping: Path = DEFAULT_PPT_MAPPING,
) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    material_manifest_path = material_manifest_path or (run_dir / "artifacts" / "material_manifest.json")
    manifest = _load_object(material_manifest_path)
    candidates = _template_candidates(manifest, run_dir)

    selection_source = "bundled_default"
    reason = "no user-provided PPT template was registered"
    selected = bundled_template.resolve()
    selected_material_id = ""

    if explicit_template:
        selected = _resolve_path(explicit_template, run_dir)
        selection_source = "explicit_user_template"
        reason = "explicit --template value provided by agent/user"
    else:
        existing_candidates = [item for item in candidates if item.get("exists")]
        if existing_candidates:
            first = existing_candidates[0]
            selected = Path(str(first["path"])).resolve()
            selected_material_id = str(first.get("material_id") or "")
            selection_source = "user_provided_template_material"
            reason = "first registered ppt_template material"

    compatibility = _token_compatibility(selected, ppt_mapping)
    return {
        "schema_version": "template_selection_v1",
        "selected_template_path": str(selected),
        "selection_source": selection_source,
        "selected_material_id": selected_material_id,
        "bundled_template_path": str(bundled_template.resolve()),
        "material_manifest": str(material_manifest_path),
        "template_candidates": candidates,
        "selection_rule": "explicit_user_template > registered ppt_template material > bundled_default",
        "reason": reason,
        "selected_template_exists": selected.exists(),
        "token_compatibility": compatibility,
        "render_policy": (
            "Selected template is token-compatible and can be used for deterministic token filling."
            if compatibility.get("is_token_fill_compatible")
            else "Selected template is not token-compatible with ppt_mapping.json; Template/Output must repair mapping/template or route to a non-final draft path."
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--template", default="", help="Explicit user-provided template path. Overrides material_manifest.")
    parser.add_argument("--material-manifest", default="")
    parser.add_argument("--bundled-template", default=str(DEFAULT_BUNDLED_TEMPLATE))
    parser.add_argument("--ppt-mapping", default=str(DEFAULT_PPT_MAPPING))
    parser.add_argument("--output", default="")
    parser.add_argument("--fail-if-missing", action="store_true")
    parser.add_argument("--fail-if-token-incompatible", action="store_true")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    output = Path(args.output) if args.output else run_dir / "artifacts" / "template_selection.json"
    payload = select_template(
        run_dir=run_dir,
        explicit_template=args.template,
        material_manifest_path=Path(args.material_manifest) if args.material_manifest else None,
        bundled_template=Path(args.bundled_template),
        ppt_mapping=Path(args.ppt_mapping),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if args.fail_if_missing and not payload.get("selected_template_exists"):
        return 1
    if args.fail_if_token_incompatible and not (payload.get("token_compatibility") or {}).get("is_token_fill_compatible"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

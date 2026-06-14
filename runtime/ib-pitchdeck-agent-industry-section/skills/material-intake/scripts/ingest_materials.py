#!/usr/bin/env python3
"""Run material intake end-to-end and emit manifest/extract artifacts."""

from __future__ import annotations

# Runtime scripts can be run directly. Shared helpers remain in runtime
# `scripts/`; production tools live under role scripts; validators live under QC.
import sys as _ib_sys
from pathlib import Path as _IbPath
_IB_ROLE_SCRIPT_DIR = _IbPath(__file__).resolve().parent
_IB_RUNTIME_ROOT = next(
    _p for _p in _IbPath(__file__).resolve().parents
    if (_p / 'templates').is_dir() and (_p / 'skills').is_dir() and (_p / 'scripts').is_dir()
)
_IB_SHARED_SCRIPT_DIR = _IB_RUNTIME_ROOT / "scripts"
_IB_ROLE_SCRIPT_DIRS = sorted((_IB_RUNTIME_ROOT / 'skills').glob('*/scripts'))
_IB_QC_VALIDATOR_DIRS = sorted((_IB_RUNTIME_ROOT / 'skills' / 'qc' / 'scripts' / 'validators').glob('*'))
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
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from extract_excel_text import extract_excel_text
from extract_pdf_text import extract_pdf_text
from extract_pptx_text import extract_pptx_text
from extract_web_url import extract_web_url
from material_intake_common import (
    as_bool,
    clean_text_block,
    classify_access,
    is_url,
    normalize_source_type_hint,
    file_fingerprint,
    text,
    infer_material_kind,
)
from source_classification import CANONICAL_SOURCE_TYPES, normalize_source_type


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _new_material_id(index: int) -> str:
    return f"MAT-{index:03d}"


def _material_access(material: dict[str, Any], source_path: str) -> str:
    return text(material.get("source_access") or classify_access(material.get("source_type", ""), source_path))


def _source_hash(source_path: str) -> str:
    if is_url(source_path):
        return hashlib.sha256(text(source_path).encode("utf-8")).hexdigest()
    return file_fingerprint(Path(source_path))


def _build_material_entry(
    material_id: str,
    source: str,
    source_type: str,
    source_access: str,
    title: str,
    brief_excerpt: str | None = None,
) -> dict[str, Any]:
    source_type = normalize_source_type(source_type)
    material = {
        "material_id": material_id,
        "source_type": normalize_source_type(source_type),
        "source_access": source_access,
        "file_path_or_url": source,
        "locator": "" if source == "inline_user_text" else source,
        "material_title": text(title),
        "material_kind": infer_material_kind(source, source_type),
        "extraction_status": "pending",
        "extraction_limitations": "not_processed",
        "can_be_used_as_evidence": False,
    }
    if brief_excerpt:
        material["brief_excerpt"] = clean_text_block(brief_excerpt)
    return material


def _default_extraction_status(source_text: str, source_file: str) -> tuple[str, list[str], bool]:
    if not source_text.strip():
        return "failed", ["no readable text extracted"], False
    if "placeholder" in source_text.lower() and len(source_text) < 200:
        return "partial", ["auto extraction returned short/placeholder-like content; confirm against source"], False
    if not source_file:
        return "partial", ["source text written to transient location only"], False
    return "complete", [], True


def _emit_entry(
    *,
    material_id: str,
    source: str,
    source_type: str,
    source_access: str,
    title: str,
    brief_excerpt: str | None = None,
    source_hash: str = "",
) -> tuple[dict[str, Any], dict[str, Any]]:
    material = _build_material_entry(
        material_id=material_id,
        source=source,
        source_type=source_type,
        source_access=source_access,
        title=title,
        brief_excerpt=brief_excerpt,
    )
    source_classification_entry = {
        "material_id": material_id,
        "source_type": material["source_type"],
        "source_access": material["source_access"],
        "file_path_or_url": source,
        "source_hash": source_hash,
        "source_date": datetime.now(timezone.utc).isoformat(),
    }
    return material, source_classification_entry


def _extract_one(material: dict[str, Any], material_texts_dir: Path) -> dict[str, Any]:
    material_id = material["material_id"]
    source = material["file_path_or_url"]
    source_type = material["source_type"]
    text_path = material_texts_dir / f"{material_id}.txt"
    text_path.parent.mkdir(parents=True, exist_ok=True)
    limitations: list[str] = []
    extracted_text = ""
    code = 1

    if source_type == "ppt_template":
        material["extracted_text_path"] = ""
        material["extraction_status"] = "template_registered"
        material["raw_text_available"] = False
        material["raw_text_extraction_status"] = "template_registered"
        material["extraction_limitations"] = (
            "PPT template registered for Template Layer analysis/rendering; "
            "not treated as project or industry evidence."
        )
        material["can_be_used_as_evidence"] = False
        material["extracted_text_preview"] = ""
        return material

    if source_type == "manual_url_ingestion":
        extracted_text, extract_limitations, code = extract_web_url(source, str(text_path), material_id=material_id)
        limitations.extend(extract_limitations)
    elif source.lower().endswith(".pdf"):
        extracted_text, extract_limitations, code = extract_pdf_text(source, str(text_path))
        limitations.extend(extract_limitations)
    elif source.lower().endswith((".ppt", ".pptx")):
        extracted_text, extract_limitations, code = extract_pptx_text(source, str(text_path))
        limitations.extend(extract_limitations)
    elif source.lower().endswith((".xls", ".xlsx", ".csv")):
        extracted_text, extract_limitations, code = extract_excel_text(source, str(text_path))
        limitations.extend(extract_limitations)
    else:
        if source == "inline_user_text":
            extracted_text = material.get("brief_excerpt") or material.get("material_title") or ""
            code = 0
            try:
                text_path.write_text(extracted_text, encoding="utf-8")
            except Exception:
                limitations.append("inline brief could not be written to extracted text path")
                code = 1
        else:
            code = 1
            limitations.append(f"unsupported source_type: {source_type}")
            limitations.append("unsupported extension for extraction")
    extraction_status, quality_limitations, can_use = _default_extraction_status(extracted_text, str(text_path))
    if quality_limitations:
        limitations.extend(quality_limitations)
    if code == 0 and extraction_status == "complete":
        text_path.write_text(extracted_text, encoding="utf-8")
        can_use = bool(text_path.exists() and extracted_text.strip())
    elif code != 0 and extracted_text:
        text_path.write_text(extracted_text, encoding="utf-8")
    material["extracted_text_path"] = str(text_path)
    material["extraction_status"] = extraction_status if code == 0 else "failed"
    material["raw_text_available"] = bool(can_use) and material["extraction_status"] == "complete"
    material["raw_text_extraction_status"] = material["extraction_status"]
    material["extraction_limitations"] = "; ".join(limitations) if limitations else "none"
    # Raw text capture is not evidence review. A role LLM must extract facts,
    # metrics, quotes, unknowns, and use limits before downstream evidence use.
    material["can_be_used_as_evidence"] = False
    material["extracted_text_preview"] = clean_text_block(extracted_text)[:320]
    return material


def ingest_materials(
    *,
    brief_text: str | None,
    files: list[str],
    template_files: list[str] | None = None,
    urls: list[str],
    default_file_source_type: str,
    default_url_source_type: str,
    output_material_manifest: Path,
    output_material_extracts: Path,
    output_source_classification: Path | None = None,
    dry_run: bool = False,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:

    materials: list[dict[str, Any]] = []
    extract_entries: list[dict[str, Any]] = []
    source_classification: list[dict[str, Any]] = []
    idx = 1

    # User brief is not considered a file/url source.
    if brief_text:
        material, classification_entry = _emit_entry(
            material_id=_new_material_id(idx),
            source="inline_user_text",
            source_type=normalize_source_type_hint("inline_user_text", "project_specific_material"),
            source_access="user_provided",
            title="User inline brief",
            brief_excerpt=brief_text,
        )
        materials.append(material)
        source_classification.append(classification_entry)
        idx += 1

    for path in files:
        source_type = normalize_source_type_hint(path, default_file_source_type)
        source_access = _material_access({"source_type": source_type}, path)
        material, classification_entry = _emit_entry(
            material_id=_new_material_id(idx),
            source=path,
            source_type=source_type,
            source_access=source_access,
            title=Path(path).name,
            source_hash=_source_hash(path),
        )
        materials.append(material)
        source_classification.append(classification_entry)
        idx += 1

    template_files = template_files or []

    for path in template_files:
        material, classification_entry = _emit_entry(
            material_id=_new_material_id(idx),
            source=path,
            source_type="ppt_template",
            source_access="user_provided",
            title=Path(path).name,
            source_hash=_source_hash(path),
        )
        material["material_kind"] = "ppt_template"
        material["extraction_status"] = "template_registered"
        material["extraction_limitations"] = "registered for template selection; not evidence"
        materials.append(material)
        source_classification.append(classification_entry)
        idx += 1

    for url in urls:
        source_type = normalize_source_type_hint(url, default_url_source_type)
        source_access = _material_access({"source_type": source_type}, url)
        material, classification_entry = _emit_entry(
            material_id=_new_material_id(idx),
            source=url,
            source_type=source_type,
            source_access=source_access,
            title=url,
            source_hash=_source_hash(url),
        )
        materials.append(material)
        source_classification.append(classification_entry)
        idx += 1

    material_texts_dir = output_material_extracts.parent / "material_texts"
    for material in materials:
        extracted = _extract_one(material, material_texts_dir)
        extract_entries.append(
            {
                "material_id": material["material_id"],
                "source_type": material["source_type"],
                "source_access": material["source_access"],
                "file_path_or_url": material["file_path_or_url"],
                "extracted_text_path": extracted["extracted_text_path"],
                "raw_text_path": extracted["extracted_text_path"],
                "raw_text_available": extracted["raw_text_available"],
                "raw_text_extraction_status": extracted["raw_text_extraction_status"],
                "content_capture_status": "captured" if extracted["raw_text_available"] else "capture_failed",
                "extraction_status": extracted["extraction_status"],
                "extraction_limitations": extracted["extraction_limitations"],
                "llm_extraction_status": (
                    "not_relevant_for_knowledge"
                    if extracted["source_type"] == "ppt_template"
                    else
                    "pending_llm_extraction"
                    if extracted["raw_text_available"]
                    else "blocked_no_readable_text"
                ),
                "can_be_used_as_evidence": False,
                "extracted_facts": [],
                "extracted_metrics": [],
                "quoted_excerpts": [],
                "unknowns_or_conflicts": [],
                "claim_use_limitations": (
                    "Raw content captured only; do not use as evidence until a role LLM extracts "
                    "source-faithful facts, metrics, quoted excerpts, unknowns/conflicts, and use limits."
                    if extracted["raw_text_available"]
                    else (
                        "Template material; use only in Template Layer for style/layout/rendering."
                        if extracted["source_type"] == "ppt_template"
                        else extracted["extraction_limitations"]
                    )
                ),
                "evidence_snapshot": extracted["extracted_text_preview"],
            }
        )

    manifest = {
        "schema_version": "material_manifest_v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "policy_context": "pre_mandate_client_pitch",
        "materials": materials,
        "source_type_policy": {
            "project_specific_material": "user_provided user input and uploaded files; candidate until extraction and review",
            "user_curated_industry_report": "curated report candidate; subject to formal evidence extraction/review",
            "manual_url_ingestion": "public source candidate; requires source locator and archive for formal evidence",
            "repository_retrieval": "retrieved source candidate from shared repository",
            "ppt_template": "user-provided presentation template; use for Template Layer selection/analysis, not evidence",
        },
    }

    extracts = {
        "schema_version": "material_extracts_v1",
        "artifact_semantics": (
            "Content capture plus LLM extraction workspace. Raw text availability does not mean "
            "evidence usability. Project facts should be transcribed into input_card.json; "
            "industry facts from provided reports should be extracted by a role LLM before entering Knowledge."
        ),
        "materials_source": str(output_material_manifest),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "extracts": extract_entries,
    }

    source_classification_payload = {
        "schema_version": "source_classification_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "materials": source_classification,
    }

    if not dry_run:
        _write_json(output_material_manifest, manifest)
        _write_json(output_material_extracts, extracts)
        if output_source_classification:
            _write_json(output_source_classification, source_classification_payload)
    return manifest, extracts, source_classification_payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brief-text", help="User brief text")
    parser.add_argument("--file", action="append", default=[], help="Upload file path")
    parser.add_argument("--template-file", action="append", default=[], help="User-provided PPT/POTX template path. Preferred over bundled template for Template/Output.")
    parser.add_argument("--url", action="append", default=[], help="Source URL")
    parser.add_argument("--default-file-source-type", default="project_specific_material")
    parser.add_argument("--default-url-source-type", default="manual_url_ingestion")
    parser.add_argument("--output-manifest", required=True)
    parser.add_argument("--output-extracts", required=True)
    parser.add_argument("--output-source-classification", default="")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    output_manifest = Path(args.output_manifest)
    output_extracts = Path(args.output_extracts)
    output_source_classification = Path(args.output_source_classification) if args.output_source_classification else None

    if any(not normalize_source_type(st) in CANONICAL_SOURCE_TYPES for st in [args.default_file_source_type, args.default_url_source_type]):
        parser.error("default file/url source type must normalize to a canonical source_type")

    manifest, extracts, source_classification = ingest_materials(
        brief_text=args.brief_text,
        files=args.file,
        template_files=args.template_file,
        urls=args.url,
        default_file_source_type=args.default_file_source_type,
        default_url_source_type=args.default_url_source_type,
        output_material_manifest=output_manifest,
        output_material_extracts=output_extracts,
        output_source_classification=output_source_classification,
        dry_run=as_bool(args.dry_run),
    )

    result = {
        "is_valid": bool(manifest.get("materials")) if not args.dry_run else True,
        "material_manifest": str(output_manifest),
        "material_extracts": str(output_extracts),
        "source_classification": str(output_source_classification) if output_source_classification else "",
        "material_count": len(manifest.get("materials") or []),
        "extracted_count": len(extracts.get("extracts") or []),
        "validation": {
            "failed": [
                item for item in [
                    "material source_type invalid" if not item.get("source_type") in CANONICAL_SOURCE_TYPES else None
                    for item in manifest.get("materials", [])
                ]
                if item
            ]
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["validation"]["failed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

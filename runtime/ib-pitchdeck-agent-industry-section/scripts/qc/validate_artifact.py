#!/usr/bin/env python3
"""Unified deterministic validator for the industry-section workflow.

This script deliberately checks only mechanical conditions: files exist, JSON is
parseable, IDs and cross-references are coherent, and renderer/PPT inputs can be
used by deterministic tooling. Content quality, page density, source judgment,
and pitch relevance are LLM responsibilities.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
RUNTIME_ROOT = next(
    parent for parent in Path(__file__).resolve().parents
    if (parent / "configs").is_dir() and (parent / "scripts").is_dir()
)
for path in [
    RUNTIME_ROOT / "scripts",
    RUNTIME_ROOT / "scripts" / "_lib",
    RUNTIME_ROOT / "scripts" / "knowledge-repository",
]:
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)

from deck_blueprint_utils import FIXED_PAGE_ROLES, VALID_CLAIM_STRENGTHS, as_list, banker_page_id_for_slide, unique
from json_utils import load_json_file
from renderer_token_source import build_token_source
from research_evidence_db import validate_db as validate_research_db
from template_contract_utils import required_body_fields


EV_RE = re.compile(r"^EV-\d{3}$")
MET_RE = re.compile(r"^MET-\d{3}$")
BP_RE = re.compile(r"^BP-\d{3}$")
SRC_RE = re.compile(r"^SRC-\d{3}$")


ARTIFACT_PATHS = {
    "material_manifest": "artifacts/material_manifest.json",
    "material_extracts": "artifacts/material_extracts.json",
    "input_card": "input_card.json",
    "industry_scope_pack": "artifacts/industry_scope_pack.json",
    "formal_search_plan": "artifacts/formal_search_plan.json",
    "executable_search_batch": "artifacts/executable_search_batch.json",
    "formal_research_execution": "artifacts/formal_research_execution_report.json",
    "source_archive": "artifacts/source_archive/source_archive_index.json",
    "research_evidence_db": "artifacts/research_evidence_db.json",
    "research_pack": "industry_research_pack.md",
    "research_request_queue": "artifacts/research_request_queue.json",
    "banker_page_pack": "banker_page_pack.json",
    "template_registry": "template_registry.json",
    "deck_blueprint": "deck_blueprint.json",
    "page_evidence_contract": "page_evidence_contract.json",
    "renderer_spec": "renderer_spec.json",
    "replacement_dict": "replacement_dict.json",
    "filled_ppt": "filled_ppt_validation.json",
    "pre_research_pack": "artifacts/stage_gate_pre_research_pack_validation.json",
    "pre_ppt": "artifacts/stage_gate_pre_ppt_validation.json",
    "final_delivery": "artifacts/final_delivery_validation.json",
}


VALIDATION_OUTPUTS = {
    "material_manifest": "artifacts/material_manifest_validation.json",
    "material_extracts": "artifacts/material_extracts_validation.json",
    "input_card": "artifacts/input_card_validation.json",
    "industry_scope_pack": "artifacts/industry_scope_pack_validation.json",
    "formal_search_plan": "artifacts/formal_search_plan_validation.json",
    "executable_search_batch": "artifacts/executable_search_batch_validation.json",
    "formal_research_execution": "artifacts/formal_research_execution_validation.json",
    "source_archive": "artifacts/source_archive_validation.json",
    "research_evidence_db": "artifacts/research_evidence_db_validation.json",
    "research_pack": "artifacts/research_pack_validation.json",
    "research_request_queue": "artifacts/research_request_queue_validation.json",
    "banker_page_pack": "artifacts/banker_page_pack_validation.json",
    "template_registry": "artifacts/template_registry_validation.json",
    "deck_blueprint": "artifacts/deck_blueprint_validation.json",
    "page_evidence_contract": "artifacts/page_evidence_contract_validation.json",
    "renderer_spec": "artifacts/renderer_spec_validation.json",
    "replacement_dict": "artifacts/replacement_dict_validation.json",
    "filled_ppt": "filled_ppt_validation.json",
    "pre_research_pack": "artifacts/stage_gate_pre_research_pack_validation.json",
    "pre_ppt": "artifacts/stage_gate_pre_ppt_validation.json",
    "final_delivery": "artifacts/final_delivery_validation.json",
}


def text(value: Any) -> str:
    return str(value or "").strip()


def _json(path: Path, errors: list[str]) -> dict[str, Any]:
    if not path.exists():
        errors.append(f"missing required file: {path}")
        return {}
    try:
        payload = load_json_file(path)
    except Exception as exc:
        errors.append(f"cannot read JSON {path}: {exc}")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{path}: top-level JSON must be an object")
        return {}
    return payload


def _ids(payload: dict[str, Any], ledger_name: str, id_keys: tuple[str, ...]) -> set[str]:
    rows = payload.get(ledger_name)
    if not isinstance(rows, list):
        return set()
    result: set[str] = set()
    for row in rows:
        if isinstance(row, dict):
            for key in id_keys:
                value = text(row.get(key))
                if value:
                    result.add(value)
                    break
    return result


def _scan_ids(value: Any, key_names: set[str]) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in key_names:
                if isinstance(item, list):
                    found.extend(text(part) for part in item if text(part))
                elif text(item):
                    found.append(text(item))
            else:
                found.extend(_scan_ids(item, key_names))
    elif isinstance(value, list):
        for item in value:
            found.extend(_scan_ids(item, key_names))
    return unique(found)


def _slide_index(payload: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {
        int(slide.get("slide_no")): slide
        for slide in as_list(payload.get("slides"))
        if isinstance(slide, dict) and isinstance(slide.get("slide_no"), int)
    }


def _assert_artifact_report(path: Path, errors: list[str]) -> None:
    payload = _json(path, errors)
    if payload and payload.get("is_valid") is False:
        errors.append(f"{path.name} is_valid=false")


def validate_material_like(artifact: str, path: Path, run_dir: Path, errors: list[str], warnings: list[str]) -> None:
    payload = _json(path, errors)
    if not payload:
        return
    if artifact == "input_card" and not (payload.get("raw_brief") or payload.get("explicit_user_facts") or payload.get("brief_text")):
        warnings.append("input_card has no obvious raw brief or explicit facts")


def validate_scope(path: Path, errors: list[str], warnings: list[str]) -> None:
    payload = _json(path, errors)
    if not payload:
        return
    if payload.get("schema_version") != "industry_scope_pack_v2":
        errors.append("industry_scope_pack must use schema_version industry_scope_pack_v2")
    if payload.get("do_not_use_as_claims") is not True:
        errors.append("industry_scope_pack.do_not_use_as_claims must be true")
    summary = payload.get("scope_summary") if isinstance(payload.get("scope_summary"), dict) else {}
    for field in ("working_market", "parent_market", "broader_market"):
        if not text(summary.get(field)):
            errors.append(f"scope_summary.{field} is required")


def _contains_key(value: Any, keys: set[str]) -> bool:
    if isinstance(value, dict):
        return any(key in keys or _contains_key(item, keys) for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_key(item, keys) for item in value)
    return False


def validate_formal_plan(path: Path, errors: list[str], warnings: list[str]) -> None:
    payload = _json(path, errors)
    if not payload:
        return
    if _contains_key(payload, {"query", "query_variants", "english_query", "chinese_query"}):
        errors.append("formal_search_plan must not contain executable query fields")
    rows = payload.get("issue_search_plan")
    if not isinstance(rows, list) or not rows:
        errors.append("formal_search_plan.issue_search_plan must be a non-empty list")


def validate_search_batch(path: Path, errors: list[str], warnings: list[str]) -> None:
    payload = _json(path, errors)
    if not payload:
        return
    raw = json.dumps(payload, ensure_ascii=False)
    if "LLM_REWRITE_REQUIRED" in raw:
        errors.append("executable_search_batch still contains LLM_REWRITE_REQUIRED")
    if "needs_authoring" in raw:
        errors.append("executable_search_batch still contains needs_authoring rows")


def validate_execution(path: Path, run_dir: Path, errors: list[str], warnings: list[str]) -> None:
    payload = _json(path, errors)
    if not payload:
        return
    search_log = run_dir / "artifacts/search_log.md"
    if not search_log.exists():
        errors.append("formal research execution requires artifacts/search_log.md")


def validate_source_archive(path: Path, run_dir: Path, errors: list[str], warnings: list[str]) -> None:
    payload = _json(path, errors)
    if not payload:
        return
    rows = payload.get("sources") or payload.get("source_archive") or payload.get("archives") or []
    if not isinstance(rows, list):
        errors.append("source archive index must contain a source list")
        return
    for idx, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            continue
        source_id = text(row.get("source_id") or row.get("id"))
        if source_id and not SRC_RE.fullmatch(source_id):
            errors.append(f"source archive row {idx}: invalid source_id {source_id}")
        status = text(row.get("research_archive_status") or row.get("archive_status"))
        archive_path = text(row.get("archive_path") or row.get("saved_path") or row.get("local_path"))
        if status in {"saved_html", "saved_text", "saved_pdf", "downloaded_pdf"} and archive_path:
            candidate = run_dir / archive_path if not Path(archive_path).is_absolute() else Path(archive_path)
            if not candidate.exists():
                errors.append(f"source archive row {idx}: archive file not found: {archive_path}")


def validate_research_evidence_db(path: Path, errors: list[str], warnings: list[str]) -> None:
    payload = _json(path, errors)
    if not payload:
        return
    db_errors, db_warnings = validate_research_db(payload)
    errors.extend(str(item) for item in db_errors)
    warnings.extend(str(item) for item in db_warnings)


def validate_research_pack(path: Path, run_dir: Path, errors: list[str], warnings: list[str]) -> None:
    if not path.exists():
        errors.append(f"missing required file: {path}")
        return
    text_body = path.read_text(encoding="utf-8", errors="replace")
    if "EV-" not in text_body and "MET-" not in text_body:
        warnings.append("research pack contains no visible EV/MET IDs")
    db_path = run_dir / "artifacts/research_evidence_db.json"
    if not db_path.exists():
        errors.append("research pack requires artifacts/research_evidence_db.json as source of truth")


def validate_banker_page_pack(path: Path, run_dir: Path, errors: list[str], warnings: list[str]) -> None:
    payload = _json(path, errors)
    if not payload:
        return
    if payload.get("schema_version") != "banker_page_pack":
        errors.append("banker_page_pack.schema_version must be banker_page_pack")
    slides = payload.get("slides")
    if not isinstance(slides, list) or len(slides) != 8:
        errors.append("banker_page_pack must contain exactly 8 slides")
        return
    db_path = run_dir / "artifacts/research_evidence_db.json"
    db = _json(db_path, []) if db_path.exists() else {}
    ev_ids = _ids(db, "evidence_ledger", ("evidence_id", "id"))
    met_ids = _ids(db, "metric_reconciliation", ("metric_id", "id"))
    for idx, slide in enumerate(slides, start=1):
        if not isinstance(slide, dict):
            errors.append(f"slide {idx}: must be an object")
            continue
        slide_no = int(slide.get("slide_no") or 0)
        expected_id = f"BP-{slide_no:03d}" if slide_no else ""
        if text(slide.get("banker_page_id") or expected_id) != expected_id:
            errors.append(f"slide {slide_no}: banker_page_id must be {expected_id}")
        if text(slide.get("claim_strength")) not in VALID_CLAIM_STRENGTHS:
            errors.append(f"slide {slide_no}: invalid claim_strength")
        for field in ("fixed_page_role", "client_question", "banker_judgment", "page_argument", "headline", "main_message", "selected_page_type", "source_note"):
            if not text(slide.get(field)):
                errors.append(f"slide {slide_no}: {field} is required")
        if not as_list(slide.get("body_blocks")):
            errors.append(f"slide {slide_no}: body_blocks is required")
        for ev_id in _scan_ids(slide, {"evidence_id", "evidence_ids"}):
            if not EV_RE.fullmatch(ev_id):
                errors.append(f"slide {slide_no}: invalid evidence id {ev_id}")
            elif ev_ids and ev_id not in ev_ids:
                errors.append(f"slide {slide_no}: evidence id {ev_id} not found in research_evidence_db")
        for metric_id in _scan_ids(slide, {"metric_id", "metric_ids"}):
            if not MET_RE.fullmatch(metric_id):
                errors.append(f"slide {slide_no}: invalid metric id {metric_id}")
            elif met_ids and metric_id not in met_ids:
                errors.append(f"slide {slide_no}: metric id {metric_id} not found in research_evidence_db")


def validate_template_registry(path: Path, errors: list[str], warnings: list[str]) -> None:
    payload = _json(path, errors)
    if not payload:
        return
    slides = payload.get("slides")
    if not isinstance(slides, list) or not slides:
        errors.append("template_registry.slides must be a non-empty list")
        return
    for slide in slides:
        if not isinstance(slide, dict):
            continue
        if not isinstance(slide.get("slide_no"), int):
            errors.append("template_registry slide missing integer slide_no")
        if not as_list(slide.get("variants")):
            warnings.append(f"template_registry slide {slide.get('slide_no')}: no variants")


def validate_deck_blueprint(path: Path, run_dir: Path, errors: list[str], warnings: list[str]) -> None:
    payload = _json(path, errors)
    if not payload:
        return
    slides = payload.get("slides")
    if not isinstance(slides, list) or len(slides) != 8:
        errors.append("deck_blueprint must contain exactly 8 slides")
        return
    template = _json(run_dir / "template_registry.json", []) if (run_dir / "template_registry.json").exists() else {}
    for slide in slides:
        if not isinstance(slide, dict):
            continue
        slide_no = int(slide.get("slide_no") or 0)
        expected = FIXED_PAGE_ROLES.get(slide_no)
        if expected and text(slide.get("fixed_page_role")) != expected:
            errors.append(f"slide {slide_no}: fixed_page_role must be {expected}")
        banker_page_id = banker_page_id_for_slide(slide)
        if not BP_RE.fullmatch(banker_page_id):
            errors.append(f"slide {slide_no}: invalid banker_page_id")
        for field in ("headline", "main_message", "body_blocks", "selected_page_type"):
            if field == "body_blocks":
                if not as_list(slide.get(field)):
                    errors.append(f"slide {slide_no}: body_blocks is required")
            elif not text(slide.get(field)):
                errors.append(f"slide {slide_no}: {field} is required")
        if template:
            try:
                required_body_fields(template, slide_no, text(slide.get("selected_page_type")))
            except Exception as exc:
                errors.append(f"slide {slide_no}: template field mapping failed: {exc}")


def validate_page_contract(path: Path, run_dir: Path, errors: list[str], warnings: list[str]) -> None:
    payload = _json(path, errors)
    if not payload:
        return
    slides = payload.get("slides")
    if not isinstance(slides, list) or len(slides) != 8:
        errors.append("page_evidence_contract must contain exactly 8 slides")
        return
    deck = _json(run_dir / "deck_blueprint.json", []) if (run_dir / "deck_blueprint.json").exists() else {}
    deck_by_no = _slide_index(deck)
    for entry in slides:
        if not isinstance(entry, dict):
            continue
        slide_no = int(entry.get("slide_no") or 0)
        expected_id = f"BP-{slide_no:03d}"
        if text(entry.get("banker_page_id")) != expected_id:
            errors.append(f"slide {slide_no}: banker_page_id must be {expected_id}")
        permission = entry.get("downstream_permission")
        if not isinstance(permission, dict):
            errors.append(f"slide {slide_no}: downstream_permission object is required")
        deck_slide = deck_by_no.get(slide_no)
        if deck_slide and text(entry.get("banker_page_id")) != banker_page_id_for_slide(deck_slide):
            errors.append(f"slide {slide_no}: banker_page_id mismatch with deck_blueprint")


def validate_renderer_spec(path: Path, run_dir: Path, errors: list[str], warnings: list[str]) -> None:
    payload = _json(path, errors)
    if not payload:
        return
    if payload.get("schema_version") != "renderer_spec_v1":
        errors.append("renderer_spec.schema_version must be renderer_spec_v1")
    slides = payload.get("slides")
    if not isinstance(slides, list) or len(slides) != 8:
        errors.append("renderer_spec must contain exactly 8 slides")
        return
    try:
        build_token_source(payload)
    except Exception as exc:
        errors.append(f"renderer_spec cannot be converted into token source: {exc}")


def validate_replacement_dict(path: Path, run_dir: Path, errors: list[str], warnings: list[str]) -> None:
    payload = _json(path, errors)
    if not payload:
        return
    def scan_values(value: Any) -> bool:
        if isinstance(value, dict):
            return any(scan_values(item) for item in value.values())
        if isinstance(value, list):
            return any(scan_values(item) for item in value)
        return isinstance(value, str) and ("{{" in value or "}}" in value)

    if scan_values(payload):
        errors.append("replacement_dict contains unresolved placeholder braces in replacement values")
    if not (run_dir / "renderer_spec.json").exists():
        errors.append("replacement_dict requires renderer_spec.json")


def validate_filled_ppt(path: Path, run_dir: Path, errors: list[str], warnings: list[str]) -> None:
    filled = run_dir / "filled_output.pptx"
    clean = run_dir / "filled_output_clean.pptx"
    if not filled.exists() and not clean.exists():
        errors.append("missing filled PPT output")
        return
    target = clean if clean.exists() else filled
    try:
        with zipfile.ZipFile(target) as archive:
            names = set(archive.namelist())
            if "[Content_Types].xml" not in names:
                errors.append(f"{target.name} is not a valid pptx package")
    except Exception as exc:
        errors.append(f"cannot inspect PPT package {target}: {exc}")


def validate_stage(artifact: str, run_dir: Path, errors: list[str], warnings: list[str]) -> None:
    if artifact == "pre_research_pack":
        required = [
            "artifacts/industry_scope_pack.json",
            "artifacts/formal_search_plan.json",
            "artifacts/formal_research_execution_report.json",
            "artifacts/source_archive/source_archive_index.json",
        ]
    elif artifact == "pre_ppt":
        required = [
            "banker_page_pack.json",
            "template_registry.json",
            "deck_blueprint.json",
            "page_evidence_contract.json",
            "renderer_spec.json",
        ]
    else:
        required = [
            "banker_page_pack.json",
            "renderer_spec.json",
            "replacement_dict.json",
        ]
    for rel in required:
        if not (run_dir / rel).exists():
            errors.append(f"missing required upstream artifact: {rel}")


def validate_artifact(artifact: str, run_dir: Path, path: Path | None = None) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    target = path or run_dir / ARTIFACT_PATHS.get(artifact, "")
    if artifact in {"material_manifest", "material_extracts", "input_card", "research_request_queue"}:
        validate_material_like(artifact, target, run_dir, errors, warnings)
    elif artifact == "industry_scope_pack":
        validate_scope(target, errors, warnings)
    elif artifact == "formal_search_plan":
        validate_formal_plan(target, errors, warnings)
    elif artifact == "executable_search_batch":
        validate_search_batch(target, errors, warnings)
    elif artifact == "formal_research_execution":
        validate_execution(target, run_dir, errors, warnings)
    elif artifact == "source_archive":
        validate_source_archive(target, run_dir, errors, warnings)
    elif artifact == "research_evidence_db":
        validate_research_evidence_db(target, errors, warnings)
    elif artifact == "research_pack":
        validate_research_pack(target, run_dir, errors, warnings)
    elif artifact == "banker_page_pack":
        validate_banker_page_pack(target, run_dir, errors, warnings)
    elif artifact == "template_registry":
        validate_template_registry(target, errors, warnings)
    elif artifact == "deck_blueprint":
        validate_deck_blueprint(target, run_dir, errors, warnings)
    elif artifact == "page_evidence_contract":
        validate_page_contract(target, run_dir, errors, warnings)
    elif artifact == "renderer_spec":
        validate_renderer_spec(target, run_dir, errors, warnings)
    elif artifact == "replacement_dict":
        validate_replacement_dict(target, run_dir, errors, warnings)
    elif artifact == "filled_ppt":
        validate_filled_ppt(target, run_dir, errors, warnings)
    elif artifact in {"pre_research_pack", "pre_ppt", "final_delivery"}:
        validate_stage(artifact, run_dir, errors, warnings)
    else:
        errors.append(f"unknown artifact: {artifact}")
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", required=True, choices=sorted(ARTIFACT_PATHS))
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--path", help="Optional explicit artifact path.")
    parser.add_argument("--output")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    path = Path(args.path) if args.path else None
    errors, warnings = validate_artifact(args.artifact, run_dir, path)
    result = {
        "is_valid": not errors,
        "artifact": args.artifact,
        "run_dir": str(run_dir),
        "path": str(path or run_dir / ARTIFACT_PATHS[args.artifact]),
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "validation_policy": "mechanical_only",
    }
    output = json.dumps(result, ensure_ascii=False, indent=2)
    output_path = Path(args.output) if args.output else run_dir / VALIDATION_OUTPUTS.get(args.artifact, f"artifacts/{args.artifact}_validation.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(output + "\n", encoding="utf-8")
    print(output)
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())

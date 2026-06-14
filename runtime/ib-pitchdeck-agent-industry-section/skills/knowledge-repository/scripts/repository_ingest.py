#!/usr/bin/env python3
"""Ingest materials into the shared repository index with dedupe checks."""

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
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from material_intake_common import text
from source_classification import normalize_source_type

from repository_common import (
    as_list,
    file_fingerprint,
    load_fingerprints,
    repository_root_default,
    load_jsonl_records,
    normalize_url,
    source_hash,
    write_fingerprints,
    write_jsonl_records,
    utcnow,
)

from json_utils import load_json_file


@dataclass
class IngestInput:
    material_id: str
    source_type: str
    source_path: str
    source_text_path: str
    source_name: str
    industry_tags: list[str]
    geography: str
    time_period: str
    source_quality: str
    reuse_limitations: list[str]


def _canonical_record_id(normalized_key: str) -> str:
    return f"R-{source_hash(normalized_key)[:12].upper()}"


def _read_snapshot_text(path: str) -> str:
    text_path = Path(path)
    if not text_path.exists():
        return ""
    try:
        return text_path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _load_records(material_manifest: dict[str, Any], material_extracts: dict[str, Any]) -> list[IngestInput]:
    material_map = {text(item.get("material_id")): item for item in as_list(material_manifest.get("materials")) if isinstance(item, dict)}
    extracts = [item for item in as_list(material_extracts.get("extracts")) if isinstance(item, dict)]
    out: list[IngestInput] = []
    for extract in extracts:
        material_id = text(extract.get("material_id"))
        manifest_row = material_map.get(material_id, {})
        source_type = normalize_source_type(extract.get("source_type") or manifest_row.get("source_type"))
        source_path = text(extract.get("file_path_or_url") or manifest_row.get("file_path_or_url"))
        source_text_path = text(extract.get("extracted_text_path"))
        source_name = text(
            manifest_row.get("source_name")
            or manifest_row.get("material_title")
            or manifest_row.get("title")
            or material_id
        )
        out.append(
            IngestInput(
                material_id=material_id,
                source_type=source_type,
                source_path=source_path,
                source_text_path=source_text_path,
                source_name=source_name,
                industry_tags=[text(tag) for tag in as_list(manifest_row.get("industry_tags")) if text(tag)],
                geography=text(manifest_row.get("geography")),
                time_period=text(manifest_row.get("source_date") or extract.get("extraction_date") or manifest_row.get("time_period")),
                source_quality=text(manifest_row.get("source_quality") or manifest_row.get("quality") or "unverified"),
                reuse_limitations=[text(item) for item in as_list(manifest_row.get("reuse_limitations")) if text(item)],
            )
        )
    return out


def _normalize_material_path(value: str, source_type: str) -> str:
    if source_type in {
        "web_search_result",
        "manual_url_ingestion",
        "official_filing",
        "business_media",
        "database",
        "other",
        "company_disclosure",
        "regulator",
    }:
        return normalize_url(value)
    return str(Path(value).as_posix())


def _merge_index_entry(mapping: dict[str, list[str]], key: str, source_id: str) -> None:
    value = mapping.get(key, [])
    if isinstance(value, str):
        value = [value] if value else []
    if not isinstance(value, list):
        value = []
    if source_id not in value:
        value.append(source_id)
    mapping[key] = value


def _first_index_hit(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list) and value:
        return text(value[0])
    return ""


def ingest(material_manifest_path: Path, material_extracts_path: Path, *, repository_root: Path, output_path: Path | None = None) -> dict[str, Any]:
    materials = load_json_file(material_manifest_path)
    extracts = load_json_file(material_extracts_path)
    records = _load_records(materials, extracts)

    sources_dir = repository_root / "sources"
    index_dir = repository_root / "index"
    repository_jsonl = index_dir / "research_repository.jsonl"
    index_json = index_dir / "source_fingerprints.json"
    existing_records = load_jsonl_records(repository_jsonl)
    fingerprints = load_fingerprints(index_json)

    # keep existing index stable and map for duplicate checks
    by_hash: dict[str, list[str]] = {}
    raw_by_hash = fingerprints.get("by_source_hash") if isinstance(fingerprints.get("by_source_hash"), dict) else {}
    for key, value in raw_by_hash.items():
        if isinstance(value, list):
            by_hash[str(key)] = [text(item) for item in value if text(item)]
        else:
            mapped = _first_index_hit(value)
            by_hash[str(key)] = [mapped] if mapped else []

    by_key: dict[str, list[str]] = {}
    raw_by_key = fingerprints.get("by_normalized_key") if isinstance(fingerprints.get("by_normalized_key"), dict) else {}
    for key, value in raw_by_key.items():
        if isinstance(value, list):
            by_key[str(key)] = [text(item) for item in value if text(item)]
        else:
            mapped = _first_index_hit(value)
            by_key[str(key)] = [mapped] if mapped else []

    inserted: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for item in records:
        if not item.material_id:
            skipped.append({"material_id": "", "status": "skipped", "reason": "material_id missing"})
            continue

        normalized_key = _normalize_material_path(item.source_path, item.source_type)
        source_text = _read_snapshot_text(item.source_text_path)
        computed_hash = file_fingerprint(Path(item.source_text_path)) if item.source_text_path else source_hash(item.source_path + source_text[:200])
        if not computed_hash:
            computed_hash = source_hash(item.source_path)
            if not computed_hash:
                skipped.append({"material_id": item.material_id, "status": "skipped", "reason": "cannot compute source hash"})
                continue

        source_id = _canonical_record_id(normalized_key or computed_hash)
        if source_id in fingerprints.get("sources", {}):
            source_id = f"{source_id}_{item.source_type[:3].upper()}"

        if by_hash.get(computed_hash) or by_key.get(normalized_key):
            duplicate_record = {
                "material_id": item.material_id,
                "source_hash": computed_hash,
                "normalized_key": normalized_key,
                "previous_source_id": _first_index_hit(by_hash.get(computed_hash) or by_key.get(normalized_key)),
            }
            duplicates.append(duplicate_record)
            continue

        snapshot_name = f"{computed_hash}.txt"
        snapshot_path = sources_dir / snapshot_name
        sources_dir.mkdir(parents=True, exist_ok=True)
        if source_text:
            snapshot_path.write_text(source_text, encoding="utf-8")
        elif item.source_path and Path(item.source_path).exists():
            try:
                shutil.copy2(item.source_path, snapshot_path)
            except Exception:
                snapshot_path.write_text(item.source_path, encoding="utf-8")
        else:
            snapshot_path.write_text("", encoding="utf-8")

        row = {
            "source_id": source_id,
            "source_hash": computed_hash,
            "normalized_key": normalized_key,
            "source_type": item.source_type or "project_specific_material",
            "source_title": item.source_name,
            "source_path": item.source_path,
            "text_snapshot_path": snapshot_path.as_posix(),
            "industry_tags": item.industry_tags,
            "geography": item.geography,
            "time_period": item.time_period,
            "source_quality": item.source_quality or "unverified",
            "reuse_limitations": item.reuse_limitations,
            "imported_at": utcnow(),
            "origin": f"material:{item.material_id}",
            "snapshot_size_bytes": snapshot_path.stat().st_size if snapshot_path.exists() else 0,
        }
        existing_records.append(row)
        inserted.append(
            {
                "source_id": source_id,
                "status": "inserted",
                "source_hash": computed_hash,
                "snapshot_path": snapshot_path.as_posix(),
            }
        )
        _merge_index_entry(by_hash, computed_hash, source_id)
        _merge_index_entry(by_key, normalized_key, source_id)
        fingerprints.setdefault("sources", {})[source_id] = {
            "source_hash": computed_hash,
            "normalized_key": normalized_key,
            "snapshot_path": snapshot_path.as_posix(),
            "imported_at": utcnow(),
        }

    write_jsonl_records(repository_jsonl, existing_records)
    fingerprints["by_source_hash"] = by_hash
    fingerprints["by_normalized_key"] = by_key
    write_fingerprints(index_json, fingerprints)

    result = {
        "is_valid": True,
        "inserted": inserted,
        "duplicates": duplicates,
        "skipped": skipped,
        "repository_jsonl": repository_jsonl.as_posix(),
        "fingerprints_index": index_json.as_posix(),
        "snapshot_dir": sources_dir.as_posix(),
    }

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--material-manifest", required=True)
    parser.add_argument("--material-extracts", required=True)
    parser.add_argument("--repository-root", default=str(repository_root_default()))
    parser.add_argument("--output", help="Optional ingest report path")
    args = parser.parse_args()

    repository_root = Path(args.repository_root)
    output_path = Path(args.output) if args.output else None
    ingest(
        Path(args.material_manifest),
        Path(args.material_extracts),
        repository_root=repository_root,
        output_path=output_path,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

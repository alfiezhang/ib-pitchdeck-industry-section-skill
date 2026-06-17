"""Repository ingest/retrieve/dedupe/validate tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "runtime" / "ib-pitchdeck-agent-industry-section" / "scripts"
ROLE_DIR = SCRIPT_DIR / "knowledge-repository"
LIB_DIR = SCRIPT_DIR / "_lib"
for path in (SCRIPT_DIR, ROLE_DIR, LIB_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from repository import dedupe as dedupe_repository
from repository import ingest as ingest_to_repository
from repository import retrieve as retrieve_from_repository
from repository import validate as validate_repository
from repository_common import repository_root_default


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_manifest_and_extracts(tmp_path: Path) -> tuple[Path, Path]:
    material_text = tmp_path / "industry_report.txt"
    _write_text(material_text, "Industry report: first-pass snapshot for regression testing.")
    manifest_path = tmp_path / "artifacts" / "material_manifest.json"
    extracts_path = tmp_path / "artifacts" / "material_extracts.json"
    _write_json(
        manifest_path,
        {
            "schema_version": "material_manifest_v1",
            "materials": [
                {
                    "material_id": "MAT-001",
                    "source_type": "industry_report",
                    "source_access": "user_provided",
                    "file_path_or_url": str(material_text),
                    "material_title": "Industry Report One",
                    "industry_tags": ["renewables", "solar"],
                    "geography": "CN",
                    "source_date": "2026-01-01",
                    "source_quality": "high",
                    "reuse_limitations": ["internal review required before publication"],
                    "extraction_status": "complete",
                    "extraction_limitations": "none",
                    "can_be_used_as_evidence": True,
                }
            ],
        },
    )
    _write_json(
        extracts_path,
        {
            "schema_version": "material_extracts_v1",
            "materials_source": str(manifest_path),
            "extracts": [
                {
                    "material_id": "MAT-001",
                    "source_type": "industry_report",
                    "source_access": "user_provided",
                    "file_path_or_url": str(material_text),
                    "extracted_text_path": str(tmp_path / "artifacts" / "MAT-001.txt"),
                    "extraction_status": "complete",
                    "extraction_limitations": "none",
                    "can_be_used_as_evidence": True,
                }
            ],
        },
    )
    _write_text(tmp_path / "artifacts" / "MAT-001.txt", material_text.read_text(encoding="utf-8"))
    return manifest_path, extracts_path


def test_repository_default_uses_user_data_dir_not_runtime(monkeypatch) -> None:
    monkeypatch.delenv("IB_PITCHDECK_REPOSITORY_DIR", raising=False)
    default_root = repository_root_default()

    assert ".ib-pitchdeck-agent-industry-section" in default_root.parts
    assert "runtime" not in default_root.parts


def test_repository_default_honors_env_override(tmp_path: Path, monkeypatch) -> None:
    override = tmp_path / "shared_repository"
    monkeypatch.setenv("IB_PITCHDECK_REPOSITORY_DIR", str(override))

    assert repository_root_default() == override


def test_repository_ingest_detects_duplicates_on_reimport(tmp_path: Path) -> None:
    repo_root = tmp_path / "repository"
    manifest_path, extracts_path = _build_manifest_and_extracts(tmp_path)

    first = ingest_to_repository(manifest_path, extracts_path, repository_root=repo_root)
    assert first["is_valid"] is True
    assert len(first["inserted"]) == 1
    assert first["duplicates"] == []

    second = ingest_to_repository(manifest_path, extracts_path, repository_root=repo_root)
    assert second["is_valid"] is True
    assert len(second["inserted"]) == 0
    assert len(second["duplicates"]) == 1
    assert second["duplicates"][0]["material_id"] == "MAT-001"


def test_repository_retrieve_filters_by_industry_tags_and_geography(tmp_path: Path) -> None:
    repo_root = tmp_path / "repository"
    repo_root.mkdir(parents=True, exist_ok=True)

    source_one = _seed_text(tmp_path, "industry_report_cn.txt", "CN example report.")
    source_two = _seed_text(tmp_path, "industry_report_us.txt", "US example report.")

    _write_index_row(
        repo_root,
        {
            "source_id": "R-000001",
            "source_hash": "hash-cn",
            "normalized_key": "https://example.com/cn",
            "source_type": "industry_report",
            "source_title": "CN Industry Report",
            "source_path": str(source_one),
            "text_snapshot_path": str(source_one),
            "industry_tags": ["solar", "renewables"],
            "geography": "CN",
            "time_period": "2026",
            "source_quality": "high",
            "reuse_limitations": ["none"],
            "imported_at": "2026-01-01T00:00:00Z",
            "origin": "manual",
            "snapshot_size_bytes": 1,
        },
    )
    _write_index_row(
        repo_root,
        {
            "source_id": "R-000002",
            "source_hash": "hash-us",
            "normalized_key": "https://example.com/us",
            "source_type": "industry_report",
            "source_title": "US Industry Report",
            "source_path": str(source_two),
            "text_snapshot_path": str(source_two),
            "industry_tags": ["wind"],
            "geography": "US",
            "time_period": "2026",
            "source_quality": "medium",
            "reuse_limitations": ["none"],
            "imported_at": "2026-01-01T00:00:00Z",
            "origin": "manual",
            "snapshot_size_bytes": 1,
        },
    )

    cn_solar = retrieve_from_repository(
        repository_root=repo_root,
        query={"industry_tags": ["solar"], "geography": "CN"},
        max_results=10,
    )
    assert cn_solar["count"] == 1
    assert cn_solar["sources"][0]["geography"] == "CN"
    assert cn_solar["sources"][0]["source_id"] == "R-000001"

    us = retrieve_from_repository(
        repository_root=repo_root,
        query={"industry_tags": ["wind"], "geography": "US"},
    )
    assert us["count"] == 1
    assert us["sources"][0]["source_id"] == "R-000002"


def test_repository_dedupe_detects_duplicate_mapping_in_jsonl(tmp_path: Path) -> None:
    repo_root = tmp_path / "repository"
    index_root = repo_root / "index"
    index_root.mkdir(parents=True, exist_ok=True)

    jsonl_path = index_root / "research_repository.jsonl"
    jsonl_path.write_text(
        "\n".join(
            [
                _row_json(
                    "R-DUP",
                    "hash-dupe",
                    "key-dupe",
                    "/tmp/a.txt",
                ),
                _row_json(
                    "R-DUP-2",
                    "hash-dupe",
                    "key-dupe",
                    "/tmp/b.txt",
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    _write_json(
        index_root / "source_fingerprints.json",
        {
            "schema_version": "repository_fingerprints_v1",
            "generated_at": "2026-01-01T00:00:00Z",
            "sources": {},
            "by_source_hash": {"hash-dupe": ["R-DUP", "R-DUP-2"]},
            "by_normalized_key": {"key-dupe": ["R-DUP", "R-DUP-2"]},
        },
    )
    result = dedupe_repository(repo_root)
    assert result["is_valid"] is False
    assert result["duplicate_group_count"] == 2
    kinds = {group["kind"] for group in result["duplicate_groups"]}
    assert kinds == {"source_hash", "normalized_key"}


def test_repository_validate_reports_missing_index(tmp_path: Path) -> None:
    repo_root = tmp_path / "repository"
    result = validate_repository(repo_root)
    assert result["is_valid"] is False
    assert "source_fingerprints.json missing" in result["errors"]
    assert "research_repository.jsonl missing" in result["errors"]


def _seed_text(tmp_path: Path, filename: str, content: str) -> Path:
    path = tmp_path / filename
    _write_text(path, content)
    return path


def _row_json(source_id: str, source_hash: str, normalized_key: str, source_path: str) -> str:
    return json.dumps(
        {
            "source_id": source_id,
            "source_hash": source_hash,
            "normalized_key": normalized_key,
            "source_type": "industry_report",
            "source_title": source_id,
            "source_path": source_path,
            "text_snapshot_path": source_path,
            "industry_tags": [],
            "geography": "CN",
            "time_period": "2026",
            "source_quality": "high",
            "reuse_limitations": [],
            "imported_at": "2026-01-01T00:00:00Z",
            "origin": "pytest",
            "snapshot_size_bytes": 1,
        },
        ensure_ascii=False,
    )


def _write_index_row(repo_root: Path, row: dict) -> None:
    index_dir = repo_root / "index"
    index_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = index_dir / "research_repository.jsonl"
    existing = jsonl_path.read_text(encoding="utf-8") if jsonl_path.exists() else ""
    prefix = existing + ("\n" if existing and not existing.endswith("\n") else "")
    jsonl_path.write_text(prefix + json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")

    index = {"schema_version": "repository_fingerprints_v1", "generated_at": "2026-01-01T00:00:00Z", "sources": {}, "by_source_hash": {}, "by_normalized_key": {}}
    payload = json.loads(index_dir.joinpath("source_fingerprints.json").read_text(encoding="utf-8")) if index_dir.joinpath("source_fingerprints.json").exists() else index
    payload["sources"][row["source_id"]] = {"source_hash": row["source_hash"], "normalized_key": row["normalized_key"]}
    source_hash_list = payload.setdefault("by_source_hash", {})
    source_hash_list.setdefault(row["source_hash"], [])
    if row["source_id"] not in source_hash_list[row["source_hash"]]:
        source_hash_list[row["source_hash"]].append(row["source_id"])
    norm_key_list = payload.setdefault("by_normalized_key", {})
    norm_key_list.setdefault(row["normalized_key"], [])
    if row["source_id"] not in norm_key_list[row["normalized_key"]]:
        norm_key_list[row["normalized_key"]].append(row["source_id"])
    index_dir.joinpath("source_fingerprints.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

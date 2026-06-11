#!/usr/bin/env python3
"""Common helpers for the local cross-project repository index."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


def text(value: Any) -> str:
    return str(value or "").strip()


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_url(value: str) -> str:
    raw = text(value)
    if not raw:
        return ""
    parsed = urlparse(raw)
    if not parsed.scheme:
        return raw.rstrip("/")
    netloc = parsed.netloc.lower().rstrip(".")
    if netloc.startswith("www."):
        netloc = netloc[4:]
    path = parsed.path.rstrip("/") or "/"
    query_parts = sorted((k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True))
    normalized = parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=netloc,
        path=path,
        fragment="",
        query=urlencode(query_parts),
    )
    return urlunparse(normalized)


def source_hash(value: str) -> str:
    digest = hashlib.sha256()
    digest.update(text(value).encode("utf-8"))
    return digest.hexdigest()


def file_fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        digest.update(path.read_bytes())
        return digest.hexdigest()
    except OSError:
        return source_hash(path.as_posix())


@dataclass
class RepositoryRecord:
    source_id: str
    source_hash: str
    normalized_key: str
    source_type: str
    source_title: str
    source_path: str
    text_snapshot_path: str
    industry_tags: list[str]
    geography: str
    time_period: str
    source_quality: str
    reuse_limitations: list[str]
    imported_at: str
    origin: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_hash": self.source_hash,
            "normalized_key": self.normalized_key,
            "source_type": self.source_type,
            "source_title": self.source_title,
            "source_path": self.source_path,
            "text_snapshot_path": self.text_snapshot_path,
            "industry_tags": self.industry_tags,
            "geography": self.geography,
            "time_period": self.time_period,
            "source_quality": self.source_quality,
            "reuse_limitations": self.reuse_limitations,
            "imported_at": self.imported_at,
            "origin": self.origin,
        }


def load_jsonl_records(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not path.exists():
        return records
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        import json

        payload = json.loads(raw_line)
        if isinstance(payload, dict):
            records.append(payload)
    return records


def write_jsonl_records(path: Path, records: list[dict[str, Any]]) -> None:
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in records) + ("\n" if records else ""),
        encoding="utf-8",
    )


def load_fingerprints(index_path: Path) -> dict[str, Any]:
    import json

    if not index_path.exists():
        return {
            "schema_version": "repository_fingerprints_v1",
            "generated_at": utcnow(),
            "sources": {},
            "by_source_hash": {},
            "by_normalized_key": {},
        }
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {
            "schema_version": "repository_fingerprints_v1",
            "generated_at": utcnow(),
            "sources": {},
            "by_source_hash": {},
            "by_normalized_key": {},
        }
    payload.setdefault("schema_version", "repository_fingerprints_v1")
    payload.setdefault("sources", {})
    payload.setdefault("by_source_hash", {})
    payload.setdefault("by_normalized_key", {})
    payload.setdefault("generated_at", utcnow())

    # Keep compatibility with older index layouts where mappings were single strings.
    def _normalize_bucket(value: Any) -> list[str]:
        if isinstance(value, list):
            return [text(item) for item in value if text(item)]
        if isinstance(value, str):
            item = text(value)
            return [item] if item else []
        return []

    payload["by_source_hash"] = {
        str(key): _normalize_bucket(value)
        for key, value in payload.get("by_source_hash", {}).items()
        if str(key)
    }
    payload["by_normalized_key"] = {
        str(key): _normalize_bucket(value)
        for key, value in payload.get("by_normalized_key", {}).items()
        if str(key)
    }
    return payload


def write_fingerprints(index_path: Path, payload: dict[str, Any]) -> None:
    import json

    payload["schema_version"] = "repository_fingerprints_v1"
    payload["generated_at"] = utcnow()
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def repository_root_default() -> Path:
    return Path(__file__).resolve().parent.parent / "repository"

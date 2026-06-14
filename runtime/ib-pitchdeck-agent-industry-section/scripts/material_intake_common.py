#!/usr/bin/env python3
"""Shared helpers for deterministic material extraction scripts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
from typing import Any

from source_classification import normalize_source_type


def text(value: Any) -> str:
    return str(value or "").strip()


def as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "y", "yes", "on"}


def is_url(value: str) -> bool:
    lowered = text(value).lower()
    return lowered.startswith(("http://", "https://", "mailto:", "ftp://"))


def infer_material_kind(source_path: str, source_type: str) -> str:
    """Classify source kind without inferring facts from file names.

    `source_type` controls whether this is a curated or user-provided URL/file;
    this helper only normalizes shape so validators have stable values.
    """

    source_path = text(source_path)
    if normalize_source_type(source_type) == "ppt_template":
        return "ppt_template"
    if source_path == "inline_user_text":
        return "text"
    if is_url(source_path):
        return "url"
    return "file"


def normalize_source_type_hint(path_or_url: str, provided_type: str | None) -> str:
    value = text(path_or_url)
    if provided_type:
        return normalize_source_type(provided_type)
    if is_url(value):
        return normalize_source_type("manual_url_ingestion")
    return normalize_source_type("project_specific_material")


def classify_access(source_type: str, source_path: str | None = None) -> str:
    normalized = normalize_source_type(source_type)
    if normalized == "repository_retrieval":
        return "repository_retrieval"
    if is_url(source_path or "") or normalized == "web_search_result":
        return "public_search"
    return "user_provided"


def file_fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        digest.update(path.read_bytes())
        return digest.hexdigest()
    except Exception:
        return ""


@dataclass
class ExtractionResult:
    text: str
    source_locator: str
    status: str
    limitations: list[str]
    can_be_used_as_evidence: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "source_locator": self.source_locator,
            "extraction_status": self.status,
            "extraction_limitations": "; ".join(self.limitations),
            "can_be_used_as_evidence": self.can_be_used_as_evidence,
        }


def read_text_file(path: str | Path) -> str:
    p = Path(path)
    try:
        raw = p.read_bytes()
    except Exception:
        return ""
    try:
        return raw.decode("utf-8")
    except Exception:
        try:
            return raw.decode("latin1")
        except Exception:
            return ""


def clean_text_block(value: str) -> str:
    text_value = value or ""
    lines = [line.strip() for line in text_value.replace("\x00", "").splitlines()]
    filtered = [line for line in lines if line and "BT" not in line and "ET" not in line]
    return "\n".join(filtered)

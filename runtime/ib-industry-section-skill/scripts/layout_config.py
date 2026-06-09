"""Helpers for resolving deterministic layout configuration paths."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from json_utils import load_json_file


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_LAYOUT_CONFIG = ROOT_DIR / "templates" / "layout_config.json"


def load_layout_config(path: Path | str = DEFAULT_LAYOUT_CONFIG) -> dict[str, Any]:
    config_path = Path(path)
    if not config_path.is_absolute():
        config_path = ROOT_DIR / config_path
    config = load_json_file(config_path)
    if config.get("schema_version") != "layout_config_v1":
        raise ValueError(f"{config_path} must use schema_version layout_config_v1")
    files = config.get("files")
    if not isinstance(files, dict):
        raise ValueError(f"{config_path} must define object field 'files'")
    return config


def layout_config_paths(path: Path | str = DEFAULT_LAYOUT_CONFIG) -> dict[str, Path]:
    config = load_layout_config(path)
    resolved: dict[str, Path] = {}
    for key, raw in config.get("files", {}).items():
        candidate = Path(str(raw))
        if not candidate.is_absolute():
            candidate = ROOT_DIR / candidate
        resolved[key] = candidate
    return resolved

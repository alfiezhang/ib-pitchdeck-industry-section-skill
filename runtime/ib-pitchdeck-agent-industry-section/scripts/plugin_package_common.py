#!/usr/bin/env python3
"""Shared helpers for plugin package/install scripts."""

from __future__ import annotations

import json
import os
import zipfile
from pathlib import Path
from typing import Any, Iterable


PLUGIN_NAME = "ib-pitchdeck-agent-industry-section"
RUNTIME_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = RUNTIME_ROOT.parents[1]

REQUIRED_PATHS = [
    ".codex-plugin/plugin.json",
    ".claude-plugin/plugin.json",
    ".codebuddy-plugin/plugin.json",
    "agents",
    "skills",
    "scripts",
    "templates",
    "assets",
    "references",
    "README.md",
    "requirements.txt",
    "setup.sh",
    "run_pipeline.sh",
]

FORBIDDEN_PARTS = {"docs", "tests", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".git", "runs", "dist", "artifacts"}
FORBIDDEN_NAMES = {".DS_Store"}


def relpath(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def should_exclude(rel: str) -> bool:
    parts = Path(rel).parts
    if any(part in FORBIDDEN_PARTS for part in parts):
        return True
    if parts and parts[-1] in FORBIDDEN_NAMES:
        return True
    if parts and parts[-1].endswith((".pyc", ".pyo")):
        return True
    return False


def iter_package_files(source_dir: Path) -> Iterable[Path]:
    for path in sorted(source_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = relpath(path, source_dir)
        if should_exclude(rel):
            continue
        yield path


def load_json_text(text: str, label: str) -> tuple[dict[str, Any] | None, str]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, f"{label} is not valid JSON: {exc}"
    if not isinstance(payload, dict):
        return None, f"{label} must be a JSON object"
    return payload, ""


def package_entries_from_dir(path: Path) -> dict[str, bytes]:
    entries: dict[str, bytes] = {}
    for file_path in path.rglob("*"):
        if file_path.is_file():
            entries[relpath(file_path, path)] = file_path.read_bytes()
    return entries


def package_entries_from_zip(path: Path) -> dict[str, bytes]:
    entries: dict[str, bytes] = {}
    with zipfile.ZipFile(path, "r") as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            entries[info.filename] = zf.read(info.filename)
    return entries


def detect_plugin_root(entries: dict[str, bytes]) -> str:
    candidates = [name for name in entries if name.endswith(".codex-plugin/plugin.json")]
    if not candidates:
        return ""
    candidate = sorted(candidates, key=len)[0]
    return candidate[: -len(".codex-plugin/plugin.json")]


def normalize_entries(entries: dict[str, bytes]) -> dict[str, bytes]:
    root = detect_plugin_root(entries)
    if not root:
        return entries
    return {name[len(root):]: value for name, value in entries.items() if name.startswith(root)}


def default_target_root(host: str) -> Path:
    home = Path.home()
    if host == "codex":
        return home / ".codex" / "plugins"
    if host == "claude":
        return home / ".claude" / "plugins"
    if host in {"codebuddy", "workbuddy"}:
        return home / ".workbuddy" / "plugins"
    raise ValueError(f"unsupported host: {host}")


def ensure_inside(path: Path, root: Path) -> None:
    resolved = path.resolve()
    root_resolved = root.resolve()
    if os.path.commonpath([str(resolved), str(root_resolved)]) != str(root_resolved):
        raise ValueError(f"target {path} is outside allowed root {root}")

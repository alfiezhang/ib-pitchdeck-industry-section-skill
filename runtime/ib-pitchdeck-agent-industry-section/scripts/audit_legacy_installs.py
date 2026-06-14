#!/usr/bin/env python3
"""Audit old installs that can conflict with the current skill package."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


LEGACY_SKILL_NAMES = [
    "ib-industry-section-skill",
    "deck-blueprint-section",
    "fill-ppt",
    "research-pack",
    "ib-industry-deck-blueprint-section",
    "ib-industry-fill-ppt",
    "ib-industry-research-pack",
]

DEFAULT_SKILL_ROOTS = [
    "~/.codex/skills",
    "~/.claude/skills",
    "~/.workbuddy/skills",
]

LEGACY_PLUGIN_NAMES = [
    "ib-pitchdeck-agent-industry-section",
]

DEFAULT_PLUGIN_ROOTS = [
    "~/.codex/plugins",
    "~/.claude/plugins",
    "~/.workbuddy/plugins",
]


def _path_summary(path: Path) -> dict[str, Any]:
    exists = path.exists()
    is_dir = path.is_dir()
    marker_files = []
    for name in ("SKILL.md", "skill.json", "plugin.json"):
        if (path / name).exists():
            marker_files.append(name)
    child_count = 0
    if is_dir:
        try:
            child_count = sum(1 for _ in path.iterdir())
        except OSError:
            child_count = 0
    return {
        "path": str(path),
        "exists": exists,
        "is_dir": is_dir,
        "marker_files": marker_files,
        "child_count": child_count,
        "legacy_install": exists and is_dir,
    }


def audit_legacy_installs(skill_roots: list[Path] | None = None, plugin_roots: list[Path] | None = None) -> dict[str, Any]:
    roots = skill_roots or [Path(item).expanduser() for item in DEFAULT_SKILL_ROOTS]
    entries: list[dict[str, Any]] = []
    for root in roots:
        for skill_name in LEGACY_SKILL_NAMES:
            path = root / skill_name
            item = _path_summary(path)
            item["skill_name"] = skill_name
            item["skill_root"] = str(root)
            entries.append(item)

    plugin_entries: list[dict[str, Any]] = []
    for root in plugin_roots or [Path(item).expanduser() for item in DEFAULT_PLUGIN_ROOTS]:
        for plugin_name in LEGACY_PLUGIN_NAMES:
            path = root / plugin_name
            item = _path_summary(path)
            item["plugin_name"] = plugin_name
            item["plugin_root"] = str(root)
            plugin_entries.append(item)

    found = [item for item in entries if item["legacy_install"]]
    plugin_found = [item for item in plugin_entries if item["legacy_install"]]
    return {
        "schema_version": "legacy_install_audit_v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "is_valid": True,
        "legacy_install_count": len(found) + len(plugin_found),
        "legacy_installs_found": bool(found or plugin_found),
        "checked_roots": [str(root) for root in roots],
        "checked_skill_names": LEGACY_SKILL_NAMES,
        "entries": entries,
        "plugin_entries": plugin_entries,
        "recommended_action": "Use the current skill install path for active runtime. Remove old plugin or legacy skill installs only after confirming no host depends on them.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill-root", action="append", help="Override skill root; may be repeated")
    parser.add_argument("--plugin-root", action="append", help="Override legacy plugin root; may be repeated")
    parser.add_argument("--output", default="artifacts/legacy_install_audit.json")
    args = parser.parse_args()

    roots = [Path(item).expanduser() for item in args.skill_root] if args.skill_root else None
    plugin_roots = [Path(item).expanduser() for item in args.plugin_root] if args.plugin_root else None
    payload = audit_legacy_installs(roots, plugin_roots)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

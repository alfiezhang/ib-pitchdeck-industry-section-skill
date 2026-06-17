#!/usr/bin/env python3
"""Validate a clean runtime skill package directory or zip."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

ROOT_DIR = Path(__file__).resolve().parents[2]
PACKAGE_TOOLS = ROOT_DIR / "devtools" / "package"
if str(PACKAGE_TOOLS) not in sys.path:
    sys.path.insert(0, str(PACKAGE_TOOLS))

from skill_package_common import (
    FORBIDDEN_NAMES,
    FORBIDDEN_PARTS,
    REQUIRED_PATHS,
    normalize_entries,
    package_entries_from_dir,
    package_entries_from_zip,
    should_exclude,
)


def _has_path(entries: dict[str, bytes], required: str) -> bool:
    if required in entries:
        return True
    prefix = required.rstrip("/") + "/"
    return any(name.startswith(prefix) for name in entries)


def _validate_skill_md(entries: dict[str, bytes], errors: list[str]) -> None:
    raw = entries.get("SKILL.md")
    if raw is None:
        errors.append("missing SKILL.md")
        return
    text = raw.decode("utf-8", errors="replace")
    if not text.startswith("---\n"):
        errors.append("SKILL.md: missing YAML frontmatter")
        return
    parts = text.split("---", 2)
    if len(parts) < 3:
        errors.append("SKILL.md: malformed YAML frontmatter")
        return
    frontmatter = parts[1]
    if "name:" not in frontmatter:
        errors.append("SKILL.md: missing name in frontmatter")
    if "description:" not in frontmatter:
        errors.append("SKILL.md: missing description in frontmatter")


def validate_entries(entries: dict[str, bytes]) -> dict[str, Any]:
    normalized = normalize_entries(entries)
    errors: list[str] = []
    warnings: list[str] = []

    for required in REQUIRED_PATHS:
        if not _has_path(normalized, required):
            errors.append(f"missing required package path: {required}")

    for name in sorted(normalized):
        parts = Path(name).parts
        if Path(name).is_absolute() or any(part in {"", ".", ".."} for part in parts):
            errors.append(f"unsafe path in package: {name}")
        forbidden_parts = [part for part in parts if part in FORBIDDEN_PARTS]
        if forbidden_parts:
            errors.append(f"forbidden path in package: {name}")
        if parts and parts[-1] in FORBIDDEN_NAMES:
            errors.append(f"forbidden file in package: {name}")
        if should_exclude(name):
            warnings.append(f"excluded-by-packager path present in validation target: {name}")

    _validate_skill_md(normalized, errors)
    if any(name.startswith(".codex-plugin/") or name.startswith(".claude-plugin/") or name.startswith(".codebuddy-plugin/") for name in normalized):
        errors.append("skill package must not contain plugin manifests")
    if any(name.startswith("agents/") for name in normalized):
        errors.append("skill package must not contain agents/")
    if any(name.startswith("skills/") for name in normalized):
        errors.append("skill package must not contain nested skills/")

    if any(name.startswith("docs/") for name in normalized):
        errors.append("runtime package must not contain docs/")
    if any(name.startswith("tests/") for name in normalized):
        errors.append("runtime package must not contain tests/")

    return {
        "schema_version": "skill_package_validation_v1",
        "is_valid": not errors,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "file_count": len(normalized),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", required=True, help="Runtime package directory or .zip file")
    parser.add_argument("--output")
    args = parser.parse_args()

    package_path = Path(args.package)
    try:
        if package_path.is_dir():
            entries = package_entries_from_dir(package_path)
        elif package_path.is_file() and package_path.suffix == ".zip":
            entries = package_entries_from_zip(package_path)
        else:
            raise ValueError(f"package path does not exist or is not supported: {package_path}")
        result = validate_entries(entries)
    except Exception as exc:
        result = {
            "schema_version": "skill_package_validation_v1",
            "is_valid": False,
            "error_count": 1,
            "warning_count": 0,
            "errors": [str(exc)],
            "warnings": [],
            "file_count": 0,
        }

    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if result["is_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

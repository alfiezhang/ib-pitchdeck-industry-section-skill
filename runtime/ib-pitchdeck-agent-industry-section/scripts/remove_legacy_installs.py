#!/usr/bin/env python3
"""Dry-run or remove legacy standalone skill installs after explicit confirmation."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from audit_legacy_installs import audit_legacy_installs


CONFIRMATION = "REMOVE_LEGACY_INSTALLS"


def remove_legacy_installs(skill_roots: list[Path] | None = None, *, confirm: str = "", dry_run: bool = True) -> dict[str, Any]:
    audit = audit_legacy_installs(skill_roots)
    candidates = [item for item in audit["entries"] if item.get("legacy_install")]
    confirmed = confirm == CONFIRMATION and not dry_run
    actions: list[dict[str, Any]] = []
    for item in candidates:
        path = Path(str(item["path"]))
        action = {
            "path": str(path),
            "skill_name": item.get("skill_name", ""),
            "would_remove": True,
            "removed": False,
            "error": "",
        }
        if confirmed:
            try:
                shutil.rmtree(path)
                action["removed"] = True
            except Exception as exc:
                action["error"] = str(exc)
        actions.append(action)

    errors = [item["error"] for item in actions if item.get("error")]
    return {
        "schema_version": "legacy_install_remove_v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "is_valid": not errors,
        "dry_run": not confirmed,
        "confirmation_required": CONFIRMATION,
        "confirmed": confirmed,
        "candidate_count": len(candidates),
        "removed_count": sum(1 for item in actions if item.get("removed")),
        "actions": actions,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill-root", action="append", help="Override skill root; may be repeated")
    parser.add_argument("--confirm", default="", help=f"Must equal {CONFIRMATION} to remove")
    parser.add_argument("--execute", action="store_true", help="Actually remove matched legacy installs")
    parser.add_argument("--output")
    args = parser.parse_args()

    roots = [Path(item).expanduser() for item in args.skill_root] if args.skill_root else None
    payload = remove_legacy_installs(roots, confirm=args.confirm, dry_run=not args.execute)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if payload["is_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

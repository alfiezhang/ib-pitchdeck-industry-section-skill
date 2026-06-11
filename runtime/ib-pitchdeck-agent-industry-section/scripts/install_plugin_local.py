#!/usr/bin/env python3
"""Install the runtime plugin package into a local host plugin source."""

from __future__ import annotations

import argparse
import json
import shutil
import zipfile
from pathlib import Path

from plugin_package_common import PLUGIN_NAME, RUNTIME_ROOT, default_target_root, ensure_inside, iter_package_files, relpath
from validate_plugin_package import validate_entries
from plugin_package_common import package_entries_from_dir, package_entries_from_zip


def _copy_dir_clean(source_dir: Path, target_dir: Path) -> int:
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for file_path in iter_package_files(source_dir):
        rel = relpath(file_path, source_dir)
        dest = target_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file_path, dest)
        count += 1
    return count


def _extract_zip_clean(zip_path: Path, target_dir: Path) -> int:
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = [info.filename for info in zf.infolist() if not info.is_dir()]
        prefix = ""
        candidates = [name for name in names if name.endswith(".codex-plugin/plugin.json")]
        if candidates:
            prefix = sorted(candidates, key=len)[0][: -len(".codex-plugin/plugin.json")]
        for name in names:
            rel = name[len(prefix):] if prefix and name.startswith(prefix) else name
            if not rel:
                continue
            rel_path = Path(rel)
            if rel_path.is_absolute() or any(part in {"", ".", ".."} for part in rel_path.parts):
                raise ValueError(f"unsafe path in plugin zip: {name}")
            dest = target_dir / rel_path
            ensure_inside(dest.resolve(), target_dir.resolve())
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(zf.read(name))
            count += 1
    return count


def install_plugin(source: Path, host: str, target_root: Path | None = None) -> dict:
    root = target_root or default_target_root(host)
    target = root / PLUGIN_NAME
    ensure_inside(target, root)

    if source.is_dir():
        validation = validate_entries(package_entries_from_dir(source))
    elif source.is_file() and source.suffix == ".zip":
        validation = validate_entries(package_entries_from_zip(source))
    else:
        raise ValueError(f"unsupported plugin source: {source}")
    if not validation["is_valid"]:
        return {
            "schema_version": "plugin_local_install_v1",
            "is_valid": False,
            "installed": False,
            "host": host,
            "target_dir": str(target),
            "validation": validation,
        }

    root.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        installed_files = _copy_dir_clean(source, target)
    else:
        installed_files = _extract_zip_clean(source, target)

    return {
        "schema_version": "plugin_local_install_v1",
        "is_valid": True,
        "installed": True,
        "host": host,
        "target_dir": str(target),
        "installed_files": installed_files,
        "validation": validation,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=str(RUNTIME_ROOT), help="Runtime package directory or clean zip")
    parser.add_argument("--host", choices=["codex", "claude", "codebuddy", "workbuddy"], required=True)
    parser.add_argument("--target-root", help="Override host plugin root; useful for tests or custom plugin sources")
    args = parser.parse_args()

    try:
        result = install_plugin(
            Path(args.source),
            args.host,
            Path(args.target_root) if args.target_root else None,
        )
    except Exception as exc:
        result = {
            "schema_version": "plugin_local_install_v1",
            "is_valid": False,
            "installed": False,
            "host": args.host,
            "target_dir": "",
            "validation": {"is_valid": False, "errors": [str(exc)]},
        }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("installed") else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Build a clean plugin package zip from the runtime package."""

from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

from plugin_package_common import PLUGIN_NAME, REPO_ROOT, RUNTIME_ROOT, iter_package_files, relpath
from validate_plugin_package import validate_entries
from plugin_package_common import package_entries_from_zip


def package_plugin(source_dir: Path, output: Path) -> dict:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in iter_package_files(source_dir):
            archive_name = f"{PLUGIN_NAME}/{relpath(file_path, source_dir)}"
            zf.write(file_path, archive_name)

    validation = validate_entries(package_entries_from_zip(output))
    return {
        "schema_version": "plugin_package_build_v1",
        "is_valid": validation["is_valid"],
        "output": str(output),
        "source_dir": str(source_dir),
        "validation": validation,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", default=str(RUNTIME_ROOT))
    parser.add_argument("--output", default=str(REPO_ROOT / "dist" / f"{PLUGIN_NAME}.zip"))
    args = parser.parse_args()

    try:
        result = package_plugin(Path(args.source_dir), Path(args.output))
    except Exception as exc:
        result = {
            "schema_version": "plugin_package_build_v1",
            "is_valid": False,
            "output": args.output,
            "source_dir": args.source_dir,
            "validation": {"is_valid": False, "errors": [str(exc)]},
        }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["is_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

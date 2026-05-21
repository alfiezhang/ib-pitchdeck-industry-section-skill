#!/usr/bin/env python3
"""Check runtime dependencies before running the skill workflow."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


REQUIRED_MODULES = {
    "pptx": "python-pptx",
}

OPTIONAL_SEARCH_MODULE_GROUPS = {
    "tavily": ["tavily"],
    "duckduckgo": ["ddgs", "duckduckgo_search"],
}


def module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def main() -> int:
    missing_required = [
        package_name
        for module_name, package_name in REQUIRED_MODULES.items()
        if not module_available(module_name)
    ]

    search_providers = {}
    for provider, module_names in OPTIONAL_SEARCH_MODULE_GROUPS.items():
        search_providers[provider] = any(module_available(name) for name in module_names)

    payload = {
        "python": sys.executable,
        "python_version": sys.version.split()[0],
        "required": {
            package_name: module_available(module_name)
            for module_name, package_name in REQUIRED_MODULES.items()
        },
        "search_providers": search_providers,
        "is_ready_for_ppt_pipeline": not missing_required,
        "has_fallback_search": any(search_providers.values()),
    }

    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if missing_required:
        print(
            "ERROR: Missing required package(s): " + ", ".join(missing_required),
            file=sys.stderr,
        )
        print("Run 'bash ./setup.sh' or install requirements.txt in this Python environment.", file=sys.stderr)
        return 1

    if not payload["has_fallback_search"]:
        print(
            "ERROR: No fallback web-search provider package is installed "
            "(need tavily-python and/or ddgs).",
            file=sys.stderr,
        )
        print("Run 'bash ./setup.sh' or install requirements.txt in this Python environment.", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

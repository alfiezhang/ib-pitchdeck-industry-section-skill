#!/usr/bin/env python3
"""Check runtime dependencies before running the skill workflow."""

from __future__ import annotations

import json
import sys


REQUIRED_IMPORTS = [
    {"module": "pptx", "package": "python-pptx"},
    {"module": "lxml.etree", "package": "lxml"},
]

OPTIONAL_SEARCH_MODULE_GROUPS = {
    "tavily": ["tavily"],
    "duckduckgo": ["ddgs", "duckduckgo_search"],
}


def import_check(module_name: str) -> dict:
    try:
        module = __import__(module_name, fromlist=["*"])
        return {
            "module": module_name,
            "available": True,
            "version": str(getattr(module, "__version__", "")),
            "error": "",
        }
    except Exception as exc:
        return {
            "module": module_name,
            "available": False,
            "version": "",
            "error": f"{type(exc).__name__}: {exc}",
        }


def main() -> int:
    required_checks = {}
    missing_required = []
    for item in REQUIRED_IMPORTS:
        result = import_check(item["module"])
        required_checks[item["package"]] = result
        if not result["available"]:
            missing_required.append(item["package"])

    search_providers = {}
    search_provider_details = {}
    for provider, module_names in OPTIONAL_SEARCH_MODULE_GROUPS.items():
        checks = [import_check(name) for name in module_names]
        search_provider_details[provider] = checks
        search_providers[provider] = any(item["available"] for item in checks)

    payload = {
        "python": sys.executable,
        "python_version": sys.version.split()[0],
        "required": required_checks,
        "search_providers": search_providers,
        "search_provider_details": search_provider_details,
        "is_ready_for_ppt_pipeline": not missing_required,
        "has_fallback_search": any(search_providers.values()),
    }

    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if missing_required:
        print("ERROR: Required import(s) failed: " + ", ".join(missing_required), file=sys.stderr)
        for package_name in missing_required:
            result = required_checks.get(package_name, {})
            if result.get("error"):
                print(f"  {package_name}: {result['error']}", file=sys.stderr)
        print("Run 'python3 scripts/bootstrap_runtime.py --force' or install requirements.txt in this Python environment.", file=sys.stderr)
        if sys.platform == "darwin" and sys.version_info >= (3, 13):
            print(
                "macOS note: Python 3.13+ can hit lxml wheel import/code-signing issues. "
                "Prefer python3 scripts/bootstrap_runtime.py --python python3.11 --force.",
                file=sys.stderr,
            )
        return 1

    if not payload["has_fallback_search"]:
        print(
            "ERROR: No fallback web-search provider package is installed "
            "(need tavily-python and/or ddgs).",
            file=sys.stderr,
        )
        print("Run 'python3 scripts/bootstrap_runtime.py' or install requirements.txt in this Python environment.", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

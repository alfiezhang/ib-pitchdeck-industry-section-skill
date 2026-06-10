#!/usr/bin/env python3
"""Check runtime dependencies before running the skill workflow."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


REQUIRED_IMPORTS = [
    {"module": "pptx", "package": "python-pptx"},
    {"module": "lxml.etree", "package": "lxml"},
]

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
SOURCE_REGISTRY = ROOT_DIR / "templates" / "source_registry.json"
SEARXNG_ENV_VARS = ("SEARXNG_BASE_URL", "SEARXNG_URL", "SEARXNG_ENDPOINT")

OPTIONAL_SEARCH_MODULE_GROUPS = {
    "tavily": ["tavily"],
    "duckduckgo": ["ddgs", "duckduckgo_search"],
    "searxng": [],
}


def _read_json(path: Path) -> dict[str, object]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _get_searxng_url() -> tuple[bool, str]:
    for env_var in SEARXNG_ENV_VARS:
        value = str(os.environ.get(env_var, "")).strip()
        if value:
            return True, value

    registry = _read_json(SOURCE_REGISTRY)
    connectors = registry.get("search_connectors", {}) if isinstance(registry, dict) else {}
    if isinstance(connectors, dict):
        searxng = connectors.get("searxng") if isinstance(connectors, dict) else {}
        if isinstance(searxng, dict):
            configured_url = str(searxng.get("default_url", "")).strip()
            if configured_url:
                return True, configured_url
    return False, ""


def get_search_provider_payload() -> dict[str, object]:
    """Return provider availability payload shared by runtime/dependency checks."""
    search_providers: dict[str, bool] = {}
    search_provider_details: dict[str, object] = {}
    searxng_configured, searxng_url = _get_searxng_url()
    for provider, module_names in OPTIONAL_SEARCH_MODULE_GROUPS.items():
        checks = [import_check(name) for name in module_names]
        search_provider_details[provider] = checks
        search_providers[provider] = any(item["available"] for item in checks)

    search_provider_details["searxng"] = {
        "configured": searxng_configured,
        "url": searxng_url,
        "module_checks": [],
        "env_ready": searxng_configured,
    }
    search_providers["searxng"] = searxng_configured
    paid_search_available = search_providers.get("tavily", False) or search_providers.get("duckduckgo", False)

    return {
        "search_providers": search_providers,
        "search_provider_details": search_provider_details,
        "paid_search_available": paid_search_available,
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

    provider_payload = get_search_provider_payload()
    search_providers = provider_payload["search_providers"]
    search_provider_details = provider_payload["search_provider_details"]
    paid_search_available = provider_payload["paid_search_available"]

    payload = {
        "python": sys.executable,
        "python_version": sys.version.split()[0],
        "required": required_checks,
        "search_providers": search_providers,
        "search_provider_details": search_provider_details,
        "manual_source_mode_supported": True,
        "paid_search_optional": True,
        "paid_search_available": paid_search_available,
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
            "WARN: No fallback web-search provider currently available. "
            "If online search is unavailable, you can still proceed with manual source mode "
            "(user-provided URLs, PDFs, and uploaded materials).",
            file=sys.stderr,
        )
        if not search_providers["searxng"]:
            print("Set SEARXNG_BASE_URL or source_registry search_connectors.searxng.default_url to enable offline-friendly fallback.", file=sys.stderr)
            return 1
        print("SearXNG is configured; script fallback search can proceed when runtime can reach it.", file=sys.stderr)
        print("Install tavily/duckduckgo packages only if paid/extra providers are required.", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

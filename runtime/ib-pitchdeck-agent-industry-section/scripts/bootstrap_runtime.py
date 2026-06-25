#!/usr/bin/env python3
"""Select or create a Python runtime for this skill.

Decision tree:
1. If an explicit/current Python can import required deps, use it.
2. If the project .venv can import required deps, use it.
3. If another local Python can import required deps, use it.
4. Otherwise create/update .venv, install requirements.txt, validate imports.

The selected interpreter is printed as JSON by default, or as a bare path with
--print-python for shell pipelines.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional


REPO_ROOT = Path(__file__).resolve().parents[1]
VENV_DIR = REPO_ROOT / ".venv"
REQUIREMENTS = REPO_ROOT / "requirements.txt"
CHECK_SCRIPT = REPO_ROOT / "scripts" / "bootstrap_runtime.py"
SOURCE_REGISTRY = REPO_ROOT / "configs" / "source_registry.json"
SEARXNG_ENV_VARS = ("SEARXNG_BASE_URL", "SEARXNG_URL", "SEARXNG_ENDPOINT")

REQUIRED_IMPORTS = [
    {"module": "pptx", "package": "python-pptx"},
    {"module": "lxml.etree", "package": "lxml"},
]

OPTIONAL_SEARCH_MODULE_GROUPS = {
    "tavily": ["tavily"],
    "duckduckgo": ["ddgs", "duckduckgo_search"],
    "searxng": [],
}

PDF_EXTRACTION_MODULES = {
    "pdfplumber": "pdfplumber",
    "pypdf": "pypdf",
}
PDF_EXTRACTION_COMMANDS = ("pdftotext",)

PREFERRED_INTERPRETERS = [
    "python3.11",
    "python3.10",
    "python3.9",
    "python3.12",
    "python3",
    "python",
]


def log(message: str, quiet: bool = False) -> None:
    if not quiet:
        print(message, file=sys.stderr)


def run(cmd: list[str], *, quiet: bool = False) -> subprocess.CompletedProcess:
    if not quiet:
        print("+ " + " ".join(cmd), file=sys.stderr)
    return subprocess.run(cmd, text=True, capture_output=True)


def resolve_executable(command: str) -> Optional[str]:
    path = shutil.which(command)
    return path if path else None


def unique_paths(paths: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in paths:
        if not item:
            continue
        resolved = resolve_executable(item) if os.sep not in item else item
        if not resolved:
            continue
        try:
            key = str(Path(resolved).resolve())
        except OSError:
            key = resolved
        if key not in seen:
            seen.add(key)
            out.append(resolved)
    return out


def python_version_ok(python: str) -> bool:
    proc = run(
        [
            python,
            "-c",
            "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)",
        ],
        quiet=True,
    )
    return proc.returncode == 0


def _read_json(path: Path) -> dict[str, object]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


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


def _get_searxng_url() -> tuple[bool, str]:
    for env_var in SEARXNG_ENV_VARS:
        value = str(os.environ.get(env_var, "")).strip()
        if value:
            return True, value

    registry = _read_json(SOURCE_REGISTRY)
    connectors = registry.get("search_connectors", {}) if isinstance(registry, dict) else {}
    if isinstance(connectors, dict):
        searxng = connectors.get("searxng")
        if isinstance(searxng, dict):
            configured_url = str(searxng.get("default_url", "")).strip()
            if configured_url:
                return True, configured_url
    return False, ""


def get_search_provider_payload() -> dict[str, object]:
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


def get_pdf_extraction_payload() -> dict[str, object]:
    module_checks = {
        name: import_check(module_name)
        for name, module_name in PDF_EXTRACTION_MODULES.items()
    }
    command_checks = {
        name: {
            "command": name,
            "available": bool(shutil.which(name)),
            "path": shutil.which(name) or "",
        }
        for name in PDF_EXTRACTION_COMMANDS
    }
    has_pdf_extraction = any(item["available"] for item in module_checks.values()) or any(
        item["available"] for item in command_checks.values()
    )
    return {
        "pdf_extraction": {
            "modules": module_checks,
            "commands": command_checks,
        },
        "has_pdf_extraction": has_pdf_extraction,
    }


def dependency_payload() -> tuple[dict[str, object], list[str]]:
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
    pdf_payload = get_pdf_extraction_payload()
    has_search_provider = any(search_providers.values())
    is_ready_for_ppt_pipeline = not missing_required
    is_ready_for_e2e_research = is_ready_for_ppt_pipeline and has_search_provider and bool(pdf_payload["has_pdf_extraction"])

    payload = {
        "python": sys.executable,
        "python_version": sys.version.split()[0],
        "required": required_checks,
        "search_providers": search_providers,
        "search_provider_details": search_provider_details,
        **pdf_payload,
        "manual_source_mode_supported": True,
        "manual_source_mode_is_fallback": False,
        "paid_search_optional": True,
        "paid_search_available": paid_search_available,
        "is_ready_for_ppt_pipeline": is_ready_for_ppt_pipeline,
        "is_ready_for_e2e_research": is_ready_for_e2e_research,
        "has_search_provider": has_search_provider,
        "has_fallback_search": has_search_provider,
    }
    return payload, missing_required


def dependency_check_main() -> int:
    payload, missing_required = dependency_payload()
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if missing_required:
        print("ERROR: Required import(s) failed: " + ", ".join(missing_required), file=sys.stderr)
        for package_name in missing_required:
            result = payload.get("required", {}).get(package_name, {}) if isinstance(payload.get("required"), dict) else {}
            if isinstance(result, dict) and result.get("error"):
                print(f"  {package_name}: {result['error']}", file=sys.stderr)
        print("Run 'python3 scripts/bootstrap_runtime.py --force' or install requirements.txt in this Python environment.", file=sys.stderr)
        if sys.platform == "darwin" and sys.version_info >= (3, 13):
            print(
                "macOS note: Python 3.13+ can hit lxml wheel import/code-signing issues. "
                "Prefer python3 scripts/bootstrap_runtime.py --python python3.11 --force.",
                file=sys.stderr,
            )
        return 1

    e2e_blocked = False
    if not payload["has_search_provider"]:
        e2e_blocked = True
        print(
            "ERROR: No configured web-search provider is available for formal E2E research. "
            "Manual source intake remains available for user-provided URLs/files, but it is not a fallback "
            "for required public-search execution.",
            file=sys.stderr,
        )
        search_providers = payload.get("search_providers", {})
        if isinstance(search_providers, dict) and not search_providers.get("searxng"):
            print("Set SEARXNG_BASE_URL or source_registry search_connectors.searxng.default_url to enable formal search execution.", file=sys.stderr)
        else:
            print("SearXNG is configured; script search can proceed when runtime can reach it.", file=sys.stderr)
            print("Install tavily/duckduckgo packages only if paid/extra providers are required.", file=sys.stderr)

    if not payload["has_pdf_extraction"]:
        e2e_blocked = True
        print(
            "ERROR: No PDF extraction capability found. Install pdfplumber or pypdf, or provide pdftotext, "
            "before relying on public filings/prospectuses/annual reports in formal E2E research.",
            file=sys.stderr,
        )

    if e2e_blocked:
        return 1

    return 0


def runtime_check(python: str, require_search_provider: bool = True) -> tuple[bool, dict]:
    proc = run([python, str(CHECK_SCRIPT), "check"], quiet=True)
    payload: dict = {
        "python": python,
        "is_ready_for_ppt_pipeline": False,
        "is_ready_for_e2e_research": False,
        "has_search_provider": False,
        "error": "",
    }
    if proc.stdout.strip():
        try:
            payload.update(json.loads(proc.stdout))
        except json.JSONDecodeError:
            payload["raw_stdout"] = proc.stdout
    if proc.stderr.strip():
        payload["stderr"] = proc.stderr.strip()
    if require_search_provider:
        ok = bool(payload.get("is_ready_for_e2e_research"))
    else:
        ok = bool(payload.get("is_ready_for_ppt_pipeline"))
    return bool(ok), payload


def candidate_interpreters(explicit_python: Optional[str]) -> list[str]:
    candidates: list[str] = []
    if explicit_python:
        candidates.append(explicit_python)
    env_python = os.environ.get("PYTHON_BIN")
    if env_python:
        candidates.append(env_python)
    if VENV_DIR.joinpath("bin/python").exists():
        candidates.append(str(VENV_DIR / "bin/python"))
    candidates.extend(PREFERRED_INTERPRETERS)
    return unique_paths(candidates)


def choose_venv_builder(explicit_python: Optional[str], quiet: bool) -> str:
    for python in unique_paths(([explicit_python] if explicit_python else []) + PREFERRED_INTERPRETERS):
        if not python_version_ok(python):
            continue
        # Prefer <=3.12 for compiled dependency wheels, but allow newer as last
        # resort if no stable interpreter is available.
        proc = run(
            [
                python,
                "-c",
                "import sys; print('.'.join(map(str, sys.version_info[:2])))",
            ],
            quiet=True,
        )
        version = proc.stdout.strip()
        if version in {"3.9", "3.10", "3.11", "3.12"}:
            return python

    for python in unique_paths(([explicit_python] if explicit_python else []) + PREFERRED_INTERPRETERS):
        if python_version_ok(python):
            log(
                f"WARNING: using {python} to create .venv. Python 3.13/3.14 can be less stable with lxml on macOS.",
                quiet,
            )
            return python
    raise RuntimeError("No Python 3.9+ interpreter found.")


def create_or_update_venv(builder: str, force: bool, quiet: bool) -> None:
    if force and VENV_DIR.exists():
        log(f"Removing existing {VENV_DIR}", quiet)
        shutil.rmtree(VENV_DIR)
    if not VENV_DIR.exists():
        log(f"Creating .venv with {builder}", quiet)
        proc = run([builder, "-m", "venv", str(VENV_DIR)], quiet=quiet)
        if proc.returncode != 0:
            raise RuntimeError(
                "Failed to create .venv. Python may lack venv/ensurepip support.\n"
                f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
            )

    pip = str(VENV_DIR / "bin/pip")
    log("Installing runtime dependencies into .venv", quiet)
    for cmd in (
        [pip, "install", "--quiet", "--upgrade", "pip"],
        [pip, "install", "--quiet", "-r", str(REQUIREMENTS)],
    ):
        proc = run(cmd, quiet=quiet)
        if proc.returncode != 0:
            raise RuntimeError(f"Dependency install failed.\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}")


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "check":
        return dependency_check_main()

    parser = argparse.ArgumentParser(description="Bootstrap and select a Python runtime for this skill.")
    parser.add_argument("--python", help="Explicit Python interpreter to test first.")
    parser.add_argument("--force", action="store_true", help="Recreate .venv before installing dependencies.")
    parser.add_argument("--no-install", action="store_true", help="Only probe existing interpreters; do not create .venv.")
    parser.add_argument("--ppt-only", action="store_true", help="Only require PPT/runtime imports; skip fallback search-provider requirement for PPT-only debug runs.")
    parser.add_argument("--print-python", action="store_true", help="Print only the selected Python path.")
    parser.add_argument("--quiet", action="store_true", help="Suppress progress logs on stderr.")
    args = parser.parse_args()

    attempts: list[dict] = []

    for python in candidate_interpreters(args.python):
        if not python_version_ok(python):
            attempts.append({"python": python, "ok": False, "reason": "Python version must be >=3.9"})
            continue
        ok, payload = runtime_check(python, require_search_provider=not args.ppt_only)
        attempts.append({"python": python, "ok": ok, "check": payload})
        if ok:
            if args.print_python:
                print(payload.get("python") or python)
            else:
                print(json.dumps({"selected_python": payload.get("python") or python, "source": "existing", "check": payload}, ensure_ascii=False, indent=2))
            return 0

    if args.no_install:
        print(json.dumps({"selected_python": "", "source": "none", "attempts": attempts}, ensure_ascii=False, indent=2))
        return 1

    try:
        builder = choose_venv_builder(args.python, args.quiet)
        create_or_update_venv(builder, args.force, args.quiet)
        venv_python = str(VENV_DIR / "bin/python")
        ok, payload = runtime_check(venv_python, require_search_provider=not args.ppt_only)
        attempts.append({"python": venv_python, "ok": ok, "check": payload, "source": "created_venv"})
        if not ok:
            raise RuntimeError(
                "Created .venv but runtime imports still failed. "
                "On macOS with Python 3.13/3.14, rerun with PYTHON_BIN=python3.11, python3.10, or python3.9."
            )
        if args.print_python:
            print(payload.get("python") or venv_python)
        else:
            print(json.dumps({"selected_python": payload.get("python") or venv_python, "source": "venv", "check": payload}, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"selected_python": "", "source": "error", "error": str(exc), "attempts": attempts}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

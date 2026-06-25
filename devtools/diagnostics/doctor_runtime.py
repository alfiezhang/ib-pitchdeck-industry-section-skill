#!/usr/bin/env python3
"""Runtime and entrypoint doctor for the IB industry-section skill."""

from __future__ import annotations

import json
import platform
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_ROOT = REPO_ROOT / "runtime" / "ib-pitchdeck-agent-industry-section"
for path in (
    RUNTIME_ROOT / "scripts",
    RUNTIME_ROOT / "scripts" / "_lib",
    RUNTIME_ROOT / "scripts" / "qc",
):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import bootstrap_runtime


def script_exists(relative_path: str) -> bool:
    return (RUNTIME_ROOT / relative_path).exists()


def runtime_diagnostic_payload() -> dict[str, object]:
    python_version = sys.version_info
    required_checks: dict[str, object] = {}
    missing_required = []
    for item in bootstrap_runtime.REQUIRED_IMPORTS:
        result = bootstrap_runtime.import_check(item["module"])
        required_checks[item["package"]] = result
        if not result["available"]:
            missing_required.append(item["package"])

    provider_payload = bootstrap_runtime.get_search_provider_payload()
    search_provider_details = provider_payload["search_provider_details"]
    search_providers = provider_payload["search_providers"]
    paid_search_available = provider_payload["paid_search_available"]
    pdf_payload = bootstrap_runtime.get_pdf_extraction_payload()
    has_search_provider = any(search_providers.values())
    is_ready_for_ppt_pipeline = not missing_required
    is_ready_for_e2e_research = is_ready_for_ppt_pipeline and has_search_provider and bool(pdf_payload["has_pdf_extraction"])

    checks = {
        "python": sys.executable,
        "python_version": platform.python_version(),
        "python_version_ok": python_version >= (3, 9),
        "required_imports": required_checks,
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
        "required_entrypoints": {
            "bootstrap_runtime": script_exists("scripts/bootstrap_runtime.py"),
            "python_pipeline": script_exists("scripts/pipeline.py"),
            "status_dashboard": script_exists("scripts/pipeline.py"),
            "pipeline_validate": script_exists("scripts/pipeline.py"),
        },
        "nonexistent_entrypoints_do_not_use": [
            "scripts/stage_gate_ppt.py",
        ],
        "recommended_commands": [
            "python3 scripts/bootstrap_runtime.py --print-python",
            "\"$PYTHON_CMD\" scripts/pipeline.py next --run-dir <run>",
            "\"$PYTHON_CMD\" scripts/pipeline.py validate --artifact pre_ppt --run-dir <run>",
            "\"$PYTHON_CMD\" scripts/pipeline.py render --run-dir <run>",
        ],
        "rules": [
            "Do not edit skill source files during a user run.",
            "Do not bypass a failing pre-PPT gate for deliverable output.",
            "Use the current concrete attempt directory as the package of record; do not create a new attempt to escape a failed gate.",
            "Use --allow-ungated-debug only with IB_SKILL_ALLOW_UNGATED_DEBUG=1 and only for local diagnostics.",
            "Generate JSON through structured APIs such as json.dump, then parse it before validation.",
        ],
    }
    checks["is_valid"] = (
        checks["python_version_ok"]
        and checks["is_ready_for_e2e_research"]
        and all(checks["required_entrypoints"].values())
    )
    return checks


def main() -> None:
    checks = runtime_diagnostic_payload()
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    if not checks["is_valid"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

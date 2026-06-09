#!/usr/bin/env python3
"""Runtime and entrypoint doctor for the IB industry-section skill."""

from __future__ import annotations

import json
import platform
import sys
from pathlib import Path

from check_runtime_dependencies import OPTIONAL_SEARCH_MODULE_GROUPS, REQUIRED_IMPORTS, import_check


REPO_ROOT = Path(__file__).resolve().parents[1]


def script_exists(relative_path: str) -> bool:
    return (REPO_ROOT / relative_path).exists()


def main() -> None:
    python_version = sys.version_info
    required_checks = {}
    missing_required = []
    for item in REQUIRED_IMPORTS:
        result = import_check(item["module"])
        required_checks[item["package"]] = result
        if not result["available"]:
            missing_required.append(item["package"])

    search_provider_details = {}
    search_providers = {}
    for provider, module_names in OPTIONAL_SEARCH_MODULE_GROUPS.items():
        checks_for_provider = [import_check(name) for name in module_names]
        search_provider_details[provider] = checks_for_provider
        search_providers[provider] = any(item["available"] for item in checks_for_provider)

    checks = {
        "python": sys.executable,
        "python_version": platform.python_version(),
        "python_version_ok": python_version >= (3, 9),
        "required_imports": required_checks,
        "search_providers": search_providers,
        "search_provider_details": search_provider_details,
        "is_ready_for_ppt_pipeline": not missing_required,
        "has_fallback_search": any(search_providers.values()),
        "required_entrypoints": {
            "bootstrap_runtime": script_exists("scripts/bootstrap_runtime.py"),
            "python_pipeline": script_exists("scripts/pipeline.py"),
            "legacy_run_pipeline": script_exists("run_pipeline.sh"),
            "validate_stage_gate": script_exists("scripts/validate_stage_gate.py"),
            "validate_final_delivery": script_exists("scripts/validate_final_delivery.py"),
        },
        "nonexistent_entrypoints_do_not_use": [
            "scripts/stage_gate_ppt.py",
        ],
        "recommended_commands": [
            "python3 scripts/bootstrap_runtime.py --print-python",
            "\"$PYTHON_CMD\" scripts/pipeline.py status --run-dir <run>",
            "\"$PYTHON_CMD\" scripts/pipeline.py render --run-dir <run>",
            "\"$PYTHON_CMD\" scripts/pipeline.py finalize --run-dir <run> --require-client-ready",
            "scripts/validate_stage_gate.py --stage pre_ppt --run-dir <run>",
            "scripts/validate_final_delivery.py --run-dir <run>",
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
        and checks["is_ready_for_ppt_pipeline"]
        and checks["has_fallback_search"]
        and all(checks["required_entrypoints"].values())
    )
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    if not checks["is_valid"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

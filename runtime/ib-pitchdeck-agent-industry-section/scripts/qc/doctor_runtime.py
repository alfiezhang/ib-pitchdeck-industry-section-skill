#!/usr/bin/env python3
"""Runtime and entrypoint doctor for the IB industry-section skill."""

from __future__ import annotations

# Runtime scripts can be run directly. Shared helpers remain in runtime
# `scripts/`; production tools live under role scripts; validators live under QC.
import sys as _ib_sys
from pathlib import Path as _IbPath
_IB_ROLE_SCRIPT_DIR = _IbPath(__file__).resolve().parent
_IB_RUNTIME_ROOT = next(
    _p for _p in _IbPath(__file__).resolve().parents
    if (_p / 'configs').is_dir() and (_p / 'scripts').is_dir()
)
_IB_SHARED_SCRIPT_DIR = _IB_RUNTIME_ROOT / "scripts"
_IB_ROLE_SCRIPT_DIRS = sorted(_p for _p in (_IB_RUNTIME_ROOT / 'scripts').iterdir() if _p.is_dir())
_IB_QC_VALIDATOR_DIRS = sorted((_IB_RUNTIME_ROOT / 'scripts' / 'qc' / 'validators').glob('*'))
_IB_IMPORT_PATHS = [str(_IB_ROLE_SCRIPT_DIR)]
for _ib_dir in [*_IB_ROLE_SCRIPT_DIRS, *_IB_QC_VALIDATOR_DIRS]:
    _ib_text = str(_ib_dir)
    if _ib_text not in _IB_IMPORT_PATHS:
        _IB_IMPORT_PATHS.append(_ib_text)
_IB_IMPORT_PATHS.append(str(_IB_SHARED_SCRIPT_DIR))
for _ib_path in list(_IB_IMPORT_PATHS):
    if _ib_path in _ib_sys.path:
        _ib_sys.path.remove(_ib_path)
for _ib_path in reversed(_IB_IMPORT_PATHS):
    _ib_sys.path.insert(0, _ib_path)

import json
import platform
import sys
from pathlib import Path

import check_runtime_dependencies


REPO_ROOT = _IB_RUNTIME_ROOT


def script_exists(relative_path: str) -> bool:
    return (REPO_ROOT / relative_path).exists()


def runtime_diagnostic_payload() -> dict[str, object]:
    python_version = sys.version_info
    required_checks: dict[str, object] = {}
    missing_required = []
    for item in check_runtime_dependencies.REQUIRED_IMPORTS:
        result = check_runtime_dependencies.import_check(item["module"])
        required_checks[item["package"]] = result
        if not result["available"]:
            missing_required.append(item["package"])

    provider_payload = check_runtime_dependencies.get_search_provider_payload()
    search_provider_details = provider_payload["search_provider_details"]
    search_providers = provider_payload["search_providers"]
    paid_search_available = provider_payload["paid_search_available"]

    checks = {
        "python": sys.executable,
        "python_version": platform.python_version(),
        "python_version_ok": python_version >= (3, 9),
        "required_imports": required_checks,
        "search_providers": search_providers,
        "search_provider_details": search_provider_details,
        "manual_source_mode_supported": True,
        "paid_search_optional": True,
        "paid_search_available": paid_search_available,
        "is_ready_for_ppt_pipeline": not missing_required,
        "has_fallback_search": any(search_providers.values()),
        "required_entrypoints": {
            "bootstrap_runtime": script_exists("scripts/bootstrap_runtime.py"),
            "python_pipeline": script_exists("scripts/pipeline.py"),
            "legacy_run_pipeline": script_exists("run_pipeline.sh"),
            "validate_stage_gate": script_exists("scripts/qc/validators/final/validate_stage_gate.py"),
            "validate_final_delivery": script_exists("scripts/qc/validators/final/validate_final_delivery.py"),
        },
        "nonexistent_entrypoints_do_not_use": [
            "scripts/stage_gate_ppt.py",
        ],
        "recommended_commands": [
            "python3 scripts/bootstrap_runtime.py --print-python",
            "\"$PYTHON_CMD\" scripts/state_report.py next --run-dir <run>",
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
        and checks["is_ready_for_ppt_pipeline"]
        and checks["has_fallback_search"]
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

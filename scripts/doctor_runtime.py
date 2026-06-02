#!/usr/bin/env python3
"""Runtime and entrypoint doctor for the IB industry-section skill."""

from __future__ import annotations

import importlib.util
import json
import platform
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def script_exists(relative_path: str) -> bool:
    return (REPO_ROOT / relative_path).exists()


def main() -> None:
    python_version = sys.version_info
    checks = {
        "python": sys.executable,
        "python_version": platform.python_version(),
        "python_version_ok": python_version >= (3, 9),
        "python_pptx_available": module_available("pptx"),
        "lxml_available": module_available("lxml"),
        "required_entrypoints": {
            "bootstrap_runtime": script_exists("scripts/bootstrap_runtime.py"),
            "run_pipeline": script_exists("run_pipeline.sh"),
            "validate_stage_gate": script_exists("scripts/validate_stage_gate.py"),
            "convert_storyboard_to_ppt_copy": script_exists("scripts/convert_storyboard_to_ppt_copy.py"),
            "validate_final_delivery": script_exists("scripts/validate_final_delivery.py"),
        },
        "nonexistent_entrypoints_do_not_use": [
            "scripts/stage_gate_ppt.py",
            "scripts/convert_to_ppt_copy.py",
        ],
        "recommended_commands": [
            "python3 scripts/bootstrap_runtime.py --print-python",
            "./run_pipeline.sh --work-root <workspace> --case-name <case> --storyboard <run>/industry_storyboard.json",
            "scripts/validate_stage_gate.py --stage pre_ppt --run-dir <run>",
            "scripts/validate_final_delivery.py --run-dir <run>",
        ],
        "rules": [
            "Do not edit skill source files during a user run.",
            "Do not bypass a failing pre-PPT gate for deliverable output.",
            "Use --allow-ungated-debug only with IB_SKILL_ALLOW_UNGATED_DEBUG=1 and only for local diagnostics.",
            "Generate JSON through structured APIs such as json.dump, then parse it before validation.",
        ],
    }
    checks["is_valid"] = (
        checks["python_version_ok"]
        and checks["python_pptx_available"]
        and checks["lxml_available"]
        and all(checks["required_entrypoints"].values())
    )
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    if not checks["is_valid"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

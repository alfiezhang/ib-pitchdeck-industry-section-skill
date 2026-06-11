"""Contract tests: Group 2 - issue analysis fixture validation."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parents[1] / "runtime" / "ib-pitchdeck-agent-industry-section"
SCRIPT_DIR = SKILL_DIR / "scripts"
FIXTURES_DIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures"


def _run(args: list[str]) -> subprocess.CompletedProcess:
    env = {**__import__("os").environ, "PYTHONPATH": str(SCRIPT_DIR)}
    return subprocess.run(args, text=True, capture_output=True, cwd=str(SKILL_DIR), env=env)


class TestIssueAnalysisValidation:
    def test_valid_issue_analysis_passes(self):
        result = _run([
            sys.executable, "scripts/validate_issue_analysis.py",
            "--issue-analysis", str(FIXTURES_DIR / "valid_issue_analysis.json"),
        ])
        assert result.returncode == 0, result.stdout + result.stderr

    def test_invalid_issue_analysis_fails(self):
        result = _run([
            sys.executable, "scripts/validate_issue_analysis.py",
            "--issue-analysis", str(FIXTURES_DIR / "invalid_issue_analysis.json"),
        ])
        assert result.returncode != 0, "invalid_issue_analysis.json should fail validation"

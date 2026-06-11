"""Contract tests: Group 13 - banker review report skeleton."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parents[1] / "runtime" / "ib-industry-section-skill"
SCRIPT_DIR = SKILL_DIR / "scripts"


def _run(args: list[str]) -> subprocess.CompletedProcess:
    env = {**__import__("os").environ, "PYTHONPATH": str(SCRIPT_DIR)}
    return subprocess.run(args, text=True, capture_output=True, cwd=str(SKILL_DIR), env=env)


class TestBankerReviewReport:
    def test_build_skeleton(self, deck_blueprint_path, compiled_artifacts, tmp_path):
        result = _run([
            sys.executable, "scripts/build_banker_review_report_skeleton.py",
            "--deck-blueprint", str(deck_blueprint_path),
            "--page-contract", str(compiled_artifacts["page_evidence_contract"]),
            "--renderer-spec", str(compiled_artifacts["renderer_spec"]),
            "--output", str(tmp_path / "banker_review_report.json"),
        ])
        assert result.returncode == 0, result.stdout + result.stderr
        report = json.loads((tmp_path / "banker_review_report.json").read_text(encoding="utf-8"))
        assert report["schema_version"] == "banker_review_report_skeleton_v1", report
        assert len(report["slide_reviews"]) == 8, report
        assert report["slide_reviews"][0]["repair_target"] == "deck_blueprint.json"
        assert report["slide_reviews"][0]["review_status"] == "pending_llm_banker_review"

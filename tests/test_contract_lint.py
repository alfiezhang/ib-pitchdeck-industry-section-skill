"""Contract tests: Group 1 - pre-flight lint checks (compileall, JSON, manifest, registries)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = REPO_ROOT / "runtime" / "ib-pitchdeck-agent-industry-section"
SCRIPT_DIR = SKILL_DIR / "scripts"
DEVTOOLS_CHECKS = REPO_ROOT / "devtools" / "checks"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from pipeline import build_template_token_report  # noqa: E402


def _run(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    env = {**__import__("os").environ, "PYTHONPATH": str(SCRIPT_DIR)}
    return subprocess.run(args, text=True, capture_output=True, cwd=str(SKILL_DIR), env=env, **kwargs)


class TestCompileAll:
    def test_scripts_compile(self):
        result = _run([sys.executable, "-m", "compileall", "-q", "scripts"])
        assert result.returncode == 0, result.stderr

    def test_references_compile(self):
        result = _run([sys.executable, "-m", "compileall", "-q", "references"])
        assert result.returncode == 0, result.stderr


class TestJsonLint:
    def test_check_json_files(self):
        result = _run([sys.executable, str(DEVTOOLS_CHECKS / "check_json_files.py"), "--root", "."])
        assert result.returncode == 0, result.stdout + result.stderr

    def test_check_artifact_manifest(self):
        result = _run([sys.executable, str(DEVTOOLS_CHECKS / "check_artifact_manifest.py")])
        assert result.returncode == 0, result.stdout + result.stderr

    def test_check_slide_registry(self):
        result = _run([sys.executable, str(DEVTOOLS_CHECKS / "check_slide_registry.py")])
        assert result.returncode == 0, result.stdout + result.stderr

    def test_check_registry_coverage(self):
        result = _run([sys.executable, str(DEVTOOLS_CHECKS / "check_registry_coverage.py")])
        assert result.returncode == 0, result.stdout + result.stderr


class TestTemplateTokenCheck:
    def test_template_tokens_match_ppt_mapping(self):
        output = build_template_token_report(
            SKILL_DIR / "assets/industry_section_template_master.pptx",
            SKILL_DIR / "configs/ppt_mapping.json",
        )
        assert output["summary"]["is_consistent"] is True, output

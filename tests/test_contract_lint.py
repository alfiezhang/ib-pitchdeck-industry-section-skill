"""Contract tests: Group 1 - pre-flight lint checks (compileall, JSON, manifest, registries)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parents[1] / "runtime" / "ib-pitchdeck-agent-industry-section"
SCRIPT_DIR = SKILL_DIR / "scripts"


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
        result = _run([sys.executable, "scripts/check_json_files.py", "--root", "."])
        assert result.returncode == 0, result.stdout + result.stderr

    def test_check_artifact_manifest(self):
        result = _run([sys.executable, "scripts/check_artifact_manifest.py"])
        assert result.returncode == 0, result.stdout + result.stderr

    def test_check_slide_registry(self):
        result = _run([sys.executable, "scripts/check_slide_registry.py"])
        assert result.returncode == 0, result.stdout + result.stderr

    def test_check_registry_coverage(self):
        result = _run([sys.executable, "scripts/check_registry_coverage.py"])
        assert result.returncode == 0, result.stdout + result.stderr


class TestTemplateTokenCheck:
    def test_template_tokens_match_ppt_mapping(self, tmp_path):
        result = _run([
            sys.executable, "scripts/check_template_tokens.py",
            "--template", "assets/industry_section_template_master.pptx",
            "--ppt-mapping", "templates/ppt_mapping.json",
            "--fail-on-diff",
            "--output", str(tmp_path / "template_token_check.json"),
        ])
        assert result.returncode == 0, result.stdout + result.stderr
        output = json.loads((tmp_path / "template_token_check.json").read_text(encoding="utf-8"))
        assert output.get("mismatched_tokens", []) == [], output

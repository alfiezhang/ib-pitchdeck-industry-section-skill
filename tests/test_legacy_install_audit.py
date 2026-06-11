#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "runtime" / "ib-pitchdeck-agent-industry-section" / "scripts"
RUNTIME_DIR = SCRIPT_DIR.parent


def _run(script: str, args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT_DIR / script), *args],
        cwd=str(RUNTIME_DIR),
        text=True,
        capture_output=True,
        env={**os.environ, "PYTHONPATH": str(SCRIPT_DIR)},
    )


def test_audit_legacy_installs_reports_found_legacy_skills(tmp_path: Path) -> None:
    skill_root = tmp_path / "skills"
    legacy = skill_root / "ib-industry-section-skill"
    legacy.mkdir(parents=True)
    (legacy / "SKILL.md").write_text("# legacy skill\n", encoding="utf-8")
    output = tmp_path / "legacy_install_audit.json"

    result = _run("audit_legacy_installs.py", ["--skill-root", str(skill_root), "--output", str(output)])

    assert result.returncode == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "legacy_install_audit_v1"
    assert payload["legacy_installs_found"] is True
    assert payload["legacy_install_count"] == 1
    found = [item for item in payload["entries"] if item["legacy_install"]]
    assert found[0]["skill_name"] == "ib-industry-section-skill"
    assert "SKILL.md" in found[0]["marker_files"]


def test_remove_legacy_installs_defaults_to_dry_run(tmp_path: Path) -> None:
    skill_root = tmp_path / "skills"
    legacy = skill_root / "fill-ppt"
    legacy.mkdir(parents=True)
    (legacy / "SKILL.md").write_text("# legacy fill ppt\n", encoding="utf-8")

    result = _run("remove_legacy_installs.py", ["--skill-root", str(skill_root)])

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["dry_run"] is True
    assert payload["candidate_count"] == 1
    assert payload["removed_count"] == 0
    assert legacy.exists()


def test_remove_legacy_installs_requires_explicit_confirmation_to_delete(tmp_path: Path) -> None:
    skill_root = tmp_path / "skills"
    legacy = skill_root / "research-pack"
    legacy.mkdir(parents=True)
    (legacy / "SKILL.md").write_text("# legacy research pack\n", encoding="utf-8")

    result = _run(
        "remove_legacy_installs.py",
        [
            "--skill-root",
            str(skill_root),
            "--execute",
            "--confirm",
            "REMOVE_LEGACY_INSTALLS",
        ],
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["dry_run"] is False
    assert payload["confirmed"] is True
    assert payload["removed_count"] == 1
    assert not legacy.exists()

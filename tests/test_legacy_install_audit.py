#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = REPO_ROOT / "runtime" / "ib-pitchdeck-agent-industry-section"
DEVTOOLS_INSTALL = REPO_ROOT / "devtools" / "install"
DEVTOOLS_DIAGNOSTICS = REPO_ROOT / "devtools" / "diagnostics"


def _run(script: str, args: list[str]) -> subprocess.CompletedProcess:
    script_path = (DEVTOOLS_DIAGNOSTICS / script) if (DEVTOOLS_DIAGNOSTICS / script).exists() else (DEVTOOLS_INSTALL / script)
    return subprocess.run(
        [sys.executable, str(script_path), *args],
        cwd=str(RUNTIME_DIR),
        text=True,
        capture_output=True,
        env={**os.environ, "PYTHONPATH": os.pathsep.join([str(DEVTOOLS_INSTALL), str(DEVTOOLS_DIAGNOSTICS)])},
    )


def test_audit_legacy_installs_reports_found_legacy_skills(tmp_path: Path) -> None:
    skill_root = tmp_path / "skills"
    legacy = skill_root / "ib-industry-section-skill"
    legacy.mkdir(parents=True)
    (legacy / "SKILL.md").write_text("# legacy skill\n", encoding="utf-8")
    output = tmp_path / "legacy_install_audit.json"

    empty_plugin_root = tmp_path / "plugins"
    result = _run(
        "audit_legacy_installs.py",
        ["--skill-root", str(skill_root), "--plugin-root", str(empty_plugin_root), "--output", str(output)],
    )

    assert result.returncode == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "legacy_install_audit_v1"
    assert payload["legacy_installs_found"] is True
    assert payload["legacy_install_count"] == 1
    found = [item for item in payload["entries"] if item["legacy_install"]]
    assert found[0]["skill_name"] == "ib-industry-section-skill"
    assert "SKILL.md" in found[0]["marker_files"]


def test_audit_legacy_installs_reports_stale_current_skill(tmp_path: Path) -> None:
    skill_root = tmp_path / "skills"
    current = skill_root / "ib-pitchdeck-agent-industry-section"
    current.mkdir(parents=True)
    (current / "SKILL.md").write_text(
        "Use scripts/pipeline.py gate and scripts/pipeline.py validate.",
        encoding="utf-8",
    )
    output = tmp_path / "legacy_install_audit.json"
    empty_plugin_root = tmp_path / "plugins"

    result = _run(
        "audit_legacy_installs.py",
        ["--skill-root", str(skill_root), "--plugin-root", str(empty_plugin_root), "--output", str(output)],
    )

    assert result.returncode == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["legacy_installs_found"] is True
    stale = [item for item in payload["current_skill_entries"] if item["stale_install"]]
    assert stale[0]["skill_name"] == "ib-pitchdeck-agent-industry-section"
    assert "scripts/pipeline.py gate" in stale[0]["stale_markers"]


def test_audit_legacy_installs_reports_personal_plugin_cache(tmp_path: Path) -> None:
    skill_root = tmp_path / "skills"
    plugin_root = tmp_path / "plugins" / "cache" / "personal"
    cached = plugin_root / "ib-pitchdeck-agent-industry-section"
    cached.mkdir(parents=True)
    (cached / "0.1.0" / "skills").mkdir(parents=True)
    output = tmp_path / "legacy_install_audit.json"

    result = _run(
        "audit_legacy_installs.py",
        ["--skill-root", str(skill_root), "--plugin-root", str(plugin_root), "--output", str(output)],
    )

    assert result.returncode == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["legacy_installs_found"] is True
    found = [item for item in payload["plugin_entries"] if item["legacy_install"]]
    assert found[0]["plugin_root"] == str(plugin_root)
    assert found[0]["plugin_name"] == "ib-pitchdeck-agent-industry-section"


def test_remove_legacy_installs_defaults_to_dry_run(tmp_path: Path) -> None:
    skill_root = tmp_path / "skills"
    plugin_root = tmp_path / "plugins"
    legacy = skill_root / "fill-ppt"
    legacy.mkdir(parents=True)
    (legacy / "SKILL.md").write_text("# legacy fill ppt\n", encoding="utf-8")

    result = _run("remove_legacy_installs.py", ["--skill-root", str(skill_root), "--plugin-root", str(plugin_root)])

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["dry_run"] is True
    assert payload["candidate_count"] == 1
    assert payload["removed_count"] == 0
    assert legacy.exists()


def test_remove_legacy_installs_requires_explicit_confirmation_to_delete(tmp_path: Path) -> None:
    skill_root = tmp_path / "skills"
    plugin_root = tmp_path / "plugins"
    legacy = skill_root / "research-pack"
    legacy.mkdir(parents=True)
    (legacy / "SKILL.md").write_text("# legacy research pack\n", encoding="utf-8")

    result = _run(
        "remove_legacy_installs.py",
        [
            "--skill-root",
            str(skill_root),
            "--plugin-root",
            str(plugin_root),
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


def test_remove_legacy_installs_can_remove_plugin_cache_with_confirmation(tmp_path: Path) -> None:
    skill_root = tmp_path / "skills"
    plugin_root = tmp_path / "plugins" / "cache" / "personal"
    cached = plugin_root / "ib-pitchdeck-agent-industry-section"
    cached.mkdir(parents=True)
    (cached / "0.1.0").mkdir()

    result = _run(
        "remove_legacy_installs.py",
        [
            "--skill-root",
            str(skill_root),
            "--plugin-root",
            str(plugin_root),
            "--execute",
            "--confirm",
            "REMOVE_LEGACY_INSTALLS",
        ],
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["dry_run"] is False
    assert payload["removed_count"] == 1
    assert not cached.exists()

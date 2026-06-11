#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import subprocess
import sys
import zipfile
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


def test_validate_plugin_package_blocks_dirty_runtime_cache_files() -> None:
    result = _run("validate_plugin_package.py", ["--package", str(RUNTIME_DIR)])

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["is_valid"] is False
    assert any("__pycache__" in item or ".DS_Store" in item for item in payload["errors"] + payload["warnings"])


def test_package_plugin_builds_clean_zip_and_validator_accepts_it(tmp_path: Path) -> None:
    output = tmp_path / "ib-pitchdeck-agent-industry-section.zip"

    build = _run("package_plugin.py", ["--source-dir", str(RUNTIME_DIR), "--output", str(output)])

    assert build.returncode == 0, build.stderr or build.stdout
    build_payload = json.loads(build.stdout)
    assert build_payload["is_valid"] is True
    assert output.exists()

    validation = _run("validate_plugin_package.py", ["--package", str(output)])
    assert validation.returncode == 0, validation.stderr or validation.stdout
    validation_payload = json.loads(validation.stdout)
    assert validation_payload["is_valid"] is True

    with zipfile.ZipFile(output, "r") as zf:
        names = zf.namelist()
    assert "ib-pitchdeck-agent-industry-section/.codex-plugin/plugin.json" in names
    assert "ib-pitchdeck-agent-industry-section/.claude-plugin/plugin.json" in names
    assert "ib-pitchdeck-agent-industry-section/.codebuddy-plugin/plugin.json" in names
    assert not any("/docs/" in f"/{name}/" or "/tests/" in f"/{name}/" for name in names)
    assert not any("__pycache__" in name or name.endswith(".pyc") or name.endswith(".DS_Store") for name in names)


def test_install_plugin_local_installs_clean_zip_to_target_root(tmp_path: Path) -> None:
    package = tmp_path / "package.zip"
    target_root = tmp_path / "codex_plugins"
    build = _run("package_plugin.py", ["--source-dir", str(RUNTIME_DIR), "--output", str(package)])
    assert build.returncode == 0, build.stdout

    install = _run(
        "install_plugin_local.py",
        [
            "--source",
            str(package),
            "--host",
            "codex",
            "--target-root",
            str(target_root),
        ],
    )

    assert install.returncode == 0, install.stderr or install.stdout
    payload = json.loads(install.stdout)
    assert payload["installed"] is True
    installed = target_root / "ib-pitchdeck-agent-industry-section"
    assert (installed / ".codex-plugin" / "plugin.json").exists()
    assert (installed / "agents" / "ib-pitchdeck-agent-industry-section.md").exists()
    assert not any("__pycache__" in str(path) or path.name == ".DS_Store" for path in installed.rglob("*"))

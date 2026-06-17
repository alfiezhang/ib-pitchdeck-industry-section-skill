#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = REPO_ROOT / "runtime" / "ib-pitchdeck-agent-industry-section"
SCRIPT_DIR = RUNTIME_DIR / "scripts"
DEVTOOLS_PACKAGE = REPO_ROOT / "devtools" / "package"
DEVTOOLS_INSTALL = REPO_ROOT / "devtools" / "install"


def _script_path(script: str) -> Path:
    for candidate in (DEVTOOLS_PACKAGE / script, DEVTOOLS_INSTALL / script, SCRIPT_DIR / script):
        if candidate.exists():
            return candidate
    return DEVTOOLS_PACKAGE / script


def _run(script: str, args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_script_path(script)), *args],
        cwd=str(RUNTIME_DIR),
        text=True,
        capture_output=True,
        env={**os.environ, "PYTHONPATH": os.pathsep.join([str(SCRIPT_DIR), str(DEVTOOLS_PACKAGE), str(DEVTOOLS_INSTALL)])},
    )


def test_validate_skill_package_accepts_clean_runtime(tmp_path: Path) -> None:
    clean = tmp_path / "runtime-clean"
    shutil.copytree(RUNTIME_DIR, clean, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"))
    result = _run("validate_skill_package.py", ["--package", str(clean)])

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["is_valid"] is True


def test_validate_skill_package_blocks_dirty_runtime_cache_files(tmp_path: Path) -> None:
    dirty = tmp_path / "dirty"
    shutil.copytree(RUNTIME_DIR, dirty, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    cache_dir = dirty / "scripts" / "__pycache__"
    cache_dir.mkdir()
    (cache_dir / "x.pyc").write_bytes(b"bad")
    (dirty / ".DS_Store").write_text("bad", encoding="utf-8")

    result = _run("validate_skill_package.py", ["--package", str(dirty)])

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["is_valid"] is False
    assert any("__pycache__" in item or ".DS_Store" in item for item in payload["errors"] + payload["warnings"])


def test_package_skill_builds_clean_zip_and_validator_accepts_it(tmp_path: Path) -> None:
    output = tmp_path / "ib-pitchdeck-agent-industry-section.zip"

    build = _run("package_skill.py", ["--source-dir", str(RUNTIME_DIR), "--output", str(output)])

    assert build.returncode == 0, build.stderr or build.stdout
    build_payload = json.loads(build.stdout)
    assert build_payload["is_valid"] is True
    assert output.exists()

    validation = _run("validate_skill_package.py", ["--package", str(output)])
    assert validation.returncode == 0, validation.stderr or validation.stdout
    validation_payload = json.loads(validation.stdout)
    assert validation_payload["is_valid"] is True

    with zipfile.ZipFile(output, "r") as zf:
        names = zf.namelist()
    assert "ib-pitchdeck-agent-industry-section/SKILL.md" in names
    assert "ib-pitchdeck-agent-industry-section/references/material-intake.md" in names
    assert not any("/.codex-plugin/" in f"/{name}" or "/.claude-plugin/" in f"/{name}" or "/.codebuddy-plugin/" in f"/{name}" for name in names)
    assert not any("/agents/" in f"/{name}/" or "/skills/" in f"/{name}/" for name in names)
    assert not any("/docs/" in f"/{name}/" or "/tests/" in f"/{name}/" for name in names)
    assert not any("/repository/" in f"/{name}/" for name in names)
    assert not any("__pycache__" in name or name.endswith(".pyc") or name.endswith(".DS_Store") for name in names)


def test_install_skill_local_installs_clean_zip_to_target_root(tmp_path: Path) -> None:
    package = tmp_path / "package.zip"
    target_root = tmp_path / "codex_skills"
    build = _run("package_skill.py", ["--source-dir", str(RUNTIME_DIR), "--output", str(package)])
    assert build.returncode == 0, build.stdout

    install = _run(
        "install_skill_local.py",
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
    assert (installed / "SKILL.md").exists()
    assert (installed / "references" / "generation.md").exists()
    assert not (installed / ".codex-plugin").exists()
    assert not (installed / "agents").exists()
    assert not (installed / "skills").exists()
    assert not any("__pycache__" in str(path) or path.name == ".DS_Store" for path in installed.rglob("*"))


def test_validate_skill_package_rejects_unsafe_zip_paths(tmp_path: Path) -> None:
    package = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(package, "w") as zf:
        zf.writestr("ib-pitchdeck-agent-industry-section/SKILL.md", "---\nname: x\ndescription: x\n---\n")
        zf.writestr("ib-pitchdeck-agent-industry-section/scripts/run.py", "print('x')")
        zf.writestr("ib-pitchdeck-agent-industry-section/configs/t.json", "{}")
        zf.writestr("ib-pitchdeck-agent-industry-section/assets/.keep", "")
        zf.writestr("ib-pitchdeck-agent-industry-section/references/r.md", "ref")
        zf.writestr("ib-pitchdeck-agent-industry-section/requirements.txt", "")
        zf.writestr("ib-pitchdeck-agent-industry-section/setup.sh", "echo setup")
        zf.writestr("ib-pitchdeck-agent-industry-section/run_pipeline.sh", "echo run")
        zf.writestr("ib-pitchdeck-agent-industry-section/../escape.txt", "bad")

    validation = _run("validate_skill_package.py", ["--package", str(package)])

    assert validation.returncode == 1
    payload = json.loads(validation.stdout)
    assert any("unsafe path" in item for item in payload["errors"])

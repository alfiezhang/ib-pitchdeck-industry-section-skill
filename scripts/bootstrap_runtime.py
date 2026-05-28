#!/usr/bin/env python3
"""Select or create a Python runtime for this skill.

Decision tree:
1. If an explicit/current Python can import required deps, use it.
2. If the project .venv can import required deps, use it.
3. If another local Python can import required deps, use it.
4. Otherwise create/update .venv, install requirements.txt, validate imports.

The selected interpreter is printed as JSON by default, or as a bare path with
--print-python for shell pipelines.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional


REPO_ROOT = Path(__file__).resolve().parents[1]
VENV_DIR = REPO_ROOT / ".venv"
REQUIREMENTS = REPO_ROOT / "requirements.txt"
CHECK_SCRIPT = REPO_ROOT / "scripts" / "check_runtime_dependencies.py"

PREFERRED_INTERPRETERS = [
    "python3.11",
    "python3.10",
    "python3.9",
    "python3.12",
    "python3",
    "python",
]


def log(message: str, quiet: bool = False) -> None:
    if not quiet:
        print(message, file=sys.stderr)


def run(cmd: list[str], *, quiet: bool = False) -> subprocess.CompletedProcess:
    if not quiet:
        print("+ " + " ".join(cmd), file=sys.stderr)
    return subprocess.run(cmd, text=True, capture_output=True)


def resolve_executable(command: str) -> Optional[str]:
    path = shutil.which(command)
    return path if path else None


def unique_paths(paths: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in paths:
        if not item:
            continue
        resolved = resolve_executable(item) if os.sep not in item else item
        if not resolved:
            continue
        try:
            key = str(Path(resolved).resolve())
        except OSError:
            key = resolved
        if key not in seen:
            seen.add(key)
            out.append(resolved)
    return out


def python_version_ok(python: str) -> bool:
    proc = run(
        [
            python,
            "-c",
            "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)",
        ],
        quiet=True,
    )
    return proc.returncode == 0


def runtime_check(python: str) -> tuple[bool, dict]:
    proc = run([python, str(CHECK_SCRIPT)], quiet=True)
    payload: dict = {
        "python": python,
        "is_ready_for_ppt_pipeline": False,
        "has_fallback_search": False,
        "error": "",
    }
    if proc.stdout.strip():
        try:
            payload.update(json.loads(proc.stdout))
        except json.JSONDecodeError:
            payload["raw_stdout"] = proc.stdout
    if proc.stderr.strip():
        payload["stderr"] = proc.stderr.strip()
    ok = proc.returncode == 0 and payload.get("is_ready_for_ppt_pipeline") and payload.get("has_fallback_search")
    return bool(ok), payload


def candidate_interpreters(explicit_python: Optional[str]) -> list[str]:
    candidates: list[str] = []
    if explicit_python:
        candidates.append(explicit_python)
    env_python = os.environ.get("PYTHON_BIN")
    if env_python:
        candidates.append(env_python)
    if VENV_DIR.joinpath("bin/python").exists():
        candidates.append(str(VENV_DIR / "bin/python"))
    candidates.extend(PREFERRED_INTERPRETERS)
    return unique_paths(candidates)


def choose_venv_builder(explicit_python: Optional[str], quiet: bool) -> str:
    for python in unique_paths(([explicit_python] if explicit_python else []) + PREFERRED_INTERPRETERS):
        if not python_version_ok(python):
            continue
        # Prefer <=3.12 for compiled dependency wheels, but allow newer as last
        # resort if no stable interpreter is available.
        proc = run(
            [
                python,
                "-c",
                "import sys; print('.'.join(map(str, sys.version_info[:2])))",
            ],
            quiet=True,
        )
        version = proc.stdout.strip()
        if version in {"3.9", "3.10", "3.11", "3.12"}:
            return python

    for python in unique_paths(([explicit_python] if explicit_python else []) + PREFERRED_INTERPRETERS):
        if python_version_ok(python):
            log(
                f"WARNING: using {python} to create .venv. Python 3.13/3.14 can be less stable with lxml on macOS.",
                quiet,
            )
            return python
    raise RuntimeError("No Python 3.9+ interpreter found.")


def create_or_update_venv(builder: str, force: bool, quiet: bool) -> None:
    if force and VENV_DIR.exists():
        log(f"Removing existing {VENV_DIR}", quiet)
        shutil.rmtree(VENV_DIR)
    if not VENV_DIR.exists():
        log(f"Creating .venv with {builder}", quiet)
        proc = run([builder, "-m", "venv", str(VENV_DIR)], quiet=quiet)
        if proc.returncode != 0:
            raise RuntimeError(
                "Failed to create .venv. Python may lack venv/ensurepip support.\n"
                f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
            )

    pip = str(VENV_DIR / "bin/pip")
    log("Installing runtime dependencies into .venv", quiet)
    for cmd in (
        [pip, "install", "--quiet", "--upgrade", "pip"],
        [pip, "install", "--quiet", "-r", str(REQUIREMENTS)],
    ):
        proc = run(cmd, quiet=quiet)
        if proc.returncode != 0:
            raise RuntimeError(f"Dependency install failed.\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap and select a Python runtime for this skill.")
    parser.add_argument("--python", help="Explicit Python interpreter to test first.")
    parser.add_argument("--force", action="store_true", help="Recreate .venv before installing dependencies.")
    parser.add_argument("--no-install", action="store_true", help="Only probe existing interpreters; do not create .venv.")
    parser.add_argument("--print-python", action="store_true", help="Print only the selected Python path.")
    parser.add_argument("--quiet", action="store_true", help="Suppress progress logs on stderr.")
    args = parser.parse_args()

    attempts: list[dict] = []

    for python in candidate_interpreters(args.python):
        if not python_version_ok(python):
            attempts.append({"python": python, "ok": False, "reason": "Python version must be >=3.9"})
            continue
        ok, payload = runtime_check(python)
        attempts.append({"python": python, "ok": ok, "check": payload})
        if ok:
            if args.print_python:
                print(payload.get("python") or python)
            else:
                print(json.dumps({"selected_python": payload.get("python") or python, "source": "existing", "check": payload}, ensure_ascii=False, indent=2))
            return 0

    if args.no_install:
        print(json.dumps({"selected_python": "", "source": "none", "attempts": attempts}, ensure_ascii=False, indent=2))
        return 1

    try:
        builder = choose_venv_builder(args.python, args.quiet)
        create_or_update_venv(builder, args.force, args.quiet)
        venv_python = str(VENV_DIR / "bin/python")
        ok, payload = runtime_check(venv_python)
        attempts.append({"python": venv_python, "ok": ok, "check": payload, "source": "created_venv"})
        if not ok:
            raise RuntimeError(
                "Created .venv but runtime imports still failed. "
                "On macOS with Python 3.13/3.14, rerun with PYTHON_BIN=python3.11, python3.10, or python3.9."
            )
        if args.print_python:
            print(payload.get("python") or venv_python)
        else:
            print(json.dumps({"selected_python": payload.get("python") or venv_python, "source": "venv", "check": payload}, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"selected_python": "", "source": "error", "error": str(exc), "attempts": attempts}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Shared pytest configuration and fixtures for ib-industry-section-skill tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "runtime" / "ib-industry-section-skill" / "scripts"
FIXTURES_DIR = ROOT / "tests" / "fixtures"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


@pytest.fixture
def root_dir() -> Path:
    return ROOT


@pytest.fixture
def script_dir() -> Path:
    return SCRIPT_DIR


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def write_json():
    return _write_json

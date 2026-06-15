#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "runtime" / "ib-pitchdeck-agent-industry-section" / "scripts"
RUNTIME_DIR = SCRIPT_DIR.parent
ROLE_SCRIPT_DIRS = sorted(path for path in SCRIPT_DIR.iterdir() if path.is_dir())
QC_VALIDATOR_DIRS = sorted((SCRIPT_DIR / "qc" / "validators").glob("*"))
SCRIPT_IMPORT_DIRS = [SCRIPT_DIR, *ROLE_SCRIPT_DIRS, *QC_VALIDATOR_DIRS]


def _script_path(script: str) -> Path:
    root_path = SCRIPT_DIR / script
    if root_path.exists():
        return root_path
    matches = [role_dir / script for role_dir in [*ROLE_SCRIPT_DIRS, *QC_VALIDATOR_DIRS] if (role_dir / script).exists()]
    return matches[0] if matches else root_path


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _run(script: str, args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_script_path(script)), *args],
        cwd=str(RUNTIME_DIR),
        text=True,
        capture_output=True,
        env={**os.environ, "PYTHONPATH": os.pathsep.join(str(path) for path in SCRIPT_IMPORT_DIRS)},
    )


def _assert_qc_issue_shape(issue: dict) -> None:
    required = {
        "issue_id",
        "severity",
        "layer",
        "artifact",
        "field_path",
        "message",
        "why_it_matters",
        "repair_owner",
        "repair_action",
        "rerun_command",
        "downstream_blocked",
    }
    assert required <= set(issue), issue


def test_qc_normalize_report_maps_legacy_errors_to_repair_schema(tmp_path: Path) -> None:
    report = tmp_path / "legacy_validation.json"
    output = tmp_path / "normalized.json"
    _write_json(
        report,
        {
            "is_valid": False,
            "errors": ["renderer_spec.json missing source_note"],
        },
    )

    result = _run(
        "qc_normalize_report.py",
        [
            "--report",
            str(report),
            "--layer",
            "generation",
            "--artifact",
            "renderer_spec.json",
            "--rerun-command",
            "$PYTHON_CMD scripts/qc/validators/generation/validate_renderer_spec.py ...",
            "--output",
            str(output),
        ],
    )

    assert result.returncode == 1
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "qc_repair_report_v1"
    assert payload["is_valid"] is False
    assert payload["blocking_issue_count"] == 1
    issue = payload["issues"][0]
    _assert_qc_issue_shape(issue)
    assert issue["layer"] == "generation"
    assert issue["artifact"] == "renderer_spec.json"
    assert "source_note" in issue["message"]


def test_qc_normalize_report_preserves_repair_targets(tmp_path: Path) -> None:
    report = tmp_path / "validation_with_repair_targets.json"
    _write_json(
        report,
        {
            "is_valid": False,
            "repair_targets": [
                {
                    "severity": "blocking",
                    "repair_target_layer": "template",
                    "repair_target_artifact": "artifacts/template_fit_validation.json",
                    "field_path": "capacity_conflicts[0]",
                    "message": "template_capacity_conflict",
                    "why_it_matters": "Content cannot be rendered without layout overflow.",
                    "repair_action": "Return to Generation and compress copy.",
                    "rerun_command": "$PYTHON_CMD scripts/template/template_fit.py ...",
                    "downstream_blocked": True,
                }
            ],
        },
    )

    result = _run("qc_normalize_report.py", ["--report", str(report), "--layer", "qc", "--artifact", "artifacts/template_fit_validation.json"])

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    issue = payload["issues"][0]
    _assert_qc_issue_shape(issue)
    assert issue["field_path"] == "capacity_conflicts[0]"
    assert issue["repair_owner"] == "template"
    assert issue["repair_action"] == "Return to Generation and compress copy."


def test_qc_normalize_report_routes_warnings_to_owner_with_disposition(tmp_path: Path) -> None:
    report = tmp_path / "validation_with_warning.json"
    _write_json(
        report,
        {
            "is_valid": True,
            "warnings": ["weak-source marker: SRC-001 is reposted and method is unclear"],
        },
    )

    result = _run(
        "qc_normalize_report.py",
        [
            "--report",
            str(report),
            "--layer",
            "qc",
            "--artifact",
            "artifacts/source_reviews_validation.json",
        ],
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["warning_issue_count"] == 1
    assert payload["requires_qc_disposition_count"] == 1
    issue = payload["issues"][0]
    _assert_qc_issue_shape(issue)
    assert issue["severity"] == "warning"
    assert issue["repair_owner"] == "research-external-evidence"
    assert issue["warning_disposition"] == "unresolved"
    assert issue["requires_qc_disposition"] is True
    assert "headline" in issue["downstream_limit"]


def test_qc_router_outputs_normalized_issues_for_missing_gate(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    output = tmp_path / "qc_router_report.json"

    result = _run("qc_router.py", ["--run-dir", str(run_dir), "--output", str(output)])

    assert result.returncode == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "qc_router_report_v1"
    assert payload["repair_schema_version"] == "qc_repair_report_v1"
    assert payload["is_valid"] is False
    assert payload["blocking_issue_count"] >= 1
    issue = payload["issues"][0]
    _assert_qc_issue_shape(issue)
    assert issue["repair_owner"] == "material-intake"
    assert issue["downstream_blocked"] is True


def test_qc_router_writes_warning_disposition_file(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True)
    _write_json(
        artifacts / "content_quality_validation.json",
        {
            "is_valid": True,
            "warning_count": 1,
            "warnings": ["slide 1 body copy may exceed advisory capacity"],
        },
    )
    output = artifacts / "qc_router_report.json"

    result = _run("qc_router.py", ["--run-dir", str(run_dir), "--output", str(output)])

    assert result.returncode == 0
    disposition_path = artifacts / "qc_warning_disposition.json"
    assert disposition_path.exists()
    payload = json.loads(disposition_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "qc_warning_disposition_v1"
    assert payload["warning_count"] == 1
    assert payload["unresolved_warning_count"] == 1
    warning = payload["warnings"][0]
    assert warning["repair_owner"] == "template"
    assert warning["disposition"] == "unresolved"


def test_qc_router_detects_ad_hoc_python_ppt_renderer(tmp_path: Path) -> None:
    work_root = tmp_path / "work"
    run_dir = work_root / "runs" / "sample_case"
    tools_dir = work_root / "tools"
    run_dir.mkdir(parents=True)
    tools_dir.mkdir(parents=True)
    (tools_dir / "build_base_makeup_deck.py").write_text(
        "from pptx import Presentation\n"
        "prs = Presentation()\n"
        "prs.save('base_makeup_brand_industry_section_EVIDENCE_LIMITED_DRAFT.pptx')\n",
        encoding="utf-8",
    )
    output = run_dir / "artifacts" / "qc_router_report.json"

    result = _run("qc_router.py", ["--run-dir", str(run_dir), "--output", str(output)])

    assert result.returncode == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    ad_hoc = [issue for issue in payload["issues"] if "ad-hoc PPT renderer" in issue.get("message", "")]
    assert ad_hoc, payload
    assert ad_hoc[0]["repair_owner"] == "output"
    brief = json.loads((output.parent / "qc_repair_brief.json").read_text(encoding="utf-8"))
    root_causes = {item["root_cause_id"] for item in brief["root_cause_groups"]}
    assert "ad_hoc_renderer" in root_causes

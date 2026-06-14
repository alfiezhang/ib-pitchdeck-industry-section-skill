#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

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


def _run_script(script: str, args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_script_path(script)), *args],
        cwd=str(RUNTIME_DIR),
        text=True,
        capture_output=True,
        env={**os.environ, "PYTHONPATH": os.pathsep.join(str(path) for path in SCRIPT_IMPORT_DIRS)},
    )


def _minimal_profile(max_units: int = 120) -> dict:
    return {
        "schema_version": "template_profile_v1",
        "template_file": "custom-template.pptx",
        "analysis_source": "unit-test",
        "visual_style": {
            "colors": {
                "brand_primary": "#123456",
                "accent_red": "#AA3322",
                "grid_gray": "#CCCCCC",
                "text_gray": "#333333",
            },
            "typography": {
                "body": "Arial",
                "table_header": "Arial",
                "table_body": "Arial",
                "legend_pt": 8.0,
            },
        },
        "text_geometry": {},
        "template_inventory": {
            "slide_count": 1,
            "slides": [
                {
                    "slide_no": 1,
                    "shape_count": 4,
                    "information_density": "medium",
                    "supports": {"text": True, "chart": False, "table": False, "source_footer": True},
                }
            ],
        },
        "layout": {
            "render_layouts": {"slides": {"1": {"overview": {}}}},
            "layout_budget": {
                "global": {"body_copy": {"max_bullet_units_default": max_units}},
                "slide_budgets": {"1:overview": {"body_fields_max_units": {"main_body": max_units}}},
            },
            "text_fit_rules": {"fields": {}, "renderer_field_aliases": {}},
        },
        "slide_variants": [
            {
                "slide_no": 1,
                "page_type": "overview",
                "render_layout": "overview",
                "supports": {"chart": False, "table": False, "matrix": False, "cards": False},
                "required_body_fields": ["main_body"],
                "field_roles": {"main_body": "body"},
                "source_footer_required": True,
            }
        ],
        "source_policy": {"source_footer_fields": ["source_footer"], "required_source_footer": True},
    }


def _renderer_spec(body_text: str) -> dict:
    return {
        "schema_version": "renderer_spec_v1",
        "slides": [
            {
                "slide_no": 1,
                "fixed_page_role": "industry_overview",
                "selected_page_type": "overview",
                "headline": "Market context",
                "main_message": "Evidence supports a focused market read.",
                "body_copy": {"main_body": body_text},
                "source_note": "Source: unit-test source review.",
            }
        ],
    }


def test_template_analyzer_extracts_inventory_from_arbitrary_pptx(tmp_path: Path) -> None:
    pptx = pytest.importorskip("pptx")
    prs = pptx.Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    title = slide.shapes.add_textbox(914400, 914400, 5486400, 914400)
    title.text = "Custom template title {{headline}}"
    source = slide.shapes.add_textbox(914400, 6400800, 7315200, 457200)
    source.text = "Source: template footer"
    rows, cols = 2, 2
    table = slide.shapes.add_table(rows, cols, 914400, 2286000, 3657600, 1371600)
    table.table.cell(0, 0).text = "Metric"
    template_path = tmp_path / "custom_template.pptx"
    prs.save(template_path)

    output = tmp_path / "template_profile.json"
    result = _run_script(
        "template_analyzer.py",
        [
            "--template",
            str(template_path),
            "--layout-config",
            str(RUNTIME_DIR / "configs" / "layout_config.json"),
            "--output",
            str(output),
        ],
    )

    assert result.returncode == 0, result.stderr or result.stdout
    profile = json.loads(output.read_text(encoding="utf-8"))
    assert profile["schema_version"] == "template_profile_v1"
    assert profile["template_inventory"]["slide_count"] == 1
    slide_inventory = profile["template_inventory"]["slides"][0]
    assert slide_inventory["supports"]["source_footer"] is True
    assert slide_inventory["supports"]["table"] is True
    assert profile["dynamic_slots"]["slides"][0]["slot_count"] >= 3


def test_template_fit_outputs_plan_and_blocks_capacity_conflict(tmp_path: Path) -> None:
    profile_path = tmp_path / "template_profile.json"
    renderer_path = tmp_path / "renderer_spec.json"
    validation_path = tmp_path / "template_fit_validation.json"
    plan_path = tmp_path / "template_fit_plan.json"

    _write_json(profile_path, _minimal_profile(max_units=20))
    _write_json(renderer_path, _renderer_spec("This body copy is intentionally long enough to exceed a tiny template slot budget."))

    result = _run_script(
        "template_fit.py",
        [
            "--renderer-spec",
            str(renderer_path),
            "--template-profile",
            str(profile_path),
            "--output",
            str(validation_path),
            "--fit-plan-output",
            str(plan_path),
        ],
    )

    assert result.returncode == 1
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    fit_plan = json.loads(plan_path.read_text(encoding="utf-8"))
    assert validation["is_valid"] is False
    assert validation["template_capacity_conflict"] is True
    assert fit_plan["fit_decision"] == "template_capacity_conflict"
    assert fit_plan["capacity_conflicts"][0]["conflict_type"] == "template_capacity_conflict"
    assert fit_plan["capacity_conflicts"][0]["repair_owner"] == "generation"
    assert fit_plan["copy_compression_recommendations"]


def test_template_fit_plan_records_slot_assignments_for_compatible_content(tmp_path: Path) -> None:
    profile_path = tmp_path / "template_profile.json"
    renderer_path = tmp_path / "renderer_spec.json"
    validation_path = tmp_path / "template_fit_validation.json"
    plan_path = tmp_path / "template_fit_plan.json"

    _write_json(profile_path, _minimal_profile(max_units=160))
    _write_json(renderer_path, _renderer_spec("Concise supported point."))

    result = _run_script(
        "template_fit.py",
        [
            "--renderer-spec",
            str(renderer_path),
            "--template-profile",
            str(profile_path),
            "--output",
            str(validation_path),
            "--fit-plan-output",
            str(plan_path),
        ],
    )

    assert result.returncode == 0, result.stderr or result.stdout
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    fit_plan = json.loads(plan_path.read_text(encoding="utf-8"))
    assert validation["is_valid"] is True
    assert fit_plan["fit_decision"] == "template_ready"
    assert fit_plan["capacity_conflicts"] == []
    assert {item["content_field"] for item in fit_plan["page_assignments"]} >= {"body_copy.main_body", "source_note"}

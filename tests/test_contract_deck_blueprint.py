"""Contract tests: Groups 4-6, 9 - deck blueprint creation, validation edge cases, compilation."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parents[1] / "runtime" / "ib-pitchdeck-agent-industry-section"
SCRIPT_DIR = SKILL_DIR / "scripts"
FIXTURES_DIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures"

sys.path.insert(0, str(SCRIPT_DIR))


def _validate_blueprint(blueprint: dict, page_argument_pack_path: Path, issue_path: Path, registry_path: Path) -> tuple[list[str], list[str], list]:
    from validate_deck_blueprint import validate
    issue = json.loads(issue_path.read_text(encoding="utf-8"))
    page_argument_pack = json.loads(page_argument_pack_path.read_text(encoding="utf-8"))
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    return validate(blueprint, page_argument_pack, registry, issue)


class TestDeckBlueprintValidation:
    def test_full_blueprint_passes(self, deck_blueprint_data, template_registry_path, page_argument_pack_path, issue_analysis):
        errors, warnings, _ = _validate_blueprint(
            deck_blueprint_data, page_argument_pack_path, FIXTURES_DIR / "valid_issue_analysis.json", template_registry_path
        )
        assert errors == [], errors

    def test_thin_slide_warns_not_fails(self, deck_blueprint_data, template_registry_path, page_argument_pack_path):
        """A slide with fewer body_blocks than expected should warn, not error."""
        blueprint = json.loads(json.dumps(deck_blueprint_data))
        for slide in blueprint["slides"]:
            if slide["slide_no"] == 4:
                slide["body_blocks"] = slide["body_blocks"][:1]
                slide["page_rationale"] = "Extra editorial field should be accepted and ignored by compiler."
                slide["body_blocks"][0]["editor_note"] = "Extra body-block helper field should not make blueprint invalid."
        errors, warnings, _ = _validate_blueprint(
            blueprint, page_argument_pack_path, FIXTURES_DIR / "valid_issue_analysis.json", template_registry_path
        )
        assert errors == [], f"thin blueprint should warn, not fail: {errors}"
        assert any("body_blocks has" in w for w in warnings), "should produce template-capacity warning"

    def test_chinese_conclusion_headline_accepted(self, deck_blueprint_data, template_registry_path, page_argument_pack_path):
        """Natural conclusion-led Chinese headlines should not trigger label warnings."""
        blueprint = json.loads(json.dumps(deck_blueprint_data))
        blueprint["slides"][7]["headline"] = "控股权出售应聚焦可验证增长质量"
        errors, warnings, _ = _validate_blueprint(
            blueprint, page_argument_pack_path, FIXTURES_DIR / "valid_issue_analysis.json", template_registry_path
        )
        assert errors == [], f"natural Chinese headline should remain valid: {errors}"
        assert not any("headline may be a label" in w for w in warnings), warnings

    def test_invalid_target_field_lists_allowed_fields(self, deck_blueprint_data, template_registry_path, page_argument_pack_path):
        """Invalid target_field should list allowed active fields in error message."""
        blueprint = json.loads(json.dumps(deck_blueprint_data))
        blueprint["slides"][0]["body_blocks"][0]["target_field"] = "left_key_1"
        errors, _, _ = _validate_blueprint(
            blueprint, page_argument_pack_path, FIXTURES_DIR / "valid_issue_analysis.json", template_registry_path
        )
        joined = "\n".join(errors)
        assert "Allowed active body fields: bullet_1, bullet_2, bullet_3" in joined, joined

    def test_invalid_target_field_fails_compiler(self, deck_blueprint_data):
        """Invalid target_field should raise ValueError in compiler."""
        from compile_deck_blueprint import _body_copy_from_blocks
        blueprint = json.loads(json.dumps(deck_blueprint_data))
        blueprint["slides"][0]["body_blocks"][0]["target_field"] = "left_key_1"
        with pytest.raises(ValueError, match="Allowed active body fields: bullet_1, bullet_2, bullet_3"):
            _body_copy_from_blocks(
                blueprint["slides"][0],
                ["bullet_1", "bullet_2", "bullet_3"],
                "industry_overview_dynamic_page",
            )


class TestDeckBlueprintCompilation:
    def test_compile_produces_valid_output(self, deck_blueprint_path, template_registry_path, page_argument_pack_path, tmp_path):
        env = {**__import__("os").environ, "PYTHONPATH": str(SCRIPT_DIR)}
        result = subprocess.run(
            [sys.executable, "scripts/generation/compile_deck_blueprint.py",
             "--page-argument-pack", str(page_argument_pack_path),
             "--issue-analysis", str(FIXTURES_DIR / "valid_issue_analysis.json"),
             "--deck-blueprint", str(deck_blueprint_path),
             "--template-registry", str(template_registry_path),
             "--page-contract-output", str(tmp_path / "page_evidence_contract.json"),
             "--renderer-spec-output", str(tmp_path / "renderer_spec.json")],
            text=True, capture_output=True, cwd=str(SKILL_DIR), env=env,
        )
        assert result.returncode == 0, result.stdout + result.stderr

    def test_value_chain_slide_body_copy_mapping(self, deck_blueprint_path, template_registry_path, page_argument_pack_path, tmp_path):
        """Slide 4 (value_chain_page) body_blocks with target_field should map to body_copy."""
        env = {**__import__("os").environ, "PYTHONPATH": str(SCRIPT_DIR)}
        subprocess.run(
            [sys.executable, "scripts/generation/compile_deck_blueprint.py",
             "--page-argument-pack", str(page_argument_pack_path),
             "--issue-analysis", str(FIXTURES_DIR / "valid_issue_analysis.json"),
             "--deck-blueprint", str(deck_blueprint_path),
             "--template-registry", str(template_registry_path),
             "--page-contract-output", str(tmp_path / "pec.json"),
             "--renderer-spec-output", str(tmp_path / "rs.json")],
            text=True, capture_output=True, cwd=str(SKILL_DIR), env=env, check=True,
        )
        renderer = json.loads((tmp_path / "rs.json").read_text(encoding="utf-8"))
        slide4 = next(s for s in renderer["slides"] if s["slide_no"] == 4)
        body = slide4["body_copy"]
        assert body["top_left"].startswith("Upstream inputs"), body
        assert body["top_center"].startswith("Manufacturing execution"), body
        assert body["top_right"].startswith("Brand ownership"), body
        assert body["bottom_left"].startswith("Channel access"), body
        assert body["bottom_center"].startswith("Profit-pool evidence"), body
        assert body["bottom_right"].startswith("Transaction relevance"), body

    def test_natural_visuals_compile(self, deck_blueprint_data, template_registry_path, page_argument_pack_path, tmp_path):
        """Chart data with natural series input and markdown table input should compile."""
        blueprint = json.loads(json.dumps(deck_blueprint_data))
        # Slide 1: natural year/value series
        blueprint["slides"][0]["chart_data"] = {
            "chart_type": "bar", "chart_title": "Natural series input should compile",
            "data_series": [
                {"year": "2022", "value": 80.0, "unit": "RMB bn", "metric_id": "MET-001"},
                {"year": "2024", "value": 100.0, "unit": "RMB bn", "metric_id": "MET-001"},
            ],
        }
        # Slide 2: growth rate series
        blueprint["slides"][1]["chart_data"] = {
            "chart_type": "bar", "chart_title": "Growth-rate rows should compile",
            "series": ["Growth rate"],
            "data_series": [
                {"segment": "Segment A", "growth_rate": 12.5, "metric_id": "MET-003"},
                {"segment": "Segment B", "growth_rate": 7.0, "metric_id": "MET-003"},
            ],
        }
        # Slide 6: markdown table
        blueprint["slides"][5]["compare_table_data"] = {
            "table_header": "Dimension | Evidence | Implication",
            "table_row_1": "Scale | large enough to matter | buyer attention",
            "table_row_2": "Capability | execution differentiates peers | diligence focus",
            "table_row_3": "Competition | fragmented field | consolidation logic",
        }
        blueprint["slides"][5]["body_blocks"] = [
            b for b in blueprint["slides"][5]["body_blocks"]
            if b.get("target_field") in {"right_top", "right_mid", "right_bottom"}
        ] or blueprint["slides"][5]["body_blocks"][:3]

        bp_path = tmp_path / "deck_blueprint_natural_visuals.json"
        _write_json(bp_path, blueprint)
        env = {**__import__("os").environ, "PYTHONPATH": str(SCRIPT_DIR)}
        subprocess.run(
            [sys.executable, "scripts/generation/compile_deck_blueprint.py",
             "--page-argument-pack", str(page_argument_pack_path),
             "--issue-analysis", str(FIXTURES_DIR / "valid_issue_analysis.json"),
             "--deck-blueprint", str(bp_path),
             "--template-registry", str(template_registry_path),
             "--page-contract-output", str(tmp_path / "pec_nv.json"),
             "--renderer-spec-output", str(tmp_path / "rs_nv.json")],
            text=True, capture_output=True, cwd=str(SKILL_DIR), env=env, check=True,
        )
        renderer = json.loads((tmp_path / "rs_nv.json").read_text(encoding="utf-8"))
        slide1 = next(s for s in renderer["slides"] if s["slide_no"] == 1)
        assert slide1["chart_data"]["categories"] == ["2022", "2024"], slide1["chart_data"]
        assert slide1["chart_data"]["series"][0]["values"] == [80.0, 100.0], slide1["chart_data"]
        assert isinstance(slide1["chart_data"]["source_rows"], list), slide1["chart_data"]
        slide2 = next(s for s in renderer["slides"] if s["slide_no"] == 2)
        assert slide2["chart_data"]["categories"] == ["Segment A", "Segment B"], slide2["chart_data"]
        assert slide2["chart_data"]["series"][0]["values"] == [12.5, 7.0], slide2["chart_data"]
        assert slide2["chart_data"]["unit"] == "%", slide2["chart_data"]
        slide6 = next(s for s in renderer["slides"] if s["slide_no"] == 6)
        assert slide6["compare_table_data"]["headers"] == ["Dimension", "Evidence", "Implication"], slide6["compare_table_data"]
        assert slide6["compare_table_data"]["rows"][0]["label"] == "Scale", slide6["compare_table_data"]

    def test_page_evidence_contract_keeps_selected_page_argument_permission_boundary(self):
        from build_page_evidence_contract import build_page_evidence_contract

        page_argument_pack = {
            "schema_version": "page_argument_pack_v1",
            "page_arguments": [
                {
                    "page_argument_id": "PA-001",
                    "source_issue_analysis_id": "IA-001",
                    "page_argument": "Headline-capable argument should not leak into PA-002.",
                    "evidence_status": "supported",
                    "allowed_deck_usage": "headline_allowed",
                    "downstream_permission": {
                        "headline_allowed": True,
                        "main_message_allowed": True,
                        "chart_allowed": True,
                        "body_copy_allowed": True,
                    },
                    "evidence_ids": ["EV-001"],
                    "metric_ids": ["MET-001"],
                },
                {
                    "page_argument_id": "PA-002",
                    "source_issue_analysis_id": "IA-001",
                    "page_argument": "Body-only argument selected for this slide.",
                    "evidence_status": "thin",
                    "allowed_deck_usage": "body_only",
                    "downstream_permission": {
                        "headline_allowed": False,
                        "main_message_allowed": False,
                        "chart_allowed": False,
                        "body_copy_allowed": True,
                    },
                    "evidence_ids": ["EV-002"],
                    "metric_ids": ["MET-002"],
                },
            ],
        }
        page_plan = {
            "slides": [
                {
                    "slide_no": 1,
                    "fixed_page_role": "industry_overview",
                    "investor_question": "What should the reader know?",
                    "page_answer": "Use only the selected body-only page argument.",
                    "page_argument_ids": ["PA-002"],
                    "primary_issue_analysis_id": "IA-001",
                    "supporting_issue_analysis_ids": [],
                    "visual_plan": {"required_capability": "chart", "visual_metric_ids": ["MET-002"]},
                    "proof_points": [
                        {
                            "point": "Selected PA-002 supports body copy only.",
                            "source_analysis_ids": ["IA-001"],
                            "evidence_ids": ["EV-002"],
                            "metric_ids": ["MET-002"],
                            "claim_strength": "supported_inference",
                        }
                    ],
                    "claim_strength": "supported_inference",
                    "caveats": [],
                    "open_questions": [],
                }
            ]
        }

        contract = build_page_evidence_contract(page_argument_pack, page_plan)
        slide = contract["slides"][0]

        assert slide["page_argument_ids"] == ["PA-002"]
        assert slide["headline_allowed"] is False
        assert slide["chart_allowed"] is False
        assert slide["chart_metric_ids"] == []
        assert slide["body_evidence_ids"] == ["EV-002"]
        assert slide["selected_page_argument_permissions"][0]["page_argument_id"] == "PA-002"
        assert slide["selected_page_argument_permissions"][0]["evidence_ids"] == ["EV-002"]
        assert slide["selected_page_argument_permissions"][0]["metric_ids"] == ["MET-002"]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

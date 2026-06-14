"""Contract tests: Group 11 - content quality classification, repair plans, layout budget, text fit."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "runtime" / "ib-pitchdeck-agent-industry-section" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))


class TestContentRootCauses:
    def test_classify_visible_claim_binding(self):
        from validate_content_quality import classify_content_root_causes
        messages = [
            "slide 1: material visible quantitative claim at 'main_message' has no metric_ids",
        ]
        root_causes = classify_content_root_causes(messages)
        by_code = {item["code"]: item for item in root_causes}
        assert "VISIBLE_CLAIM_BINDING" in by_code
        assert by_code["VISIBLE_CLAIM_BINDING"]["category"] == "metric_claims"
        assert by_code["VISIBLE_CLAIM_BINDING"]["repair_target"] == "deck_blueprint.json"
        assert "slides[].visible_metric_claims" in by_code["VISIBLE_CLAIM_BINDING"]["repair_fields"]

    def test_classify_chart_metric_binding(self):
        from validate_content_quality import classify_content_root_causes
        messages = [
            "slide 2: chart_data.source_rows is required when chart data contains visible datapoints",
        ]
        root_causes = classify_content_root_causes(messages)
        by_code = {item["code"]: item for item in root_causes}
        assert by_code["CHART_METRIC_BINDING"]["repair_target"] == "deck_blueprint.json"
        assert (
            "scripts/qc/validators/final/validate_chart_metric_binding.py"
            in by_code["CHART_METRIC_BINDING"]["rerun_steps"]
        )

    def test_classify_layout_fit_risk(self):
        from validate_content_quality import classify_content_root_causes
        messages = [
            "slide 4: left_panel is 86.2 layout units; max for summary_page is 78.0; reduce by ~9 CJK char(s)",
        ]
        root_causes = classify_content_root_causes(messages)
        by_code = {item["code"]: item for item in root_causes}
        assert by_code["LAYOUT_FIT_RISK"]["category"] == "layout_density"

    def test_classify_weak_or_generic_source(self):
        from validate_content_quality import classify_content_root_causes
        messages = [
            "slide 6: source_note contains generic source phrase 'industry report'",
        ]
        root_causes = classify_content_root_causes(messages)
        by_code = {item["code"]: item for item in root_causes}
        assert by_code["WEAK_OR_GENERIC_SOURCE"]["fallback_repair_targets"]

    def test_classify_target_advocacy(self):
        from validate_content_quality import classify_content_root_causes
        messages = [
            "slide 8: target advocacy phrase appears in headline",
        ]
        root_causes = classify_content_root_causes(messages)
        by_code = {item["code"]: item for item in root_causes}
        assert "*.pptx" in by_code["TARGET_ADVOCACY_OR_OVERCLAIM"]["do_not_edit"]

    def test_build_content_repair_plan(self):
        from validate_content_quality import build_content_repair_plan, classify_content_root_causes
        messages = [
            "slide 1: material visible quantitative claim at 'main_message' has no metric_ids",
            "slide 2: chart_data.source_rows is required when chart data contains visible datapoints",
            "slide 4: left_panel is 86.2 layout units; max for summary_page is 78.0; reduce by ~9 CJK char(s)",
            "slide 6: source_note contains generic source phrase 'industry report'",
            "slide 8: target advocacy phrase appears in headline",
        ]
        root_causes = classify_content_root_causes(messages)
        repair_plan = build_content_repair_plan(root_causes)
        assert repair_plan["status"] == "repair_required"
        assert "deck_blueprint.json" in repair_plan["primary_repair_targets"]
        assert "renderer_spec.json" in repair_plan["do_not_edit"]
        assert "replacement_dict.json" in repair_plan["do_not_edit"]
        assert repair_plan["targets"][0]["repair_fields"]


class TestLayoutBudget:
    def test_layout_budget_findings_advisory(self):
        from validation_common import layout_budget_findings
        long_body = "结构性机会：" + "渠道迁移、产品功效化和品牌利润池共同支撑页面论证，" * 8
        errors, warnings = layout_budget_findings(
            {"left_panel": long_body},
            8,
            "summary_page",
            {
                "global": {"body_copy": {"max_bullet_units_default": 20, "max_newlines_per_field": 1}, "table": {"max_cell_units": 12}},
                "slide_budgets": {},
                "page_type_budgets": {"summary_page": {"body_fields_max_units": {"left_panel": 20}}},
            },
        )
        assert not errors, errors
        assert any("advisory body capacity" in w for w in warnings), warnings

    def test_check_body_length_density_warning(self):
        from validate_content_quality import check_body_length
        long_body = "结构性机会：" + "渠道迁移、产品功效化和品牌利润池共同支撑页面论证，" * 8
        blocking: list = []
        density_warnings: list = []
        check_body_length(long_body, 8, "left_panel", density_warnings, blocking)
        assert density_warnings
        assert not blocking


class TestTextFit:
    def test_headline_exceeding_max_lines_blocks(self):
        from validate_content_quality import check_text_fit
        fit_warnings: list = []
        fit_blocking: list = []
        check_text_fit(
            "这是一个明显超出标题文本框容量的长标题，需要继续延长以触发硬性标题换行限制",
            "headline",
            1,
            "industry_overview_dynamic_page",
            {
                "renderer_field_aliases": {"headline": "slide_title"},
                "fields": {
                    "1:industry_overview_dynamic_page:slide_title": {
                        "placeholder": "{{slide_01_title}}",
                        "max_line_units": 10,
                        "target_lines": 1,
                        "max_lines": 1,
                        "block_if_exceeds_max_lines": True,
                    }
                },
            },
            fit_warnings,
            fit_blocking,
        )
        assert fit_blocking, fit_warnings

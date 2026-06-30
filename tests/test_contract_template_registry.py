"""Contract tests: Group 3 - template registry extraction and validation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parents[1] / "runtime" / "ib-pitchdeck-agent-industry-section"
SCRIPT_DIR = SKILL_DIR / "scripts"

EXPECTED_ROLES = {
    1: "industry_overview", 2: "market_size_segmentation", 3: "key_industry_drivers",
    4: "value_chain_profit_pool", 5: "key_barriers_value_drivers", 6: "competitive_landscape",
    7: "industry_trends_future_evolution", 8: "industry_takeaways_for_project",
}
EXPECTED_DEFAULT_VARIANTS = {
    1: "industry_overview_dynamic_page", 2: "chart_page", 3: "driver_card_page",
    4: "value_chain_page", 5: "moat_page", 6: "compare_table_page",
    7: "trend_page", 8: "summary_page",
}


class TestTemplateRegistryExtraction:
    def test_extract_template_registry(self, template_registry_path):
        assert template_registry_path.exists(), "template_registry.json should be created"
        registry = json.loads(template_registry_path.read_text(encoding="utf-8"))
        assert registry["schema_version"] == "template_registry_v1", registry

    def test_registry_has_8_slides(self, template_registry_path):
        registry = json.loads(template_registry_path.read_text(encoding="utf-8"))
        assert len(registry["slides"]) == 8, registry["slides"]

    def test_registry_slide_roles(self, template_registry_path):
        registry = json.loads(template_registry_path.read_text(encoding="utf-8"))
        for slide in registry["slides"]:
            no = slide["slide_no"]
            assert slide["fixed_page_role"] == EXPECTED_ROLES[no], slide

    def test_registry_default_variants(self, template_registry_path):
        registry = json.loads(template_registry_path.read_text(encoding="utf-8"))
        for slide in registry["slides"]:
            no = slide["slide_no"]
            assert slide["default_variant"] == EXPECTED_DEFAULT_VARIANTS[no], slide

    def test_registry_has_variants(self, template_registry_path):
        registry = json.loads(template_registry_path.read_text(encoding="utf-8"))
        for slide in registry["slides"]:
            assert "variants" in slide, f"slide {slide['slide_no']} missing variants"
            assert len(slide["variants"]) >= 1, f"slide {slide['slide_no']} has no variants"

    def test_registry_validate(self, template_registry_path, tmp_path):
        from validate_artifact import validate_artifact

        errors, warnings = validate_artifact("template_registry", tmp_path, template_registry_path)
        assert errors == []
        assert isinstance(warnings, list)

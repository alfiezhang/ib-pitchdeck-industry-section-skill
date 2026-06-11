"""Contract tests: Group 10 - postprocess PPT visuals."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "runtime" / "ib-pitchdeck-agent-industry-section" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))


class TestBuildChart:
    def test_invalid_series_returns_not_rendered_with_repair_hint(self):
        """build_chart should return rendered=False with repair_hint for invalid series."""
        try:
            from postprocess_ppt_visuals import build_chart
        except SystemExit:
            pytest.skip("postprocess_ppt_visuals not importable")

        result = build_chart(
            None,
            {
                "slide_no": 1,
                "selected_page_type": "industry_overview_dynamic_page",
                "chart_data": {
                    "chart_type": "bar",
                    "categories": ["2024"],
                    "series": ["Market size"],  # string instead of dict
                },
            },
            {},
        )
        assert result.get("rendered") is False, result
        assert result.get("reason") == "invalid chart_data.series item", result
        assert "repair_hint" in result, result

#!/usr/bin/env bash
# Focused contract checks for the deck-blueprint industry-section workflow.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SKILL_DIR="$ROOT_DIR/runtime/ib-industry-section-skill"
FIXTURES_DIR="$ROOT_DIR/tests/fixtures"
PYTHON_CMD="${PYTHON_CMD:-python3}"
TMP_DIR="$(mktemp -d)"
export TMP_DIR FIXTURES_DIR
trap 'rm -rf "$TMP_DIR"' EXIT

cd "$SKILL_DIR"
export PYTHONPATH="$SKILL_DIR/scripts${PYTHONPATH:+:$PYTHONPATH}"

"$PYTHON_CMD" -m compileall -q scripts
"$PYTHON_CMD" scripts/check_json_files.py --root . >/dev/null
"$PYTHON_CMD" scripts/check_artifact_manifest.py >/dev/null
"$PYTHON_CMD" scripts/check_slide_registry.py >/dev/null
"$PYTHON_CMD" scripts/check_registry_coverage.py >/dev/null
"$PYTHON_CMD" scripts/check_template_tokens.py \
  --template assets/industry_section_template_master.pptx \
  --ppt-mapping templates/ppt_mapping.json \
  --fail-on-diff \
  --output "$TMP_DIR/template_token_check.json" >/dev/null

"$PYTHON_CMD" scripts/validate_issue_analysis.py \
  --issue-analysis "$FIXTURES_DIR/valid_issue_analysis.json" >/dev/null
if "$PYTHON_CMD" scripts/validate_issue_analysis.py \
  --issue-analysis "$FIXTURES_DIR/invalid_issue_analysis.json" >/dev/null 2>&1; then
  echo "invalid_issue_analysis.json should fail validation" >&2
  exit 1
fi

"$PYTHON_CMD" scripts/extract_template_registry.py \
  --template assets/industry_section_template_master.pptx \
  --slide-registry templates/slide_registry.json \
  --page-type-rules templates/page_type_rules.json \
  --ppt-mapping templates/ppt_mapping.json \
  --layout-budget templates/layout_budget.json \
  --text-fit-rules templates/text_fit_rules.json \
  --output "$TMP_DIR/template_registry.json" >/dev/null

"$PYTHON_CMD" - <<'PY'
import json
import os
from pathlib import Path

tmp = Path(os.environ["TMP_DIR"])
roles = {
    1: "industry_overview",
    2: "market_size_segmentation",
    3: "key_industry_drivers",
    4: "value_chain_profit_pool",
    5: "key_barriers_value_drivers",
    6: "competitive_landscape",
    7: "industry_trends_future_evolution",
    8: "transaction_implications",
}
page_types = {
    1: "industry_overview_dynamic_page",
    2: "chart_page",
    3: "driver_card_page",
    4: "value_chain_page",
    5: "moat_page",
    6: "compare_table_page",
    7: "trend_page",
    8: "summary_page",
}
block_counts = {1: 3, 2: 3, 3: 4, 4: 6, 5: 3, 6: 3, 7: 3, 8: 4}
issue_ids = {
    1: ["IA-001"],
    2: ["IA-001", "IA-002"],
    3: ["IA-003"],
    4: ["IA-003"],
    5: ["IA-003"],
    6: ["IA-003"],
    7: ["IA-003"],
    8: ["IA-003", "IA-004"],
}
copy_themes = [
    "Scale evidence establishes a market large enough for senior buyer attention.",
    "Forecast evidence needs period assumptions, not broad extrapolation.",
    "Segmentation evidence identifies where growth differs from the total market.",
    "Demand evidence links customer behavior to repeatable revenue pools.",
    "Channel evidence explains how access converts product relevance into share.",
    "Value-chain economics show where margin control tends to accumulate.",
    "Capability barriers matter more than a single visible share statistic.",
    "Peer dispersion creates a comparison basis without target advocacy.",
    "Trend evidence remains directional unless supported by hard data.",
    "Transaction relevance should stay separate from target marketing language.",
    "Source limitations shape how assertive the page conclusion can be.",
    "Competitive intensity clarifies whether the sector rewards scale or focus.",
    "Pricing evidence indicates whether growth is volume-led or premium-led.",
    "Regulatory context frames risk without becoming the main page story.",
    "Technology change matters when it alters cost, quality, or route to market.",
    "Customer concentration affects repeatability and buyer diligence priorities.",
    "Business model evidence separates recurring economics from project revenue.",
    "Margin evidence distinguishes profitable growth from headline expansion.",
    "Market-cycle context prevents overstating a short-term demand spike.",
    "End-market mix explains which pockets deserve deeper buyer discussion.",
    "Distribution power affects bargaining leverage across the chain.",
    "Supply constraints can create advantage only when they persist.",
    "Brand trust evidence matters when purchase risk is high.",
    "Product differentiation must be tied to customer willingness to pay.",
    "M&A evidence supports interest only when multiple cases point the same way.",
    "Valuation context should be caveated when peer comparability is thin.",
    "Risk evidence should lead to questions, not unsupported bearish claims.",
    "Management data can inform context but needs explicit verification status.",
    "Operational KPIs explain why similar revenue bases may trade differently.",
    "Geographic scope matters before comparing market size or growth rates.",
    "Historical growth should be separated from forecast assumptions.",
    "The final page should turn sector view into focused buyer discussion points.",
]

slides = []
for no in range(1, 9):
    ids = issue_ids[no]
    evidence = ["EV-001"] if "IA-001" in ids or "IA-002" in ids else ["EV-003"]
    metrics = ["MET-001"] if no == 1 else (["MET-003"] if no == 2 else [])
    blocks = []
    for idx in range(1, block_counts[no] + 1):
        theme = copy_themes[((no - 1) * 6 + idx - 1) % len(copy_themes)]
        blocks.append(
            {
                "role": f"point_{idx}",
                "copy": theme,
                "source_analysis_ids": ids[:1],
                "evidence_ids": evidence,
                "metric_ids": metrics if idx == 1 else [],
                "claim_strength": "supported_inference",
            }
        )
    if no == 4:
        blocks = [
            {
                "role": "profit_pool",
                "target_field": "bottom_center",
                "copy": "Profit-pool evidence shows where economics accrue across the industry chain.",
                "source_analysis_ids": ids[:1],
                "evidence_ids": evidence,
                "metric_ids": [],
                "claim_strength": "supported_inference",
            },
            {
                "role": "upstream",
                "target_field": "top_left",
                "copy": "Upstream inputs define cost exposure before operating capabilities take effect.",
                "source_analysis_ids": ids[:1],
                "evidence_ids": evidence,
                "metric_ids": [],
                "claim_strength": "supported_inference",
            },
            {
                "role": "transaction_implication",
                "target_field": "bottom_right",
                "copy": "Transaction relevance should stay tied to sector economics, not target promotion.",
                "source_analysis_ids": ids[:1],
                "evidence_ids": evidence,
                "metric_ids": [],
                "claim_strength": "supported_inference",
            },
            {
                "role": "manufacturing",
                "target_field": "top_center",
                "copy": "Manufacturing execution explains why quality control can become a buyer diligence topic.",
                "source_analysis_ids": ids[:1],
                "evidence_ids": evidence,
                "metric_ids": [],
                "claim_strength": "supported_inference",
            },
            {
                "role": "brand",
                "target_field": "top_right",
                "copy": "Brand ownership converts category credibility into pricing and repeat-purchase power.",
                "source_analysis_ids": ids[:1],
                "evidence_ids": evidence,
                "metric_ids": [],
                "claim_strength": "supported_inference",
            },
            {
                "role": "channel",
                "target_field": "bottom_left",
                "copy": "Channel access determines whether product strength can convert into scaled demand.",
                "source_analysis_ids": ids[:1],
                "evidence_ids": evidence,
                "metric_ids": [],
                "claim_strength": "supported_inference",
            },
        ]
    visual_design = {"required_capability": "text", "purpose": f"Support slide {no} page thesis."}
    chart_data = {}
    compare_table_data = {}
    if no == 1:
        visual_design = {"required_capability": "chart", "purpose": "Show current market scale.", "visual_metric_ids": ["MET-001"]}
        chart_data = {
            "chart_type": "bar",
            "title": "Current market scale",
            "categories": ["Current"],
            "series": [{"name": "Market size", "values": [100.0]}],
            "unit": "RMB bn",
            "source_rows": [{"label": "Current", "value": 100.0, "metric_id": "MET-001"}],
        }
    if no == 2:
        visual_design = {"required_capability": "chart", "purpose": "Show segmentation metric.", "visual_metric_ids": ["MET-003"]}
        chart_data = {
            "chart_type": "bar",
            "title": "Segment split",
            "categories": ["Segment"],
            "series": [{"name": "Share", "values": [45.0]}],
            "unit": "%",
            "source_rows": [{"label": "Segment", "value": 45.0, "metric_id": "MET-003"}],
        }
    if no == 6:
        visual_design = {"required_capability": "table", "purpose": "Compare competitive dimensions."}
        compare_table_data = {
            "headers": ["Dimension", "Evidence-backed read", "Pitch implication"],
            "rows": [
                {"label": "Scale", "cells": ["Large enough to matter", "EV-003 supports capability lens", "Frame strategic interest"]},
                {"label": "Capabilities", "cells": ["Execution matters", "EV-003 supports operating lens", "Assess repeatability"]},
                {"label": "Competition", "cells": ["Differentiation varies", "EV-003 supports peer lens", "Avoid target advocacy"]},
            ],
            "comparison_basis_note": "Illustrative peer dimensions from selected issue analysis.",
        }
    slides.append(
        {
            "slide_no": no,
            "fixed_page_role": roles[no],
            "investor_question": f"What should an investor learn from slide {no}?",
            "page_thesis": f"Slide {no} answers a distinct industry question with evidence-backed judgment.",
            "why_this_page_matters": f"Slide {no} matters because it converts research into a pitch-relevant page argument.",
            "issue_analysis_ids": ids,
            "selected_page_type": page_types[no],
            "claim_strength": "supported_inference",
            "headline": f"Slide {no}: conclusion-led industry view with distinct implication",
            "main_message": f"Slide {no} connects evidence to the pitch without repeating the title.",
            "body_blocks": blocks,
            "visual_design": visual_design,
            "chart_data": chart_data,
            "compare_table_data": compare_table_data,
            "source_note": "Sources: " + "; ".join(evidence),
            "pitch_relevance": "Sector credibility first; target context remains selective.",
            "caveats": [],
            "open_questions": ["Verify target-specific fit after mandate"] if no == 8 else [],
        }
    )

blueprint = {
    "schema_version": "deck_blueprint_v1",
    "section_meta": {"target_company": "Example Target", "industry": "Example sector"},
    "deck_storyline": "The section moves from market scale to structure, competition, and transaction relevance while preserving evidence boundaries.",
    "slides": slides,
}
(tmp / "deck_blueprint.json").write_text(json.dumps(blueprint, ensure_ascii=False, indent=2), encoding="utf-8")
PY

"$PYTHON_CMD" scripts/validate_deck_blueprint.py \
  --deck-blueprint "$TMP_DIR/deck_blueprint.json" \
  --issue-analysis "$FIXTURES_DIR/valid_issue_analysis.json" \
  --template-registry "$TMP_DIR/template_registry.json" \
  --output "$TMP_DIR/deck_blueprint_validation.json" >/dev/null

"$PYTHON_CMD" - <<'PY'
import json
import os
from pathlib import Path

from json_utils import load_json_file
from validate_deck_blueprint import validate

tmp = Path(os.environ["TMP_DIR"])
blueprint = json.loads((tmp / "deck_blueprint.json").read_text(encoding="utf-8"))
for slide in blueprint["slides"]:
    if slide["slide_no"] == 4:
        slide["body_blocks"] = slide["body_blocks"][:1]
        slide["page_rationale"] = "Extra editorial field should be accepted and ignored by compiler."
        slide["body_blocks"][0]["editor_note"] = "Extra body-block helper field should not make blueprint invalid."
thin_path = tmp / "deck_blueprint_thin_page.json"
thin_path.write_text(json.dumps(blueprint, ensure_ascii=False, indent=2), encoding="utf-8")
errors, warnings = validate(
    blueprint,
    load_json_file(Path(os.environ["FIXTURES_DIR"]) / "valid_issue_analysis.json"),
    load_json_file(tmp / "template_registry.json"),
)
if errors:
    raise SystemExit("thin deck_blueprint should warn, not fail: " + json.dumps(errors, ensure_ascii=False))
if not any("body_blocks has" in warning for warning in warnings):
    raise SystemExit("thin deck_blueprint should produce template-capacity warning")

natural = json.loads((tmp / "deck_blueprint.json").read_text(encoding="utf-8"))
natural["slides"][7]["headline"] = "控股权出售应聚焦可验证增长质量"
errors, warnings = validate(
    natural,
    load_json_file(Path(os.environ["FIXTURES_DIR"]) / "valid_issue_analysis.json"),
    load_json_file(tmp / "template_registry.json"),
)
if errors:
    raise SystemExit("natural conclusion-led Chinese headline should remain valid: " + json.dumps(errors, ensure_ascii=False))
if any("headline may be a label" in warning for warning in warnings):
    raise SystemExit("natural conclusion-led Chinese headline should not trigger label warning: " + json.dumps(warnings, ensure_ascii=False))
PY

"$PYTHON_CMD" scripts/compile_deck_blueprint.py \
  --issue-analysis "$FIXTURES_DIR/valid_issue_analysis.json" \
  --deck-blueprint "$TMP_DIR/deck_blueprint.json" \
  --template-registry "$TMP_DIR/template_registry.json" \
  --page-contract-output "$TMP_DIR/page_evidence_contract.json" \
  --renderer-spec-output "$TMP_DIR/renderer_spec.json" >/dev/null

"$PYTHON_CMD" - <<'PY'
import json
import os
from pathlib import Path

tmp = Path(os.environ["TMP_DIR"])
renderer = json.loads((tmp / "renderer_spec.json").read_text(encoding="utf-8"))
slide4 = next(slide for slide in renderer["slides"] if slide["slide_no"] == 4)
body = slide4["body_copy"]
assert body["top_left"].startswith("Upstream inputs"), body
assert body["top_center"].startswith("Manufacturing execution"), body
assert body["top_right"].startswith("Brand ownership"), body
assert body["bottom_left"].startswith("Channel access"), body
assert body["bottom_center"].startswith("Profit-pool evidence"), body
assert body["bottom_right"].startswith("Transaction relevance"), body
PY

"$PYTHON_CMD" - <<'PY'
import json
import os
import subprocess
import sys
from pathlib import Path

tmp = Path(os.environ["TMP_DIR"])
blueprint = json.loads((tmp / "deck_blueprint.json").read_text(encoding="utf-8"))
for slide in blueprint["slides"]:
    if slide["slide_no"] == 1:
        slide["chart_data"] = {
            "chart_type": "bar",
            "chart_title": "Natural series input should compile",
            "data_series": [
                {"year": "2022", "value": 80.0, "unit": "RMB bn", "metric_id": "MET-001"},
                {"year": "2024", "value": 100.0, "unit": "RMB bn", "metric_id": "MET-001"},
            ],
        }
    if slide["slide_no"] == 2:
        slide["chart_data"] = {
            "chart_type": "bar",
            "chart_title": "Growth-rate rows should compile",
            "series": ["Growth rate"],
            "data_series": [
                {"segment": "Segment A", "growth_rate": 12.5, "metric_id": "MET-003"},
                {"segment": "Segment B", "growth_rate": 7.0, "metric_id": "MET-003"},
            ],
        }
    if slide["slide_no"] == 6:
        slide["compare_table_data"] = {
            "table_header": "Dimension | Evidence | Implication",
            "table_row_1": "Scale | large enough to matter | buyer attention",
            "table_row_2": "Capability | execution differentiates peers | diligence focus",
            "table_row_3": "Competition | fragmented field | consolidation logic",
        }
        slide["body_blocks"] = [
            block
            for block in slide["body_blocks"]
            if block.get("target_field") in {"right_top", "right_mid", "right_bottom"}
        ] or slide["body_blocks"][:3]
natural_path = tmp / "deck_blueprint_natural_visuals.json"
natural_path.write_text(json.dumps(blueprint, ensure_ascii=False, indent=2), encoding="utf-8")
renderer_path = tmp / "renderer_spec_natural_visuals.json"
subprocess.run(
    [
        sys.executable,
        "scripts/compile_deck_blueprint.py",
        "--issue-analysis",
        str(Path(os.environ["FIXTURES_DIR"]) / "valid_issue_analysis.json"),
        "--deck-blueprint",
        str(natural_path),
        "--template-registry",
        str(tmp / "template_registry.json"),
        "--page-contract-output",
        str(tmp / "page_evidence_contract_natural_visuals.json"),
        "--renderer-spec-output",
        str(renderer_path),
    ],
    check=True,
    stdout=subprocess.DEVNULL,
)
renderer = json.loads(renderer_path.read_text(encoding="utf-8"))
slide1 = next(slide for slide in renderer["slides"] if slide["slide_no"] == 1)
assert slide1["chart_data"]["categories"] == ["2022", "2024"], slide1["chart_data"]
assert slide1["chart_data"]["series"][0]["values"] == [80.0, 100.0], slide1["chart_data"]
assert isinstance(slide1["chart_data"]["source_rows"], list), slide1["chart_data"]
slide2 = next(slide for slide in renderer["slides"] if slide["slide_no"] == 2)
assert slide2["chart_data"]["categories"] == ["Segment A", "Segment B"], slide2["chart_data"]
assert slide2["chart_data"]["series"][0]["values"] == [12.5, 7.0], slide2["chart_data"]
assert slide2["chart_data"]["unit"] == "%", slide2["chart_data"]
slide6 = next(slide for slide in renderer["slides"] if slide["slide_no"] == 6)
assert slide6["compare_table_data"]["headers"] == ["Dimension", "Evidence", "Implication"], slide6["compare_table_data"]
assert slide6["compare_table_data"]["rows"][0]["label"] == "Scale", slide6["compare_table_data"]
PY

"$PYTHON_CMD" - <<'PY'
try:
    from postprocess_ppt_visuals import build_chart
except SystemExit:
    raise SystemExit(0)

result = build_chart(
    None,
    {
        "slide_no": 1,
        "selected_page_type": "industry_overview_dynamic_page",
        "chart_data": {
            "chart_type": "bar",
            "categories": ["2024"],
            "series": ["Market size"],
        },
    },
    {},
)
if result.get("rendered") is not False:
    raise SystemExit(result)
if result.get("reason") != "invalid chart_data.series item":
    raise SystemExit(result)
if "repair_hint" not in result:
    raise SystemExit(result)
PY

"$PYTHON_CMD" - <<'PY'
from validate_content_quality import build_content_repair_plan, classify_content_root_causes

messages = [
    "slide 1: material visible quantitative claim at 'main_message' has no metric_ids",
    "slide 2: chart_data.source_rows is required when chart data contains visible datapoints",
    "slide 4: left_panel is 86.2 layout units; max for summary_page is 78.0; reduce by ~9 CJK char(s)",
    "slide 6: source_note contains generic source phrase 'industry report'",
    "slide 8: target advocacy phrase appears in headline",
]
root_causes = classify_content_root_causes(messages)
by_code = {item["code"]: item for item in root_causes}
assert by_code["VISIBLE_CLAIM_BINDING"]["category"] == "metric_claims", by_code
assert by_code["VISIBLE_CLAIM_BINDING"]["repair_target"] == "deck_blueprint.json", by_code
assert "slides[].visible_metric_claims" in by_code["VISIBLE_CLAIM_BINDING"]["repair_fields"], by_code
assert by_code["CHART_METRIC_BINDING"]["repair_target"] == "deck_blueprint.json", by_code
assert "scripts/validate_chart_metric_binding.py" in by_code["CHART_METRIC_BINDING"]["rerun_steps"], by_code
assert by_code["LAYOUT_FIT_RISK"]["category"] == "layout_density", by_code
assert by_code["WEAK_OR_GENERIC_SOURCE"]["fallback_repair_targets"], by_code
assert "*.pptx" in by_code["TARGET_ADVOCACY_OR_OVERCLAIM"]["do_not_edit"], by_code
repair_plan = build_content_repair_plan(root_causes)
assert repair_plan["status"] == "repair_required", repair_plan
assert "deck_blueprint.json" in repair_plan["primary_repair_targets"], repair_plan
assert "renderer_spec.json" in repair_plan["do_not_edit"], repair_plan
assert "replacement_dict.json" in repair_plan["do_not_edit"], repair_plan
assert repair_plan["targets"][0]["repair_fields"], repair_plan
PY

"$PYTHON_CMD" scripts/validate_page_evidence_contract.py \
  --issue-analysis "$FIXTURES_DIR/valid_issue_analysis.json" \
  --deck-blueprint "$TMP_DIR/deck_blueprint.json" \
  --page-contract "$TMP_DIR/page_evidence_contract.json" \
  --output "$TMP_DIR/page_evidence_contract_validation.json" >/dev/null

"$PYTHON_CMD" scripts/validate_renderer_spec.py \
  --renderer-spec "$TMP_DIR/renderer_spec.json" \
  --template-registry "$TMP_DIR/template_registry.json" \
  --deck-blueprint "$TMP_DIR/deck_blueprint.json" \
  --page-contract "$TMP_DIR/page_evidence_contract.json" \
  --output "$TMP_DIR/renderer_spec_validation.json" >/dev/null

"$PYTHON_CMD" - <<'PY'
import json
import os
import subprocess
import sys
from pathlib import Path

from validate_final_delivery import validate_issue_artifacts
from validate_research_pack import validate as validate_research_pack

tmp = Path(os.environ["TMP_DIR"])
run_dir = tmp / "issue_artifact_run"
artifacts = run_dir / "artifacts"
artifacts.mkdir(parents=True)
(run_dir / "industry_issue_analysis.json").write_text((Path(os.environ["FIXTURES_DIR"]) / "valid_issue_analysis.json").read_text(encoding="utf-8"), encoding="utf-8")
(run_dir / "template_registry.json").write_text((tmp / "template_registry.json").read_text(encoding="utf-8"), encoding="utf-8")
(run_dir / "deck_blueprint.json").write_text((tmp / "deck_blueprint.json").read_text(encoding="utf-8"), encoding="utf-8")
(run_dir / "page_evidence_contract.json").write_text((tmp / "page_evidence_contract.json").read_text(encoding="utf-8"), encoding="utf-8")
for name in (
    "issue_analysis_validation.json",
    "template_registry_validation.json",
    "deck_blueprint_validation.json",
    "page_evidence_contract_validation.json",
):
    (artifacts / name).write_text(json.dumps({"is_valid": True, "error_count": 0}, ensure_ascii=False), encoding="utf-8")
(artifacts / "deck_blueprint_validation.json").write_text(json.dumps({"is_valid": False, "error_count": 1}, ensure_ascii=False), encoding="utf-8")
errors, _ = validate_issue_artifacts(run_dir)
if "deck_blueprint_validation.json is_valid=false" not in errors:
    raise SystemExit("final delivery issue-artifact gate did not catch is_valid=false: " + json.dumps(errors, ensure_ascii=False))

bad_run = tmp / "bad_upstream_run"
bad_artifacts = bad_run / "artifacts"
bad_artifacts.mkdir(parents=True)
for source, name in (
    (Path(os.environ["FIXTURES_DIR"]) / "valid_issue_analysis.json", "industry_issue_analysis.json"),
    (tmp / "template_registry.json", "template_registry.json"),
    (tmp / "deck_blueprint.json", "deck_blueprint.json"),
):
    (bad_run / name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
(bad_run / "industry_research_pack.md").write_text("# Too Short\n", encoding="utf-8")
for name in (
    "industry_scope_pack_validation.json",
    "formal_research_execution_validation.json",
    "stage_gate_pre_research_pack_validation.json",
    "research_pack_validation.json",
    "issue_analysis_validation.json",
    "deck_blueprint_validation.json",
    "template_registry_validation.json",
):
    (bad_artifacts / name).write_text(json.dumps({"is_valid": True, "error_count": 0}, ensure_ascii=False), encoding="utf-8")
(bad_artifacts / "industry_scope_pack.json").write_text(json.dumps({"schema_version": "industry_scope_pack_v1"}, ensure_ascii=False), encoding="utf-8")
(bad_artifacts / "source_reviews_validation.json").write_text(json.dumps({"is_valid": False, "error_count": 1}, ensure_ascii=False), encoding="utf-8")
research_result = validate_research_pack(bad_run / "industry_research_pack.md", run_dir=bad_run)
if not any("source_reviews_validation.json is_valid=false" in item for item in research_result["errors"]):
    raise SystemExit("research pack validation must surface failed source_reviews_validation: " + json.dumps(research_result, ensure_ascii=False))
issue_result = subprocess.run(
    [
        sys.executable,
        "scripts/validate_issue_analysis.py",
        "--issue-analysis",
        str(bad_run / "industry_issue_analysis.json"),
        "--research-pack",
        str(bad_run / "industry_research_pack.md"),
    ],
    text=True,
    capture_output=True,
)
if issue_result.returncode == 0:
    raise SystemExit("validate_issue_analysis must reject formal run with failed source_reviews_validation")
if "source_reviews_validation.json is_valid=false" not in (issue_result.stdout + issue_result.stderr):
    raise SystemExit(issue_result.stdout + issue_result.stderr)
deck_result = subprocess.run(
    [
        sys.executable,
        "scripts/validate_deck_blueprint.py",
        "--issue-analysis",
        str(bad_run / "industry_issue_analysis.json"),
        "--deck-blueprint",
        str(bad_run / "deck_blueprint.json"),
        "--template-registry",
        str(bad_run / "template_registry.json"),
    ],
    text=True,
    capture_output=True,
)
if deck_result.returncode == 0:
    raise SystemExit("validate_deck_blueprint must reject formal run with failed source_reviews_validation")
if "source_reviews_validation.json is_valid=false" not in (deck_result.stdout + deck_result.stderr):
    raise SystemExit(deck_result.stdout + deck_result.stderr)
compile_result = subprocess.run(
    [
        sys.executable,
        "scripts/compile_deck_blueprint.py",
        "--issue-analysis",
        str(bad_run / "industry_issue_analysis.json"),
        "--deck-blueprint",
        str(bad_run / "deck_blueprint.json"),
        "--template-registry",
        str(bad_run / "template_registry.json"),
        "--page-contract-output",
        str(bad_run / "page_evidence_contract.json"),
        "--renderer-spec-output",
        str(bad_run / "renderer_spec.json"),
    ],
    text=True,
    capture_output=True,
)
if compile_result.returncode == 0:
    raise SystemExit("compile_deck_blueprint must reject formal run with failed source_reviews_validation")
if "source_reviews_validation.json is_valid=false" not in (compile_result.stdout + compile_result.stderr):
    raise SystemExit(compile_result.stdout + compile_result.stderr)
PY

"$PYTHON_CMD" - <<'PY'
import json
import os
import subprocess
import sys
from pathlib import Path

from generate_replacement_dict import build_replacement_dict
from renderer_token_source import build_token_source

tmp = Path(os.environ["TMP_DIR"])
renderer = json.loads((tmp / "renderer_spec.json").read_text(encoding="utf-8"))
ppt_mapping = json.loads(Path("templates/ppt_mapping.json").read_text(encoding="utf-8"))
replacements = build_replacement_dict(
    build_token_source(renderer)["token_source"],
    ppt_mapping,
    keep_unmapped_empty=False,
    renderer_spec_path=tmp / "renderer_spec.json",
    ppt_mapping_path=Path("templates/ppt_mapping.json"),
)
replacement_path = tmp / "replacement_dict.json"
replacement_path.write_text(json.dumps(replacements, ensure_ascii=False, indent=2), encoding="utf-8")
result = subprocess.run(
    [
        sys.executable,
        "scripts/validate_replacement_dict.py",
        "--replacement-dict",
        str(replacement_path),
        "--renderer-spec",
        str(tmp / "renderer_spec.json"),
        "--ppt-mapping",
        "templates/ppt_mapping.json",
    ],
    text=True,
    capture_output=True,
)
if result.returncode != 0:
    raise SystemExit(result.stdout + result.stderr)

issue = json.loads((Path(os.environ["FIXTURES_DIR"]) / "valid_issue_analysis.json").read_text(encoding="utf-8"))
for item in issue["issue_analyses"]:
    if item.get("analysis_id") == "IA-001":
        item["downstream_permission"]["chart_allowed"] = False
bad_issue = tmp / "issue_analysis_chart_forbidden.json"
bad_issue.write_text(json.dumps(issue, ensure_ascii=False, indent=2), encoding="utf-8")
bad_contract = tmp / "page_evidence_contract_chart_forbidden.json"
subprocess.run(
    [
        sys.executable,
        "scripts/compile_deck_blueprint.py",
        "--issue-analysis",
        str(bad_issue),
        "--deck-blueprint",
        str(tmp / "deck_blueprint.json"),
        "--template-registry",
        str(tmp / "template_registry.json"),
        "--page-contract-output",
        str(bad_contract),
        "--renderer-spec-output",
        str(tmp / "renderer_spec_forbidden.json"),
    ],
    check=True,
    stdout=subprocess.DEVNULL,
)
result = subprocess.run(
    [
        sys.executable,
        "scripts/validate_page_evidence_contract.py",
        "--issue-analysis",
        str(bad_issue),
        "--deck-blueprint",
        str(tmp / "deck_blueprint.json"),
        "--page-contract",
        str(bad_contract),
    ],
    text=True,
    capture_output=True,
)
if result.returncode == 0:
    raise SystemExit("page evidence contract must fail when chart proof metrics lack chart_allowed permission")
if "downstream_permission.chart_allowed" not in result.stdout:
    raise SystemExit(result.stdout + result.stderr)
PY

"$PYTHON_CMD" - <<'PY'
import json
import tempfile
from pathlib import Path

from validate_formal_research_execution import validate as validate_formal_research_execution
from validate_formal_search_plan import validate as validate_formal_search_plan
from validate_industry_scope_pack import validate as validate_industry_scope_pack
from validate_source_archive import validate as validate_source_archive
from validate_source_reviews import validate as validate_source_reviews
from validate_stage_gate import validate_stage
from validate_run_state import validate_run_state

with tempfile.TemporaryDirectory() as tmp:
    run_dir = Path(tmp)
    artifacts = run_dir / "artifacts"
    artifacts.mkdir()

    (run_dir / "input_card.json").write_text("{}", encoding="utf-8")
    (artifacts / "input_card_validation.json").write_text(json.dumps({"is_valid": True}), encoding="utf-8")
    scope_pack = {
        "schema_version": "industry_scope_pack_v1",
        "meta": {"industry": "example"},
        "scope_summary": {
            "working_market": "example working market",
            "parent_market": "example parent market",
            "broader_market": "example broader market",
            "adjacent_markets": ["adjacent category"],
        },
        "market_definitions": {
            "narrow_definition": {
                "included_segments": ["core segment"],
                "excluded_segments": ["adjacent category"],
                "use_case": "market sizing / competitive share",
            },
            "broad_definition": {
                "included_segments": ["core segment"],
                "additional_segments": ["adjacent extension"],
                "use_case": "trend discussion / product ecosystem",
            },
        },
        "ambiguous_boundaries": [
            {
                "item": "adjacent extension",
                "why_ambiguous": "It may be classified in the parent category or adjacent category.",
                "research_treatment": "Track separately until formal sources reconcile scope.",
            }
        ],
        "data_hierarchy": [
            {"level": 1, "metric_scope": "broader market", "can_be_compared_with": ["same scope"], "cannot_be_compared_with": ["working market"]},
            {"level": 2, "metric_scope": "parent market", "can_be_compared_with": ["same parent scope"], "cannot_be_compared_with": ["platform GMV"]},
            {"level": 3, "metric_scope": "working market", "can_be_compared_with": ["same working scope"], "cannot_be_compared_with": ["brand ranking"]},
        ],
        "unvalidated_leads": [
            {
                "lead": "A source lead may contain a numerical market-size datapoint.",
                "claim_type": "market_size",
                "source_hint": "example source",
                "must_validate": ["Confirm definition, period, geography, and methodology."],
            }
        ],
        "required_reconciliations": [
            {
                "topic": "working market size scope",
                "why_it_matters": "Different sources may include adjacent extensions.",
                "formal_research_requirement": "Record source definition before promoting any metric.",
            }
        ],
        "formal_research_seed_questions": [
            "What is the current market size under narrow and broad definitions?",
            "Which segments are included by each source?",
            "Which source definitions cannot be compared directly?",
        ],
        "do_not_use_as_claims": True,
    }
    scope_errors, scope_warnings = validate_industry_scope_pack(scope_pack)
    assert not scope_errors, scope_errors
    (artifacts / "industry_scope_pack.json").write_text(json.dumps(scope_pack, ensure_ascii=False, indent=2), encoding="utf-8")
    (artifacts / "industry_scope_pack_validation.json").write_text(json.dumps({"is_valid": True, "errors": [], "warnings": scope_warnings}, ensure_ascii=False), encoding="utf-8")
    polluted_scope = json.loads(json.dumps(scope_pack))
    polluted_scope["scope_summary"]["working_market"] = "example market is 100亿元 and already validated"
    polluted_errors, _ = validate_industry_scope_pack(polluted_scope)
    assert any("numeric finding appears outside unvalidated_leads" in item for item in polluted_errors), polluted_errors
    no_gap_scope = json.loads(json.dumps(scope_pack))
    no_gap_scope["ambiguous_boundaries"] = []
    no_gap_scope["required_reconciliations"] = []
    no_gap_scope["scope_confidence_rationale"] = "No material category boundary ambiguity was identified from the brief at scoping stage."
    no_gap_scope["reconciliation_policy"] = "No material metric-scope conflict was identified at scoping stage; formal research will still record source definitions."
    no_gap_errors, _ = validate_industry_scope_pack(no_gap_scope)
    assert not no_gap_errors, no_gap_errors
    missing_policy_scope = json.loads(json.dumps(no_gap_scope))
    missing_policy_scope["scope_confidence_rationale"] = ""
    missing_policy_scope["reconciliation_policy"] = ""
    missing_policy_errors, _ = validate_industry_scope_pack(missing_policy_scope)
    assert any("scope_confidence_rationale" in item for item in missing_policy_errors), missing_policy_errors
    assert any("reconciliation_policy" in item for item in missing_policy_errors), missing_policy_errors

    plan = {
        "schema_version": "formal_search_plan_v1",
        "meta": {"industry": "example"},
        "industry_scope_pack": {"artifact_path": "artifacts/industry_scope_pack.json"},
        "issue_search_plan": [
            {
                "issue_area": "market_size_growth",
                "subissue": "current_market_size",
                "research_question": "What is the current market size?",
                "priority": "high",
                "search_instructions": [{"instruction_id": "FS-001", "query": "sector market size formal source", "purpose": "Find a current market-size source."}],
            },
            {
                "issue_area": "industry_structure",
                "subissue": "value_chain",
                "research_question": "Where does value accrue?",
                "priority": "high",
                "search_instructions": [{"instruction_id": "FS-002", "query": "sector value chain formal source", "purpose": "Find value-chain economics support."}],
            },
        ],
    }
    (artifacts / "formal_search_plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    plan_errors, plan_warnings = validate_formal_search_plan(plan)
    assert not plan_errors, plan_errors
    assert any("high-priority issue has only" in item for item in plan_warnings), plan_warnings
    (artifacts / "formal_search_plan_validation.json").write_text(json.dumps({"is_valid": True, "errors": [], "warnings": plan_warnings}, ensure_ascii=False), encoding="utf-8")
    invalid_plan = json.loads(json.dumps(plan))
    invalid_plan["issue_search_plan"][1]["search_instructions"][0]["instruction_id"] = "FS-001"
    invalid_plan["issue_search_plan"][1]["search_instructions"][0]["query"] = "<industry> placeholder"
    plan_errors, _ = validate_formal_search_plan(invalid_plan)
    assert any("duplicate instruction_id" in item for item in plan_errors), plan_errors
    assert any("placeholder" in item for item in plan_errors), plan_errors
    bad_taxonomy_plan = json.loads(json.dumps(plan))
    bad_taxonomy_plan["issue_search_plan"][0]["subissue"] = "made_up_subissue"
    plan_errors, _ = validate_formal_search_plan(bad_taxonomy_plan)
    assert any("Valid subissues for 'market_size_growth'" in item for item in plan_errors), plan_errors
    (artifacts / "search_log.md").write_text(
        """# Search Log

## Search Attempts

### Search 1
- Query: example industry definition
- Provider: WebSearch
- Search Stage: broad_discovery
- Result Count: 5
- Selected Sources: https://example.com/scope
- Dimension: industry_definition_scope
- Opened / Reviewed: yes
- Source Locator / Raw Excerpt: section 1 explains the relevant industry boundary and source leads.

### Search 2
- Query: sector market size formal source
- Provider: WebSearch
- Search Stage: formal_research_execution
- Search Instruction IDs: FS-001
- Result Count: 4
- Selected Sources: https://example.com/market-size
- Dimension: market_size_growth
- Opened / Reviewed: yes
- Source Locator / Raw Excerpt: table 2 contains current market size and scope definition.

### S-003
- Query: sector value chain formal source
- Provider: WebSearch
- Search Stage: formal_research_execution
- Search Instruction IDs: FS-002
- Result Count: 4
- Selected Sources: https://example.com/value-chain
- Dimension: industry_structure
- Opened / Reviewed: yes
- Source Locator / Raw Excerpt: section 3 describes value chain economics and margin pools.
""",
        encoding="utf-8",
    )
    source_reviews = {
        "schema_version": "source_reviews_v1",
        "reviews": [
            {"source_review_id": "SRC-001", "url": "https://example.com/market-size", "title": "Example market size report", "locator": "table 2, current market-size row with geography and scope columns", "excerpt": "The report gives a current market-size datapoint with geography and scope.", "search_attempt_ids": ["S-002"], "evidence_ids": ["EV-001"], "usable_as_evidence": True},
            {"source_review_id": "SRC-002", "url": "https://example.com/value-chain", "title": "Example value chain report", "locator": "section 3, value-chain economics paragraph and margin-pool discussion", "excerpt": "The source describes where value accrues across the example industry chain.", "search_attempt_ids": ["S-003"], "evidence_ids": ["EV-002"], "usable_as_evidence": True},
        ],
    }
    (artifacts / "source_reviews.json").write_text(json.dumps(source_reviews, ensure_ascii=False, indent=2), encoding="utf-8")
    archive_dir = artifacts / "source_archive"
    archive_dir.mkdir()
    (archive_dir / "SRC-001.md").write_text(
        "# SRC-001 Snapshot\n\nURL: https://example.com/market-size\n\nLocator: table 2.\n\nReviewed excerpt: The report gives a current market-size datapoint with geography and source scope; this snapshot preserves the reviewed table context for audit.\n",
        encoding="utf-8",
    )
    (archive_dir / "SRC-002.md").write_text(
        "# SRC-002 Snapshot\n\nURL: https://example.com/value-chain\n\nLocator: section 3.\n\nReviewed excerpt: The source describes where value accrues across the example industry chain and supports a caveated value-chain finding.\n",
        encoding="utf-8",
    )
    source_archive_index = {
        "schema_version": "source_archive_index_v1",
        "created_at": "2026-06-07T10:10:00",
        "entries": [
            {"source_review_id": "SRC-001", "url": "https://example.com/market-size", "title": "Example market size report", "archive_status": "excerpt_snapshot", "archive_path": "artifacts/source_archive/SRC-001.md", "captured_at": "2026-06-07T10:10:00", "locator": "table 2", "reviewed_excerpt": "The report gives a current market-size datapoint with geography and scope."},
            {"source_review_id": "SRC-002", "url": "https://example.com/value-chain", "title": "Example value chain report", "archive_status": "excerpt_snapshot", "archive_path": "artifacts/source_archive/SRC-002.md", "captured_at": "2026-06-07T10:11:00", "locator": "section 3", "reviewed_excerpt": "The source describes where value accrues across the example industry chain."},
        ],
    }
    (archive_dir / "source_archive_index.json").write_text(json.dumps(source_archive_index, ensure_ascii=False, indent=2), encoding="utf-8")
    report = {
        "schema_version": "formal_research_execution_report_v1",
        "formal_research_completed_at": "2026-06-07T10:00:00",
        "search_log": "artifacts/search_log.md",
        "issue_results": [
            {"result_id": "FR-001", "issue_area": "market_size_growth", "subissue": "current_market_size", "research_question": "What is the current market size?", "status": "supported", "search_instruction_ids": ["FS-001"], "search_attempt_ids": ["S-002"], "source_discovery_attempt_ids": ["S-001"], "selected_source_urls": ["https://example.com/market-size"], "source_review_ids": ["SRC-001"], "evidence_ids": ["EV-001"], "metric_ids": ["MET-001"], "findings_summary": "Current market size is source-backed with explicit scope.", "limitations": [], "research_pack_handling": "Promote to Evidence Ledger and Metric Reconciliation."},
            {"result_id": "FR-002", "issue_area": "industry_structure", "subissue": "value_chain", "research_question": "Where does value accrue?", "status": "thin", "search_instruction_ids": ["FS-002"], "search_attempt_ids": ["S-003"], "source_discovery_attempt_ids": ["S-001"], "selected_source_urls": ["https://example.com/value-chain"], "source_review_ids": ["SRC-002"], "evidence_ids": ["EV-002"], "metric_ids": [], "findings_summary": "Value-chain economics are directionally supported.", "limitations": ["Quantified profit-pool data is not available."], "research_pack_handling": "Use as a caveated industry structure finding."},
        ],
        "coverage_summary": {"covered_issue_areas": ["market_size_growth", "industry_structure"], "thin_or_unresolved_subissues": ["industry_structure/value_chain"]},
    }
    (artifacts / "formal_research_execution_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    errors, warnings = validate_formal_research_execution(report, plan, artifacts / "search_log.md")
    assert not errors, errors
    (artifacts / "formal_research_execution_validation.json").write_text(json.dumps({"is_valid": True, "errors": [], "warnings": warnings}, ensure_ascii=False), encoding="utf-8")
    archive_result = validate_source_archive(source_reviews_path=artifacts / "source_reviews.json", source_archive_index_path=archive_dir / "source_archive_index.json", run_dir=run_dir)
    assert archive_result["is_valid"], archive_result
    (artifacts / "source_archive_validation.json").write_text(json.dumps(archive_result, ensure_ascii=False), encoding="utf-8")
    source_result = validate_source_reviews(artifacts / "source_reviews.json", search_log_path=artifacts / "search_log.md", formal_research_execution_report_path=artifacts / "formal_research_execution_report.json", source_archive_index_path=archive_dir / "source_archive_index.json", run_dir=run_dir)
    assert source_result["is_valid"], source_result
    assert not any("S-001" in item for item in source_result["warnings"]), source_result
    weak_reviews = json.loads(json.dumps(source_reviews))
    weak_reviews["reviews"][0]["limitations"] = ["This page is a repost without methodology and should remain lead-only."]
    (artifacts / "source_reviews_weak.json").write_text(json.dumps(weak_reviews, ensure_ascii=False, indent=2), encoding="utf-8")
    weak_result = validate_source_reviews(artifacts / "source_reviews_weak.json", search_log_path=artifacts / "search_log.md", formal_research_execution_report_path=artifacts / "formal_research_execution_report.json", source_archive_index_path=archive_dir / "source_archive_index.json", run_dir=run_dir)
    assert not weak_result["is_valid"], weak_result
    assert any("weak-source marker" in item for item in weak_result["errors"]), weak_result
    weak_reviews["reviews"][0]["methodology_locator"] = "Original report methodology and table 2 were reviewed directly."
    (artifacts / "source_reviews_weak_with_original.json").write_text(json.dumps(weak_reviews, ensure_ascii=False, indent=2), encoding="utf-8")
    recovered_result = validate_source_reviews(artifacts / "source_reviews_weak_with_original.json", search_log_path=artifacts / "search_log.md", formal_research_execution_report_path=artifacts / "formal_research_execution_report.json", source_archive_index_path=archive_dir / "source_archive_index.json", run_dir=run_dir)
    assert recovered_result["is_valid"], recovered_result
    alias_reviews = json.loads(json.dumps(source_reviews))
    alias_reviews["source_reviews"] = alias_reviews.pop("reviews")
    (artifacts / "source_reviews_alias.json").write_text(json.dumps(alias_reviews, ensure_ascii=False, indent=2), encoding="utf-8")
    alias_result = validate_source_reviews(artifacts / "source_reviews_alias.json", search_log_path=artifacts / "search_log.md", formal_research_execution_report_path=artifacts / "formal_research_execution_report.json", source_archive_index_path=archive_dir / "source_archive_index.json", run_dir=run_dir)
    assert alias_result["is_valid"], alias_result
    assert alias_result["review_count"] == 2, alias_result
    (artifacts / "source_reviews_validation.json").write_text(json.dumps(source_result, ensure_ascii=False), encoding="utf-8")
    stage_result = validate_stage("pre_research_pack", run_dir, None)
    assert stage_result["is_valid"], stage_result
    (artifacts / "stage_gate_pre_research_pack_validation.json").write_text(json.dumps(stage_result, ensure_ascii=False), encoding="utf-8")
    state = validate_run_state(run_dir)
    assert state["current_stage"] == "RESEARCH_PACK_MISSING_OR_FAILED", state
    (run_dir / "industry_research_pack.md").write_text("validated research pack body", encoding="utf-8")
    (artifacts / "research_pack_validation.json").write_text(json.dumps({"is_valid": True, "errors": [], "warnings": []}, ensure_ascii=False), encoding="utf-8")
    (run_dir / "industry_issue_analysis.json").write_text("{}", encoding="utf-8")
    (artifacts / "issue_analysis_validation.json").write_text(json.dumps({"is_valid": True, "errors": [], "warnings": []}, ensure_ascii=False), encoding="utf-8")
    (artifacts / "gate_retry_state.json").write_text(
        json.dumps(
            {
                "schema_version": "gate_retry_state_v1",
                "gates": {
                    "issue_analysis": {
                        "status": "blocked",
                        "failed_validation_count": 4,
                        "max_repair_cycles": 3,
                        "last_errors": ["older issue-analysis failure"],
                    }
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    state = validate_run_state(run_dir)
    assert state["current_stage"] == "TEMPLATE_REGISTRY_MISSING_OR_FAILED", state

    invalid_report = json.loads(json.dumps(report))
    invalid_report["issue_results"][0]["search_attempt_ids"] = ["S-001"]
    errors, _ = validate_formal_research_execution(invalid_report, plan, artifacts / "search_log.md")
    assert any("expected formal_research" in item for item in errors), errors

    fs_as_attempt_report = json.loads(json.dumps(report))
    fs_as_attempt_report["issue_results"][0]["search_attempt_ids"] = ["FS-001"]
    errors, _ = validate_formal_research_execution(fs_as_attempt_report, plan, artifacts / "search_log.md")
    assert any("FS-xxx is a planned search instruction" in item for item in errors), errors
    assert any("search_attempt_ids must contain actual S-xxx" in item for item in errors), errors

    bad_structure_report = {"issue_results": [{}]}
    errors, _ = validate_formal_research_execution(bad_structure_report, plan, artifacts / "search_log.md")
    assert any("formal_research_execution_report.skeleton.json" in item for item in errors), errors
    assert any("copy issue_area, subissue, and research_question" in item for item in errors), errors
PY

if IB_SKILL_ALLOW_PPT_ONLY_DEBUG=1 bash run_pipeline.sh \
  --no-research-gate \
  --debug-reason "Research completed - generate PPT from validated renderer spec" \
  --renderer-spec "$TMP_DIR/missing_renderer_spec.json" >/dev/null 2>"$TMP_DIR/bad_debug_reason.err"; then
  echo "run_pipeline.sh must reject research/delivery shortcut debug reasons" >&2
  exit 1
fi
grep -q "research/delivery shortcut" "$TMP_DIR/bad_debug_reason.err"

echo "Contract tests passed."

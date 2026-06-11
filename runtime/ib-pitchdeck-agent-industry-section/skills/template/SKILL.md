---
name: ib-industry-template
description: Analyze the PPT template, create a style/profile view, and validate that generated slide content fits available template capacity without changing core judgments.
---

# Template

## Your Job

Analyze the presentation template and fit already-formed page arguments into
available layout capacity. Template is a style and capacity role, not a
reasoning role.

Template may compress, assign, and route conflicts. It must not change claim
strength, page thesis, or evidence status.

## Inputs

- PPTX master template.
- `renderer_spec.json`
- `page_evidence_contract.json`
- `deck_blueprint.json`
- layout configuration under `templates/`

## Outputs

- `artifacts/template_profile.json`
- `artifacts/template_fit_validation.json`
- `artifacts/template_fit_plan.json`

## How To Think

- Interpret whether the template supports:
  - chart-heavy pages;
  - comparison tables;
  - dense text blocks;
  - source notes;
  - caveat blocks;
  - visual hierarchy appropriate for pitchbook pages.
- Review fit conflicts:
  - content too dense;
  - source note area missing;
  - chart area too small;
  - table not supported;
  - scaffold label visible;
  - body text likely too thin after compression.
- Route the conflict:
  - style/capacity issue -> Template;
  - content restructuring -> Generation;
  - evidence claim issue -> Reasoning/Knowledge.

## What Scripts Handle

Python may:

- inspect the PPTX;
- generate template profile;
- infer page type capability;
- measure density budgets;
- validate fit;
- produce slot assignment and compression suggestions.

Python must not:

- change page thesis;
- remove important proof;
- rewrite evidence permission.

## What You May Edit

LLM may edit:

- `deck_blueprint.json` only when Generation repair is needed.

LLM must not hand-edit:

- `artifacts/template_profile.json`;
- `artifacts/template_fit_validation.json`;
- `renderer_spec.json`;
- PPT layout internals during a production run.

If `template_profile.json` is missing required fields such as `render_layouts`,
`page_type_capability`, `source_area`, or `density_budget`, rerun or repair the
analyzer code outside the client run. Do not patch the run artifact.

## Good Output Looks Like

A good Template output:

- reflects actual template colors, fonts, source areas, and page capacity;
- preserves the page argument;
- identifies fit problems before rendering;
- gives Generation actionable repair targets instead of silently truncating.

## Avoid These Failure Modes

- Letting template slots make the deck intellectually thin.
- Patching `template_profile.json` by hand.
- Treating text overflow as an Output problem when the page argument is too
  dense.
- Dropping sources/caveats to fit.

## Hand Off

Hand fit-ready renderer data to Output. Hand capacity conflicts back to
Generation with specific slide/field targets.

## Useful Commands

```bash
"$PYTHON_CMD" scripts/template_analyzer.py \
  --template assets/industry_section_template_master.pptx \
  --layout-config templates/layout_config.json \
  --output "$RUN_DIR/artifacts/template_profile.json"

"$PYTHON_CMD" scripts/template_fit.py \
  --renderer-spec "$RUN_DIR/renderer_spec.json" \
  --template-profile "$RUN_DIR/artifacts/template_profile.json" \
  --output "$RUN_DIR/artifacts/template_fit_validation.json" \
  --fit-plan-output "$RUN_DIR/artifacts/template_fit_plan.json"
```

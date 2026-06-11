---
name: ib-industry-template
description: Analyze the PPT template, create a style/profile view, and validate that generated slide content fits available template capacity without changing core judgments.
---

# Template

Owns template analysis and capacity fit after page arguments exist and before
deterministic rendering.

## Outputs

- `artifacts/template_profile.json`
- `artifacts/template_fit_validation.json`

## Responsibilities

- Identify template colors, fonts, layout rules, source areas, chart/table
  capabilities, and information density.
- Fit renderer spec content into available layout capacity.
- Report capacity conflicts back to Generation, not Output.

## Does Not Do

- Does not change page thesis.
- Does not change evidence permission or claim strength.
- Does not remove key proof just to make a slide fit.
- Does not render final PPT.

## Commands

```bash
"$PYTHON_CMD" scripts/template_analyzer.py \
  --template assets/industry_section_template_master.pptx \
  --layout-config templates/layout_config.json \
  --output "$RUN_DIR/artifacts/template_profile.json"

"$PYTHON_CMD" scripts/template_fit.py \
  --renderer-spec "$RUN_DIR/renderer_spec.json" \
  --template-profile "$RUN_DIR/artifacts/template_profile.json" \
  --output "$RUN_DIR/artifacts/template_fit_validation.json"
```

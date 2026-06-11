---
name: ib-industry-generation
description: Turn validated banker reasoning into page arguments, slide drafts, deck_blueprint.json, page evidence contracts, and renderer specs without changing evidence status or bypassing template rules.
---

# Generation

Owns page argument and deck blueprint. It is the page-editor layer, not the PPT
render layer.

## Outputs

- `deck_blueprint.json`
- `page_evidence_contract.json` (derived)
- `renderer_spec.json` (derived)

Preferred reasoning input:

- `artifacts/page_argument_pack.json`

## Responsibilities

- Consume `artifacts/page_argument_pack.json` where available.
- Convert page arguments into conclusion-led slide drafts and `deck_blueprint.json`.
- Define each slide's client question, page thesis, main message, body blocks,
  visual intent, source use, caveats, and open questions.
- Use `template_registry.json` for available page types and active fields.
- Compile derived artifacts with scripts.

## Does Not Do

- Does not invent facts.
- Does not upgrade weak evidence.
- Does not hand-write `page_evidence_contract.json` or `renderer_spec.json`.
- Does not make template capacity the reason to delete core logic.

## Commands

```bash
"$PYTHON_CMD" scripts/extract_template_registry.py \
  --output "$RUN_DIR/template_registry.json"

"$PYTHON_CMD" scripts/validate_deck_blueprint.py \
  --deck-blueprint "$RUN_DIR/deck_blueprint.json" \
  --issue-analysis "$RUN_DIR/industry_issue_analysis.json" \
  --template-registry "$RUN_DIR/template_registry.json" \
  --layout-budget templates/layout_budget.json \
  --output "$RUN_DIR/artifacts/deck_blueprint_validation.json"

"$PYTHON_CMD" scripts/compile_deck_blueprint.py \
  --issue-analysis "$RUN_DIR/industry_issue_analysis.json" \
  --deck-blueprint "$RUN_DIR/deck_blueprint.json" \
  --template-registry "$RUN_DIR/template_registry.json" \
  --page-contract-output "$RUN_DIR/page_evidence_contract.json" \
  --renderer-spec-output "$RUN_DIR/renderer_spec.json"
```

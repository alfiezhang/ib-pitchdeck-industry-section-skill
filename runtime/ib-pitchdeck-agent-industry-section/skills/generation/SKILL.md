---
name: ib-industry-generation
description: Turn validated banker reasoning into page arguments, slide drafts, deck_blueprint.json, page evidence contracts, and renderer specs without changing evidence status or bypassing template rules.
---

# Generation

## Your Job

Turn banker reasoning into page arguments and slide drafts. This role is the
page editor: it decides how the industry story should be presented before the
template is fitted and before PPT is rendered.

Generation does not do research, upgrade evidence, run template analysis, or
render PPT.

## Inputs

- `artifacts/page_argument_pack.json`
- `industry_issue_analysis.json`
- `artifacts/research_evidence_db.json`
- `template_registry.json`

## Outputs

- `deck_blueprint.json`
- `page_evidence_contract.json` (derived)
- `renderer_spec.json` (derived)

## How To Think

- Convert each page argument into a slide thesis:
  - client question;
  - headline;
  - main message;
  - supporting body blocks;
  - visual intent;
  - caveat or diligence angle.
- Make slides conclusion-led, not memo excerpts.
- Preserve evidence status:
  - supported claims can anchor headlines;
  - directional evidence belongs in body/context;
  - caveats belong in caveat/diligence blocks.
- Decide which proof belongs on the page and which belongs only in notes.
- Keep enough body density for a pitchbook page. Do not over-compress because a
  template slot looks small; let Template report capacity conflicts later.
- Avoid repetitive slides that all say "market is attractive" without distinct
  evidence.

## What Scripts Handle

Python may:

- extract template registry;
- validate active fields and evidence references;
- compile `page_evidence_contract.json`;
- compile `renderer_spec.json`;
- describe valid fields when a template field is wrong.

Python must not:

- write page theses;
- decide investor relevance;
- delete core content to fit a layout.

## What You May Edit

LLM may edit:

- `deck_blueprint.json`, including headline, message, body blocks, visual intent,
  source use, and caveats.

LLM must not hand-edit:

- `page_evidence_contract.json`;
- `renderer_spec.json`;
- `replacement_dict.json`;
- PPT files.

## Good Output Looks Like

A good Generation output has:

- one clear page question per slide;
- a headline that states a defensible point of view;
- body copy with enough proof and specificity;
- charts/tables tied to the thesis;
- source use and caveats that match evidence strength;
- no invented facts.

## Avoid These Failure Modes

- Turning the research pack into thin bullet summaries.
- Letting the fixed 8-slide template dictate the story.
- Using unsupported metrics in headlines.
- Writing pages that are all caveats because Reasoning was evidence-limited.
- Guessing placeholder names instead of using template registry/field tools.

## Hand Off

Hand off the blueprint and compiled artifacts to Template. If the page argument
is too thin, return to Reasoning or Research instead of padding slides.

## Useful Commands

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

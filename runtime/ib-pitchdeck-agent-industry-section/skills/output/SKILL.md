---
name: ib-industry-output
description: Render and finalize the PowerPoint output through the deterministic IB industry section pipeline. Use only after upstream evidence, reasoning, generation, template, and QC gates are current.
---

# Output

## Your Job

Render and finalize the PPT through the deterministic pipeline. Output is the
delivery mechanic. It does not research, reason, design pages, fit templates, or
patch upstream content.

The core question is: **can the current validated artifacts be rendered into a
client-ready PPT, and if not, which upstream role owns the repair?**

## Inputs

- `page_evidence_contract.json`
- `renderer_spec.json`
- `artifacts/template_profile.json`
- `artifacts/template_fit_validation.json`
- current pre-PPT gate
- current final-delivery requirements

## Outputs

- `replacement_dict.json`
- `industry_section_filled.pptx`
- `industry_section_filled_clean.pptx`
- `filled_ppt_validation.json`
- `artifacts/final_delivery_validation.json`

## How To Think

- Confirm upstream gates are current before rendering.
- Interpret render/final-delivery failures and route them:
  - missing upstream evidence -> Knowledge/Research/Reasoning;
  - unsupported claim -> Generation/Reasoning;
  - template capacity -> Template/Generation;
  - token/placeholder/rendering issue -> Output;
  - final client-ready false -> QC.
- Report final status accurately. An existing PPT file is not enough.

## What Scripts Handle

Python owns rendering:

- generate replacement dictionary;
- fill PPT tokens;
- generate charts/tables/visuals where supported;
- clean remaining tokens;
- validate filled deck;
- run final delivery validation;
- write latest-run pointers.

## What You May Edit

LLM must not hand-edit:

- `replacement_dict.json`;
- generated PPTX files;
- `renderer_spec.json`;
- validation artifacts.

If output fails, repair upstream artifacts or route through QC. Do not create
custom `python-pptx`, PptxGenJS, Keynote, LibreOffice, or screenshot-based PPT
scripts to bypass the package.

## Good Output Looks Like

A good Output result has:

- deterministic pipeline provenance;
- no unresolved placeholders;
- clean final PPT path;
- final delivery validation with `client_ready=true`;
- clear blocked status when client-ready is false.

## Avoid These Failure Modes

- Calling a debug PPT complete.
- Hand-writing `replacement_dict.json`.
- Patching the PPT to hide upstream evidence or template problems.
- Reporting `industry_section_filled_clean.pptx` without final delivery pass.

## Hand Off

If render succeeds, hand final PPT and validation summary to the user. If it
fails, hand a precise repair target to QC or the upstream owner role.

## Useful Command

```bash
"$PYTHON_CMD" scripts/pipeline.py render --run-dir "$RUN_DIR"
```

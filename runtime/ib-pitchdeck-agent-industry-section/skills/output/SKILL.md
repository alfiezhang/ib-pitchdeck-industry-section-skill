---
name: ib-industry-output
description: Render and finalize the PowerPoint output through the deterministic IB industry section pipeline. Use only after upstream evidence, reasoning, generation, template, and QC gates are current.
---

# Output

Owns deterministic PPT rendering and final delivery. It does not perform
research, reasoning, or page design.

## Inputs

- `page_evidence_contract.json`
- `renderer_spec.json`
- `artifacts/template_profile.json`
- `artifacts/template_fit_validation.json`
- current pre-PPT gate

## Outputs

- `replacement_dict.json`
- `industry_section_filled.pptx`
- `industry_section_filled_clean.pptx`
- `filled_ppt_validation.json`
- `artifacts/final_delivery_validation.json`

## Rules

- Use `scripts/pipeline.py render --run-dir "$RUN_DIR"` as the formal path.
- Do not hand-write `replacement_dict.json`.
- Do not create ad-hoc `python-pptx`, PptxGenJS, Keynote, or LibreOffice scripts.
- Do not call a debug or failed PPT client-ready.
- If output fails, report the gate and route repair to QC/Generation/Template as appropriate.

## Command

```bash
"$PYTHON_CMD" scripts/pipeline.py render --run-dir "$RUN_DIR"
```

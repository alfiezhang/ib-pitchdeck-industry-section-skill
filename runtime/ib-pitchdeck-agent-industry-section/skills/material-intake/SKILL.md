---
name: ib-industry-material-intake
description: Ingest user-provided text, PDFs, PPTs, URLs, Excel files, reports, and notes for the IB industry section workflow. Classify materials and create a clean normalized input card without adding industry conclusions.
---

# Material Intake

Turns user materials into auditable project inputs. This role answers: what did
the user provide, what does each source say, and what can be used as project
context?

## Inputs

- User text brief.
- User-provided PDF/PPT/Excel/Word/text files.
- User-provided URLs.
- User-curated industry reports.
- Company materials such as websites, product pages, filings, or news releases.

## Outputs

- `input_card.json`
- Future artifacts:
  - `artifacts/material_manifest.json`
  - `artifacts/material_extracts.json`
  - `artifacts/source_classification.json`

## Source Types

Use these categories when classifying materials:

- `project_specific_material`
- `user_curated_industry_report`
- `company_material`
- `web_search_result`
- `market_data_source`
- `repository_retrieval`
- `manual_url_ingestion`

## Rules

- Transcribe user-provided project facts faithfully.
- Preserve locators: page, slide, table, URL, section, timestamp if available.
- User-curated reports are high-priority candidate sources, not automatically true.
- Do not infer peers, market size, valuation, growth, buyer universe, or page conclusions.
- Do not start industry research from a raw PDF/PPT; extract facts first.
- Use deterministic extraction scripts; do not infer content labels from filenames or model
  guesses.

## Validation

```bash
"$PYTHON_CMD" scripts/ingest_materials.py \
  --brief-text "<exact user brief, or omit when using files/URLs>" \
  --file "<path/to/file1>" --file "<path/to/file2>" \
  --url "<https://source1>" --url "<https://source2>" \
  --output-manifest "$RUN_DIR/artifacts/material_manifest.json" \
  --output-extracts "$RUN_DIR/artifacts/material_extracts.json" \
  --output-source-classification "$RUN_DIR/artifacts/source_classification.json"

"$PYTHON_CMD" scripts/validate_material_manifest.py \
  --material-manifest "$RUN_DIR/artifacts/material_manifest.json" \
  --output "$RUN_DIR/artifacts/material_manifest_validation.json"

"$PYTHON_CMD" scripts/validate_material_extracts.py \
  --material-extracts "$RUN_DIR/artifacts/material_extracts.json" \
  --output "$RUN_DIR/artifacts/material_extracts_validation.json"

"$PYTHON_CMD" scripts/validate_input_card.py \
  --input-card "$RUN_DIR/input_card.json" \
  --output "$RUN_DIR/artifacts/input_card_validation.json"
```

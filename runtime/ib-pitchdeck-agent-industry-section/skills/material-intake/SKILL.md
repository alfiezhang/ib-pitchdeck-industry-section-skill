---
name: ib-industry-material-intake
description: Ingest user-provided text, PDFs, PPTs, URLs, Excel files, reports, and notes for the IB industry section workflow. Classify materials and create a clean normalized input card without adding industry conclusions.
---

# Material Intake

## Your Job

Turn user-provided material into a clean, auditable project starting point. This
role answers only:

- What did the user provide?
- What type of source is each item?
- Which statements are explicit user/project facts?
- Which items are candidate external sources to review later?
- What is unknown or unavailable from the provided material?

Do not begin industry research or pitch reasoning in this role.

## Inputs

- User text brief.
- User-provided PDF/PPT/Excel/Word/text files.
- User-provided URLs.
- User-curated industry reports.
- Company materials such as websites, product pages, filings, or news releases.

## Outputs

- `input_card.json`
- `artifacts/material_manifest.json`
- `artifacts/material_extracts.json`
- `artifacts/source_classification.json`

## How To Think

- Classify each source by use case:
  - project-specific material;
  - user-curated industry report;
  - company material;
  - public web source;
  - market data source;
  - repository retrieval;
  - manual URL ingestion.
- Separate explicit user facts from your interpretation.
- Preserve access level: user-provided, public, repository, inaccessible, or
  model inference.
- Identify locators that future roles need: page, slide, table, URL, section,
  timestamp, file name, or sheet name.
- Flag missing context without filling it in.
- Decide whether a user-curated report should feed Knowledge immediately or be
  reviewed later by Research as external evidence.

## What Scripts Handle

Use scripts for extraction, source manifests, URL fetches, and validation. Do
not manually parse large PDFs/PPTs/Excels when an extraction script exists.

Python may:

- extract text from files and URLs;
- generate `material_manifest` and `material_extracts`;
- validate `input_card.json` structure;
- preserve source IDs and locators.

Python must not:

- infer target industry conclusions;
- add peers, market sizes, M&A cases, or valuation logic;
- decide source credibility beyond basic availability/access metadata.

## What You May Edit

LLM may edit:

- `input_card.json`, but only by faithful transcription from user-provided
  material;
- extracted material summaries when the extractor output is noisy, as long as
  locators and provenance remain clear.

LLM must not edit:

- validation artifacts;
- script output IDs solely to satisfy downstream checks;
- project facts by adding unstated assumptions.

## Good Output Looks Like

A good Material Intake output lets the next role answer:

- what the user actually said;
- which facts came from which material;
- which materials are project-specific versus external context;
- which facts remain unverified;
- which source locators can be audited later.

## Avoid These Failure Modes

- Treating a user-provided industry report as automatically true.
- Inferring target competitors, market size, growth, or buyer logic from a brief.
- Losing locators while summarizing PDFs/PPTs.
- Mixing project facts with public evidence.
- Starting web research before the provided material has been extracted.

## Hand Off

Hand off to Knowledge/Scoping with a clean `input_card.json`, source
classification, extracted material facts, and explicit unknowns. Do not hand off
industry conclusions.

## Useful Commands

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

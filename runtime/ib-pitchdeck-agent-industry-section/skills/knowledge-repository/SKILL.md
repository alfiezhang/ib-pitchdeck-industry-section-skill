---
name: ib-industry-knowledge-repository
description: Maintain the current-project evidence database and future reusable research repository. Use for facts, metrics, source provenance, conflicts, unknowns, and evidence-pack export; do not use for judgment or searching.
---

# Knowledge Repository

## Your Job

Maintain the factual store. This role is not a researcher, banker, page editor,
or PPT renderer. It receives material extracts, reviewed sources, repository
hits, and formal research outputs, then turns them into auditable facts,
metrics, conflicts, limitations, and unknowns.

The core question is: **what can the project fact base safely say, with what
source, scope, and limitation?**

## Inputs

- `input_card.json`
- `artifacts/material_manifest.json`
- `artifacts/material_extracts.json`
- `artifacts/source_reviews.json`
- `artifacts/formal_research_execution_report.json`
- `artifacts/coverage_accounting.json`
- `artifacts/repository_retrieval.json`

## Outputs

- `artifacts/research_evidence_db.json` as the evidence source of truth.
- `industry_research_pack.md` as a generated readable export.
- long-lived repository entries under `$IB_PITCHDECK_REPOSITORY_DIR` or
  `~/.ib-pitchdeck-agent-industry-section/repository`.

## How To Think

- Decide whether a reviewed source row becomes:
  - source material only;
  - extract/fact candidate;
  - metric candidate;
  - conflict/limitation;
  - unknown or gap.
- Preserve source type, locator, period, geography, unit, scope, and method.
- Distinguish:
  - user-provided company facts;
  - user-curated report facts;
  - public web facts;
  - repository facts;
  - model inference;
  - unresolved hypotheses.
- Identify metric comparability problems, such as GMV vs retail sales, platform
  sample vs all-channel market, narrow vs broad category, or 2024 vs MAT data.
- Keep `coverage_accounting` out of evidence rows. Not-executed or
  accounting-only search rows belong in gaps, not facts.

## What Scripts Handle

Use scripts to build, validate, export, retrieve, ingest, dedupe, and index
repository material.

Python may:

- create DB skeletons from reviewed source material;
- assign and preserve row structure;
- export `industry_research_pack.md` from DB;
- validate required fields;
- ingest reusable repository materials.

Python must not:

- decide whether a fact is pitch-relevant;
- write banker conclusions;
- turn weak evidence into supported judgment.

## What You May Edit

LLM may edit:

- `artifacts/research_evidence_db.json`, especially extract summaries,
  limitations, metric scopes, conflict notes, and use permissions.

LLM must not hand-edit:

- `industry_research_pack.md` as the source of truth;
- validation artifacts;
- source archive snapshots;
- coverage accounting into evidence facts.

## Good Output Looks Like

A good Knowledge output has:

- source-level traceability;
- explicit metric scope and units;
- clear distinction between facts, metrics, unknowns, conflicts, and gaps;
- no page claims or banker conclusions;
- enough raw material for Reasoning to make judgment without rereading every
  source.

## Avoid These Failure Modes

- Treating search coverage rows as evidence.
- Converting unreviewed snippets into facts.
- Losing source locators during summarization.
- Mixing platform/channel data with all-market claims.
- Exporting a polished memo instead of an evidence binder.

## Hand Off

Hand off the evidence DB and generated research pack to Reasoning. Reasoning
decides what matters; Knowledge preserves what is supportable.

## Useful Commands

```bash
"$PYTHON_CMD" scripts/build_research_evidence_db.py \
  --input-card "$RUN_DIR/input_card.json" \
  --scope-pack "$RUN_DIR/artifacts/industry_scope_pack.json" \
  --formal-search-plan "$RUN_DIR/artifacts/formal_search_plan.json" \
  --formal-research-execution-report "$RUN_DIR/artifacts/formal_research_execution_report.json" \
  --source-reviews "$RUN_DIR/artifacts/source_reviews.json" \
  --material-manifest "$RUN_DIR/artifacts/material_manifest.json" \
  --material-extracts "$RUN_DIR/artifacts/material_extracts.json" \
  --repository-sources "$RUN_DIR/artifacts/repository_retrieval.json" \
  --output "$RUN_DIR/artifacts/research_evidence_db.json"

"$PYTHON_CMD" scripts/validate_research_evidence_db.py \
  --research-evidence-db "$RUN_DIR/artifacts/research_evidence_db.json" \
  --output "$RUN_DIR/artifacts/research_evidence_db_validation.json"

"$PYTHON_CMD" scripts/export_research_pack_from_db.py \
  --research-evidence-db "$RUN_DIR/artifacts/research_evidence_db.json" \
  --output "$RUN_DIR/industry_research_pack.md"

"$PYTHON_CMD" scripts/repository_retrieve.py \
  --industry-tag "<industry-tag>" --max-results 50 \
  --output "$RUN_DIR/artifacts/repository_retrieval.json"

"$PYTHON_CMD" scripts/repository_ingest.py \
  --material-manifest "$RUN_DIR/artifacts/material_manifest.json" \
  --material-extracts "$RUN_DIR/artifacts/material_extracts.json"
```

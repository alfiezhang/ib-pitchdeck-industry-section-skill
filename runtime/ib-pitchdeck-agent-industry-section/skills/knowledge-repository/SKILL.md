---
name: ib-industry-knowledge-repository
description: Maintain the current-project evidence database and future reusable research repository. Use for facts, metrics, source provenance, conflicts, unknowns, and evidence-pack export; do not use for judgment or searching.
---

# Knowledge Repository

Owns the factual store. It receives material extracts and reviewed research
outputs, then keeps facts, metrics, conflicts, limitations, and unknowns clean.

## Main Artifact

- `artifacts/research_evidence_db.json` is the evidence source of truth.
- `industry_research_pack.md` is a generated readable export.

## Responsibilities

- Preserve source type, access level, locator, period, geography, metric scope,
  and limitations.
- Distinguish user-provided company facts, user-curated report facts, public web
  facts, repository facts, model inference, and unresolved hypotheses.
- Export the Markdown research pack from the DB.

## Does Not Do

- Does not search the web.
- Does not write investment or transaction judgments.
- Does not write deck copy.
- Does not hand-edit `industry_research_pack.md` as the source of truth.

## Commands

```bash
"$PYTHON_CMD" scripts/build_research_evidence_db.py \
  --input-card "$RUN_DIR/input_card.json" \
  --scope-pack "$RUN_DIR/artifacts/industry_scope_pack.json" \
  --formal-search-plan "$RUN_DIR/artifacts/formal_search_plan.json" \
  --formal-research-execution-report "$RUN_DIR/artifacts/formal_research_execution_report.json" \
  --source-reviews "$RUN_DIR/artifacts/source_reviews.json" \
  --material-manifest "$RUN_DIR/artifacts/material_manifest.json" \
  --material-extracts "$RUN_DIR/artifacts/material_extracts.json" \
  --output "$RUN_DIR/artifacts/research_evidence_db.json"

"$PYTHON_CMD" scripts/validate_research_evidence_db.py \
  --research-evidence-db "$RUN_DIR/artifacts/research_evidence_db.json" \
  --output "$RUN_DIR/artifacts/research_evidence_db_validation.json"

"$PYTHON_CMD" scripts/export_research_pack_from_db.py \
  --research-evidence-db "$RUN_DIR/artifacts/research_evidence_db.json" \
  --output "$RUN_DIR/industry_research_pack.md"
```

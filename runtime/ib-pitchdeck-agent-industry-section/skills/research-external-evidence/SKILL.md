---
name: ib-industry-research-external-evidence
description: Execute public and user-provided evidence collection for the IB industry section workflow, including formal search planning, SearXNG/manual URL/PDF ingestion, source reviews, source archive, formal execution accounting, and evidence DB handoff.
---

# Research / External Evidence

Collects public and reviewable external evidence. Research does not own final
pitch judgment.

## Outputs

- `artifacts/formal_search_plan.json`
- `artifacts/search_log.md`
- `artifacts/source_reviews.json`
- `artifacts/source_archive/source_archive_index.json`
- `artifacts/formal_research_execution_report.json`
- evidence inputs for `artifacts/research_evidence_db.json`

## Search Discipline

- `FS-xxx` = planned search instruction / coverage row.
- `S-xxx` = actual executed search attempt.
- `SRC-xxx` = reviewed source.
- Planned query is not evidence.
- Search result snippet is not evidence.
- Only reviewed sources with locators/excerpts can support evidence.

## Source Priority

1. User-provided PDFs, URLs, reports, and files that can be reviewed and archived.
2. Agent-native Web Search for LLM-led research.
3. Script fallback search via `scripts/web_search.py --provider auto`.
4. Manual URL ingestion when exact URLs are supplied.

Provider order for script fallback is configured in
`templates/source_registry.json` and currently prioritizes SearXNG.

## Commands

```bash
"$PYTHON_CMD" scripts/build_formal_search_plan_skeleton.py \
  --input-card "$RUN_DIR/input_card.json" \
  --scope-pack "$RUN_DIR/artifacts/industry_scope_pack.json" \
  --output "$RUN_DIR/artifacts/formal_search_plan.json"

"$PYTHON_CMD" scripts/append_search_attempt.py \
  --search-log "$RUN_DIR/artifacts/search_log.md" \
  --query "<exact query actually searched>" \
  --stage formal_research_execution \
  --fs-id FS-001 \
  --selected-source "<reviewed URL or source locator>" \
  --result-count 5 \
  --opened-reviewed yes \
  --locator-excerpt "<locator and short excerpt or limitation>"

"$PYTHON_CMD" scripts/build_source_reviews_skeleton.py \
  --search-log "$RUN_DIR/artifacts/search_log.md" \
  --input-card "$RUN_DIR/input_card.json" \
  --output "$RUN_DIR/artifacts/source_reviews.json"

"$PYTHON_CMD" scripts/build_formal_research_execution_report_skeleton.py \
  --formal-search-plan "$RUN_DIR/artifacts/formal_search_plan.json" \
  --search-log "$RUN_DIR/artifacts/search_log.md" \
  --source-reviews "$RUN_DIR/artifacts/source_reviews.json" \
  --include-unexecuted \
  --output "$RUN_DIR/artifacts/formal_research_execution_report.json"
```

## Loop 2: Evidence Supplementation

Reasoning may create `research_request_queue` items. Research executes public
evidence collection and returns new sources to Knowledge, then Reasoning
re-judges. Research must not convert hypotheses into conclusions.

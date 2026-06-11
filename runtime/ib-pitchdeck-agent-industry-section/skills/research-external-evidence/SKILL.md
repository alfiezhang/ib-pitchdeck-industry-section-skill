---
name: ib-industry-research-external-evidence
description: Execute public and user-provided evidence collection for the IB industry section workflow, including formal search planning, SearXNG/manual URL/PDF ingestion, source reviews, source archive, formal execution accounting, and evidence DB handoff.
---

# Research / External Evidence

## Your Job

Collect reviewable public and user-provided evidence. Research owns source
collection and evidence usability, not final pitch judgment.

The core question is: **what publicly reviewable material can support or limit
the pitch reasoning, and what remains unresearched?**

## Inputs

- `artifacts/industry_scope_pack.json`
- `artifacts/boundary_research_requests.json`
- `artifacts/research_request_queue.json`
- user-provided reports, URLs, files, and manual sources
- repository retrieval results

## Outputs

- `artifacts/formal_search_plan.json`
- `artifacts/search_log.md`
- `artifacts/source_reviews.json`
- `artifacts/source_archive/source_archive_index.json`
- `artifacts/formal_research_execution_report.json`
- `artifacts/coverage_accounting.json`
- evidence inputs for `artifacts/research_evidence_db.json`

## How To Think

- Treat taxonomy rows as a coverage audit, not as equal-depth mandatory search.
- Convert coverage needs into executable search batches:
  - clean Chinese query;
  - clean English query when useful;
  - source-specific query for reports, filings, associations, data platforms, or
    listed peers;
  - reconciliation query when definitions may conflict.
- Prefer source-specific searches over generic keyword soup.
- Treat `LLM_REWRITE_REQUIRED` query rows as unfinished workspace. Rewrite them
  into real, human-searchable queries before running any search.
- Open and review sources before marking them usable.
- Decide source use scope:
  - primary evidence;
  - directional evidence;
  - context only;
  - lead only;
  - rejected/unusable.
- Record what a source supports and what it does not support.
- Source quality is a research/QC judgment. Script warnings about reposts,
  snippets, mirrors, or unavailable methodology are cues for review, not an
  automatic accept/reject decision.
- Account for unexecuted or unavailable coverage honestly.

## What Scripts Handle

Python may:

- build plan skeletons and coverage maps;
- append search attempts to logs;
- create source-review skeletons from actual reviewed attempts;
- archive reviewed source snapshots;
- build formal execution accounting.

Python must not:

- decide that a source is credible enough for a claim;
- decide source quality solely from URL/domain/string markers;
- invent S-IDs for unexecuted searches;
- convert planned queries into evidence.

## Source Priority

1. User-provided PDFs, URLs, reports, and files that can be reviewed and
   archived.
2. Agent-native Web Search for LLM-led research.
3. Script fallback search via `scripts/web_search.py --provider auto`.
4. Manual URL ingestion when exact URLs are supplied.

Script fallback provider order is configured in
`templates/source_registry.json`, currently prioritizing SearXNG.

## What You May Edit

LLM may edit:

- actual query text in `formal_search_plan.json`;
- source review fields such as locator, excerpt, use scope, source quality, and
  limitations;
- formal execution result handling where evidence is thin or unavailable.

LLM must not:

- create fake `S-xxx` IDs;
- mark opened/reviewed without actual review;
- attach unexecuted search rows to source reviews;
- write deck claims or issue conclusions.

## Good Output Looks Like

A good Research output has:

- executable, human-searchable queries;
- reviewed sources with locators/excerpts;
- clear source usability and limitations;
- planned-vs-actual accounting;
- no contamination of evidence with unexecuted coverage rows.

## Avoid These Failure Modes

- Query strings copied from taxonomy labels instead of written for search.
- Treating search snippets as evidence.
- Running 10 searches and implying 40+ coverage rows were researched.
- Filling source reviews just to satisfy IDs.
- Letting coverage accounting dominate the evidence binder.

## Hand Off

Hand off reviewed sources and formal execution accounting to Knowledge. If
evidence is thin, hand off explicit gaps and research requests; do not disguise
thin evidence as supported findings.

## Useful Commands

```bash
"$PYTHON_CMD" scripts/build_formal_search_plan_skeleton.py \
  --input-card "$RUN_DIR/input_card.json" \
  --scope-pack "$RUN_DIR/artifacts/industry_scope_pack.json" \
  --output "$RUN_DIR/artifacts/formal_search_plan.json"

"$PYTHON_CMD" scripts/validate_formal_search_plan.py \
  --formal-search-plan "$RUN_DIR/artifacts/formal_search_plan.json" \
  --output "$RUN_DIR/artifacts/formal_search_plan_validation.json"

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
  --output "$RUN_DIR/artifacts/formal_research_execution_report.json" \
  --coverage-accounting "$RUN_DIR/artifacts/coverage_accounting.json"
```

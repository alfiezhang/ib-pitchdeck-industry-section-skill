---
name: ib-industry-research-pack
description: Create the source-disciplined research evidence pack and issue analysis pack for the IB industry section skill, including source reviews, archive, evidence/metric reconciliation, and issue-by-issue banker judgments.
---

# Research Pack

Build the factual and analytical base for the IB industry section. This stage is
not PPT writing.

Main outputs:

- `artifacts/industry_scope_pack.json`
- `artifacts/formal_search_plan.json`
- `artifacts/search_log.md`
- `artifacts/source_reviews.json`
- `artifacts/source_archive/source_archive_index.json`
- `artifacts/formal_research_execution_report.json`
- `artifacts/research_evidence_db.json` (source of truth)
- `industry_research_pack.md` (generated readable export)
- `industry_issue_analysis.json`

The research pack is an evidence binder, not a narrative memo. Preserve
source-level extracts, metrics, scope limits, conflicts, and gaps so issue
analysis has material to reason from.

## Read Only What You Need

Always read:

1. `references/scope_boundary.md`
2. `references/execution_discipline.md`

Read on demand:

- `references/research_policy.md` for source policy, search discipline, and
  source tiering.
- `references/industry_research_pack_template.md` when filling the pack.
- `references/search_log_template.md` only if the helper cannot create/append
  the search log.

Do not bulk-read schemas, tests, or fixtures as content examples.

## Runtime

Set one interpreter and use it everywhere:

```bash
PYTHON_CMD="$(bash setup.sh --print-python)"
```

Formal research requires real search capability: agent Web Search or fallback
providers (`tavily-python` / `ddgs`). If no search is available, use only
user-provided/offline sources that can be reviewed and archived; otherwise stop
at the research blocker.

## Stage Order

Use `scripts/workflow.py next --run-dir "$RUN_DIR"` before moving downstream.
For a new brief, the research stage runs in this order:

1. `input_card.json`
2. `industry_scope_pack.json`
3. `formal_search_plan.json`
4. real `S-xxx` search attempts in `search_log.md`
5. `source_reviews.json`
6. `source_archive/source_archive_index.json`
7. `formal_research_execution_report.json`
8. `artifacts/research_evidence_db.json`
9. `industry_research_pack.md`
10. `industry_issue_analysis.json`

Do not write the execution report before real formal searches, source reviews,
and source archive exist.

## Input Card

`input_card.json` is transcription-only:

- copy user-provided target, transaction type, industry, geography, language,
  and brief facts faithfully;
- do not add inferred peers, sources, topics, market size, risks, or valuation;
- mark optional target facts from management/user brief as unverified unless
  externally validated later.

Validate before research:

```bash
"$PYTHON_CMD" scripts/validate_input_card.py \
  --input-card "$RUN_DIR/input_card.json" \
  --output "$RUN_DIR/artifacts/input_card_validation.json"
```

## Industry Scoping

Purpose: define what is being researched. Do not form conclusions.

First draft `llm_definition_draft` from the brief and model knowledge only.
Then run 3-6 broad discovery searches to validate/refine vocabulary, category
boundaries, parent/adjacent markets, metric scope, value-chain boundary,
regulation/standard terminology, or business-model boundary.

Broad discovery queries should use scope terms such as `definition`,
`classification`, `included segments`, `adjacent market`, `taxonomy`, `metric
scope`, `methodology`, `value chain boundary`. Avoid market size, CAGR, share,
ranking, valuation, M&A, specific-year, or page-thesis terms.

Numbers found during scoping are `unvalidated_leads` only. They cannot be used
in issue analysis or slides until formal research validates them.

Validate:

```bash
"$PYTHON_CMD" scripts/validate_industry_scope_pack.py \
  --scope-pack "$RUN_DIR/artifacts/industry_scope_pack.json" \
  --output "$RUN_DIR/artifacts/industry_scope_pack_validation.json"
```

## Formal Search Plan

Build the full taxonomy skeleton first:

```bash
"$PYTHON_CMD" scripts/build_formal_search_plan_skeleton.py \
  --input-card "$RUN_DIR/input_card.json" \
  --scope-pack "$RUN_DIR/artifacts/industry_scope_pack.json" \
  --output "$RUN_DIR/artifacts/formal_search_plan.json"
```

Then edit only the industry-specific research questions, query strings,
purposes, and source hints. Do not delete canonical issue/subissue rows.

Important: full taxonomy is a coverage audit, not an equal-depth search
mandate. A planned `FS-xxx` row is not evidence, and a planned query is not a
real search. Each row carries an execution expectation:

- `deep_search`: material row; normally needs 2+ actual `S-xxx` attempts or a
  clear explanation why fewer were sufficient/unavailable.
- `light_search`: relevant row; normally needs at least 1 actual `S-xxx`
  attempt.
- `accounting_only`: low-materiality row; may have zero searches, but must be
  accounted for later as not material/backlog and cannot support claims.

Thin coverage upstream leads to thin issue analysis and thin PPT pages. The fix
is better search execution or explicit coverage accounting, not fake `S-xxx`
IDs and not deleting planned rows.

The plan must not contain investment hypotheses, page headlines, or deck
conclusions.

Validate:

```bash
"$PYTHON_CMD" scripts/validate_formal_search_plan.py \
  --formal-search-plan "$RUN_DIR/artifacts/formal_search_plan.json" \
  --output "$RUN_DIR/artifacts/formal_search_plan_validation.json"
```

## Formal Searches And Search Log

Execute the planned `FS-xxx` instructions as real searches. Record each real
attempt as `S-xxx` immediately:

```bash
"$PYTHON_CMD" scripts/append_search_attempt.py \
  --search-log "$RUN_DIR/artifacts/search_log.md" \
  --query "<exact query actually searched>" \
  --stage formal_research_execution \
  --fs-id FS-001 \
  --selected-source "<exact opened/reviewed URL or offline source locator>" \
  --result-count 5 \
  --opened-reviewed yes \
  --locator-excerpt "<page/section/table plus short excerpt or limitation>"
```

Use `--provider user_attachment` or a clear equivalent when a user-provided
offline document substitutes for web search. Still record what was reviewed and
where the excerpt came from.

Rules:

- `FS-xxx` appears in `search_instruction_ids`.
- `S-xxx` appears in `search_attempt_ids`.
- Only actual formal/latest/peer searches can receive `S-xxx` IDs.
- Do not create `S-xxx` IDs for unexecuted planned `FS-xxx` rows.
- Broad-discovery `S-xxx` attempts stay in discovery/source-lead fields; do not
  reuse them as formal execution.
- Do not remove failed, thin, or unexecuted `FS-xxx` rows. Mark the result
  `executed_with_evidence`, `executed_no_usable_source`, `not_executed`,
  `not_material`, or `accounting_only` in formal execution accounting.
- If 10 actual formal searches were executed against 40+ planned rows, write
  that gap explicitly. The remaining rows go to coverage accounting/gap audit;
  they do not become source reviews, evidence, or slide claims.

## Source Reviews

Generate `SRC-xxx` skeletons from selected URLs/source locators:

```bash
"$PYTHON_CMD" scripts/build_source_reviews_skeleton.py \
  --search-log "$RUN_DIR/artifacts/search_log.md" \
  --output "$RUN_DIR/artifacts/source_reviews.json"
```

The LLM reviews each source and fills:

- exact URL / offline source locator;
- title / source owner;
- locator and excerpt/paraphrase;
- linked `S-xxx`;
- `evidence_use_tier`;
- `claim_use_scope`;
- candidate `EV-xxx` links if promoted later;
- honest `usable_as_evidence`.

Do not batch-fill `usable_as_evidence=true` or `false` to pass validation. A
lead, search snippet, root domain, unavailable report, unreviewed page, or weak
repost should not feed formal EV/MET rows.

First-pass validation:

```bash
"$PYTHON_CMD" scripts/validate_source_reviews.py \
  --source-reviews "$RUN_DIR/artifacts/source_reviews.json" \
  --search-log "$RUN_DIR/artifacts/search_log.md" \
  --output "$RUN_DIR/artifacts/source_reviews_validation.json"
```

## Source Archive

Archive every non-user source marked `usable_as_evidence=true`:

```bash
"$PYTHON_CMD" scripts/build_source_archive.py \
  --source-reviews "$RUN_DIR/artifacts/source_reviews.json" \
  --run-dir "$RUN_DIR" \
  --overwrite
```

Prefer saved PDFs or clean text/markdown snapshots when available. If the tool
surface cannot download the full source, save an `excerpt_snapshot` with URL,
title, `SRC-xxx`, captured time, locator, reviewed excerpt, and limitation note.
Do not fabricate full report/article text.

Validate:

```bash
"$PYTHON_CMD" scripts/validate_source_archive.py \
  --source-reviews "$RUN_DIR/artifacts/source_reviews.json" \
  --source-archive-index "$RUN_DIR/artifacts/source_archive/source_archive_index.json" \
  --run-dir "$RUN_DIR" \
  --output "$RUN_DIR/artifacts/source_archive_validation.json"
```

## Formal Research Execution

Build the report skeleton after search log, source reviews, and source archive:

```bash
"$PYTHON_CMD" scripts/build_formal_research_execution_report_skeleton.py \
  --formal-search-plan "$RUN_DIR/artifacts/formal_search_plan.json" \
  --search-log "$RUN_DIR/artifacts/search_log.md" \
  --source-reviews "$RUN_DIR/artifacts/source_reviews.json" \
  --include-unexecuted \
  --output "$RUN_DIR/artifacts/formal_research_execution_report.json"
```

The helper maps `FS-xxx`, `S-xxx`, and `SRC-xxx`. The LLM edits judgment fields:

- `status`
- `terminal_status`
- `downstream_permission`
- `findings_summary`
- `limitations`
- `research_pack_handling`
- real EV/MET links if already known

The execution report is planned-vs-actual coverage accounting. It must reconcile
every planned `FS-xxx` row with actual `S-xxx` searches. Do not claim all rows
were searched unless the search log contains corresponding actual attempts.

Validate:

```bash
"$PYTHON_CMD" scripts/validate_formal_research_execution.py \
  --report "$RUN_DIR/artifacts/formal_research_execution_report.json" \
  --formal-search-plan "$RUN_DIR/artifacts/formal_search_plan.json" \
  --search-log "$RUN_DIR/artifacts/search_log.md" \
  --output "$RUN_DIR/artifacts/formal_research_execution_validation.json"

"$PYTHON_CMD" scripts/validate_stage_gate.py \
  --stage pre_research_pack \
  --run-dir "$RUN_DIR" \
  --source-registry templates/source_registry.json \
  --output "$RUN_DIR/artifacts/stage_gate_pre_research_pack_validation.json"
```

If the gate fails, repair search/source/execution artifacts. Do not start the
research pack.

## Research Evidence Database

Build the source-of-truth JSON skeleton:

```bash
"$PYTHON_CMD" scripts/build_research_evidence_db.py \
  --input-card "$RUN_DIR/input_card.json" \
  --scope-pack "$RUN_DIR/artifacts/industry_scope_pack.json" \
  --formal-search-plan "$RUN_DIR/artifacts/formal_search_plan.json" \
  --formal-research-execution-report "$RUN_DIR/artifacts/formal_research_execution_report.json" \
  --source-reviews "$RUN_DIR/artifacts/source_reviews.json" \
  --output "$RUN_DIR/artifacts/research_evidence_db.json"
```

Diagnostic-only extraction workspace:

```bash
"$PYTHON_CMD" scripts/build_evidence_candidate_skeleton.py \
  --formal-research-execution-report "$RUN_DIR/artifacts/formal_research_execution_report.json" \
  --source-reviews "$RUN_DIR/artifacts/source_reviews.json" \
  --output "$RUN_DIR/artifacts/evidence_candidate_skeleton.json"
```

Use this helper only when EV/MET extraction is stuck or needs audit support. It
is not part of the main workflow path and should not delay DB authoring when the
database can be filled directly.

Fill `artifacts/research_evidence_db.json` as the binder:

- Formal Research Extracts
- Evidence Ledger
- Metric Reconciliation
- IB Issue Fact Inventory
- Metric conflicts and reconciliation logic
- Research gaps / unavailable evidence

Every promoted EV/MET row needs reviewed source support and scope limits. Do not
write page evidence packs here; deck blueprint and compiler own page contracts.

Validate:

```bash
"$PYTHON_CMD" scripts/validate_research_evidence_db.py \
  --research-evidence-db "$RUN_DIR/artifacts/research_evidence_db.json" \
  --output "$RUN_DIR/artifacts/research_evidence_db_validation.json"
```

Then export the readable Markdown pack:

```bash
"$PYTHON_CMD" scripts/export_research_pack_from_db.py \
  --research-evidence-db "$RUN_DIR/artifacts/research_evidence_db.json" \
  --output "$RUN_DIR/industry_research_pack.md"

"$PYTHON_CMD" scripts/validate_research_pack.py \
  --research-pack "$RUN_DIR/industry_research_pack.md" \
  --run-dir "$RUN_DIR" \
  --source-registry templates/source_registry.json \
  --output "$RUN_DIR/artifacts/research_pack_validation.json"
```

## Issue Analysis

Build the skeleton:

```bash
"$PYTHON_CMD" scripts/build_issue_analysis_skeleton.py \
  --research-evidence-db "$RUN_DIR/artifacts/research_evidence_db.json" \
  --formal-research-execution-report "$RUN_DIR/artifacts/formal_research_execution_report.json" \
  --output "$RUN_DIR/industry_issue_analysis.json"
```

Replace every `TODO_REPLACE...` placeholder with substantive banker analysis.
Issue analysis is not slide copy. Each analysis block should include:

- issue area and subissue;
- core statement;
- substantive analysis paragraph;
- supporting points tied to EV/MET IDs;
- sufficiency/status/limitations;
- downstream permissions for headline/body/chart use.

If evidence is weak, use `research_backlog` or caveated analysis; do not promote
the gap into a confident conclusion. Do not decide slide numbers, template
variants, or chart contracts here.

Validate:

```bash
"$PYTHON_CMD" scripts/normalize_issue_analysis.py \
  --input "$RUN_DIR/industry_issue_analysis.json" \
  --output "$RUN_DIR/industry_issue_analysis.json" \
  --report "$RUN_DIR/artifacts/issue_analysis_normalization.json"

"$PYTHON_CMD" scripts/validate_issue_analysis.py \
  --issue-analysis "$RUN_DIR/industry_issue_analysis.json" \
  --research-pack "$RUN_DIR/industry_research_pack.md" \
  --output "$RUN_DIR/artifacts/issue_analysis_validation.json"
```

If validation fails, read `artifacts/issue_analysis_validation.json.repair_plan`
and repair the named fields. Do not delete analysis blocks or move downstream to
avoid the issue-analysis gate.

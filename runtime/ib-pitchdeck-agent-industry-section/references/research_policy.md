# Research Policy

Use this file when a workflow starts from a brief, attachments, or an existing
research pack that the user wants to expand.

Before running any local script, select one runtime and reuse it:

```bash
PYTHON_CMD="$(python3 scripts/bootstrap_runtime.py --print-python)"
```

## Baseline

- Web/public-source research is mandatory unless the user already provided
  sufficient reviewable source materials and explicitly said not to expand them.
- Provided materials are high-priority inputs. User-provided PDFs, URLs,
  reports, filings, and company materials should be reviewed first, but they do
  not replace public source review for a formal delivery unless the user
  explicitly limits scope to offline/manual-source mode.
- Keep `input_card.json` transcription-only. Planner-inferred peers, sources,
  risks, or topics belong in the scope pack/search plan, not in the input card.
- The material is for `pre_mandate_transaction_pitch`: show sector credibility
  first, transaction relevance second, and selective target context only where
  supported.
- Broad discovery is scoping, not research synthesis. It defines the industry,
  vocabulary, category boundaries, reconciliation risks, and boundary-
  validation questions.
- Formal research execution is the research gate. The search plan itself is not
  a hypothesis gate, but it must cover every canonical issue/subissue so
  downstream issue analysis is not starved of source material.
- Full taxonomy coverage is a coverage audit, not proof that every row has been
  searched. Planned `FS-xxx` rows and planned query strings are not evidence.
  Evidence can only flow from actual `S-xxx` searches, reviewed `SRC-xxx`
  sources, and promoted `EV-xxx` / `MET-xxx` rows.

## Source Priority And Search Providers

Use source channels in this order:

1. User-provided PDFs, URLs, reports, files, and other materials that can be
   opened, logged, reviewed, archived, and caveated.
2. Agent-native Web Search for LLM-led industry boundary validation and formal
   research.
3. Configured graph/manual worker search, with provider order and source menus
   governed by `configs/source_registry.json` when a non-native worker is used.
4. Manual URL ingestion when search is rate-limited but exact source URLs are
   available.

Use unrestricted web search by default for ordinary exploratory queries. Add
domain constraints only when:

1. the user explicitly provided preferred domains or websites;
2. a source pack/domain was selected after broad discovery;
3. the operator deliberately requests a default-pack pass.

Never remove official, regulator, filing, company disclosure, or other
higher-authority domains merely to reduce a domain count. If research scope is
too broad, trim lower-authority media or aggregators first.

If the agent's native Web Search is rate-limited or unavailable, switch to a
configured graph worker or explicitly supplied source URLs/files and record the limitation in
`artifacts/research_graph_state.json`. Do not convert planned queries or model
memory into `S-xxx`, `SRC-xxx`, `EV-xxx`, or `MET-xxx` evidence.

## Industry Scope Pack And Search Plan

Create these artifacts before formal research execution:

- `artifacts/industry_scope_pack.json`
- `artifacts/industry_boundary_qc.json`
- `artifacts/industry_scope_pack_validation.json`
- `artifacts/formal_search_plan.json`
- `artifacts/coverage_map.json`
- `artifacts/executable_search_batch.json`
- `artifacts/research_graph_state.json`
- `artifacts/formal_search_plan_validation.json`

Recommended sequence:

1. Read `configs/source_registry.json` as a source menu only.
2. Draft a short industry boundary card from the brief and model knowledge
   only. It is a scope hypothesis, not evidence.
3. If needed, identify 1-5 boundary-validation questions in
   `boundary_validation_needed`. These questions should be definition/scope-
   oriented, not market-answer-oriented.
4. Record broad-discovery notes in the boundary QC workstream; do
   not hand-author compiled `search_log.md`.
5. Run broad discovery to verify/refine the boundary card and learn:
   - what the industry is called;
   - how narrowly it should be scoped;
   - parent/adjacent markets to exclude;
   - relevant geography and period terms;
   - likely source leads and peer/player categories.
   Do not use market-size, growth, CAGR, share, ranking, valuation, M&A, thesis, or specific-year query terms at this stage. Those belong in formal `FS-xxx` searches after the scope pack.
6. Write `artifacts/industry_scope_pack.json` with:
   - working market, parent market, and broader market;
   - `core`, `broad`, `adjacent`, and `excluded` category lists;
   - `must_reconcile` items that affect source scope, metric comparability, or page claims;
   - `boundary_validation_needed` only for material unresolved boundary questions;
   - `handoff_to_research` labels and exclusions.
   Keep it to a boundary card. Do not write a scoping memo, market findings, or a research plan.
7. Run Industry Boundary QC before formal research planning. QC must decide
   `pass`, `needs_scope_repair`, or `needs_boundary_validation`. If the QC
   artifact is missing or not `pass`, do not create formal research artifacts.
   Boundary QC may use small validation searches, but it must not become full
   market research.
8. Validate the scope pack after boundary QC has passed:
   ```bash
   "$PYTHON_CMD" scripts/qc/validators/scoping/validate_industry_scope_pack.py \
     --scope-pack artifacts/industry_scope_pack.json \
     --output artifacts/industry_scope_pack_validation.json
   ```
9. Prepare the research graph in one operator-facing step. This writes
   `artifacts/formal_search_plan.json`, `artifacts/coverage_map.json`,
   `artifacts/executable_search_batch.json`, and
   `artifacts/research_graph_state.json`; then edit executable queries in
   the executable batch using the scope pack:
   ```bash
   "$PYTHON_CMD" scripts/research-external-evidence/ib_research_graph.py prepare \
     --run-dir "$RUN_DIR"
   ```
   Use `configs/artifact_templates/formal_search_plan.template.json` for field meaning, not as a
   final copy/paste artifact.
   The formal plan is the coverage and evidence-need map. It must not contain
   `query` or `query_variants`. `executable_search_batch.json` is the
   researcher's workbench for actual source-specific Chinese/English queries.
   The skeleton intentionally emits `LLM_REWRITE_REQUIRED` query workspaces.
   Research must replace them with real, executable, source-specific queries
   before validation or search execution. Do not execute searches from the
   mechanical coverage-map wording.
10. Validate `artifacts/formal_search_plan.json` with
   `scripts/qc/validators/research/validate_formal_search_plan.py` before executing formal searches.

Do not put confirmed market size, growth rate, share, ranking, valuation,
competitive landscape, or page-ready claims in the scope pack. Any number found
during broad discovery is an unvalidated lead until formal research execution
promotes it.

The search plan must be issue/subissue based and must include every canonical
subissue from the same taxonomy used by `industry_issue_analysis.json`:

- `market_size_growth`
- `demand_customer_logic`
- `industry_structure`
- `key_trends_drivers`
- `competitive_landscape`
- `competitive_dynamics`
- `pitch_relevance_target_context`

Do not write investment hypotheses in the search plan. For every
issue/subissue, write a research question, evidence need, source hint, and
planned FS instruction. Author exact executable query strings only in
`artifacts/executable_search_batch.json`. Do not delete low-relevance subissues.
Use `execution_expectation` to decide depth:

- `deep_search`: material row; normally needs multiple actual searches or a
  documented unavailable result.
- `light_search`: relevant row; normally needs at least one actual search.
- `accounting_only`: low-materiality row; may be accounted for without search,
  but cannot support claims.

If a subissue turns out to be weak, irrelevant, unavailable, or not comparable
after real searching, keep it in the formal execution report with limitations.
Do not create fake `S-xxx` IDs for unexecuted rows and do not delete planned
taxonomy coverage to make the report look complete.

## Formal Research Execution

After the lightweight plan, run formal/latest/peer searches against the chosen
queries and sources. Record every attempt, opened source, source locator,
faithful excerpt, candidate evidence row, candidate metric row, and limitation
inside `artifacts/research_graph_state.json`. `FS-xxx` IDs are planned
instructions only. A real `S-xxx` attempt exists only when a research unit has
an actual executed attempt in the state graph.

While executing research, write each useful output directly into one of two
state fields:

- `audited_metric`: required for every key number, ranking, growth rate,
  market size, share, penetration rate, capacity, volume, price, regulatory
  threshold, or chart datapoint. Each promoted `MET-xxx` row must carry
  indicator, value, unit, period, geography, source, original locator, short
  excerpt, and audit note.
- `research_context`: open_deep_research-style background notes with source
  URLs/titles/summaries. These notes can guide wording and context but cannot
  support key numbers, chart data, hard claims, or client-facing source notes
  unless promoted into `EV-xxx` / `MET-xxx`.

Do not hand-author `search_log.md`, `source_archive_index.json`, or
`formal_research_execution_report.json`; they are compiled from
`research_graph_state.json`. `research_evidence_db.json` is different: build a
Knowledge skeleton from validated execution/archive artifacts, then have
Knowledge LLM author source usability, EV/MET rows, metric audit, conflicts,
and claim-use limits.

For `research_context`, do not force an audit-grade snapshot. Record the search
attempt, source URL/title, short note/summary, and limitations in
`research_graph_state.json`; the compiler will mark the source
`archive_status=research_context` and keep it out of evidence promotion.

Treat `FS-xxx`, `S-xxx`, and `SRC-xxx` as internal traceability IDs. The
operator-facing write surface is `research_context`, `metrics`, and `evidence`.
Do not make a researcher manage IDs as the main workflow; the compiler assigns
or reconciles missing internal IDs.

For `audited_metric` and promoted `EV-xxx` evidence, use full saved source text
where available. If full-page archive fails but Research did open and read the
page, the archive is only `needs_research_verification` until Research completes
a second-pass check. Reopen the page, search a distinctive quote, find the
original report or credible repost, then update the matching source entry in
`research_graph_state.json` with `secondary_verification=verified`,
`secondary_verification_notes`, and
`research_archive_status=manual_verified_excerpt`.
Also record `verification_method` as one of `opened_original_url`,
`user_provided_pdf`, `archived_copy_reviewed`, `official_filing_reviewed`, or
`manual_source_reviewed`.

Only full saved sources and Research-declared `manual_verified_excerpt` rows can
feed promoted EV/MET evidence. `secondary_verification=verified` alone is not
enough; Research must also make the archive-status decision explicitly. Search
snippets, `research_context`, and `needs_research_verification` rows stay as
context/leads/gaps.

`saved_text`, `saved_html`, and `saved_pdf` mean a full source capture or
equivalent archived source with an explicit `capture_method` such as
`full_page_capture`, `downloaded_pdf`, `user_provided_file`, or
`archived_copy_reviewed`. A long raw excerpt, scraped snippet, or copied search
result is not a saved source.

```bash
"$PYTHON_CMD" scripts/research-external-evidence/ib_research_graph.py compile \
  --state "$RUN_DIR/artifacts/research_graph_state.json" \
  --formal-search-plan "$RUN_DIR/artifacts/formal_search_plan.json" \
  --run-dir "$RUN_DIR"

"$PYTHON_CMD" scripts/qc/validators/research/validate_source_archive.py \
  --source-archive-index "$RUN_DIR/artifacts/source_archive/source_archive_index.json" \
  --run-dir "$RUN_DIR" \
  --output "$RUN_DIR/artifacts/source_archive_validation.json"

"$PYTHON_CMD" scripts/qc/validators/research/validate_formal_research_execution.py \
  --report "$RUN_DIR/artifacts/formal_research_execution_report.json" \
  --formal-search-plan "$RUN_DIR/artifacts/formal_search_plan.json" \
  --search-log "$RUN_DIR/artifacts/search_log.md" \
  --output "$RUN_DIR/artifacts/formal_research_execution_validation.json"
```

The compiler synchronizes `FS-xxx`, real `S-xxx`, archived/captured `SRC-xxx`,
execution status, and coverage accounting from one state source. It does not
author the Knowledge evidence DB. Candidate EV/MET rows in research state are
only candidates until Knowledge LLM promotes them in
`research_evidence_db.json`.

The generated/edited report should contain one `issue_results[]` entry per
planned instruction. It is a planned-vs-actual coverage ledger, not a narrative
research summary. Since the formal search plan covers the full taxonomy, this
report is where weak, unavailable, not-material, or unexecuted topics are
accounted for; do not remove them from the plan to avoid work:

- `result_id`: `FR-001`, `FR-002`, ...
- `issue_area` / `subissue`
- `research_question`
- `status`: `supported`, `thin`, `conflicting`, `not_comparable`,
  `insufficient`, or `unavailable_after_research`
- `terminal_status`: `executed_with_evidence`, `executed_no_usable_source`,
  `not_executed`, `not_material`, or `accounting_only`
- `downstream_permission`: `may_support_claim`, `contextual_only`,
  `research_backlog_only`, or `not_allowed`
- `search_instruction_ids`: `FS-xxx` instructions from the formal search plan
- `search_attempt_ids`: real formal/latest/peer `S-xxx` searches from
  `search_log.md` only; never put `FS-xxx` here
- `source_discovery_attempt_ids`: broad searches that discovered source leads
- `selected_source_urls`
- `source_review_ids`
- `evidence_ids` / `metric_ids` when already assigned
- `findings_summary`
- `limitations`
- `research_pack_handling`

Generate the execution report with `ib_research_graph.py compile`. Do not treat
compiled JSON as a hand-fill template. If an issue was weak, perform the search
and mark it weak in `research_graph_state.json`; do not pretend unsearched
issues were researched.

`selected_source_urls` means exact URLs actually opened/reviewed and archived in
`source_archive`; it is not a list of all search-result URLs. Leave unreviewed
leads in `search_log.md`.

Do not invent or reclassify `issue_area` / `subissue` in the execution report.
Copy `issue_area`, `subissue`, and `research_question` from the
`formal_search_plan.issue_search_plan[]` item associated with each executed
`FS-xxx`. The execution report records execution results; the search plan owns
the issue/subissue taxonomy choice.

If a broad-discovery search only found vocabulary or a source lead, keep it in
`source_discovery_attempt_ids`. Do not move it into `search_attempt_ids`, delete
it, or relabel it to pass validation.

When formal execution validation fails, check actual search execution first:
missing `S-xxx` attempts mean the fix is more formal search, not taxonomy
rewriting or report reshaping.

If only 10 actual searches were executed out of 40+ planned `FS-xxx` rows, the
execution report must say so in `coverage_summary` and `fs_row_execution_status`.
The unexecuted rows must be marked `not_executed`, `not_material`, or
`accounting_only`. They cannot enter `source_archive`, `research_evidence_db`,
issue-analysis claims, or deck headlines as evidence.

Validate formal execution and source archive before writing the research pack:

```bash
"$PYTHON_CMD" scripts/qc/validators/research/validate_formal_search_plan.py \
  --formal-search-plan "$RUN_DIR/artifacts/formal_search_plan.json" \
  --output "$RUN_DIR/artifacts/formal_search_plan_validation.json"

"$PYTHON_CMD" scripts/qc/validators/research/validate_formal_research_execution.py \
  --report "$RUN_DIR/artifacts/formal_research_execution_report.json" \
  --formal-search-plan "$RUN_DIR/artifacts/formal_search_plan.json" \
  --search-log "$RUN_DIR/artifacts/search_log.md" \
  --output "$RUN_DIR/artifacts/formal_research_execution_validation.json"

"$PYTHON_CMD" scripts/qc/validators/research/validate_source_archive.py \
  --source-archive-index "$RUN_DIR/artifacts/source_archive/source_archive_index.json" \
  --run-dir "$RUN_DIR" \
  --output "$RUN_DIR/artifacts/source_archive_validation.json"

"$PYTHON_CMD" scripts/qc/validators/final/validate_stage_gate.py \
  --stage pre_research_pack \
  --run-dir "$RUN_DIR" \
  --source-registry configs/source_registry.json \
  --output "$RUN_DIR/artifacts/stage_gate_pre_research_pack_validation.json"
```

Do not write `industry_research_pack.md` by hand. After QC accepts the research
handoff for evidence extraction, build the machine-readable evidence database
first:

```bash
"$PYTHON_CMD" scripts/knowledge-repository/build_research_evidence_db.py \
  --input-card "$RUN_DIR/input_card.json" \
  --scope-pack "$RUN_DIR/artifacts/industry_scope_pack.json" \
  --formal-search-plan "$RUN_DIR/artifacts/formal_search_plan.json" \
  --formal-research-execution-report "$RUN_DIR/artifacts/formal_research_execution_report.json" \
  --source-archive-index "$RUN_DIR/artifacts/source_archive/source_archive_index.json" \
  --research-graph-state "$RUN_DIR/artifacts/research_graph_state.json" \
  --output "$RUN_DIR/artifacts/research_evidence_db.json"

"$PYTHON_CMD" scripts/qc/validators/knowledge/validate_research_evidence_db.py \
  --research-evidence-db "$RUN_DIR/artifacts/research_evidence_db.json" \
  --output "$RUN_DIR/artifacts/research_evidence_db_validation.json"

"$PYTHON_CMD" scripts/knowledge-repository/export_research_pack_from_db.py \
  --research-evidence-db "$RUN_DIR/artifacts/research_evidence_db.json" \
  --output "$RUN_DIR/industry_research_pack.md"

"$PYTHON_CMD" scripts/qc/validators/knowledge/validate_research_pack.py \
  --research-pack "$RUN_DIR/industry_research_pack.md" \
  --run-dir "$RUN_DIR" \
  --source-registry configs/source_registry.json \
  --output "$RUN_DIR/artifacts/research_pack_validation.json"
```

The JSON database is the source of truth. The Markdown pack is a generated
readable export and must be regenerated after DB edits. The LLM extracts
facts/metrics into the DB, promotes supported items into EV/MET rows, updates
issue fact status, and completes the gap audit before export/validation.

## Data Conflicts

When sources disagree on market size, growth, share, margin, valuation, or peer
metrics:

- preserve the conflicting numbers in Metric Reconciliation;
- record source scope, period, unit, geography, and denominator;
- choose a preferred number only when there is a clear authority/scope reason;
- otherwise use a range, caveat, or `conflicting` status;
- do not promote a conflicting metric into a confident headline/chart.

## Source Archive And Embedded Source Review

`search_log.md` records search execution. `source_archive/` records the opened
source material that Knowledge can inspect for promoted evidence. Ordinary
open_deep_research-style background notes are recorded as `research_context`
with URL/title/summary and do not require an audit-grade snapshot. Source-review
decisions live inside `artifacts/research_evidence_db.json` under embedded
source review/source material fields.

Root domains, search result snippets, or unreviewed pages are not formal
evidence. For `audited_metric` / promoted EV rows, archive only what was
actually opened/reviewed, with a URL, title, locator, excerpt/paraphrase, search
attempt ID, and limitations. For `research_context`, keep the source URL/title
and summary notes, but do not promote its numbers into Metric Reconciliation.

Inside `research_evidence_db.json`, `usable_as_evidence` is a source-quality
decision, not a formatting field. Set it to true only when the exact
page/report/PDF was opened, the locator and excerpt support the linked EV row,
and the source is acceptable for that claim's strength. Set it to false for
search snippets, root domains, unavailable reports, weak mirrors/reposts without
methodology, and pages that only identify a lead for later research. Do not
batch-convert missing values to true merely to pass validation.

Before setting the boolean in the evidence DB, assign a source-use tier:

- `core_evidence`: source can support a formal EV/MET row and may feed a chart
  or headline if the linked issue analysis permits it.
- `contextual_evidence`: source can support body-copy context or caveated
  implications, but should not be the sole basis for a headline or chart.
- `directional_only`: source can guide research or provide directional color,
  but do not promote its numbers into Metric Reconciliation unless corroborated.
- `lead_only`: source only suggests where to look next.
- `rejected`: source was reviewed and found unusable for this run.

Also write `claim_use_scope` in plain language. Examples: "historical category
definition only", "online GMV proxy, not all-channel market size", or
"peer product ranking disclosure only". This prevents a weak but opened source
from being overused downstream simply because `usable_as_evidence=true`.

Run graph compilation as an automatic build step after research state updates:

```bash
"$PYTHON_CMD" scripts/research-external-evidence/ib_research_graph.py compile \
  --state "$RUN_DIR/artifacts/research_graph_state.json" \
  --formal-search-plan "$RUN_DIR/artifacts/formal_search_plan.json" \
  --run-dir "$RUN_DIR"
```

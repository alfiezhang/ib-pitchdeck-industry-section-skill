# Research Policy

Use this file for public evidence collection and Knowledge handoff. It defines
evidence discipline; it is not a script-driven workplan.

## Non-Negotiables

- Formal client-ready delivery needs reviewable public evidence unless the user
  explicitly limits the work to user-provided/manual sources.
- Search snippets, model memory, root domains, and unopened URLs are leads, not
  evidence.
- Planned `FS-xxx` rows are coverage instructions. Real evidence can only flow
  from executed attempts, opened/reviewed sources, and Knowledge-promoted
  `EV-xxx` / `MET-xxx` rows.
- User-provided target metrics are unaudited project context unless independently
  verified by a reviewable external source.
- Do not hand-author `search_log.md`, `source_archive_index.json`, or
  `formal_research_execution_report.json`; they are compiled from
  `research_graph_state.json`.
- `research_evidence_db.json` is the Knowledge LLM-authored source of truth for
  usable facts, metrics, source limitations, conflicts, and claim-use scope.
- `industry_research_pack.md` is a readable export from the DB. Regenerate it
  after DB edits; do not repair it by hand.

## Source Priority

Use sources in this order:

1. User-provided PDFs, URLs, reports, files, and company materials that can be
   opened, logged, reviewed, and caveated.
2. Agent-native Web Search for boundary validation and formal research.
3. Configured graph/manual worker search using `configs/source_registry.json`.
4. Manual URL ingestion when search is rate-limited but exact source URLs are
   available.

Use unrestricted web search for exploration. Add domain constraints only for
explicit user domains, selected source packs, or deliberate source-specific
passes. Never drop official, regulator, filing, company-disclosure, or other
higher-authority domains merely to reduce source count.

If search/PDF capability is unavailable, stop before formal client-ready
rendering. Use manual-source mode only when exact reviewable sources are
provided, and record the limitation.

## Boundary And Planning

Before formal research:

- write `artifacts/industry_scope_pack.json` as a short boundary card;
- run Boundary QC and require `decision=pass`;
- prepare the research graph with `scripts/pipeline.py research-prepare`;
- let the LLM author executable queries in `artifacts/executable_search_batch.json`.

The scope pack must not contain market size, growth, share, ranking, valuation,
competitive conclusions, or page-ready claims. Boundary checks answer definition
and scope questions only.

`formal_search_plan.json` is a coverage/evidence-need map. It must not contain
final query strings. `executable_search_batch.json` is the only query-authoring
workbench.

The formal plan starts from the configured issue taxonomy and may add material
industry-specific evidence needs. Treat taxonomy coverage as an audit menu, not
as a requirement to perform equal-depth research for every row.

## Execution State

Record actual research activity in `artifacts/research_graph_state.json`:

- executed search attempts;
- opened sources and locators;
- archive/capture status;
- reviewed excerpts or summaries;
- candidate evidence and metric rows;
- source limitations, conflicts, and unavailable results.

Run `scripts/pipeline.py research-compile` after state updates. The compiler
synchronizes internal IDs, search log, source archive index, formal execution
report, and coverage accounting. It must not author the Knowledge DB or decide
claim strength.

For unexecuted, weak, unavailable, or not-material topics, say so in state and
coverage. Do not create fake `S-xxx`, `SRC-xxx`, `EV-xxx`, or `MET-xxx` IDs to
look complete.

## Evidence Promotion

Promote only two kinds of material into hard evidence:

- `EV-xxx`: source-backed factual evidence with locator, excerpt, scope, and
  limitation;
- `MET-xxx`: audited metric evidence for visible/key numbers, with indicator,
  value, unit, period, geography, source, original locator, short excerpt, and
  audit note.

Background notes may remain `research_context`. They can guide wording and
source discovery, but they cannot support key numbers, chart data, hard claims,
or source notes unless Knowledge promotes them.

For archive status:

- `saved_text`, `saved_html`, and `saved_pdf` mean full source capture or
  equivalent archived source with explicit capture method.
- `manual_verified_excerpt` requires Research to reopen/review the source or an
  equivalent trusted copy, record `verification_method`, and explain the
  secondary verification.
- Search snippets, long copied excerpts, and unavailable pages remain leads or
  gaps.

## Knowledge DB

After execution/archive validation, use `scripts/pipeline.py evidence-build` to
prepare a DB skeleton only when starting or intentionally refreshing Knowledge
authoring. Then Knowledge LLM edits `artifacts/research_evidence_db.json`.

For each source, Knowledge should decide:

- `usable_as_evidence`;
- source-use tier: `core_evidence`, `contextual_evidence`,
  `directional_only`, `lead_only`, or `rejected`;
- `claim_use_scope`;
- limitations, conflicts, and comparable/non-comparable scope.

Do not batch-fill source usability, verification, or downstream permission just
to pass validation. If evidence is thin, mark it as thin, caveated, directional,
or research-required.

## Data Conflicts

When sources disagree on market size, growth, share, margin, valuation, or peer
metrics:

- preserve conflicting numbers in Metric Reconciliation;
- record source scope, period, unit, geography, and denominator;
- choose a preferred number only with a clear authority/scope reason;
- otherwise use a range, caveat, or conflicting status;
- do not promote a conflicting metric into a confident headline/chart.

## Public Commands

Use the public controller only:

```bash
PYTHON_CMD=python3
"$PYTHON_CMD" scripts/pipeline.py research-prepare --run-dir "$RUN_DIR"
"$PYTHON_CMD" scripts/pipeline.py research-compile --run-dir "$RUN_DIR"
"$PYTHON_CMD" scripts/pipeline.py validate --artifact formal_search_plan --run-dir "$RUN_DIR"
"$PYTHON_CMD" scripts/pipeline.py validate --artifact formal_research_execution --run-dir "$RUN_DIR"
"$PYTHON_CMD" scripts/pipeline.py validate --artifact source_archive --run-dir "$RUN_DIR"
"$PYTHON_CMD" scripts/pipeline.py evidence-build --run-dir "$RUN_DIR"
"$PYTHON_CMD" scripts/pipeline.py validate --artifact research_evidence_db --run-dir "$RUN_DIR"
"$PYTHON_CMD" scripts/pipeline.py evidence-export --run-dir "$RUN_DIR"
```

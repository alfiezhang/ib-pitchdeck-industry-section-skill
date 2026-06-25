# Research Policy

Use this as the evidence discipline behind public research and Knowledge handoff. It is here to protect traceability and honesty, not to turn research into a script.

## Core Principles

Client-ready delivery needs reviewable evidence unless the user explicitly limits the work to user-provided or manually supplied sources. Search snippets, model memory, root domains, and unopened URLs are leads only.

Planned `FS-xxx` rows describe coverage. Real evidence flows from executed attempts, opened or reviewed sources, and Knowledge-promoted `EV-xxx` / `MET-xxx` rows. User-provided target metrics remain unaudited project context unless an external reviewable source verifies them.

`research_graph_state.json` records research execution. `search_log.md`, `source_archive_index.json`, and `formal_research_execution_report.json` are compiled from that state. `research_evidence_db.json` is the Knowledge LLM-authored source of truth for usable facts, metrics, source limits, conflicts, and claim-use scope. `industry_research_pack.md` is only a readable export from the DB.

## Source Priority

Start with reviewable user-provided sources, then agent-native web search, then configured graph/manual search, then manual URL ingestion when exact sources are available. Use unrestricted web search for exploration. Add domain constraints only for explicit user domains, selected source packs, or deliberate source-specific passes.

If search or PDF capability is unavailable, stop before formal client-ready rendering. Manual-source mode is acceptable only when exact reviewable sources are provided and the limitation is recorded.

## Boundary And Planning

Formal research starts after a short `industry_scope_pack.json` boundary card and Boundary QC pass. The scope pack handles definitions and reconciliation rules; it should not contain market size, growth, share, ranking, valuation, competitive conclusions, or page-ready claims.

Use `scripts/pipeline.py research-prepare` to seed `formal_search_plan.json`, `coverage_map.json`, `executable_search_batch.json`, and `research_graph_state.json`. Treat `formal_search_plan.json` as the coverage/evidence-need map. Let the LLM author concrete query strings only in `executable_search_batch.json`.

The configured taxonomy is an audit menu. Add material industry-specific evidence needs, and mark low-relevance rows as accounting/not material rather than forcing equal-depth searches.

## Execution And Archive

Record what actually happened in `artifacts/research_graph_state.json`: searches run, sources opened, locators, archive status, excerpts, candidate facts, candidate metrics, limitations, conflicts, and unavailable results.

Run `scripts/pipeline.py research-compile` after state updates. The compiler synchronizes IDs, search log, archive index, execution report, and coverage accounting. It should not author the Knowledge DB or decide claim strength.

Use `status=supported` only with explicit `terminal_status=executed_with_evidence`, reviewed source IDs, real attempts, candidate EV/MET rows, and valid downstream permission. Directional, backlog, not-executed, weak, or missing-authorization rows should stay thin, insufficient, unavailable, or backlog-only. A clean gap is better than fake `S-xxx`, `SRC-xxx`, `EV-xxx`, or `MET-xxx` IDs.

## What Becomes Evidence

Promote only two kinds of hard evidence:

- `EV-xxx`: source-backed factual evidence with locator, excerpt, scope, and limitation;
- `MET-xxx`: audited metric evidence for visible/key numbers, with indicator, value, unit, period, geography, source, original locator, short excerpt, and audit note.

Background notes can remain `research_context`. They may guide wording and source discovery, but they cannot support key numbers, chart data, hard claims, or source notes unless Knowledge promotes them.

For archive status:

- `saved_text`, `saved_html`, and `saved_pdf` mean full source capture or equivalent archived source with explicit capture method.
- `manual_verified_excerpt` means Research reopened or reviewed the source or an equivalent trusted copy, recorded `verification_method`, and explained secondary verification.
- Search snippets, long copied excerpts, and unavailable pages remain leads or gaps.

After execution/archive validation, use `scripts/pipeline.py evidence-build` only to prepare a Knowledge skeleton when starting or intentionally refreshing DB authoring. Knowledge LLM then edits `artifacts/research_evidence_db.json`, promoting only supported candidates into `evidence_ledger` or `metric_reconciliation`.

Do not fill source usability, verification, or downstream permission merely to satisfy validation. If evidence is thin, mark it as thin, caveated, directional, or research-required.

## Conflicting Data

When sources disagree on market size, growth, share, margin, valuation, or peer metrics, keep the conflict visible. Preserve scope, period, unit, geography, denominator, and source authority. Choose a preferred number only when the source hierarchy and scope support it; otherwise use a range, caveat, or conflicting status.

## Commands

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

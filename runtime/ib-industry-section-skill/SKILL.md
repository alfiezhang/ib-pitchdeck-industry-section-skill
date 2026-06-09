---
name: ib-industry-section
description: Generate a source-disciplined, issue-analysis-driven investment banking industry section for a pitchbook, with controlled research, LLM-first deck blueprint planning, deterministic PPT rendering, and final delivery gates. Use when the user asks for this skill or asks for an industry chapter/PPT linked to a potential target company. Supports Chinese or English output.
---

# IB Industry Section

Generate a high-quality pitchbook industry section. The PPT file is the delivery
format, not the objective.

Default context: `pre_mandate_transaction_pitch`. The deck is for pitching a
potential client before a formal mandate is won. Sector credibility comes first;
transaction relevance comes second; target-company promotion must be selective
and evidence-based.

This is not a BP, CIM, retained-client sell-side book, target advertisement,
generic industry report, or quick "make any PPT" template.

## Quick Start

Work from the installed skill root, for example:

```bash
cd ~/.codex/skills/ib-industry-section-skill
PYTHON_CMD="$(bash setup.sh --print-python)"
"$PYTHON_CMD" scripts/check_runtime_dependencies.py
```

Runtime requirements:

- Python 3.9+; Python 3.9-3.11 is preferred for `python-pptx` / `lxml`.
- PPT rendering requires `python-pptx` and `lxml`.
- Formal research requires either the agent's web-search tool or fallback search
  packages (`tavily-python` and/or `ddgs`) installed by `setup.sh`.
- If no network/search provider is available, do not fake searches. Use only
  user-provided/offline sources that can be reviewed, logged, archived, and
  caveated; otherwise stop at the research blocker.

`setup.sh` is a thin wrapper around `scripts/bootstrap_runtime.py`; use the
returned `PYTHON_CMD` for all scripts in the run.

## Files To Read

At task start read only:

1. `references/execution_discipline.md`
2. `references/scope_boundary.md`
3. The sub-skill for the current stage:
   - research / issue analysis: `skills/research-pack/SKILL.md`
   - deck blueprint / renderer compilation: `skills/deck-blueprint-section/SKILL.md`
   - PPT filling / final delivery: `skills/fill-ppt/SKILL.md`

Do not bulk-read every reference, schema, test, or fixture. Use
`templates/artifact_manifest.json` as the machine source of truth for artifact
order, validators, and stale-validation relationships.

## Stage Stop Rule

Before every downstream transition, run:

```bash
"$PYTHON_CMD" scripts/workflow.py next --run-dir "$RUN_DIR"
```

If the current gate is `failed`, `missing`, `stale`, or `blocked`, repair that
gate in the same `RUN_DIR`, rerun its validator, and continue only after
`workflow.py next` advances. Do not write downstream artifacts, render PPT, or
summarize the project as complete while the run state forbids it.

This is especially important after `source_reviews`, `source_archive`,
`research_pack`, `issue_analysis`, `deck_blueprint`, `content_quality`, and
`final_delivery`; those failures are not formatting details.

If a run becomes hard to reason about, generate role packets instead of rereading
the whole skill only when explicitly doing diagnostics. Role packets are not
part of the main workflow path.

## Non-Negotiable Rules

For a project brief + "generate PPT" request, this is a formal delivery task.

Do:

1. Create `input_card.json` by transcription only.
2. Create an LLM-only `llm_definition_draft`, then validate/refine it with thin
   industry scoping searches in `industry_scope_pack.json`.
3. Build a full-taxonomy `formal_search_plan.json` skeleton and execute real
   formal searches as `S-xxx` attempts. `FS-xxx` rows are planned coverage
   instructions, not evidence and not actual searches.
4. Build source-review skeletons from the search log; the LLM reviews exact
   sources, locators, excerpts, use scope, and evidence usability.
5. Archive usable reviewed sources, then build the formal execution report from
   plan/log/reviews.
6. Build and edit `artifacts/research_evidence_db.json` as the source-of-truth
   evidence database, then export `industry_research_pack.md` from it.
7. Build issue-analysis skeletons mechanically, then replace placeholders with
   substantive banker analysis.
8. Let `deck_blueprint.json` be the single LLM-authored page-design artifact.
9. Compile `page_evidence_contract.json` and `renderer_spec.json`; do not
   hand-write derived artifacts.
10. Render/finalize with `scripts/pipeline.py render --run-dir "$RUN_DIR"` only
    after upstream gates are current.

Do not:

- start from `run_pipeline.sh` when starting from a brief;
- use tests, fixtures, schema files, previous runs, or a "minimum viable
  renderer spec" as production content;
- use `--no-research-gate` for a research-backed PPT request;
- use debug PPT output as a deliverable;
- skip research evidence DB, generated research pack, issue analysis, deck
  blueprint, or final delivery gates;
- hand-write `replacement_dict.json`;
- create ad-hoc PPT scripts (`generate_ppt.py`, custom `python-pptx`,
  PptxGenJS, LibreOffice, Keynote, manual drawing) to bypass the package;
- offer validation-bypass choices such as "fix issue_analysis or manually build
  PPT"; formal delivery has only the validated pipeline path;
- call any PPT client-ready unless final delivery validation passes.

Common wrong path:

`brief -> inspect tests/schemas -> minimal JSON -> --no-research-gate -> debug PPT`

Correct path:

`brief -> scope pack -> full-taxonomy search plan -> formal searches -> source reviews/archive -> execution report -> research_evidence_db -> generated research pack -> issue analysis -> deck blueprint -> compiled contract/renderer -> formal pipeline -> final delivery`

## Formal Workflow

Use one run directory as the package of record:

`<work_root>/runs/<case_slug>/attempt_<timestamp>/`

Do not create nested `runs/` folders inside an attempt. Do not create a new
attempt to escape stale or failed validation.

Core stages:

1. **Runtime**: set `PYTHON_CMD` with `bash setup.sh --print-python`.
2. **Input card**: transcribe user brief only; validate input card.
3. **Industry scoping**: define the market boundary and data-risk map; no
   confirmed market-size/growth/share/ranking/valuation claims.
4. **Formal research plan**: full canonical issue/subissue coverage; executable
   queries only; no investment hypotheses or slide conclusions. Treat taxonomy
   rows as a coverage map, not as a claim that every row has already been
   searched at equal depth.
5. **Source chain**: execute real searches, append `S-xxx`, review exact sources,
   archive usable evidence, then build/validate formal execution.
6. **Research evidence database**: preserve source-level extracts, EV/MET
   ledgers, issue fact inventory, metric reconciliation, conflicts, and gaps in
   `artifacts/research_evidence_db.json`; export `industry_research_pack.md`
   from the DB for readable review and existing validators.
7. **Issue analysis**: form banker judgments from validated evidence; weak
   support remains caveated or in backlog.
8. **Deck blueprint**: design pages, headline/main message/body blocks, visual
   intent, caveats, source use, and pitch relevance.
9. **Compile/render**: compile deterministic artifacts, run content/replacement
   validation, render PPT, and pass final delivery.

For detailed step commands, read the relevant sub-skill and run:

```bash
"$PYTHON_CMD" scripts/workflow.py next --run-dir "$RUN_DIR"
```

The recommended commands from `workflow.py next` are the preferred repair path.

## Artifact Layers

Keep the mental model simple:

- **Authoring artifacts**: the few files where LLM judgment matters
  (`input_card.json`, `artifacts/research_evidence_db.json`,
  `industry_issue_analysis.json`, `deck_blueprint.json`). The research support
  files under `artifacts/` exist to make the evidence pack auditable.
- **Derived artifacts**: deterministic outputs such as
  `industry_research_pack.md`, `page_evidence_contract.json`,
  `renderer_spec.json`, `replacement_dict.json`, `source_archive/`, and the
  PPT. Do not hand-author these.
- **Validation artifacts**: gate outputs under `artifacts/*_validation.json`.
  Do not edit these; repair the upstream authoring artifact.
- **Diagnostic artifacts**: optional helpers such as banker review reports,
  candidate workspaces, agent handoff packets, and run quality summaries. Use
  them only when they clarify a repair; they are not the main path.

`templates/artifact_manifest.json` is the machine-readable source of truth for
these layers.

## Research Discipline

ID meanings:

- `FS-xxx`: planned search instruction in `formal_search_plan.json`
- `S-xxx`: actual search attempt in `search_log.md`
- `SRC-xxx`: reviewed source in `source_reviews.json`
- `FR-xxx`: formal issue/subissue execution result
- `EV-xxx` / `MET-xxx`: evidence and metric rows authored in
  `research_evidence_db.json` and exported into the research pack

Broad discovery is only for scoping. It should use terms such as `definition`,
`classification`, `included segments`, `adjacent market`, `scope`, `taxonomy`,
`value chain boundary`, and `metric definition`. Do not run growth, share,
ranking, valuation, M&A, specific-year, or investment-thesis searches in broad
discovery; record accidental numeric finds only as `unvalidated_leads`.

Formal search planning covers all canonical issue/subissue rows. If evidence is
unavailable, keep the row, run a reasonable search, and later mark the FR result
`thin`, `insufficient`, or `unavailable_after_research` with limitations.

Planned-vs-actual discipline:

- A planned `FS-xxx` row is not evidence.
- A planned query string is not evidence.
- Only an actually executed formal/latest/peer search may receive an `S-xxx`
  ID.
- Do not create fake `S-xxx` IDs for unexecuted planned rows.
- Do not fast-track from partial searches to `source_reviews`,
  `research_evidence_db`, issue analysis, or deck blueprint.
- If only 10 searches were actually executed out of 40+ planned `FS-xxx` rows,
  say so explicitly in `formal_research_execution_report.json`. Account for the
  remaining rows as `not_executed`, `not_material`, `accounting_only`,
  `insufficient`, or backlog. They cannot support evidence, headlines, charts,
  or body claims.
- A few strong sources are not enough if planned-vs-actual coverage has not been
  accounted for.

Search count alone is not evidence quality. Reviewed sources need locators,
excerpts/paraphrases, use scope, provenance tier, and source archive snapshots.

## Page And Template Discipline

Current delivery uses a fixed 8-slide master template. The fixed sequence is a
delivery constraint, not a reasoning shortcut. Page-type variants are controlled
by `slide_registry.json`, `page_type_rules.json`, `template_registry.json`, and
the PPT mapping files. Do not invent unsupported slide structures unless the
template registry and validation logic are updated together.

`deck_blueprint.json` owns page judgment and copy. `page_evidence_contract.json`,
`renderer_spec.json`, and `replacement_dict.json` are deterministic downstream
artifacts. If content needs changing, edit the blueprint and recompile.

## Pipeline

For a validated attempt:

```bash
"$PYTHON_CMD" scripts/pipeline.py render --run-dir "$RUN_DIR"
```

This command operates on the current attempt. It does not perform research,
create page judgments, or create a new attempt. It runs pre-PPT checks,
replacement generation, PPT fill/clean/postprocess, filled-PPT validation, final
delivery validation, run quality summary, and latest-run index updates.

`run_pipeline.sh` remains a legacy compatibility wrapper for older automation.
It delegates to `scripts/pipeline.py render` and no longer creates attempts,
stages artifacts, or repairs gates. Do not choose it as the first step for a new
brief.

## Debug Mode

Debug mode is only for local PPT template or renderer diagnostics. Use the
specific low-level script for the behavior being tested, for example token
replacement, cleanup, or post-processing. The legacy `run_pipeline.sh` wrapper
rejects `--no-research-gate` for formal delivery and does not provide a
client-ready debug path.

Debug output is never task completion for a new project brief and must not be
reported as client-ready.

## Repair Integrity

Do not weaken evidence to pass validators. Never:

- mark `Opened / Reviewed=yes` without actual review;
- relabel weak leads as formal evidence;
- delete EV/MET/source references instead of repairing support;
- batch-set `usable_as_evidence=false` while retaining EV/MET or supported FR
  findings;
- rewrite taxonomy to hide missing research;
- patch a PPT file to hide upstream failure.

For `content_quality` failures, open
`artifacts/content_quality_validation.json` and follow its `repair_plan`. Repair
the named upstream target (`deck_blueprint.json`, research evidence DB /
generated research pack, or issue analysis), recompile, and rerun validation. Do
not patch `renderer_spec.json`,
`replacement_dict.json`, or the PPT as a shortcut.

If the same gate reaches `STOP_AND_REPORT`, preserve the attempt directory and
report the failed gate, validation artifact, top errors, likely root cause, and
smallest next fix.

## Final Reporting

Report a final PPT path only when:

- `artifacts/final_delivery_validation.json` is valid and `client_ready=true`;
- the PPT was produced by the packaged deterministic pipeline; and
- `LATEST_FINAL_PPT.txt` or the run's final delivery validation points to it.

If final delivery is false, call the run blocked or debug-only. Do not describe
an existing PPT file as complete just because it exists.

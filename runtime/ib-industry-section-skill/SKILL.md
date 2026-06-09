---
name: ib-industry-section
description: Generate a source-disciplined, issue-analysis-driven investment banking industry section for a pitchbook, with controlled research, LLM-first deck blueprint planning, deterministic PPT rendering, and final delivery gates. Use when the user asks for this skill or asks for an industry chapter/PPT linked to a potential target company. Supports Chinese or English output.
---

# IB Industry Section

Generate a high-quality pitchbook industry section. The PPT file is the delivery format, not the objective.

## Stage Stop Rule

Before every downstream transition, run:

```bash
"$PYTHON_CMD" scripts/workflow.py next --run-dir "$RUN_DIR"
```

If `status` is `failed`, `missing`, `stale`, or `blocked`, stop downstream movement at that gate. Do not write downstream artifacts, do not run the PPT pipeline, and do not summarize the project as complete.

This is especially important after `source_reviews`, `source_archive`, `research_pack`, and `deck_blueprint`; those failures are not formatting details.

For one-shot formal PPT requests, stopping downstream movement does **not** mean
stopping the task. Repair the current gate in the same `RUN_DIR`, rerun its
validator, and continue only after `workflow.py next` advances. Report a blocked
state only when the workflow reports `repair_limit_exceeded` / `blocked`, when
research is genuinely unavailable, or when user input is required. Never ask the
user whether to skip validation, manually compile a PPT, or continue with a
degraded deck during a formal delivery run.

## Non-Negotiable Agent Rules

If the user provides a project brief and asks to generate a PPT, this is a formal delivery task.

There is no one-command "brief to PPT" shortcut. `scripts/pipeline.py render --run-dir "$RUN_DIR"` only turns an already validated formal run package into a deck inside the current attempt. `run_pipeline.sh` is compatibility-only.

Do:
1. Create `input_card.json` in transcription mode.
2. Draft the LLM-only industry definition inside `artifacts/industry_scope_pack.json` as `llm_definition_draft`; this uses the brief and model knowledge only and must contain no numbers or conclusions.
3. Run broad discovery only to verify/refine that definition draft, then complete thin `artifacts/industry_scope_pack.json`, validate it, and build a full-taxonomy `artifacts/formal_search_plan.json` skeleton.
4. Validate `artifacts/formal_search_plan.json`, then execute every planned formal search instruction as a real search and use `scripts/append_search_attempt.py` to log the resulting `S-xxx` attempts.
5. Use `scripts/build_source_reviews_skeleton.py` to create `SRC-xxx` review cards from selected `S-xxx` URLs, then have the LLM review exact sources, locators, excerpts, and usability.
6. Use `scripts/build_formal_research_execution_report_skeleton.py` to create the execution report from `FS-xxx` / `S-xxx` / `SRC-xxx`, edit judgment fields, then archive usable evidence snapshots with `scripts/build_source_archive.py`.
7. Use `scripts/build_research_evidence_pack_skeleton.py` and optional `scripts/build_evidence_candidate_skeleton.py`, then complete and validate `industry_research_pack.md` as a research evidence binder.
8. Use `scripts/build_issue_analysis_skeleton.py` to create the mechanical structure, replace all skeleton/TODO text with substantive issue analysis, then validate `industry_issue_analysis.json`.
9. Extract `template_registry.json`, then write and validate `deck_blueprint.json` as the banker page-design artifact.
10. Compile `deck_blueprint.json` into `page_evidence_contract.json` and `renderer_spec.json`; do not hand-write those derived files.
11. Build the non-blocking banker review packet/report, repair `deck_blueprint.json` if page quality is thin, then run formal content/replacement/PPT validation.
12. Render and finalize from the same attempt with `scripts/pipeline.py render --run-dir "$RUN_DIR"`. Deliver only when final delivery validation is client-ready.

Do not:
- start from `run_pipeline.sh` when starting from a brief;
- search for a one-click script, smoke fixture, schema-only shortcut, or "minimum viable renderer spec" to produce a PPT;
- use `tests/`, `fixtures/`, `templates/*.schema.json`, or previous run artifacts as production content;
- use `--no-research-gate` for a research-backed PPT request;
- use debug PPT output as a deliverable;
- skip research pack or issue analysis artifacts;
- hand-write `replacement_dict.json`;
- provide or repair a separate PPT-copy JSON path;
- patch the final PPT manually to hide upstream failures;
- create a custom PPT-generation script such as `generate_ppt.py`, or use ad-hoc `python-pptx`, PptxGenJS, LibreOffice, Keynote, or manual drawing to bypass the packaged deterministic pipeline;
- call a hand-built PPT `industry_section_filled_clean.pptx` or a completed delivery when the formal pipeline/final gate failed;
- offer validation-bypass choices such as "fix issue_analysis or manually build PPT"; formal delivery has only the validated pipeline path;
- treat "generate PPT" as "make any PPT file."

Formal research ID discipline:
- `FS-xxx` means a planned search instruction in `artifacts/formal_search_plan.json`.
- `S-xxx` means an actual search attempt recorded in `artifacts/search_log.md`.
- `search_instruction_ids` in the execution report must contain `FS-xxx`.
- `search_attempt_ids` in the execution report must contain real `S-xxx` attempts only.
- Never mark "formal research execution" complete just because the plan exists. After writing the plan, run the actual WebSearch / search-provider calls for the planned `FS-xxx` instructions, append `S-xxx` entries to `search_log.md`, and only then write the execution report.
- If validation complains about formal execution, first check whether real `S-xxx` formal searches were performed and logged; do not start by rewriting taxonomy or reshaping JSON.

Broad discovery query discipline:
- Broad discovery validates the LLM-only `llm_definition_draft`; it does not discover investment conclusions. Query strings should use words like `definition`, `classification`, `included segments`, `adjacent market`, `scope`, `taxonomy`, `value chain boundary`, `metric definition`, or their local-language equivalents.
- Do not put `market size`, `growth`, `CAGR`, `share`, `ranking`, `valuation`, `M&A`, specific years, or transaction-thesis terms into broad discovery queries. Those belong in formal `FS-xxx` searches after the scope pack.
- If a scoping search result contains numbers anyway, record them only as `unvalidated_leads`; do not use them as findings.

`--no-research-gate` is reserved only for explicit local template/rendering diagnostics. It requires both `IB_SKILL_ALLOW_PPT_ONLY_DEBUG=1` and `--debug-reason`. The reason must describe a template/rendering diagnostic, not a research, research pack, renderer-spec, schema, or delivery shortcut. A debug PPT is never task completion for a new project brief.

If you cannot complete web research, source review, or issue analysis validation after honest repair attempts, report the blocked gate and preserve the run directory. Do not compensate by fabricating "validation-shaped" artifacts.

## Repair Integrity

Do not optimize artifacts merely to pass validators.

After a failed research, research pack, issue-analysis, deck-blueprint, renderer-spec, or content-quality gate, audit recent repair edits in the current attempt before continuing. Identify any change that may weaken evidence integrity or research provenance, including:

- changing `Opened / Reviewed` from `no` to `yes` without actually opening or reviewing the source;
- removing `broad_discovery` search IDs instead of adding formal/latest validation searches;
- clearing `source_pack` fields only to reduce domain counts;
- replacing official, filing, company disclosure, regulator, or higher-authority domains with lower-authority media domains;
- deleting EV/MET/source references instead of adding proper validation or moving them to the correct artifact;
- relabeling weak or lead-only sources as formal evidence instead of moving them out of the Evidence Ledger.
- batch-marking `usable_as_evidence=false` while keeping `EV-xxx` / `MET-xxx` links or supported/thin FR findings. If a source is unusable, either find/review/archive a usable source, remove the unsupported EV/MET claim, or downgrade the formal finding with explicit limitations.

For each such edit, restore the stronger evidence path, add the missing formal research execution, or explicitly justify why the edit preserves research integrity. Do not regenerate research pack, deck blueprint, compiled renderer spec, or PPT until this repair-integrity audit is complete.

## Common Failure Mode To Avoid

Wrong path:

`brief -> inspect schemas/tests -> hand-build minimal JSON -> run --no-research-gate -> return debug PPT`

Correct path:

`brief -> industry scope pack -> full-taxonomy issue/subissue search plan -> formal research execution -> research pack -> issue analysis -> template registry -> deck blueprint -> compiled evidence contract/renderer spec -> replacement audit -> formal pipeline -> final delivery gate`

Schema files define shape only. Test fixtures prove validators work. Neither is evidence, research, or a substitute for the formal workflow.

When resuming a run after an interruption or context compaction, first run
`scripts/workflow.py status --run-dir <run_dir>` and tell the user which stage is
already validated and which stage you are continuing from. Do not silently skip
research, source review, or final delivery steps just because artifacts exist;
the workflow status and current validation artifacts decide whether the stage is
complete.

## Engagement Context

Default context is `pre_mandate_transaction_pitch`: the material is for pitching a potential client before a formal mandate is won.

This is not:
- a BP;
- a CIM;
- a retained-client sell-side marketing book;
- a target company advertisement;
- a generic industry report.

Sector credibility comes first. Transaction relevance comes second. Explicit target context should be selective, evidence-based, and clearly separated from industry-level conclusions.

## First Files To Read

At task start:
1. Read `references/execution_discipline.md`.
2. Read `references/scope_boundary.md`.
3. Then read only the sub-skill needed for the current stage:
   - research and issue analysis artifacts: `skills/research-pack/SKILL.md`
   - deck blueprint and renderer compilation: `skills/deck-blueprint-section/SKILL.md`
   - deterministic PPT filling: `skills/fill-ppt/SKILL.md`

Do not bulk-read every reference file. Load detailed references only when a stage needs them.

## Workflow Selection

Use the smallest workflow that matches the request:

- **New industry section from brief/attachments, including "generate PPT"**: run the full formal workflow through research, formal research execution, research pack, issue analysis, deck blueprint, compiled renderer spec, PPT fill, and final delivery QC.
- **User asks to "run the skill" from a brief**: create the research artifacts yourself according to this workflow, validate each gate, and use `scripts/workflow.py status` / `scripts/workflow.py next` to confirm allowed next actions before moving downstream.
- **Research-only update**: stop after research pack validation and gap audit.
- **Page/renderer update**: use an existing validated research pack and issue analysis pack; do not add new research facts.
- **Existing PPT improvement**: audit current storyline and validations, then regenerate only necessary upstream artifacts unless the user asks for a full rebuild.
- **Formatting-only fix for an already-validated run**: operate on PPT fill/clean/postprocess only; do not change research, deck blueprint, or compiled renderer inputs.

If a task begins from a brief, it is never formatting-only.

## Formal Run Sequence

`templates/artifact_manifest.json` is the machine source of truth for formal
artifact paths, builders, validators, and stale-validation input relationships.
When prose instructions and the manifest disagree about artifact sequencing,
follow the manifest and the validators.

Use one run directory as the package of record:

`<work_root>/runs/<case_slug>/attempt_<timestamp>/`

Do not create nested `runs/` directories inside an attempt. Do not copy only the PPT out as the apparent deliverable.
Before moving downstream, run `scripts/workflow.py next --run-dir <run_dir>`.
If it returns `STOP_AND_REPORT`, stop generating downstream artifacts and report
the blocker; do not continue patching JSON to chase validators.

When a run becomes hard to reason about, or when handing work across model
sessions, generate role-specific packets instead of rereading the whole skill:

```bash
"$PYTHON_CMD" scripts/build_agent_handoff.py --run-dir "$RUN_DIR"
```

These packets are local coordination aids. They do not replace validators or
authorize a downstream role to fabricate missing upstream artifacts.

All JSON artifacts must be written with ASCII JSON string delimiters (`"`), not
smart/Chinese quotes (`“”`). Generate JSON through `json.dump(...,
ensure_ascii=False, indent=2)` or an equivalent structured writer. If validation
reports smart quotes, run `scripts/repair_json_smart_quotes.py <file> --in-place`
once, then revalidate; if repair fails, rebuild the JSON from the source object.

Formal one-shot sequence:

1. **Runtime**
   ```bash
   PYTHON_CMD="$(python3 scripts/bootstrap_runtime.py --print-python)"
   ```

2. **Input card**
   - Generate `input_card.json` by transcription only.
   - Do not add inferred peers, source preferences, risks, or research topics.
   - Validate:
     ```bash
     "$PYTHON_CMD" scripts/validate_input_card.py \
       --input-card input_card.json \
       --output artifacts/input_card_validation.json
     ```

3. **Search planning and execution**
   - Use `skills/research-pack/SKILL.md`.
   - First draft `llm_definition_draft` inside `artifacts/industry_scope_pack.json` from the input card and model knowledge only. This is not evidence and cannot be used downstream as a claim.
   - Use the draft to design 3-6 scoping searches. Keep them industry-neutral and definition-oriented:
     1. industry naming / vocabulary / classification;
     2. parent market, adjacent market, and category hierarchy;
     3. product, service, process, application, or value-chain segment boundaries;
     4. customer / end-market / channel / business-model boundary if relevant;
     5. metric scope and methodology terms used by sources;
     6. optional regulatory, technical, capacity, or transaction-context vocabulary when it affects industry definition.
   - Do not let broad discovery become a consumer-goods pattern. For manufacturing, industrials, software, healthcare, services, or infrastructure, adapt the same scoping questions to process steps, equipment categories, end markets, deployment model, contract model, capacity, regulation, and standards.
   - Do not run growth, market share, peer-ranking, valuation, or investment-thesis searches in broad discovery except as unvalidated leads for later formal research.
   - Complete `artifacts/industry_scope_pack.json` from `templates/industry_scope_pack.template.json` by reconciling the initial `llm_definition_draft` with scoping search results.
   - Do not write confirmed market size, growth rate, market share, channel ranking, competitive landscape, valuation multiples, or page-ready claims in the scope pack. Any numerical or directional finding encountered during broad discovery belongs only in `unvalidated_leads` and cannot be used downstream unless formal research later validates it.
   - Validate:
     ```bash
     "$PYTHON_CMD" scripts/validate_industry_scope_pack.py \
       --scope-pack artifacts/industry_scope_pack.json \
       --output artifacts/industry_scope_pack_validation.json
     ```
   - After the scope pack passes, build `artifacts/formal_search_plan.json` as a full-taxonomy issue/subissue research plan. Use the builder first so taxonomy coverage and `FS-xxx` numbering are mechanical:
     ```bash
     "$PYTHON_CMD" scripts/build_formal_search_plan_skeleton.py \
       --input-card "$RUN_DIR/input_card.json" \
       --scope-pack "$RUN_DIR/artifacts/industry_scope_pack.json" \
       --output "$RUN_DIR/artifacts/formal_search_plan.json"
     ```
   - Then edit the generated `research_question`, `query`, `purpose`, and `source_hint` fields to fit the scoped industry. Do not delete issue/subissue rows. The formal plan must cover every canonical subissue because thin upstream search produces thin issue analysis and thin PPT pages.
   - Do not write issue hypotheses in the search plan. The search-plan gate checks execution readiness and coverage: valid taxonomy, every canonical issue/subissue present, unique `FS-xxx` IDs, executable queries, and no page/deck conclusions.
   - Validate:
     ```bash
     "$PYTHON_CMD" scripts/validate_formal_search_plan.py \
       --formal-search-plan artifacts/formal_search_plan.json \
       --output artifacts/formal_search_plan_validation.json
     ```
   - Execute every planned `FS-xxx` formal/latest/peer search as a real tool call and record each real attempt as `S-xxx` in `artifacts/search_log.md`. If evidence is unavailable, keep the `FS-xxx` row, run a reasonable search, and later mark the `FR-xxx` result `thin`, `insufficient`, or `unavailable_after_research` with limitations; do not delete the subissue from the plan to make validation easier.
   - Prefer the helper instead of hand-editing search numbering:
     ```bash
     "$PYTHON_CMD" scripts/append_search_attempt.py \
       --search-log "$RUN_DIR/artifacts/search_log.md" \
       --query "<exact query actually searched>" \
       --stage formal_research_execution \
       --fs-id FS-001 \
       --selected-source "<exact opened/reviewed URL>" \
       --opened-reviewed yes \
       --locator-excerpt "<page/section/table plus short excerpt or limitation>"
     ```
   - Do not move to the execution report until the search log contains real `S-xxx` formal/latest/peer attempts for the retained `FS-xxx` instructions.
   - Build an initial execution-report skeleton from the plan and search log. This proves `FS-xxx` has real `S-xxx` execution before any source promotion:
     ```bash
     "$PYTHON_CMD" scripts/build_formal_research_execution_report_skeleton.py \
       --formal-search-plan "$RUN_DIR/artifacts/formal_search_plan.json" \
       --search-log "$RUN_DIR/artifacts/search_log.md" \
       --include-unexecuted \
       --output "$RUN_DIR/artifacts/formal_research_execution_report.json"
     ```
   - Build source-review skeletons from selected URLs so the LLM does not hand-maintain `SRC-xxx` numbering:
     ```bash
     "$PYTHON_CMD" scripts/build_source_reviews_skeleton.py \
       --search-log "$RUN_DIR/artifacts/search_log.md" \
       --output "$RUN_DIR/artifacts/source_reviews.json"
     ```
   - Then open/review each exact source and edit `source_reviews.json`: exact URL, locator, excerpt/paraphrase, linked `S-xxx`, source-use tier, claim-use scope, linked `EV-xxx`, and honest `usable_as_evidence` values. Use canonical fields (`source_review_id`, `url`, `title`, `locator`, `excerpt`, `evidence_use_tier`, `claim_use_scope`); validators tolerate common aliases but new artifacts should not rely on them. Decide `evidence_use_tier` before the boolean: `core_evidence` and `contextual_evidence` may support EV rows within a narrow `claim_use_scope`; `directional_only`, `lead_only`, and `rejected` should not feed formal EV/MET rows. Do not batch-fill `usable_as_evidence=true` or `false` merely to satisfy validation; use false for search-result snippets, weak leads, unavailable reports, root domains, or unreviewed pages.
   - Rebuild the execution-report skeleton after `source_reviews.json` exists, then edit judgment fields instead of hand-synchronizing IDs:
     ```bash
     "$PYTHON_CMD" scripts/build_formal_research_execution_report_skeleton.py \
       --formal-search-plan "$RUN_DIR/artifacts/formal_search_plan.json" \
       --search-log "$RUN_DIR/artifacts/search_log.md" \
       --source-reviews "$RUN_DIR/artifacts/source_reviews.json" \
       --include-unexecuted \
       --output "$RUN_DIR/artifacts/formal_research_execution_report.json"
     ```
     The helper copies `issue_area`, `subissue`, `research_question`, `FS-xxx`, `S-xxx`, and `SRC-xxx` references. You must still review and edit `status`, `findings_summary`, `limitations`, `research_pack_handling`, and EV/MET IDs based on the actual source support.
   - For every non-user source with `usable_as_evidence=true`, create `artifacts/source_archive/source_archive_index.json` and a reviewable snapshot file under `artifacts/source_archive/`. Prefer a saved PDF or clean markdown/text snapshot; if the tool surface cannot download the full source, save an `excerpt_snapshot` markdown file with URL, title, locator, reviewed excerpt, and limitation note. Do not fabricate full-page text.
   - Prefer the archive helper for excerpt snapshots:
     ```bash
     "$PYTHON_CMD" scripts/build_source_archive.py \
       --source-reviews "$RUN_DIR/artifacts/source_reviews.json" \
       --run-dir "$RUN_DIR" \
       --overwrite
     ```
   - Validate the pre-research pack gate before writing the research pack.

4. **Research Evidence Pack**
   - Build `industry_research_pack.md` from the evidence-pack skeleton:
     ```bash
     "$PYTHON_CMD" scripts/build_research_evidence_pack_skeleton.py \
       --input-card "$RUN_DIR/input_card.json" \
       --scope-pack "$RUN_DIR/artifacts/industry_scope_pack.json" \
       --formal-search-plan "$RUN_DIR/artifacts/formal_search_plan.json" \
       --formal-research-execution-report "$RUN_DIR/artifacts/formal_research_execution_report.json" \
       --source-reviews "$RUN_DIR/artifacts/source_reviews.json" \
       --output "$RUN_DIR/industry_research_pack.md"
     ```
   - Complete it as an evidence binder, not a narrative memo: fill Formal Research Extracts, Evidence Ledger, Metric Reconciliation, IB Issue Fact Inventory, and Research Gap Audit from reviewed source rows.
   - The skeleton is not final. It should fail validation until source-faithful EV/MET extraction, fact inventory updates, and gap audit are complete.
   - Do not build the formal page evidence contract in the research pack; `deck_blueprint.json` and `scripts/compile_deck_blueprint.py` own that boundary.
   - Validate `artifacts/research_pack_validation.json`.

5. **Issue Analysis**
   - Build the mechanical issue-analysis skeleton from the validated research pack:
     ```bash
     "$PYTHON_CMD" scripts/build_issue_analysis_skeleton.py \
       --research-pack "$RUN_DIR/industry_research_pack.md" \
       --formal-research-execution-report "$RUN_DIR/artifacts/formal_research_execution_report.json" \
       --output "$RUN_DIR/industry_issue_analysis.json"
     ```
   - Replace every `TODO_REPLACE...` / skeleton placeholder with substantive banker analysis from the research evidence pack. The validator intentionally blocks helper placeholder text.
   - Validate it before deck blueprint.
   - Issue analysis is for issue-by-issue industry analysis only: each block covers one IB industry subissue with a substantive paragraph, supporting points, evidence sufficiency, EV/MET IDs, limitations, and downstream permissions.
   - Do not create a one-line idea list. If a subissue lacks support, put it in `research_backlog` with the needed evidence and research action.
   - Do not decide slide numbers, template variants, headline claims, or chart contracts in issue analysis.
   - Rejected analyses must not flow into slides.
   - Unverified or insufficient analyses may only flow into caveats/open questions when deck blueprint allows it.
   - If validation fails, first run `scripts/normalize_issue_analysis.py` for
     mechanical cleanup, then read
     `artifacts/issue_analysis_validation.json.repair_plan`. Repair the named
     fields in `industry_issue_analysis.json` / `industry_research_pack.md` and
     rerun validation. Do not create an empty `issue_analyses` array, do not
     move to deck blueprint, and do not offer a manual-PPT bypass while this
     gate is invalid.

6. **Template Registry And Deck Blueprint**
   - Use `skills/deck-blueprint-section/SKILL.md`.
   - Extract `template_registry.json` with `scripts/extract_template_registry.py`.
   - Write `deck_blueprint.json` as the single LLM-authored page-design artifact after issue analysis.
   - The blueprint owns deck storyline, investor question, page thesis, selected issue analysis IDs, template variant, headline, main message, body blocks, visual intent/data, caveats, open questions, and EV/MET bindings.
   - Do not write slide content as research notes. Each body block should be PPT copy with a label + data/mechanism + why it matters.
   - Validate `deck_blueprint.json`.
   - Compile `page_evidence_contract.json` and `renderer_spec.json` from the blueprint with `scripts/compile_deck_blueprint.py`; do not hand-write or patch the derived files unless you also update the blueprint and recompile.
   - Build `artifacts/banker_review_packet.md` with `scripts/build_banker_review_packet.py` and review page quality before treating content-quality validation as a formatting exercise.
   - Validate `template_registry`, `deck_blueprint`, `page_evidence_contract`, and `renderer_spec`.

7. **Renderer Spec**
   - Use `skills/deck-blueprint-section/SKILL.md`.
   - `renderer_spec.json` is compiled by `scripts/compile_deck_blueprint.py`.
   - Do not use `renderer_spec.json` as the page-writing surface in formal runs. If copy, layout, chart, table, or evidence needs changing, update `deck_blueprint.json`, revalidate, and recompile.
   - Each slide needs `pitch_relevance`; explicit target linkage is optional and selective.
   - Validate renderer spec against template registry, deck blueprint, and page evidence contract.
   - Run content quality validation.

8. **PPT**
   - Use `skills/fill-ppt/SKILL.md`.
   - Prefer the Python orchestrator after all formal upstream artifacts exist:
     ```bash
     "$PYTHON_CMD" scripts/pipeline.py render --run-dir "$RUN_DIR"
     ```
   - `run_pipeline.sh` remains a compatibility wrapper for older automation. Do not start from it when an existing attempt already contains validated upstream artifacts.
   - PPT generation uses PPT/runtime dependencies only; search-provider availability belongs to the research stage, not the fill pipeline.
   - The pipeline must pass `pre_ppt` stage gate before filling PPT.
   - Only final delivery validation can mark the deck complete.

9. **Final report**
   - Report the run directory.
   - Run quality summary is written to `artifacts/run_quality_summary.md` and `artifacts/run_quality_summary.json`.
   - Report the final PPT path only if final delivery validation passes.
   - Summarize validation status and warnings.
   - If blocked, report the failed gate and smallest next fix.

## Required Formal Artifacts

A formal delivery run should include:

- `input_card.json`
- `artifacts/input_card_validation.json`
- `artifacts/industry_scope_pack.json`
- `artifacts/industry_scope_pack_validation.json`
- `artifacts/formal_search_plan.json`
- `artifacts/formal_search_plan_validation.json`
- `artifacts/search_log.md`
- `artifacts/source_reviews.json`
- `artifacts/source_archive/source_archive_index.json`
- `artifacts/source_reviews_validation.json`
- `artifacts/source_archive_validation.json`
- `artifacts/formal_research_execution_report.json`
- `artifacts/formal_research_execution_validation.json`
- `artifacts/stage_gate_pre_research_pack_validation.json`
- `industry_research_pack.md`
- `artifacts/research_pack_validation.json`
- `industry_issue_analysis.json`
- `template_registry.json`
- `deck_blueprint.json`
- `page_evidence_contract.json`
- `artifacts/issue_analysis_validation.json`
- `artifacts/template_registry_validation.json`
- `artifacts/deck_blueprint_validation.json`
- `artifacts/page_evidence_contract_validation.json`
- `renderer_spec.json`
- `artifacts/renderer_spec_validation.json`
- `artifacts/chart_metric_binding_validation.json`
- `artifacts/content_quality_validation.json`
- `artifacts/stage_gate_pre_ppt_validation.json`
- `replacement_dict.json`
- `artifacts/replacement_dict_validation.json`
- `industry_section_filled.pptx`
- `industry_section_filled_clean.pptx`
- `filled_ppt_validation.json`
- `artifacts/banker_review_report.json`
- `artifacts/final_delivery_validation.json`
- `artifacts/run_quality_summary.json`

Missing upstream artifacts mean the run is not formal delivery.

## Pipeline Use

For formal PPT generation from an existing validated attempt, use the Python orchestrator:

```bash
"$PYTHON_CMD" scripts/pipeline.py render --run-dir "$RUN_DIR"
```

This command operates on the current `attempt_*` directory. It does not create a new attempt, does not perform research, and does not write page judgments. It runs pre-PPT checks, replacement generation, PPT fill/clean/postprocess, filled-PPT validation, final delivery validation, run quality summary, and latest-run index updates.

Use `scripts/pipeline.py status --run-dir "$RUN_DIR"` or `scripts/pipeline.py next --run-dir "$RUN_DIR"` when you need the current run state.

`run_pipeline.sh` is retained for compatibility with older command surfaces:

```bash
./run_pipeline.sh \
  --work-root <work_root> \
  --case-name "<project-or-target-name>" \
  --deck-blueprint <path/to/deck_blueprint.json>
```

Do not pass a `runs/` directory as `--work-root`; pass its parent workspace.

If `--deck-blueprint` is already inside an `attempt_*` directory, the pipeline keeps
that attempt as the package of record by default. Use `--new-attempt`,
`--resume-active`, `--attempt-name`, or `--output-dir` only when intentionally
creating or selecting a different attempt.

During normal agent execution, do not choose `--new-attempt` or create a fresh attempt to escape stale or failed validation. Repair the current package-of-record attempt unless the user explicitly asks for a new attempt.

## Debug Mode

Debug mode is only for local PPT template or renderer diagnostics.

To use it:

```bash
IB_SKILL_ALLOW_PPT_ONLY_DEBUG=1 ./run_pipeline.sh \
  --no-research-gate \
  --debug-reason "local template/rendering diagnostic: <what is being tested>" \
  --renderer-spec <path/to/renderer_spec.json>
```

Debug output:
- is named with `DEBUG_NOT_FOR_DELIVERY`;
- writes `DEBUG_OUTPUT_ONLY.txt`;
- must not update latest-final pointers;
- must not be described as client-ready or final delivery.

Debug reason examples that must be rejected:
- "research completed, generating PPT"
- "deck blueprint fixed for schema compliance"
- "research pack validation is too strict"
- "generate PPT from validated content"

## Quality Gates

Formal delivery requires:

- input card validation passing;
- formal search plan validation passing as a full-taxonomy issue/subissue research plan;
- formal research execution report passing;
- pre-research pack gate passing;
- research pack validation passing;
- issue analysis / template registry / deck blueprint / page evidence contract validation passing;
- renderer spec validation passing;
- chart metric binding validation passing;
- content quality validation passing;
- pre-PPT gate passing;
- filled PPT validation passing;
- final delivery validation passing.

If a gate fails, repair upstream artifacts. Do not bypass the gate.

For `content_quality` failures, open
`artifacts/content_quality_validation.json` and follow `repair_plan` before
editing anything. The repair plan classifies the finding, names the
`primary_repair_targets`, lists the affected fields, and gives the rerun steps.
Do not resolve content-quality failures by patching `renderer_spec.json`,
`replacement_dict.json`, or a PPT file; fix the upstream deck blueprint, research
pack, or issue analysis named by the repair plan and recompile.

The same gate should not be retried indefinitely. If the repair loop is exhausted, stop and report the blocker.

Before advancing between major stages, run:

```bash
"$PYTHON_CMD" scripts/workflow.py next --run-dir "$RUN_DIR"
```

Treat `allowed_next_actions` and `forbidden_actions` as the authoritative run-state contract.

## Core Quality Rules

- Web research is mandatory when starting from a brief or attachments.
- Search logs must record real executed searches, opened/reviewed URLs, and source-locator context.
- Every important claim or metric needs EV/MET traceability.
- Do not fabricate market data, source names, CAGRs, market sizes, rankings, company names, or valuation multiples.
- Do not put low-provenance discovery leads into formal evidence unless explicitly disclosed and unavoidable.
- Do not force target mentions on every slide.
- Slide 4 is industry value chain / profit pool first.
- Slide 5 is industry barriers / winner capabilities first.
- Slide 6 is market structure / peer positioning first.
- Slide 8 balances pitch implications with open diligence questions.
- The fixed 8-slide template is a delivery constraint, not a reasoning shortcut.

## Human Review

Default mode stops after:
1. `industry_research_pack.md`
2. `deck_blueprint.json`

Continue to PPT in one shot only when the user asks for direct PPT output. One-shot removes manual pauses, not machine gates, and it never authorizes a custom rendering path.

## Failure Reporting

Before continuing after a failed gate, run:

```bash
"$PYTHON_CMD" scripts/workflow.py status --run-dir "$RUN_DIR"
"$PYTHON_CMD" scripts/report_run_status.py --run-dir "$RUN_DIR"
```

Use the reported `allowed_next_actions` and `forbidden_actions` as the package-of-record state. Do not proceed to downstream stages when the run-state report forbids them.

When blocked, preserve the attempt directory and report:

- failed gate;
- validation artifact path;
- top errors/warnings;
- likely root cause;
- smallest next fix;
- whether a debug PPT exists and why it is not final.

Only report a final PPT from `LATEST_FINAL_PPT.txt` or from a run whose `artifacts/final_delivery_validation.json` is valid/client-ready.
If `report_run_status.py` says `client_ready=false`, call the output a blocked run or debug artifact, never a completed delivery.
If a PPT file exists but was not produced by the packaged deterministic pipeline and validated by final delivery, mention it only as an invalid bypass artifact.

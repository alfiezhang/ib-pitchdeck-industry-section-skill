---
name: ib-industry-section
description: Generate a source-disciplined, issue-analysis-driven investment banking industry section for a pitchbook, with controlled research, LLM-first deck blueprint planning, deterministic PPT rendering, and final delivery gates. Use when the user asks for this skill or asks for an industry chapter/PPT linked to a potential target company. Supports Chinese or English output.
---

# IB Industry Section

Generate a high-quality pitchbook industry section. The PPT file is the delivery format, not the objective.

## Non-Negotiable Agent Rules

If the user provides a project brief and asks to generate a PPT, this is a formal delivery task.

There is no one-command "brief to PPT" shortcut. `run_pipeline.sh` only turns an already validated formal run package into a deck.

Do:
1. Create `input_card.json` in transcription mode.
2. Run broad discovery only for industry scoping.
3. Create thin `artifacts/industry_scope_pack.json`, validate it, then create `artifacts/formal_search_plan.json`.
4. Validate `artifacts/formal_search_plan.json`, then execute every planned formal search instruction as a real search, log the resulting `S-xxx` attempts, and write `artifacts/formal_research_execution_report.json`.
5. Write `artifacts/source_reviews.json` for exact opened/reviewed sources, archive usable evidence snapshots in `artifacts/source_archive/`, and validate them.
6. Write and validate `industry_research_pack.md`.
7. Write and validate `industry_issue_analysis.json`.
8. Extract `template_registry.json`, then write and validate `deck_blueprint.json` as the banker page-design artifact.
9. Compile `deck_blueprint.json` into `page_evidence_contract.json` and `renderer_spec.json`; do not hand-write those derived files.
10. Run the formal PPT pipeline, including replacement-dictionary semantic validation.
11. Deliver only when final delivery validation is client-ready.

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
- create a custom PPT-generation script such as `generate_ppt.py`, or use ad-hoc `python-pptx`, PptxGenJS, LibreOffice, Keynote, or manual drawing to bypass `run_pipeline.sh`;
- call a hand-built PPT `industry_section_filled_clean.pptx` or a completed delivery when the formal pipeline/final gate failed;
- treat "generate PPT" as "make any PPT file."

Formal research ID discipline:
- `FS-xxx` means a planned search instruction in `artifacts/formal_search_plan.json`.
- `S-xxx` means an actual search attempt recorded in `artifacts/search_log.md`.
- `search_instruction_ids` in the execution report must contain `FS-xxx`.
- `search_attempt_ids` in the execution report must contain real `S-xxx` attempts only.
- Never mark "formal research execution" complete just because the plan exists. After writing the plan, run the actual WebSearch / search-provider calls for the planned `FS-xxx` instructions, append `S-xxx` entries to `search_log.md`, and only then write the execution report.
- If validation complains about formal execution, first check whether real `S-xxx` formal searches were performed and logged; do not start by rewriting taxonomy or reshaping JSON.

`--no-research-gate` is reserved only for explicit local template/rendering diagnostics. It requires both `IB_SKILL_ALLOW_PPT_ONLY_DEBUG=1` and `--debug-reason`. The reason must describe a template/rendering diagnostic, not a research, research pack, renderer-spec, schema, or delivery shortcut. A debug PPT is never task completion for a new project brief.

If you cannot complete web research, source review, or issue analysis validation, stop and report the blocked gate. Do not compensate by fabricating "validation-shaped" artifacts.

## Repair Integrity

Do not optimize artifacts merely to pass validators.

After a failed research, research pack, issue-analysis, deck-blueprint, renderer-spec, or content-quality gate, audit recent repair edits in the current attempt before continuing. Identify any change that may weaken evidence integrity or research provenance, including:

- changing `Opened / Reviewed` from `no` to `yes` without actually opening or reviewing the source;
- removing `broad_discovery` search IDs instead of adding formal/latest validation searches;
- clearing `source_pack` fields only to reduce domain counts;
- replacing official, filing, company disclosure, regulator, or higher-authority domains with lower-authority media domains;
- deleting EV/MET/source references instead of adding proper validation or moving them to the correct artifact;
- relabeling weak or lead-only sources as formal evidence instead of moving them out of the Evidence Ledger.

For each such edit, restore the stronger evidence path, add the missing formal research execution, or explicitly justify why the edit preserves research integrity. Do not regenerate research pack, deck blueprint, compiled renderer spec, or PPT until this repair-integrity audit is complete.

## Common Failure Mode To Avoid

Wrong path:

`brief -> inspect schemas/tests -> hand-build minimal JSON -> run --no-research-gate -> return debug PPT`

Correct path:

`brief -> industry scope pack -> issue/subissue search plan -> formal research execution -> research pack -> issue analysis -> template registry -> deck blueprint -> compiled evidence contract/renderer spec -> replacement audit -> formal pipeline -> final delivery gate`

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
   - Broad discovery is scoping only: industry definition, parent/adjacent market mapping, included/excluded segments, ambiguous boundaries, data hierarchy, unvalidated leads, reconciliation requirements, and seed questions.
   - Before writing the scope pack, run only 3-6 scoping searches. Keep them industry-neutral and definition-oriented:
     1. industry naming / vocabulary / classification;
     2. parent market, adjacent market, and category hierarchy;
     3. product, service, process, application, or value-chain segment boundaries;
     4. customer / end-market / channel / business-model boundary if relevant;
     5. metric scope and methodology terms used by sources;
     6. optional regulatory, technical, capacity, or transaction-context vocabulary when it affects industry definition.
   - Do not let broad discovery become a consumer-goods pattern. For manufacturing, industrials, software, healthcare, services, or infrastructure, adapt the same scoping questions to process steps, equipment categories, end markets, deployment model, contract model, capacity, regulation, and standards.
   - Do not run growth, market share, peer-ranking, valuation, or investment-thesis searches in broad discovery except as unvalidated leads for later formal research.
   - Write `artifacts/industry_scope_pack.json` from `templates/industry_scope_pack.template.json`.
   - Do not write confirmed market size, growth rate, market share, channel ranking, competitive landscape, valuation multiples, or page-ready claims in the scope pack. Any numerical or directional finding encountered during broad discovery belongs only in `unvalidated_leads` and cannot be used downstream unless formal research later validates it.
   - Validate:
     ```bash
     "$PYTHON_CMD" scripts/validate_industry_scope_pack.py \
       --scope-pack artifacts/industry_scope_pack.json \
       --output artifacts/industry_scope_pack_validation.json
     ```
   - After the scope pack passes, write `artifacts/formal_search_plan.json` as a lightweight issue/subissue research plan.
   - Do not write issue hypotheses in the search plan. The search-plan gate is lightweight and checks only execution readiness: valid taxonomy, unique `FS-xxx` IDs, executable queries, and no page/deck conclusions.
   - Validate:
     ```bash
     "$PYTHON_CMD" scripts/validate_formal_search_plan.py \
       --formal-search-plan artifacts/formal_search_plan.json \
       --output artifacts/formal_search_plan_validation.json
     ```
   - Execute the planned `FS-xxx` formal/latest searches as real tool calls and record each real attempt as `S-xxx` in `artifacts/search_log.md`.
   - Do not move to the execution report until the search log contains real `S-xxx` formal/latest/peer attempts for the retained `FS-xxx` instructions.
   - Write `artifacts/formal_research_execution_report.json` from the minimal skeleton only after those `S-xxx` attempts exist. Copy `issue_area`, `subissue`, and `research_question` from the owning `formal_search_plan` item for each executed `FS-xxx`; do not reclassify taxonomy in the execution report.
   - Write `artifacts/source_reviews.json` with exact source URLs, locators, excerpts, linked `S-xxx`, linked `EV-xxx`, and honest `usable_as_evidence` values. Do not set `usable_as_evidence=true` merely to satisfy validation; use false for search-result snippets, weak leads, unavailable reports, root domains, or unreviewed pages.
   - For every non-user source with `usable_as_evidence=true`, create `artifacts/source_archive/source_archive_index.json` and a reviewable snapshot file under `artifacts/source_archive/`. Prefer a saved PDF or clean markdown/text snapshot; if the tool surface cannot download the full source, save an `excerpt_snapshot` markdown file with URL, title, locator, reviewed excerpt, and limitation note. Do not fabricate full-page text.
   - Validate the pre-research pack gate before writing the research pack.

4. **Research Pack**
   - Write `industry_research_pack.md`.
   - Include Evidence Ledger, Metric Reconciliation, IB Issue Fact Inventory, and Research Gap Audit.
   - Do not build the formal page evidence contract in the research pack; `deck_blueprint.json` and `scripts/compile_deck_blueprint.py` own that boundary.
   - Validate `artifacts/research_pack_validation.json`.

5. **Issue Analysis**
   - Write:
     - `industry_issue_analysis.json`
   - Validate it before deck blueprint.
   - Issue analysis is for issue-by-issue industry analysis only: each block covers one IB industry subissue with a substantive paragraph, supporting points, evidence sufficiency, EV/MET IDs, limitations, and downstream permissions.
   - Do not create a one-line idea list. If a subissue lacks support, put it in `research_backlog` with the needed evidence and research action.
   - Do not decide slide numbers, template variants, headline claims, or chart contracts in issue analysis.
   - Rejected analyses must not flow into slides.
   - Unverified or insufficient analyses may only flow into caveats/open questions when deck blueprint allows it.

6. **Template Registry And Deck Blueprint**
   - Use `skills/deck-blueprint-section/SKILL.md`.
   - Extract `template_registry.json` with `scripts/extract_template_registry.py`.
   - Write `deck_blueprint.json` as the single LLM-authored page-design artifact after issue analysis.
   - The blueprint owns deck storyline, investor question, page thesis, selected issue analysis IDs, template variant, headline, main message, body blocks, visual intent/data, caveats, open questions, and EV/MET bindings.
   - Do not write slide content as research notes. Each body block should be PPT copy with a label + data/mechanism + why it matters.
   - Validate `deck_blueprint.json`.
   - Compile `page_evidence_contract.json` and `renderer_spec.json` from the blueprint with `scripts/compile_deck_blueprint.py`; do not hand-write or patch the derived files unless you also update the blueprint and recompile.
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
   - Prefer `run_pipeline.sh` after all formal upstream artifacts exist.
   - PPT generation uses PPT/runtime dependencies only; search-provider availability belongs to the research stage, not the fill pipeline.
   - The pipeline must pass `pre_ppt` stage gate before filling PPT.
   - Only final delivery validation can mark the deck complete.

9. **Final report**
   - Report the run directory.
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
- `industry_section_filled_clean.pptx`
- `filled_ppt_validation.json`
- `artifacts/final_delivery_validation.json`

Missing upstream artifacts mean the run is not formal delivery.

## Pipeline Use

For formal PPT generation, run the packaged pipeline only after the formal upstream artifacts exist:

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
- formal search plan validation passing as a lightweight issue/subissue research plan;
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
If a PPT file exists but was not produced by `run_pipeline.sh` and validated by final delivery, mention it only as an invalid bypass artifact.

---
name: ib-industry-section
description: Generate a transaction-oriented investment banking industry section for a pitchbook, with structured draft, controlled page planning, PPT-ready copy, and optional fixed-template PPT filling. Use when the user explicitly asks for this skill or asks for an industry chapter linked to a specific target company. Supports Chinese or English output.
---

# IB Industry Section

Generate a transaction-oriented industry section for an investment banking pitchbook and, if requested, populate the bundled PowerPoint template.

This skill uses a lightweight agent-style workflow with LLM reasoning at the center, not a rigid serial JSON pipeline. The default workflow has two human review gates and four encapsulated sub-skills.

Design principle:
- This workflow is intentionally **LLM-driven** for research synthesis, storyline design, and slide drafting.
- Deterministic scripts should constrain execution and validation, not replace high-judgment reasoning.
- The goal is not to reduce model freedom, but to define clear stage contracts, review gates, and downstream execution rules.

## Purpose

Produce a target-linked, source-disciplined 8-slide industry section that tells a coherent transaction story — not a generic industry report. The default engagement context is `pre_mandate_transaction_pitch`: the section should demonstrate sector understanding, transaction relevance, and selective target implications before a formal mandate is necessarily won. LLM reasoning drives storyline strategy, page planning, page type selection, and slide-level copy in one integrated step (`industry_storyboard.json`), while deterministic scripts handle PPT token filling and quality validation.

At task start, read `references/execution_discipline.md` and then the task-relevant references it names. Before research or storyboarding, read `references/scope_boundary.md`. These define the fixed 8-slide delivery boundary, workflow decision tree, three relevance levels (`sector_credibility`, `transaction_relevance`, `target_implication`), claim-strength discipline, and cross-slide metric consistency.

## Workflow Decision Tree

Choose the smallest workflow that satisfies the user request:
- New industry section from a brief or attachments: run full workflow through research, memo, gap audit, storyboard, PPT fill, and QC.
- Existing industry PPT improvement: extract the current storyline, audit gaps and consistency, then regenerate only necessary pages unless a full rebuild is requested.
- Research-only update: stop after memo, memo validation, and gap audit.
- Storyboard-only update: use an existing validated memo; do not add new research facts.
- PPT formatting-only fix: skip research and storyboard changes; run PPT fill/clean/postprocess/validation or targeted formatting repair.

## Inputs

- **Target brief** or **input card** (`templates/input_card.template.json`)
  - Now supports `research_direction` with priority websites, source domains, source packs, topics, peer set, and exclusions.
  - `engagement_context` defaults to `pre_mandate_transaction_pitch`; do not ask the user to fill it unless they explicitly specify another context.
  - Do not enrich `input_card` with planner-inferred peers, risks, source preferences, or must-cover topics. The input card is for user-provided facts plus safe normalized metadata; planner hypotheses belong in `artifacts/research_plan.json`.
  - Generate `input_card.json` in transcription mode: copy the user's facts faithfully, perform only minimal metadata normalization, leave planner/research fields empty unless explicitly provided, and set output language to the user's request language unless the user asks otherwise.
- **User attachments** (optional — pitchbook drafts, CIM extracts, research notes)
- **Existing `industry_input_memo.md`** (optional — treated as canonical input if provided and user says "do not expand")

## Source Registry

`templates/source_registry.json` contains default priority-source packs and domain lists for research.

Source priority options:
1. User-specified domains from `input_card.research_direction`
2. User-specified source packs
3. Default source packs (`source_registry.json` → `default_packs`) only when `--use-default-packs` is requested
4. Unrestricted web search, which remains the default when no site or source-pack option is passed

Source packs are defined in `templates/source_registry.json`; treat that JSON as authoritative. At the time of writing it includes official, capital-markets, financial-data, filings, market-research, consulting, regional official, and business-media packs. Default packs are a smaller opt-in subset from the same registry.

The enhanced `scripts/web_search.py` supports `--site`, `--sites`, `--site-mode priority|only`, `--source-registry`, `--source-pack`, and `--use-default-packs` flags. Site-constrained search forces DuckDuckGo (Tavily API does not support `site:` syntax). Do not use `--use-default-packs` for every query; reserve it for a deliberate source-discovery pass or targeted validation pass.

Research source planning rule:
1. Read `templates/source_registry.json` as a menu before search.
2. Create a lightweight discovery plan in `artifacts/research_plan.json` from `templates/research_plan.template.json`. At this stage, fill meta fields and broad discovery queries only; keep industry boundaries, peer sets, source packs, and priority domains provisional or blank unless the user explicitly provided them.
3. Write `artifacts/search_log.md` before the first search attempt, using `references/search_log_template.md`. Update it incrementally during research; do not backfill it only after the memo is written.
4. Run initial unrestricted broad discovery queries before any default-pack or source-pack search. Use these searches to learn vocabulary, industry boundaries, metric names, source leads, and likely peer categories.
5. Upgrade the discovery plan into a formal research plan: add discovered source leads, selected source packs/domains by dimension, targeted validation queries, and selection reasons. Aim for 6-15 distinct high-priority domains across the full memo; use more only for regulated, cross-border, or data-sparse industries.
6. Validate the formal `artifacts/research_plan.json` before memo synthesis. A discovery-stage plan is not enough for memo/PPT work; missing targeted validation queries, selected domains, or selected source packs/domains are blocking in formal validation.
7. Run targeted validation against selected packs/domains. Do not run every default pack against every query.
8. Do not enter memo synthesis, storyboard, or PPT filling unless `research_plan.json`, `research_plan_validation.json`, and `search_log.md` exist in the same run directory and the formal research plan gate is passing.

## Runtime Bootstrap

Before starting from a brief or running PPT scripts, ensure the runtime is ready:

```bash
python3 scripts/bootstrap_runtime.py
```

`scripts/bootstrap_runtime.py` is the only supported runtime decision point. It checks existing Python interpreters first; if one can import `pptx`, `lxml.etree`, and at least one fallback-search provider, use it directly. Only if no existing interpreter is complete should it create/update `.venv` and install `requirements.txt`.

Do not manually split the PPT pipeline across multiple Python interpreters. Do not install packages into unrelated system or Node environments. Do not edit scripts to work around dependency issues. If bootstrap fails, stop and report the bootstrap error.

For shell use, get the selected interpreter with:

```bash
PYTHON_CMD="$(python3 scripts/bootstrap_runtime.py --print-python)"
```

If `.venv` creation fails because Python lacks `ensurepip` / `venv`, stop and install the matching system package (for example `python3-venv` or `python3.14-venv` on Debian/Ubuntu) or rerun bootstrap with `--python` / `PYTHON_BIN` pointing to a Python installation that supports `venv`.

On macOS, prefer Python 3.9-3.11 for this skill. If `python-pptx` installs but `lxml.etree` fails to import because of binary/code-signing issues, recreate the environment with a stable interpreter:

```bash
python3 scripts/bootstrap_runtime.py --python python3.11 --force
# or: python3 scripts/bootstrap_runtime.py --python python3.10 --force
# or: python3 scripts/bootstrap_runtime.py --python python3.9  --force
```

Do not proceed to research, storyboard, or PPT generation if mandatory runtime dependencies are missing.

Before research, validate any generated input card. If validation fails, rewrite the input card from the original user brief in transcription mode instead of patching it with inferred content:

```bash
"$PYTHON_CMD" scripts/validate_input_card.py \
  --input-card input_card.json \
  --output artifacts/input_card_validation.json
```

This gate is strict by design: do not auto-split the user's brief into inferred investment highlights, peer sets, risk lists, preferred sources, or must-cover research topics. Those belong in the research plan or memo only after research or explicit user instruction.

## Default Workflow

### 1. Research Memo
Use `skills/research-memo/SKILL.md`.

The research phase now includes:
- **Scope boundary**: read `references/scope_boundary.md` before planning; preserve fixed 8-slide output while researching broadly enough to support transaction judgment.
- **Research plan**: create `artifacts/research_plan.json` before memo synthesis; validate it with `scripts/validate_research_plan.py`.
- **Research emphasis**: after broad discovery, write a short `Research Emphasis / Hypothesis Plan` before memo synthesis so the formal memo focuses on the questions that matter for this transaction.
- **Freshness discipline**: fill `research_as_of_date` and `user_material_data_cutoff`; treat user-material periods as historical data periods, not as the current research date.
- **Source priority resolution**: apply the source planning rule described in Source Registry above.
- **Multi-round search**: cover all 9 dimensions (definition, size, segmentation, drivers, value chain, barriers, competition, trends, target implications).
- **Search log**: write `artifacts/search_log.md` incrementally during research.
- **Evidence Ledger**: assign an Evidence ID (EV-001, EV-002, ...) to each important claim or metric.
- **Research Gap Audit**: after the memo is written, audit critical gaps, weak sources, metric-scope conflicts, and transaction relevance before storyboarding.
- **Supplemental Research**: run one focused supplemental research pass only when the gap audit identifies critical gaps.
- **Chart-ready data**: mark quantitative Key Data Points with `chart_ready: true`.
- **Per-page Evidence Rows**: at least 2-3 per page.

Output: `industry_input_memo.md` (following updated `references/industry_input_memo_template.md`)

**Stop for human review** unless the user explicitly requests one-shot generation.

Reviewer should confirm: industry definition, market sizing logic, growth drivers, competitive landscape, target linkage, data sources and gaps, Research Plan coverage, Evidence Ledger completeness.

Research gap audit rule:
- Do not enter storyboard if `industry_input_memo.md` has unresolved Critical Gaps in its Research Gap Audit.
- Supplemental research is for critical gaps only; do not restart broad discovery or keep searching indefinitely.

If this run starts from only a brief or attachments and verified online research cannot be completed, stop after reporting the failure. Continue only if the operator explicitly chooses a degraded mode; any degraded output must label unsupported facts as `training_data` and must not be treated as diligence-grade.

Research plan audit rule:
- Broad discovery coverage in `search_log.md` does not by itself make research complete.
- After broad discovery, update `artifacts/research_plan.json` with actual selected source packs/domains, targeted validation queries, latest/current queries, and selection rationale.
- Run formal validation before memo synthesis:

```bash
"$PYTHON_CMD" scripts/validate_research_plan.py \
  --plan artifacts/research_plan.json \
  --source-registry templates/source_registry.json \
  --stage formal \
  --output artifacts/research_plan_validation.json
```

If formal validation fails, fix `research_plan.json` before writing the memo. Do not dismiss missing targeted queries or missing selected sources as formatting warnings.

### 2. Storyboard Section
Use `skills/storyboard-section/SKILL.md`.

Input: `industry_input_memo.md` + target brief + page type rules + slide layout library + content quality rules + layout budget

Output: `industry_storyboard.json`

This is the **main LLM reasoning step**. It generates, in one pass: storyline strategy, 8-slide page plan, selected page types (with rationale), slide-level PPT copy, source notes (with Evidence IDs), and template binding decisions.

Storyboard must preserve the pre-mandate transaction context: not a generic sector report, not a retained-client sell-side book, and not a target advertisement. Each slide's `slide_story_contract` must identify `primary_relevance_level`, `target_link_type`, and `claim_strength`.

**Content density requirements** (enforced by `templates/content_quality_rules.json`):
- Every body_copy field: label + opinion + evidence/implication
- Per-field density targets (see storyboard prompt for ranges)
- No banned generic phrases in body_copy or source_note
- At least 2 Evidence IDs or memo section references per slide
- Headline and main_message fit rules are enforced by `templates/text_fit_rules.json`: title must fit one line; subtitle/main_message targets one line and must not exceed two lines.
- Page-level copy and visual budgets are defined in `templates/layout_budget.json`: body fields must be short bullet-style points, table cells must stay compact, and `main_message` must not end with punctuation.
- Slide 1 right-side visual area is executable: storyboard must set `chart_data.chart_type` to `bar`, `stacked_bar`, `line`, `metric_cards`, or `none`; non-`none` choices need data that `scripts/postprocess_ppt_visuals.py` can render.

**Stop for human review** unless the user explicitly requests one-shot generation.

### 3. Storyboard Contract Validation

Run `scripts/validate_storyboard.py` before conversion or PPT filling.

Output: `artifacts/storyboard_validation.json`

This is deterministic validation of page type choices, `template_binding`, and active `body_copy` fields. If it fails, fix `industry_storyboard.json` upstream. The active layout contract is strict: missing fields, blank fields, or extra `body_copy` fields that the selected page type will ignore are errors, not cleanup suggestions.

### 3b. Content Quality Validation

Run `scripts/validate_content_quality.py` after storyboard validation. Density warnings remain advisory by default, but `source_warnings` and title/subtitle line-fit breaches are hard gates because weak sourcing and unreadable titles can make output non-deliverable.

```bash
"$PYTHON_CMD" scripts/validate_content_quality.py \
  --storyboard industry_storyboard.json \
  --memo industry_input_memo.md \
  --rules templates/content_quality_rules.json \
  --output artifacts/content_quality_validation.json
```

Review the output. Address `source_warnings` and blocking `layout_warnings` before proceeding. Address `density_warnings`, non-blocking `layout_warnings`, `chart_data_warnings`, `generic_copy_warnings`, and `evidence_warnings` as quality improvements, or use `--quality-gate` to make every warning a hard gate. Use `--allow-source-warnings` only for explicitly degraded/debug drafts that will not be delivered as diligence-grade output.

Content quality validation also checks that:
- `latest_query` and research artifacts do not treat user-material years as the current research period;
- body fields read like concise PPT bullets, not memo paragraphs;
- each body field has evidence, a metric, or mechanism / implication language rather than a bare topic label;
- titles, subtitles, source notes, chart data, and repeated metrics remain consistent enough for PPT delivery.

### 4. PPT Copy Finalize *(optional)*
Use `skills/ppt-copy-finalize/SKILL.md`.

Run only if: storyboard copy is too long, not PPT-ready, or `fill-ppt` requires the canonical `industry_section_ppt_copy.json` format.

Output: `industry_section_ppt_copy.json`

Do **not** introduce new facts. Only compress, reword, and align fields to `templates/ppt_copy_schema.json`.

In standard runs, if `industry_storyboard.json` already uses canonical `body_copy` field names, the deterministic converter may generate `industry_section_ppt_copy.json` directly. Use the LLM finalize step only when copy needs compression or field repair.

### 5. Fill PPT
Use `skills/fill-ppt/SKILL.md`.

This is a **deterministic script-driven step**. The LLM does not hand-write `replacement_dict.json`.

Outputs: `replacement_dict.json` → `industry_section_filled.pptx` → `industry_section_filled_clean.pptx` → `filled_ppt_validation.json`

Final PPT validation is a hard gate. If `filled_ppt_validation.json` has `summary.is_valid=false`, do not deliver the PPT. Fix the underlying issue instead of explaining it away.

Validation/fix loop limit: try at most 3 repair cycles for the same validation gate. If the same gate still fails, stop and report the failed gate, remaining errors, likely root cause, and smallest next action.

Operational note:
- Required runtime command: `python3 scripts/bootstrap_runtime.py --print-python`
- `run_pipeline.sh` can now start from `industry_storyboard.json` alone and auto-generate `industry_section_ppt_copy.json` when it is missing.

## Human Review Gates

| Gate | After | Artifact to Review |
|------|-------|--------------------|
| Gate 1 | Research Memo | `industry_input_memo.md` |
| Gate 2 | Storyboard Section | `industry_storyboard.json` |

Do **not** require separate manual review for intermediate debug files; the workflow checkpoints are the memo and storyboard.

## One-Shot vs Review Mode

- **Default mode**: stop after `industry_input_memo.md`, then stop again after `industry_storyboard.json`.
- **One-shot mode**: continue through storyboard, ppt_copy, and PPT filling only when the user explicitly asks for one-shot generation, full draft generation, or direct PPT output.
- **Weak-source caution**: one-shot mode removes manual review pauses, not machine gates. If source quality is clearly weak or key facts remain unverified, stop unless the operator explicitly chooses degraded/debug mode. Degraded output must flag gaps explicitly and must not be delivered as diligence-grade output.
- **Progress discipline**: use the checklist in `references/execution_discipline.md` internally for one-shot runs so research emphasis, gap audit, validation, and final delivery checks are not skipped.

## Required Outputs

- `industry_input_memo.md`
- `artifacts/research_plan.json`
- `artifacts/research_plan_validation.json`
- `artifacts/search_log.md` (written incrementally during research)
- `industry_storyboard.json`
- `artifacts/storyboard_validation.json`
- `artifacts/content_quality_validation.json`
- `industry_section_ppt_copy.json` (canonical input to deterministic PPT filling)
- `replacement_dict.json`
- `industry_section_filled_clean.pptx` (when PPT output is requested)
- `filled_ppt_validation.json`
- `artifacts/final_delivery_validation.json`
- `artifacts/run_quality_summary.md`
- `<work_root>/runs/RUNS_INDEX.md`
- `<work_root>/runs/LATEST_FINAL_RUN.txt`
- `<work_root>/runs/LATEST_FINAL_PPT.txt`

For final delivery, run:

```bash
"$PYTHON_CMD" scripts/validate_final_delivery.py \
  --run-dir <work_root>/runs/attempt_<timestamp> \
  --output <work_root>/runs/attempt_<timestamp>/artifacts/final_delivery_validation.json
```

Then generate a short quality report:

```bash
"$PYTHON_CMD" scripts/generate_run_quality_summary.py \
  --run-dir <work_root>/runs/attempt_<timestamp>
```

If multiple `attempt_*` directories exist, update the runs index before reporting the final answer:

```bash
"$PYTHON_CMD" scripts/update_runs_index.py \
  --runs-dir <work_root>/runs
```

Report the path from `LATEST_FINAL_PPT.txt` as the final PPT. Do not ask the user to infer the final deliverable from multiple attempt folders.

Do not deliver if final delivery validation fails.

Attempt management:
- For one user task, keep repairing the same active attempt directory.
- `run_pipeline.sh` writes `<work_root>/runs/ACTIVE_ATTEMPT.txt` and reuses it by default.
- Use `--attempt-name` only when intentionally starting or switching to a new attempt.
- Do not say a deck is complete until `artifacts/final_delivery_validation.json` reports `is_valid=true` for that same attempt and `LATEST_FINAL_PPT.txt` points to that deck.

## Input Resolution

This skill is meant to run inside a user's arbitrary workspace. Do not assume the current directory is clean, relevant, or already organized for this workflow.

Resolve inputs in this order:
1. explicit user-named files or folders
2. files attached or explicitly referenced in the conversation
3. user-provided text brief
4. limited current-directory discovery, only when the user did not specify inputs

Hard rules:
- Treat a user-specified folder as the effective work root.
- Do not silently adopt discovered files; use them only after explicit user confirmation.
- Do not treat the skill package directory as user source material.

## Output Convention

Generated working files should live near the resolved user materials. By default, deterministic pipeline outputs should be written under:

- `<work_root>/runs/attempt_<timestamp>/`

Use one run directory as the single package of record. Do not create a second nested `runs/attempt_*` directory inside an existing attempt directory, and do not copy only the final PPT out of the pipeline directory as the apparent delivery.

Only static skill assets should be resolved relative to the skill package itself, such as `scripts/`, `templates/`, `assets/`, `references/`, and `prompts/`.

## Non-Negotiable Rules

- Do **not** fabricate market data, source names, CAGRs, market sizes, or company facts.
- Do **not** rewrite user input into enriched facts before research. Inferred peers, source packs, priority websites, risks, and must-cover topics must be labeled as planner hypotheses in `research_plan.json` or researched findings in `industry_input_memo.md`.
- Default output language follows the user's request language. Only use another language when the user explicitly asks for it.
- Separate facts from interpretations. Directional judgments must read as inference, not disguised fact.
- User-provided target facts take priority for target-specific data unless clearly impossible; external sources take priority for industry, market, peer, and transaction context. Material discrepancies must be documented.
- Keep cross-slide metrics consistent: same value, unit, market definition, period, ranking basis, and target financials across all slides unless differences are explicitly labeled.
- Separate Sources from Notes discipline: sources identify origin; notes explain scope, calculations, assumptions, exclusions, and caveats.
- Every important number must have a source note. If a fact cannot be verified, write `Insufficient data`.
- If source data conflicts, state the conflict — do not average without explanation.
- The PPT template (8 logical slides, 16 physical slides with controlled variants on Slides 2/3/6/7) is a **delivery constraint**, not a reasoning constraint.
- `replacement_dict.json` must be generated **deterministically** from final PPT copy — never hand-written by the LLM.
- `industry_storyboard.json` is the main LLM reasoning artifact.
- `industry_section_ppt_copy.json` remains the canonical input to deterministic PPT filling.
- JSON artifacts must use ASCII double quotes (`"`) for all keys and string delimiters. Never use Chinese/smart quotes (`“”‘’`) in JSON syntax.
- Create JSON from structured objects whenever possible. Do not repair malformed storyboard JSON with global string replacements; if parsing fails, rebuild the object and serialize it with a JSON library.
- Validation artifacts must reference files inside the same attempt directory and must be newer than the source files they validate. Cross-attempt validation reuse is invalid.
- Web research is mandatory when starting from a brief or attachments.
- Source attribution must reference specific sources or Evidence IDs, not "industry reports" or "public sources."
- Weak sources such as Q&A sites, low-quality reposts, document-sharing pages, generic company-info pages, or SEO research portals may be used only as lead-finding aids. Put them in Rejected Sources or Lead-only Sources unless no stronger source exists, and label any retained claim as low confidence.
- Every body_copy field must contain opinion + evidence, not just a topic label or vague claim.

## When to Run Optional Steps

- **PPT Copy Finalize**: run when storyboard copy exceeds PPT placeholder limits, when copy is verbose rather than punchy, or when the user requests a cleaner `industry_section_ppt_copy.json`.
- **Content Quality Validation**: always run before PPT filling. Source warnings are blocking; review other warnings and fix issues in the storyboard before proceeding.
- **Storyboard validation**: always run before deterministic PPT filling. Fix the storyboard contract before attempting PPT execution.

## Failure Handling

- If a step fails, stop the chain, preserve completed run outputs, and report the failed step plus the next recommended action.
- If `fill-ppt` scripts fail, fix the upstream PPT copy or mapping — never patch the final PPT manually.
- If validation fails, diagnose and fix upstream rather than bypassing validation.
- If content quality validation produces source warnings, fix source attribution or evidence before PPT filling. Other warnings should be addressed when they materially affect deck quality; thin copy will produce thin slides.
- For Slide 2 `chart_plus_mini_table_page` and Slide 6 `compare_table_page`, final output must use real PPT table objects from post-processing; plain text with separators is not acceptable as the final table.

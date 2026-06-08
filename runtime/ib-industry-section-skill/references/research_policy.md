# Research Policy

Use this file when a workflow starts from a brief, attachments, or an existing
research pack that the user wants to expand.

Before running any local script, select one runtime and reuse it:

```bash
PYTHON_CMD="$(python3 scripts/bootstrap_runtime.py --print-python)"
```

## Baseline

- Web research is mandatory unless the user already provided
  `industry_research_pack.md` and explicitly said not to expand it.
- Provided materials are high-priority inputs, but they do not replace public
  source review for a formal delivery.
- Keep `input_card.json` transcription-only. Planner-inferred peers, sources,
  risks, or topics belong in the scope pack/search plan, not in the input card.
- The material is for `pre_mandate_transaction_pitch`: show sector credibility
  first, transaction relevance second, and selective target context only where
  supported.
- Broad discovery is scoping, not research synthesis. It defines the industry,
  vocabulary, category boundaries, data hierarchy, reconciliation risks, and
  unvalidated source leads.
- Formal research execution is the research gate. The search plan itself is not
  a hypothesis gate.

## Source Priority

Use unrestricted web search by default. Add domain constraints only when:

1. the user explicitly provided preferred domains or websites;
2. a source pack/domain was selected after broad discovery;
3. the operator deliberately requests a default-pack pass.

Never remove official, regulator, filing, company disclosure, or other
higher-authority domains merely to reduce a domain count. If research scope is
too broad, trim lower-authority media or aggregators first.

## Industry Scope Pack And Search Plan

Create these artifacts before formal research execution:

- `artifacts/industry_scope_pack.json`
- `artifacts/industry_scope_pack_validation.json`
- `artifacts/formal_search_plan.json`
- `artifacts/formal_search_plan_validation.json`
- `artifacts/search_log.md`

Recommended sequence:

1. Read `templates/source_registry.json` as a source menu only.
2. Draft 3-6 broad-discovery searches.
3. Create `artifacts/search_log.md` from
   `references/search_log_template.md` before the first search.
4. Run broad discovery to learn:
   - what the industry is called;
   - how narrowly it should be scoped;
   - parent/adjacent markets to exclude;
   - relevant geography and period terms;
   - likely source leads and peer/player categories.
5. Write `artifacts/industry_scope_pack.json` with:
   - working market, parent market, broader market, and adjacent markets;
   - narrow and broad definitions with included/excluded segments;
   - ambiguous category boundaries and how formal research should treat them;
   - data hierarchy and metric scopes that cannot be compared directly;
   - unvalidated numerical/directional leads that require formal validation;
   - required reconciliations and seed questions.
6. Validate the scope pack:
   ```bash
   "$PYTHON_CMD" scripts/validate_industry_scope_pack.py \
     --scope-pack artifacts/industry_scope_pack.json \
     --output artifacts/industry_scope_pack_validation.json
   ```
7. Write `artifacts/formal_search_plan.json` using
   `templates/formal_search_plan.template.json`.
8. Validate `artifacts/formal_search_plan.json` with
   `scripts/validate_formal_search_plan.py` before executing formal searches.

Do not put confirmed market size, growth rate, share, ranking, valuation,
competitive landscape, or page-ready claims in the scope pack. Any number found
during broad discovery is an unvalidated lead until formal research execution
promotes it.

The search plan must be issue/subissue based. Reuse the same issue taxonomy as
`industry_issue_analysis.json`:

- `market_size_growth`
- `demand_customer_logic`
- `industry_structure`
- `key_trends_drivers`
- `competitive_landscape`
- `competitive_dynamics`
- `pitch_relevance_target_context`

Do not write investment hypotheses in the search plan. For each relevant
issue/subissue, write a research question and one or more executable
`search_instructions[]` with exact query strings the next step should actually
run. The plan can be incomplete when an issue is not relevant, but every planned
`FS-xxx` instruction must be executed or removed before formal research
validation.

## Formal Research Execution

After the lightweight plan, run formal/latest/peer searches against the chosen
queries and sources. Record every attempt immediately in `search_log.md`.
`FS-xxx` IDs are planned instructions only. Each formal/latest/peer tool call
must create a real `S-xxx` search attempt in `search_log.md` before it can appear
in the execution report. Do not write the execution report from the plan alone.

Then write `artifacts/formal_research_execution_report.json` with one
`issue_results[]` entry per planned issue/subissue or explicit gap:

- `result_id`: `FR-001`, `FR-002`, ...
- `issue_area` / `subissue`
- `research_question`
- `status`: `supported`, `thin`, `conflicting`, `not_comparable`,
  `insufficient`, or `unavailable_after_research`
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

Start from `templates/formal_research_execution_report.skeleton.json` only for
the root structure. Do not treat it as a fill-all template, and do not create
results for unresearched issues just to populate the JSON.

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

Validate formal execution and source reviews before writing the research pack:

```bash
"$PYTHON_CMD" scripts/validate_formal_search_plan.py \
  --formal-search-plan "$RUN_DIR/artifacts/formal_search_plan.json" \
  --output "$RUN_DIR/artifacts/formal_search_plan_validation.json"

"$PYTHON_CMD" scripts/validate_formal_research_execution.py \
  --report "$RUN_DIR/artifacts/formal_research_execution_report.json" \
  --formal-search-plan "$RUN_DIR/artifacts/formal_search_plan.json" \
  --search-log "$RUN_DIR/artifacts/search_log.md" \
  --output "$RUN_DIR/artifacts/formal_research_execution_validation.json"

"$PYTHON_CMD" scripts/validate_source_reviews.py \
  --source-reviews "$RUN_DIR/artifacts/source_reviews.json" \
  --search-log "$RUN_DIR/artifacts/search_log.md" \
  --formal-research-execution-report "$RUN_DIR/artifacts/formal_research_execution_report.json" \
  --source-archive-index "$RUN_DIR/artifacts/source_archive/source_archive_index.json" \
  --run-dir "$RUN_DIR" \
  --output "$RUN_DIR/artifacts/source_reviews_validation.json"

"$PYTHON_CMD" scripts/validate_source_archive.py \
  --source-reviews "$RUN_DIR/artifacts/source_reviews.json" \
  --source-archive-index "$RUN_DIR/artifacts/source_archive/source_archive_index.json" \
  --run-dir "$RUN_DIR" \
  --output "$RUN_DIR/artifacts/source_archive_validation.json"

"$PYTHON_CMD" scripts/validate_stage_gate.py \
  --stage pre_research_pack \
  --run-dir "$RUN_DIR" \
  --source-registry templates/source_registry.json \
  --output "$RUN_DIR/artifacts/stage_gate_pre_research_pack_validation.json"
```

Do not write `industry_research_pack.md` until this pre-research-pack gate
passes.

## Data Conflicts

When sources disagree on market size, growth, share, margin, valuation, or peer
metrics:

- preserve the conflicting numbers in Metric Reconciliation;
- record source scope, period, unit, geography, and denominator;
- choose a preferred number only when there is a clear authority/scope reason;
- otherwise use a range, caveat, or `conflicting` status;
- do not promote a conflicting metric into a confident headline/chart.

## Source Reviews

`search_log.md` records search execution. `source_reviews.json` records source
audit cards. Use a root object with `schema_version: source_reviews_v1` and a
`reviews[]` array. A formal source review should include:

- exact URL;
- source title;
- locator (page/table/section/paragraph);
- short excerpt;
- linked search attempt IDs;
- linked EV IDs when applicable;
- `usable_as_evidence`.

Root domains, search result snippets, or unreviewed pages are not formal
evidence.

`usable_as_evidence` is a source-quality decision, not a formatting field.
Set it to true only when the exact page/report/PDF was opened, the locator and
excerpt support the linked EV row, and the source is acceptable for that claim's
strength. Set it to false for search snippets, root domains, unavailable
reports, weak mirrors/reposts without methodology, and pages that only identify
a lead for later research. Do not batch-convert missing values to true merely to
pass validation.

For every non-user source with `usable_as_evidence=true`, archive a reviewable
snapshot under `artifacts/source_archive/` and list it in
`artifacts/source_archive/source_archive_index.json`. Prefer a saved PDF or
clean markdown/text file. If the tool cannot save the full page/report, save an
`excerpt_snapshot` markdown file with URL, title, locator, reviewed excerpt, and
limitations. Do not invent full source text; archive what was actually reviewed.

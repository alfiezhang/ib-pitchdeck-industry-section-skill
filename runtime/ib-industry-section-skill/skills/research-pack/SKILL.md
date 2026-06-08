---
name: ib-industry-research-pack
description: Create the source-disciplined research pack and issue analysis pack for the IB industry section skill, including evidence and metric reconciliation.
---

# research pack

Generate or expand a structured industry research pack that serves as the canonical factual input for all downstream steps.

This skill is called at the start of every standard workflow run. It ensures the LLM has a complete, well-sourced, well-structured research base before any storyline or copy drafting begins.

This step is intentionally **LLM-driven**. The purpose is not to reduce research into a fixed template search routine, but to ensure the model leaves behind a research pack that downstream steps can treat as the factual contract.

## Purpose

Produce `industry_research_pack.md` — a comprehensive, source-disciplined research pack covering the industry definition, market sizing, growth drivers, value chain, competitive landscape, trends, and pitch-relevant implications / open questions.

The research pack is the human-readable source of truth for all facts used downstream. The machine-readable research output from this stage is `industry_issue_analysis.json`; deck blueprint and compiled page evidence contract are downstream artifacts and must trace back to research pack evidence and metrics.

Default context: this is a pre-mandate, transaction-oriented industry section used to pitch a potential client before a formal mandate is won. It is not a BP, CIM, retained-client deliverable, or target marketing document. Read `references/scope_boundary.md` before research. The research pack should support a pitch discussion by showing sector credibility, transaction relevance, and selective target context or open questions where supported, not by forcing target promotion on every page.

Also read `references/execution_discipline.md` at task start. Apply its data conflict handling, cross-slide metric consistency, Sources vs Notes discipline, and anti-patterns during research pack construction.

## Inputs

| Input | Required | Purpose |
|-------|----------|---------|
| Target brief / input card | Yes | Transaction context: target name, industry, transaction type, and optional `research_direction` |
| User attachments | No | Pitchbook drafts, CIM extracts, equity research, consultant reports |
| Existing `industry_research_pack.md` | No | If provided, this becomes expansion mode (refresh and deepen, don't start from scratch) |
| `templates/source_registry.json` | Optional | Source packs and domains for explicit priority search |
| `templates/formal_search_plan.template.json` | Yes | Planning artifact for executable formal research searches after thin industry scoping |
| `templates/formal_research_execution_report.skeleton.json` | Yes | Minimal root structure for execution reporting; do not treat it as a fill-all template |

## Issue Analysis Artifact

After formal research execution and research pack drafting, convert research pack evidence into the required issue-by-issue analysis pack:

- `industry_issue_analysis.json`: substantive analysis blocks, research backlog, and rejected/deprioritized analysis attempts

Generate issue analyses by transforming research pack facts into industry issue judgments. Do not freely brainstorm "interesting points." For each issue/subissue analysis:

1. Name the `issue_area` and one `subissue`.
2. Write a `core_statement`.
3. Write a substantive `analysis_text` paragraph. This is not slide copy and not a one-line insight.
4. List `supporting_points`, each tied to EV/MET IDs already present in the research pack where available.
5. Assign `evidence_sufficiency`, status, limitations, and downstream permission.
6. If support is insufficient, add a `research_backlog` item with the evidence needed and the research action. Do not promote the gap into a confident analysis block.

Rejected analyses must not flow into deck blueprint. Weak or single-source analyses may appear in body copy with caveats, but must not become confident headlines or chart anchors unless their `downstream_permission` allows it.

Do not use issue analysis to decide slide numbers, page layout, template variants, headline claims, or visual composition. The research layer may say whether an analysis is chart/headline/body eligible; deck blueprint is responsible for page allocation and drafting.

### Issue Analysis Contract

Do not invent alternate field names. `industry_issue_analysis.json` must use this
shape exactly:

```json
{
  "meta": {
    "target_company": "Target or Unknown Target",
    "industry": "Relevant industry",
    "geography": "Relevant geography",
    "research_as_of_date": "YYYY-MM-DD"
  },
  "issue_analyses": [
    {
      "analysis_id": "IA-001",
      "source_execution_result_ids": ["FR-001"],
      "issue_area": "market_size_growth",
      "subissue": "current_market_size",
      "analysis_type": "descriptive_market_fact",
      "core_statement": "One issue-level finding or evidence gap.",
      "analysis_text": "A substantive paragraph that explains the evidence, interpretation, limitation, and why the issue matters for the pitch discussion.",
      "supporting_points": [
        {
          "point": "A factual support point from the research pack.",
          "evidence_ids": ["EV-001"],
          "metric_ids": ["MET-001"],
          "role": "primary_fact",
          "evidence_sufficiency": "sufficient"
        }
      ],
      "evidence_sufficiency": "sufficient",
      "status": "validated",
      "evidence_ids": ["EV-001"],
      "metric_ids": ["MET-001"],
      "limitations": [],
      "candidate_use_cases": ["market_attractiveness"],
      "downstream_permission": {
        "headline_allowed": true,
        "chart_allowed": true,
        "body_copy_allowed": true
      }
    }
  ],
  "research_backlog": [
    {
      "issue_area": "competitive_landscape",
      "subissue": "winners_losers",
      "attempted_statement": "A judgment the research pack cannot yet support.",
      "reason": "Why current research pack evidence is insufficient.",
      "needed_evidence": ["Specific evidence needed before this can become issue analysis."],
      "research_action": "review_peer_data",
      "downstream_permission": "do_not_use_for_strong_claim"
    }
  ],
  "rejected_or_deprioritized_analyses": []
}
```

Valid enums:
- `issue_area`: `market_size_growth`, `demand_customer_logic`, `industry_structure`, `key_trends_drivers`, `competitive_landscape`, `competitive_dynamics`, `pitch_relevance_target_context`
- `evidence_sufficiency`: `sufficient`, `thin`, `insufficient`, `not_applicable`, `unavailable_after_research`
- `status`: `validated`, `partially_validated`, `unverified`, `rejected`

Common invalid aliases:
- do not use `insights`; use `issue_analyses`
- do not use `insight_id`; use `analysis_id`
- do not use `issue_topics`; use one `subissue` per analysis block
- do not use `status: active`; use `status: validated|partially_validated|unverified|rejected`
- do not use a string for `downstream_permission`; use the boolean object above

If an LLM draft already contains these alias fields, normalize it mechanically
before validation:

```bash
"$PYTHON_CMD" scripts/normalize_issue_analysis.py \
  --input industry_issue_analysis.json \
  --output industry_issue_analysis.json \
  --report artifacts/issue_analysis_normalization.json
```

## Starting Modes

- **Brief-only mode**: create `input_card.json` in transcription mode, then run broad discovery before formal search planning.
- **Input-card mode**: validate the provided card first; do not add inferred facts to make validation pass.
- **Existing-research pack mode**: treat the research pack as canonical if the user asks for refinement or PPT generation from it; refresh research only when requested or when freshness checks require it.

Before running any script in this skill, select one runtime and reuse it:

```bash
PYTHON_CMD="$(python3 scripts/bootstrap_runtime.py --print-python)"
```

For JSON artifacts, build a native object/dict and serialize with
`json.dump(..., ensure_ascii=False, indent=2)` or an equivalent structured
writer. JSON syntax must use ASCII double quotes (`"`), never smart/Chinese
quote delimiters (`“”`). If validation reports smart quotes, run
`scripts/repair_json_smart_quotes.py <file> --in-place` once and revalidate; if
repair fails, rebuild the JSON from the object/dict.

## Input Card Discipline

Do not enrich or rewrite `input_card.json` with inferred facts before research.

Build `input_card.json` in transcription mode:
- copy the user's brief faithfully into `target_business_summary`
- do not split user text into investment highlights, risks, peers, topics, or source preferences unless the user explicitly provided those as separate requirements
- leave `research_direction` empty unless the user explicitly supplied preferred websites, domains, packs, topics, peers, or exclusions
- set `language` to the user's request language by default; use another language only when explicitly requested
- if unsure whether a value is user-provided or inferred, leave the field blank and handle it in `formal_search_plan.json`

Allowed in input card:
- user-provided facts and explicit user requirements
- safe normalized metadata such as industry, geography, language, and transaction type, marked in `_provenance.normalized_metadata_paths`

Not allowed in input card unless explicitly provided by the user and marked in `_provenance.user_provided_paths`:
- peer set
- priority websites or preferred domains
- preferred source packs
- investment highlights
- risks/open questions
- must-cover topics

Planner-generated peers, sources, risks, and research topics belong in `artifacts/formal_search_plan.json`, then in `industry_research_pack.md` once researched.

Validate before research when an input card is generated:

```bash
"$PYTHON_CMD" scripts/validate_input_card.py \
  --input-card input_card.json \
  --output artifacts/input_card_validation.json
```

If this validation fails, restart from the original user brief and regenerate the card in transcription mode. Do not patch the failed card by adding new inferred content.

### research pack Generation Mode
- Trigger: brief only, or brief + attachments
- Process: industry scope pack → issue/subissue formal research execution → synthesize into structured research pack
- Always perform Web research, even when attachments are present

### research pack Expansion Mode
- Trigger: existing `industry_research_pack.md` is provided
- Default behavior: expand with Web research (refresh stale data, deepen weak sections, fill gaps)
- If user explicitly says "do not expand": treat research pack as canonical, skip research

## Source Priority

Use unrestricted web search by default. Add domain constraints only when the user provides preferred sources, the search plan selects a source pack, or a deliberate default-pack source pass is needed.

1. **User-specified**: `input_card.research_direction.preferred_source_domains` or `priority_websites`
2. **User-specified source packs**: `input_card.research_direction.preferred_source_packs`
3. **Default source packs**: `templates/source_registry.json` → `default_packs`, only with `--use-default-packs`
4. **Unrestricted web search**, the normal default

Use `scripts/web_search.py --site` / `--source-pack` / `--source-registry` / `--use-default-packs` for domain-constrained search.
Site mode forces DuckDuckGo because Tavily API does not support `site:` syntax.

## Industry Scope Pack And Search Plan Sequence

Before research pack synthesis, create:

- `artifacts/industry_scope_pack.json`
- `artifacts/industry_scope_pack_validation.json`
- `artifacts/formal_search_plan.json`
- `artifacts/search_log.md`

Execution order:
1. Read `templates/source_registry.json` as a source menu only. Do not execute default packs yet.
2. Create `artifacts/search_log.md` from `references/search_log_template.md` before the first search attempt.
3. Run 3-6 unrestricted broad discovery queries to learn industry vocabulary, scope, source leads, player categories, and unresolved definition questions.
4. Write `artifacts/industry_scope_pack.json` from `templates/industry_scope_pack.template.json`.
   - This stage is scoping only: define the working market, parent/adjacent markets, narrow/broad category boundaries, ambiguous items, data hierarchy, required reconciliations, unvalidated leads, and formal research seed questions.
   - Do not write confirmed market size, growth rate, share, ranking, competitive landscape, valuation multiples, or page-ready claims.
   - Any number or directional finding encountered during broad discovery belongs only in `unvalidated_leads` with explicit `must_validate[]`.
5. Validate the scope pack with `scripts/validate_industry_scope_pack.py`.
6. Write `artifacts/formal_search_plan.json` using `templates/formal_search_plan.template.json`.
7. Validate the formal search plan with `scripts/validate_formal_search_plan.py`.
8. The formal search plan must be issue/subissue based. Do not write investment hypotheses, transaction theses, or slide conclusions in the plan.
9. For each relevant issue/subissue, write a research question and clear executable `search_instructions[]`: `FS-xxx`, exact query string, purpose, and optional source hint. Do not write broad search angles, investment hypotheses, or slide conclusions.
10. Run formal/latest/peer searches by executing the planned `FS-xxx` instructions as real search tool calls. For each executed instruction:
   - run WebSearch or the configured local search provider using the exact query string or a minimally improved equivalent;
   - append one real `S-xxx` attempt to `search_log.md` immediately;
   - set `Search Stage: formal_research_execution`, `latest_check`, or `peer_check`;
   - set `Search Instruction IDs: FS-xxx`;
   - record selected source URLs, opened/reviewed status, and source limitations honestly.
11. Before writing the execution report, verify every `FS-xxx` kept in `formal_search_plan.json` has at least one real formal/latest/peer `S-xxx` attempt in `search_log.md`, or remove the unexecuted instruction from the plan.
12. Write `artifacts/formal_research_execution_report.json` from `templates/formal_research_execution_report.skeleton.json`. Do not use a filled template. Add one `issue_results[]` object for each executed `FS-xxx` instruction or unresolved planned issue/subissue.
   - Do not invent or reclassify `issue_area` / `subissue` in this report.
   - Copy `issue_area`, `subissue`, and `research_question` from the `formal_search_plan.issue_search_plan[]` item that owns each `FS-xxx`.
   - Put `FS-xxx` values only in `search_instruction_ids`.
   - Put actual `S-xxx` values only in `search_attempt_ids`.
   - If you have not run the search yet, do not create an `FR-xxx` result pretending it was executed; go back and run the search.
   - The execution report is an execution record: it records what was searched, what was found, what source was reviewed, and what remains thin or unavailable.
   - If a broad-discovery search only found source leads or vocabulary, keep it in `source_discovery_attempt_ids`; do not move it into `search_attempt_ids`.
13. Write `artifacts/source_reviews.json` for exact opened/reviewed page/report/PDF URLs.
   - `usable_as_evidence=true` means the source was actually opened/reviewed and can support a named EV row.
   - Use `usable_as_evidence=false` for search snippets, root domains, unavailable reports, mirrors/reposts without methodology, or pages that only provide a lead.
   - Do not batch-fill missing `usable_as_evidence` values with true. If validation flags missing fields, review each source and decide true/false from the locator, excerpt, source owner, and support for the claim.

Validate formal research execution before research pack synthesis:

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
  --output "$RUN_DIR/artifacts/source_reviews_validation.json"

"$PYTHON_CMD" scripts/validate_stage_gate.py \
  --stage pre_research_pack \
  --run-dir "$RUN_DIR" \
  --source-registry templates/source_registry.json \
  --output "$RUN_DIR/artifacts/stage_gate_pre_research_pack_validation.json"
```

If the pre-research pack gate fails, continue research or revise the formal research execution report. Do not start research pack synthesis.

Search count alone is not evidence of research quality. The formal execution report must show what issue/subissue each search supports, which source was reviewed, what was found, and what remains thin or unavailable. Do not maintain a separate topic coverage checklist in the research pack or search log.

If formal execution validation fails, repair in this order:
1. Check whether each planned `FS-xxx` was actually searched and logged as a real `S-xxx`.
2. Add missing formal searches and source reviews.
3. Only then repair execution-report fields.
Do not first rewrite taxonomy or reshape JSON unless the validator specifically says an issue/subissue pair is invalid. If the report has many schema errors immediately after planning, assume the execution report was written too early from the plan; return to real formal searches instead of polishing the JSON.

## Output

`industry_research_pack.md` following the structure defined in `references/industry_research_pack_template.md`.

This research pack is the stage contract for downstream reasoning:
- deck blueprint and compiled renderer spec should not introduce new facts beyond it
- weak, missing, or conflicting data should be visible here rather than silently corrected later

Required sections:
- Project meta (target, industry, geography, transaction type, date)
- **search plan** (references to industry scope pack, formal search plan, formal research execution, and selected source rationale; no separate coverage checklist)
- **Scope Boundary** (confirm pre-mandate transaction-oriented industry section, not generic report / consulting study / company deep dive)
- **Scope Pack And Formal Research Execution Summary** (project classification, issue/subissue research actually executed, source reviews, limitations)
- **Source Selection Rationale** (why selected packs/domains are relevant, and what was intentionally excluded)
- Deal context (why this industry section matters for this transaction)
- Target business summary
- Industry definition and scope
- Source materials (user-provided vs. web-researched, with attribution)
- **Evidence Ledger** (table: Evidence ID → claim → source → reliability → confidence)
- **IB Issue Fact Inventory** (fact status by common IB industry issue topic; this feeds issue analysis generation, not slide mapping)
- For every `Key Data Points` entry: `Definition`, `Source Name`, `Source Date`, `Confidence`, and `chart_ready` (true/false)
- **Research Gap Audit** (critical gaps, optional gaps, intentionally excluded topics, metric consistency)

### IB Issue Fact Inventory

Populate `## IB Issue Fact Inventory` before generating `industry_issue_analysis.json`.

This section records the factual base for common IB industry research topics. It does not decide slide order and does not force every topic into the PPT.

Allowed issue areas:
- `market_size_growth`
- `demand_customer_logic`
- `industry_structure`
- `key_trends_drivers`
- `competitive_landscape`
- `competitive_dynamics`
- `pitch_relevance_target_context`

Allowed fact status:
- `sufficient`: enough EV/MET support for a defensible judgment
- `thin`: some support exists, but downstream wording must stay cautious
- `insufficient`: do not create a confident issue analysis; use `research_backlog` or supplemental research
- `not_applicable`: explain why the topic does not apply to this industry or project scope

For `sufficient` or `thin` rows, include at least one EV-ID or MET-ID. Do not mark a topic sufficient merely because a source was found; the source must actually support the topic and have a usable scope, period, and definition.

Slide 1 requires explicit chart-readiness work. For the industry overview page,
actively search for and reconcile:
- historical market size or comparable benchmark data for at least 3 periods;
- CAGR or enough datapoints to calculate it;
- one structurally meaningful segmentation, benchmark, or adoption split where available;
- chart-ready data with consistent definition, geography, period, unit, and MET-IDs.

The downstream deck blueprint should be able to use `industry_overview_dynamic_page`
with left-side key messages and, where evidence supports it, a right-side
primary chart. If exact relevant market data is unavailable, document a safe
chartable proxy with clear caveats. If no reliable comparable chart or proxy is
defensible, document the data limitation explicitly so downstream deck blueprint does not
force weak evidence into a chart.

After writing the research pack, validate it before deck blueprint drafting:

```bash
"$PYTHON_CMD" scripts/validate_research_pack.py \
  --research-pack industry_research_pack.md \
  --run-dir . \
  --output artifacts/research_pack_validation.json
```

If validation fails, fix the research pack first. Do not proceed to deck blueprint, compiled renderer spec, or PPT with an incomplete research pack, missing Evidence Ledger rows, missing research artifacts, unresolved critical gaps, or low-provenance discovery leads promoted into formal evidence.

Before any second or later repair pass, run a repair-integrity audit on the files edited in the current attempt. Do not weaken evidence provenance merely to pass validators:

- do not change `Opened / Reviewed` from `no` to `yes` unless the source was actually opened or reviewed;
- do not delete broad-discovery search IDs when the correct fix is adding a formal/latest validation search;
- do not clear `source_pack` or swap higher-authority domains for lower-authority media just to reduce domain counts;
- do not delete EV/MET/source references instead of moving lead-only or low-provenance sources to search log / supplementary notes;
- do not relabel lead-only sources as formal Evidence Ledger rows.

For each such edit, restore the stronger evidence path, add the missing formal research execution, or justify why research integrity is preserved before regenerating the research pack.

### Evidence Ledger

Every important claim or metric must have an Evidence ID (EV-001, EV-002, ...). These IDs are the anchor points for downstream:
- Renderer spec `source_note` fields reference them
- Phase 2/3 fact-grounding harness traces them

Do not save fact creation for the final PPT stage. Page strategy should select and compress issue analyses and proof points from the research pack; the PPT fill step must not add new facts.

### Metric Reconciliation Discipline

`Metric Reconciliation` is the canonical metric table. Every MET-ID used in
Key Data Points, Chart-ready Data, deck blueprint, page evidence contract, renderer spec
chart data, headlines, or main takeaways must
first be defined as a populated row in the Metric Reconciliation table.

Do not create MET-IDs only inside page notes. Key Data Points must reference
existing Metric Reconciliation IDs, not invent new ones.

For CAGR rows, `CAGR Endpoint IDs` is mandatory and must contain exactly two
ordered value metrics: begin MET-ID, end MET-ID. Endpoint IDs must be existing
numeric `MET-###` rows, for example `MET-021, MET-022`. Do not use labels such
as `MET-BGN`, `MET-END`, `METBGN`, or `METEND`, and do not put endpoints in
`Comparable With`. Do not rely on a generic 5-year fallback. The begin/end rows
must share the same metric type, market definition, channel scope, geography,
and unit; otherwise the CAGR is not chart- or headline-ready.

For each slide-bound metric row, fill at minimum:
- Metric ID
- Metric Name
- Metric Type
- Market Definition
- Channel Scope
- Geography
- Data Period
- Value
- Unit
- Conflict Status

For time-series charts, use one MET-ID per period/datapoint with the same
Metric Type, Market Definition, Channel Scope, Geography, and Unit. Data Period
should differ by datapoint. Do not use Parent Metric ID to link time-series
datapoints to one another; Parent Metric ID is only for true subset/superset
relationships.

For share / category-share rows, either use a shared Parent Metric ID or make
the metric names/definitions explicit enough to show they are parts of one
structure split. The shares should sum to approximately 100% when they represent
a complete segmentation.

### Research Gap Audit

After the research pack is drafted and before deck blueprint drafting, add `## Research Gap Audit`.

Audit for material gaps in:
- sector definition and scope
- market size and growth
- segmentation
- growth drivers and headwinds
- value chain / profit pool
- competitive landscape
- business model economics
- transaction relevance
- buyer / investor logic
- valuation / M&A context
- selective target context or open diligence questions
- risks / counterarguments
- evidence quality
- metric consistency

Classify gaps as:
- `Critical Gap`: must be fixed before deck blueprint / compiled renderer spec
- `Optional Gap`: useful to mention as an open question
- `Not Relevant`: intentionally excluded with rationale

If any Critical Gap remains unresolved, run one focused Supplemental Research pass and update the research pack. Also run one focused supplemental-search pass for single-source or conflicting market size, CAGR, market share, ranking, channel mix, valuation / transaction multiple, or target financial metrics that would anchor a slide title, chart, main takeaway, or transaction implication. Do not proceed to deck blueprint, compiled renderer spec, or PPT with unresolved Critical Gaps unless the operator explicitly chooses degraded/debug mode.

### Metric Consistency

For every key metric, preserve scope and unit:
- TAM / SAM / SOM
- full industry / sub-sector / online / platform-specific
- GMV / revenue / sales / retail sales
- CAGR start/end years
- market share denominator
- ranking basis (platform, period, sales volume, GMV, or another measure)

If sources conflict, document the conflict and choose the cleanest source for charting; do not average silently.

User-provided target facts should remain the source of truth for target-specific data unless clearly impossible. External sources should support industry, market, peer, and transaction context. If the same target metric or market metric differs across materials, record the discrepancy and the selected source basis.

### Chart-ready Data

For quantitative pages (especially Slide 2), mark chart-ready Key Data Points with `chart_ready: true` and add a `Chart-ready Data` block with categories, values, units, periods, and source Evidence IDs.

## Research Rules

See `references/research_policy.md` for the full source hierarchy and verification rules.

Key principles:
- **Web research is mandatory** when starting from a brief or attachments.
- **Broad discovery precedes default-pack search**: read the source registry first, but do not run `--use-default-packs` until broad discovery has identified which source families are likely useful.
- **Formal research execution validation is mandatory** before research pack synthesis. The search plan is lightweight; the execution report and source reviews are the gate.
- **Formal execution blockers are not harmless** in one-shot delivery. Missing formal searches, missing source reviews, or unresolved issue/subissue results must be fixed or explicitly carried as gaps before research pack synthesis.
- **Search log is procedural, not post-hoc**: create it before the first search attempt and update it after each search. Do not reconstruct a clean log only after the research pack is complete.
- **Discovery plan is intentionally lightweight**: before broad discovery, avoid filling unknown peer sets, source packs, and industry boundaries from model prior knowledge. Let broad discovery inform the formal plan.
- **Runtime bootstrap is mandatory before fallback search**: run `python3 scripts/bootstrap_runtime.py --print-python` and use the returned interpreter for `scripts/web_search.py`.
- **Fail closed on mandatory research failure**: if built-in WebSearch/WebFetch and fallback search cannot return verified online sources, stop the workflow. Do not generate deck blueprint, renderer spec, or PPT from `training_data` unless the operator explicitly chooses degraded mode.
- **Low-provenance sources stay outside formal evidence by default**: search snippets, reposts, unsourced summaries, generic profile pages, document mirrors, and pages without a clear original publisher/methodology may suggest search terms but should be recorded as rejected or lead-only sources unless no stronger source exists and the limitation is explicitly disclosed.
- **Do not overstate source confidence**: aggregators, reposted report summaries, and pages without clear original methodology are not `verified` evidence by themselves. Mark them `inferred` or `secondary` unless independently validated by an official source, filing, primary report, or reputable media/source owner.
- **Record user-provided materials separately** from online research in `Source Materials`.
- **Use the source hierarchy**: primary (government/regulatory filings) > secondary (industry association reports) > tertiary (consulting firm summaries) > lowest (news articles).
- **Keep low-provenance sources out of core evidence**: unclear-origin, unsourced, mirrored, or search-optimized pages can suggest search terms but should be recorded as `Rejected Sources` or lead-only sources unless no stronger source exists.
- **Cross-check**: verify key numbers across multiple sources where possible.
- **Date everything**: note the period, geography, and source for every numeric fact.
- **Label confidence explicitly** in every `Key Data Points` row:
  - `verified`: directly supported by cited search/user-provided sources
  - `inferred`: calculated or synthesized from cited facts with a clear reasoning bridge
  - `training_data`: background knowledge not verified in this run and requiring follow-up
- **Search for the latest source first**: do not hard-code a year or period from user-provided materials into search queries unless the metric is inherently year-specific or you are verifying a source already known to be the latest available period.
- **Separate source date from data period**: the latest available disclosed datapoint may still be for an earlier period; search broadly first, then record the actual reporting period in the research pack.
- **Capture chart-ready data, not only chart ideas**: when a page is likely to need a quantitative chart, preserve the underlying categories, series values, units, and source rows in the research pack notes so downstream renderer-spec drafting can structure them.

## Search Tool Fallback

When the AI's built-in `WebSearch` / `WebFetch` tools are unavailable (e.g., third-party API proxy does not support them), use the project's fallback search script:

**Three-tier fallback:**
1. **First**: try the AI built-in `WebSearch` / `WebFetch`
2. **Detect failure**: if the response contains phrases like "I don't have a web search tool", "I'd be happy to help but", or returns no actual URLs/data — treat it as a hallucination, not a real search result
3. **Fallback 1 — Tavily** (requires `TAVILY_API_KEY` env var):
   ```bash
   python scripts/web_search.py --query "your search query" --provider tavily --output tmp/search_results.json
   ```
4. **Fallback 2 — DuckDuckGo** (free, no key needed):
   ```bash
   python scripts/web_search.py --query "your search query" --provider duckduckgo --output tmp/search_results.json
   ```
5. Or let auto mode handle it (Tavily first, DuckDuckGo fallback):
   ```bash
   python scripts/web_search.py --query "your search query" --output tmp/search_results.json
   ```
6. Read the results file and continue research with the data returned.

For priority site search:
```bash
"$PYTHON_CMD" scripts/web_search.py \
  --query "target industry market size" \
  --site cninfo.com.cn \
  --site-mode priority \
  --output tmp/search_results.json
```

For source-pack search:
```bash
"$PYTHON_CMD" scripts/web_search.py \
  --query "industry regulation policy" \
  --source-pack china_official \
  --source-registry templates/source_registry.json \
  --output tmp/search_results.json
```

For an explicit default-pack validation pass after broad discovery:
```bash
"$PYTHON_CMD" scripts/web_search.py \
  --query "industry market size latest official data" \
  --use-default-packs \
  --source-registry templates/source_registry.json \
  --output tmp/search_results.json
```

Use the default-pack command sparingly. It is useful for source discovery or validation, but it can fan out to many `site:` searches.

Run runtime bootstrap first with `PYTHON_CMD="$(python3 scripts/bootstrap_runtime.py --print-python)"`, then use `"$PYTHON_CMD"` for fallback search scripts. If bootstrap fails because Python lacks venv/ensurepip support, install the matching system package such as `python3-venv` or `python3.14-venv`, then rerun bootstrap. If `python-pptx` installs but `lxml.etree` fails to import on macOS Python 3.13/3.14, rerun with Python 3.9-3.11, for example `python3 scripts/bootstrap_runtime.py --python python3.11 --force`.

If all search providers fail or return zero results in a brief-only run, stop. Do not silently continue with `training_data` estimates.

## Expansion Rules (research pack Expansion Mode)

- Preserve useful transaction framing from the original research pack.
- Refresh weak, stale, unsupported, or missing sections with new Web research.
- Do **not** carry unsupported claims from the old research pack forward as facts.
- If the old research pack conflicts with stronger new evidence, prefer the more reliable, more recent, and more definition-matched source.
- Directional judgments are allowed, but they must read as inference or hypothesis rather than disguised fact.

## Human Review Gate

After this skill produces `industry_research_pack.md`, **stop for human review** unless the user explicitly requested one-shot generation.

Operational rule:
- in default mode, stop here
- in one-shot mode, continue only after making data gaps and source strength explicit in the research pack rather than hiding uncertainty

## Mandatory Checklist Before research pack Validation

1. Apply Evidence Promotion Gate: all Evidence Ledger rows must have been opened and reviewed.
2. Populate Claim Scope and Evidence Status for every EV row.
3. Populate Source Locator and Raw Excerpt for every primary-reviewed EV row.
4. Keep lead-only sources out of Evidence Ledger, Key Data Points, and downstream renderer-spec claims.
5. Populate Metric Reconciliation for every slide-bound quantitative metric.
6. Add Parent Metric ID for subset relationships.
7. Add CAGR Endpoint IDs for CAGR rows.
8. Resolve or explicitly flag conflicting / not_comparable / unresolved metrics.
9. Do not allow unresolved MET-IDs into downstream deck blueprint, page evidence contract, renderer spec, or slide notes.

---

The reviewer should confirm:
- Industry definition is accurate and appropriately scoped
- Market sizing and segmentation logic is sound
- Key growth drivers are well-identified and sourced
- Competitive landscape is correctly characterized
- Pitch relevance is clear; target context is selective and evidence-backed where used
- Data sources are credible and gaps are acknowledged
- formal research execution covers the issue/subissue points used downstream, or explicitly records gaps/backlog
- Evidence Ledger entries are present for key claims
- Chart-ready data has been preserved for quantitative pages

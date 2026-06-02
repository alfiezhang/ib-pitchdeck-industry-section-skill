# Storyboard Section

Convert a finalized industry input memo into a complete 8-slide industry storyboard that integrates storyline strategy, page planning, page type selection, and slide-level PPT copy in a single LLM reasoning step.

This is the **core reasoning step** and the single integrated LLM planning artifact for the industry section.

This step is intentionally **LLM-driven**. The purpose is to let the model reason through investor questions, transaction relevance, and slide logic in one pass, while still producing a disciplined downstream contract.

Before running any validator script in this skill, select one runtime and reuse it:

```bash
PYTHON_CMD="$(python3 scripts/bootstrap_runtime.py --print-python)"
```

## Purpose

The storyboard is a **planning + drafting** artifact, not a mechanical schema fill. The LLM must reason about the industry thesis, investor questions, page sequencing, and copy before writing. The output should read as a coherent narrative plan, not a disconnected JSON dump.

Default engagement context is `pre_mandate_transaction_pitch`: this is a transaction-oriented industry section for a potential pitch before a formal mandate is won. Read `references/scope_boundary.md` before drafting. The section must show sector understanding, transaction relevance, and selective target implications; it must not read like generic research or retained-client promotional copy.

Also read `references/execution_discipline.md` before drafting. Apply its cross-slide metric consistency, Sources vs Notes discipline, data conflict handling, and critical anti-patterns.

## Inputs

| Input | Required | Purpose |
|-------|----------|---------|
| `industry_input_memo.md` | Yes | Canonical research source for all facts, data, and source notes |
| Target brief / input card | Yes | Transaction context and target linkage anchor |
| `templates/page_type_rules.json` | Yes | Valid page types per slide and selection priority rules |
| `templates/slide_layout_library.json` | Yes | Physical slide XML file bindings per page type |
| `templates/ppt_copy_schema.json` | Yes | Field-level schema for body_copy structure |
| `templates/storyboard_schema.json` | Yes | Output schema — the contract this skill must fulfill |
| `templates/content_quality_rules.json` | Yes | Density targets, banned phrases, and quality thresholds |
| `templates/layout_budget.json` | Yes | Page-type capacity limits for body copy, tables, subtitles, and visuals |

## Required Pre-Draft Read

Before creating or editing `industry_storyboard.json`, read these files in this
order and keep them open as the contract:

1. `templates/storyboard_schema.json`
2. `templates/page_type_rules.json`
3. `templates/ppt_copy_schema.json`
4. `templates/ppt_copy_mapping.json`
5. `templates/layout_budget.json`
6. `templates/content_quality_rules.json`

Do not write a first draft and then discover the schema after JSON validation
fails. Build the storyboard as a native object/dict and serialize it with a JSON
writer such as `json.dump(..., ensure_ascii=False, indent=2)`. If the JSON is
malformed, rebuild from the object/dict; do not patch smart quotes or broken
JSON text by hand.

## Output

`industry_storyboard.json` — a single JSON file conforming to `templates/storyboard_schema.json`, containing:

1. **section_meta**: target name, industry, geography, language, source memo path
2. **storyline_strategy**: one-sentence thesis, transaction relevance, investor questions (3–5), key messages (5–8), known data gaps, tone guidance
3. **slides** (×8): slide role, selected page type, decision rationale, headline, main message, body copy, visual direction, optional chart_data, target link, source note, data gaps
4. **template_binding**: final variant selections for slides 2/3/6/7, list of inactive variants to remove
5. **qc_self_check**: honest self-assessment covering generic report risk, target linkage, source support, repetition, template fit, and content density

## Page Type Selection

This skill owns the final page type decision. The upstream memo may suggest presentation direction (`Presentation Hint`, `Visual Candidate`), but those are **soft inputs only**.

Before writing JSON, read the active page-type contract from:
- `templates/page_type_rules.json`
- `templates/ppt_copy_schema.json`
- `templates/ppt_copy_mapping.json`
- `templates/text_fit_rules.json`
- `templates/layout_budget.json`

For each slide, choose `selected_page_type` first, then fill only the active `body_copy` fields for that page type. Do not carry inactive fields from another variant into the final storyboard.

### Fixed Slides (no choice)

| Slide / canonical `slide_role` | Page Type |
|-------|-----------|
| 4 — `value_chain_profit_pool` | `value_chain_page` |
| 5 — `key_barriers_value_drivers` | `moat_page` |
| 8 — `key_takeaways_for_target` | `summary_page` |

### Controlled-Variant Slides (must choose)

| Slide / canonical `slide_role` | Options | Selection Priority |
|-------|---------|-------------------|
| 1 — `industry_overview` | `industry_overview_dynamic_page` or `summary_page` | Prefer dynamic overview when chart-ready market trend, benchmark, or structural split data exists; use summary only as fallback |
| 2 — `market_size_segmentation` | `chart_page` or `chart_plus_mini_table_page` | Prefer `chart_plus_mini_table_page` when segmentation needs side-by-side quantitative context; prefer `chart_page` when one visual carries the page |
| 3 — `key_industry_drivers` | `driver_card_page`, `driver_card_5_page`, or `driver_card_6_page` | Choose the card count supported by distinct MECE drivers; do not invent filler drivers to use a larger layout |
| 6 — `competitive_landscape` | `compare_table_page` or `matrix_page` | Prefer `compare_table_page` when named peer comparison is the clearest story; prefer `matrix_page` when 2D positioning is central |
| 7 — `industry_trends_future_evolution` | `trend_page`, `timeline_page`, `trend_4_card_page`, `trend_5_card_page`, or `trend_6_card_page` | Choose the card count supported by distinct trends; prefer `timeline_page` when sequence/timing is central |

Every variant selection must include a `decision_rationale` explaining why the chosen page type is better for this specific content.

## Mandatory Reasoning Flow

Before writing any JSON, the LLM must reason through these questions internally:

1. What is the **single most important conclusion** an investor should take from this section?
2. Given the transaction type, what **investor questions** must the section answer?
3. Which facts in the memo are **well-sourced**? Which are weaker?
4. How should the 8 slides **flow** from context → sizing → drivers → chain → barriers → competition → trends → target takeaways?
5. For each variant slide, which page type **best supports** the specific content and message?

The `storyline_strategy` section captures this reasoning explicitly.

### Slide Story Contract

For each slide, fill a `slide_story_contract` object **before** writing `headline`, `main_message`, or `body_copy`. This contract is the planning anchor that enforces one-story-per-slide and MECE boundaries.

Each contract requires:
- **question**: The single investor question this slide answers. One question only.
- **answer**: One-sentence conclusion that aligns with the headline.
- **primary_relevance_level**: `sector_credibility`, `transaction_relevance`, `target_implication`, or `mixed`.
- **target_link_type**: `light`, `selective`, or `central`. Not every slide should be target-central. Every slide must have a target_link; use `light` for slides where the target connection is contextual rather than the main message.
- **claim_strength**: `hard_fact`, `supported_inference`, `management_claim`, or `hypothesis`.
- **evidence_ids**: Evidence IDs from the memo that support this answer (at least 2 distinct IDs).
- **forbidden_topics**: Content types that must NOT appear on this slide (MECE enforcement). Be explicit.
- **visual_role**: What the visual area should communicate, in one sentence.

Default mapping: Slides 1/2/4/6 usually build `sector_credibility` with `target_link_type=light`; Slides 3/5/7 usually build `transaction_relevance` with `target_link_type=selective`; Slide 8 usually uses `target_implication` with `target_link_type=central`. Override only when the memo supports a better choice.

This contract is validated by `validate_storyboard.py`. If `forbidden_topics` overlap with body_copy content, the validator will flag a MECE violation. Because that validator is only a substring backstop, the LLM must also self-check every `forbidden_topics` item before writing body_copy.

### Use Page Evidence Packs

Before writing each slide, read that page's `Page Evidence Pack` in `industry_input_memo.md`.

- Select the strongest 2-4 memo arguments for the slide.
- Prefer arguments whose `relevance_level` and `claim_strength` match the slide story contract.
- Convert selected arguments into active `body_copy` fields.
- Preserve `Fact / data` -> `So what` -> `Target relevance`.
- Do not add new facts or do second-pass research in storyboard or PPT fill. If the memo evidence pack is thin, flag `data_gaps` instead of filling with generic copy.

### Bind Quantitative Claims to MET-IDs

For every slide containing a quantitative headline, chart, table, ranking,
market share, CAGR, GMV, valuation multiple, or financial metric:

- populate `slide_story_contract.metric_ids`;
- use only MET-IDs listed in the memo Metric Reconciliation table;
- do not use MET-IDs marked `conflicting`, `not_comparable`, or `unresolved`;
- ensure chart values and headline values match the memo values exactly.
- prefer MET-IDs with `cross-checked` or at minimum `single-source` status.
- for every quantitative `chart_data.source_rows[]` datapoint, include
  `metric_id` from the memo Metric Reconciliation table.
- do not put metrics with different `Metric Type`, `Geography`, `Unit`, or
  charted `Data Period` in the same bar/column chart unless they have been
  normalized to a common comparable basis and that basis is disclosed in
  `chart_data.notes`.

### Cross-Slide Metric Consistency

Before finalizing the storyboard, check that repeated metrics use the same value, unit, period, market definition, ranking basis, and target financials across slides. If different definitions are intentionally used, label them clearly in `source_note`, `chart_data.notes`, or `data_gaps`.

### Sources vs Notes

Use `source_note` to identify sources and Evidence IDs. Use `chart_data.notes` or `data_gaps` for scope, calculations, assumptions, exclusions, and caveats. Do not put source names, Evidence IDs, or parenthetical Chinese source citations such as `（某行业报告, 2025）` in body text.

### Pre-Mandate Relevance Balance

Across the 8-slide section:
- At least 3 slides should build `sector_credibility`.
- At least 2 slides should explain `transaction_relevance`.
- At least 2 slides should include `target_implication`.
- No more than 4 slides should use `target_link_type = central`.

Do not force target mentions on every slide. Target linkage should be selective, evidence-based, and transaction-relevant.

## Storyline Discipline

### One Story Per Slide

Each slide must cover **one core story dimension**. Do not mix unrelated topics on the same slide. If a fact does not fit the slide's role, it belongs on a different slide or should be dropped.

### MECE Content Allocation

Allocate content to slides so that the 8 slides together form a **complete, non-overlapping** story. Before drafting copy, map each major insight from the memo to exactly one slide:

| Content Type | Belongs On | Do NOT Put On |
|---|---|---|
| Overall market size, growth, TAM | Slide 1 or 2 (not both) | — |
| Selected structural drill-down (segmentation, channel, customer, application, etc.) | Slide 2 | Slide 1, 3 |
| Industry concentration (CR5/CR10) | Slide 6 (competitive landscape) | Slide 2 |
| Growth drivers / demand factors | Slide 3 | Slide 1, 2 |
| Value chain / margin structure | Slide 4 | Slide 5 |
| Entry barriers / moats | Slide 5 | Slide 4 |
| Competitor positioning / peer comparison | Slide 6 | Slide 3 |
| Regulatory / tech / ESG trends | Slide 7 | Slide 1–6 |
| Target-specific implications / recommendations | Slide 8 | Slide 1–7 |

### Slide 5 Barrier Discipline

For Slide 5 (`key_barriers_value_drivers` / `moat_page`), slide-level role overrides the global target-linked objective.

- Primary subject: industry-level barriers, winner capabilities, and value drivers.
- Secondary subject: selective Target implications, evidence of fit, or diligence questions.
- Required card logic: industry barrier / value driver -> why it matters in this sector -> Target implication or diligence question.
- Do not write this as a target-only moat page. Avoid headlines such as "Target's three moats" or "Target's competitive barriers."

### Slide 4 Value Chain Discipline

Slide 4 (`value_chain_profit_pool`) should primarily explain the industry value chain, profit pool, and value capture logic. Target positioning is secondary; do not make the headline primarily about the Target being in the best chain position.

### Slide 8 Balance Discipline

Slide 8 (`key_takeaways_for_target`) should synthesize transaction implications with judgment. Include at least one explicit open diligence question, risk, or validation item; do not make the final page only a positive target advocacy page.

### Slide 6 Competitive Landscape Discipline

Slide 6 (`competitive_landscape`) should primarily explain market structure, peer segmentation, and positioning dimensions. Target positioning is secondary; the headline and main message should not be primarily about the Target's advantage.

### Slide 1: Dynamic Industry Overview

Slide 1 is the industry overview. It should answer: is this industry large
enough, growing enough, and structurally interesting enough to deserve a
transaction discussion?

Use `industry_overview_dynamic_page` when the memo contains chart-ready data.
This dynamic page uses the existing slide 1 canvas, not a new master template:
preserve the left-side `KEY MESSAGES` area for three concise bullets, while
deterministic scripts replace only the right-side `CHART / VISUAL` area with a
real chart.

Preferred structure:

1. **Left key messages**: three concise bullets in `body_copy.bullet_1` through `body_copy.bullet_3`.
2. **Right primary chart**: historical market-size trend, benchmark trend, or another comparable quantitative series with at least 3 datapoints.

Use `summary_page` only when no reliable comparable chart data exists, metric
definitions are unresolved, or charting would be misleading. Do not default to
three flashcards when the memo has usable market-size, growth, benchmark, or
segmentation data.

Do not use a funnel unless the metrics are strict parent-child subsets under
the same geography, period, unit, and market definition. Otherwise, use a trend,
benchmark, or segmentation chart and label scopes clearly.

### Slide 2: Best Available Drill-down

Slide 2 must drill into the most decision-relevant structural factor from the
industry overview. It answers: **what structural dimension best explains the
industry opportunity?**

Do **not** hard-code Slide 2 as channel, segment, or any single topic. Select
the strongest drill-down role from `templates/drilldown_role_library.json` based
on evidence quality, distinctiveness from Slide 1, visualizability, and
transaction relevance.

Score candidate drill-downs using these dimensions (1-5 scale per criterion,
pick the highest total):

| Criterion | What it measures |
|---|---|
| Evidence strength | Quality and quantity of memo evidence |
| Decision relevance | How directly this axis matters for the transaction |
| Distinctiveness | How different from what Slide 1 shows |
| Visualizability | Can it be effectively charted or tabled |
| Transaction relevance | How it connects to target or transaction thesis |

Available drill-down roles (see `templates/drilldown_role_library.json` for
full descriptions): `market_segmentation`, `customer_structure`,
`channel_structure`, `application_scenarios`, `value_chain_profit_pool`,
`penetration_and_benchmark`, `technology_or_product_evolution`,
`policy_and_regulation`, `supply_demand_dynamics`, `competitive_structure`.

Fill the Slide 2 contract fields:
- `drilldown_role`: selected role from the library
- `page_role`: same as `drilldown_role`
- `drill_down_from_slide`: 1
- `new_information_added`: list the categories of new structural info this slide adds
- `primary_metric_ids`: MET-IDs that form this slide's quantitative backbone

CR5 / concentration data does NOT belong on Slide 2 — it belongs on Slide 6.

### Pyramid Writing Rule

Every `body_copy` field must follow the **conclusion → data → implication** pyramid:

```
[Conclusion/judgment]: [supporting data point] → [implication/target relevance]
```

Not: label-only text that states a topic without an opinion.
Not: data dumps without a takeaway.
Not: source references in body text — all Evidence IDs and source names belong in `source_note`.

| Pattern | Example |
|---|---|
| ❌ Label only | "需求结构：重点场景占比提升" |
| ❌ Data dump | "2023年占比62%，2024年预计65%，2025年预计68%" |
| ❌ Source in body | "重点场景占比达65%（EV-005），增长迅速" |
| ✅ Pyramid | "重点场景主导增长：占比从62%→65%→68%（2023-25E），带动行业价值池向高频应用集中" |

## Copy Rules

- **Headlines must be conclusion-led**: "The addressable market is a ¥XXX bn structural growth opportunity" — not "Market Size Overview."
- **Main messages must be one sentence**: The slide's thesis in a single investment-grade sentence.
- **Main messages are subtitles**: They must target one line, never exceed two lines, and must not end with terminal punctuation.
- **Body copy must be PPT-ready**: Bullets, cards, or panels — scannable, not paragraph-length. Use the field names from `ppt_copy_schema.json` for each slide role.
- **Body copy must fit the layout budget**: Apply `templates/layout_budget.json` before drafting; use slide-specific budgets when present (`1:summary_page`, `8:summary_page`), and keep table cells as compact labels, figures, or short judgments, not prose.
- **Chart-ready slides should carry data, not only chart ideas**: when a slide depends on a quantitative visual, include `chart_data` with chart type, categories, series, unit, and source-row notes.
- **Executable chart_data is mandatory for quantitative layouts**: `chart_page`, `chart_plus_mini_table_page`, and Slide 1 must include a `chart_data.chart_type` supported by the deterministic renderer.
- **Chart schema by type**:
  - `bar`, `clustered_column`, `stacked_bar`, `stacked_column`, `line`: require `categories`, `series[].name`, numeric `series[].values`, `unit`, and one `source_rows[]` entry per chart datapoint. Each quantitative `source_rows[]` entry must include a matching `metric_id`, `value`, and `period` from the memo Metric Reconciliation table. For multi-series charts, also include `series_name` and `category` on each `source_rows[]` entry so validation does not rely on row order.
  - `metric_cards`: require at least 3 `source_rows` for Slide 1 and at least 2 for any other slide; every row needs `label`, `value`, `period`, and `source`.
  - `none` is allowed only for non-quantitative layouts with no verified visual data.
- **Slide 1 dynamic overview data**: For `industry_overview_dynamic_page`, keep `body_copy.bullet_1` through `body_copy.bullet_3` as left-side key messages and use a primary `bar`, `stacked_bar`, `clustered_column`, or `line` chart in the right-side visual area. Do not add right-side flashcards when a chart is available. If only KPI cards are supportable, choose fallback `summary_page`.
- **Slide 1 visual anchor is executable**: Slide 1 is rendered from `chart_data`. Use a clean `metric_cards` payload only for fallback `summary_page`; do not describe a funnel if the actual `chart_data.chart_type` is `metric_cards`.
- **Metric card units are row-level when mixed**: if `metric_cards` mix currency, percentages, counts, or rankings, put `unit` or `value_unit` on each `source_rows[]` item, or include the unit directly in each value string. Do not use one mixed `chart_data.unit` such as `RMB / %`.
- **Matrix slides need coordinates**: for `matrix_page`, include numeric x/y coordinates per plotted player in `chart_data.source_rows`, or provide two numeric series that map to the x and y axes.
- **`chart_title` must stay client-facing downstream**: quantitative slides should make `chart_data.title` usable as the on-slide chart label; execution notes belong in `visual_direction` or `chart_data.notes`.
- **Target link is mandatory on every slide**: If a slide doesn't connect to the target, it's a generic industry slide — fix it or flag it.
- **Source notes are mandatory**: Reference memo Evidence IDs (e.g., EV-001), memo sections, or named sources. Never write "industry reports" or similarly vague attributions.
- **Weak sources are not formal evidence**: Do not use Zhihu, Baijiahao, repost/content-farm pages, document-sharing sites, SEO research pages, or generic company-info pages in slide `source_note` or as direct evidence. If they informed discovery, leave them in the search log as lead-only/rejected sources.

## Page Type Selection

- **Slide 1**: Prefer `industry_overview_dynamic_page` when chart-ready market trend, benchmark, or structural split data exists. Use `summary_page` only when reliable comparable chart data is unavailable or unsafe to chart.
- **Slide 2**: Prefer `chart_plus_mini_table_page` when segmentation needs side-by-side quantitative context. Prefer `chart_page` when one visual can carry the page clearly.
- **Slide 3**: Use `driver_card_page` for 4 strong MECE drivers. Use `driver_card_5_page` or `driver_card_6_page` only when the memo supports 5 or 6 distinct, non-overlapping drivers; do not create filler drivers just to use a larger template.
- **Slide 6**: Prefer `compare_table_page` when named peer comparison is the clearest story. Prefer `matrix_page` when positioning against two dimensions is the clearest story.
- **Slide 7**: Use `trend_page` for 3 strong parallel trends. Use larger trend-card variants only when the memo supports that many distinct trends; prefer `timeline_page` when sequence and timing are central.

## Content Density

Use the available template capacity fully — the goal is a rich, well-supported deck, not minimal placeholder-filling.

Target ranges (from `templates/content_quality_rules.json`):

| Field Type | Target Range |
|---|---|
| title / headline | Must fit one title line under `templates/text_fit_rules.json` |
| main_takeaway | Target one line; hard max two lines under `templates/text_fit_rules.json` |
| bullet / card | 45–95 chars, subject to `layout_budget.json` |
| panel | 55–105 chars, subject to `layout_budget.json` |
| table_row | 30–70 chars; cells must stay compact |
| timeline_stage | 60–100 chars |
| source_footer | 30+ chars |

Every active body_copy field must contain: **label/prefix + opinion/judgment + evidence/data/mechanism/target implication from the memo Page Evidence Pack**. See the storyboard prompt (`prompts/storyboard_section.prompt.md`) for examples.

Fields that fall below the minimum will be flagged by `validate_content_quality.py`.

## Guardrails

- Do **not** introduce facts not present in `industry_input_memo.md`.
- Do **not** invent CAGRs, market sizes, rankings, company names, or source names.
- Directional judgments are allowed but must read as inference ("management believes," "this suggests," "indicative"), not as hard fact.
- Match wording to `claim_strength`: `hard_fact` can be direct, `supported_inference` should be cautious, `management_claim` must be labeled as company/user-provided unless externally verified, and `hypothesis` must read as a diligence question or working hypothesis.
- Avoid overclaim language unless directly sourced as hard fact: 确定性, 不可逆, 无放缓迹象, 不可复制, 必然, 绝对领先.
- If a fact cannot be verified, write `Insufficient data` and flag it in `data_gaps`.
- If the memo contains conflicting data, state the conflict rather than silently picking one side or averaging.
- Every slide should reference at least 2 Evidence IDs or memo sections across body_copy + source_note.
- Avoid banned generic phrases (see `templates/content_quality_rules.json`).

## Post-Storyboard Quality Check

After producing `industry_storyboard.json`, run the content quality validator before human review:

```bash
"$PYTHON_CMD" scripts/validate_storyboard.py \
  --storyboard industry_storyboard.json \
  --schema templates/storyboard_schema.json \
  --text-fit-rules templates/text_fit_rules.json \
  --output artifacts/storyboard_validation.json

"$PYTHON_CMD" scripts/validate_content_quality.py \
  --storyboard industry_storyboard.json \
  --memo industry_input_memo.md \
  --rules templates/content_quality_rules.json \
  --output artifacts/content_quality_validation.json
```

Density and generic-copy warnings are advisory by default, except paragraph-like body fields that breach layout readability. Source warnings, title/subtitle line-fit breaches, and blocking layout warnings must be fixed because they affect diligence quality and final PPT readability. Review the output and address warnings before proceeding to PPT filling.

## Human Review Gate

After this skill produces `industry_storyboard.json`, **stop for human review** unless the user explicitly requested one-shot generation.

Operational rule:
- in default mode, stop here
- in one-shot mode, continue only if machine gates pass; weak-source areas require explicit degraded/debug mode and must not be delivered as diligence-grade output

The reviewer should confirm:
- Industry thesis supports the transaction
- Page sequence tells a coherent story
- Page type choices are appropriate for the content
- Every slide has a clear target link
- Key numbers have source attribution with Evidence IDs
- No generic-industry-report feel
- Body copy fields meet density targets
- No banned generic phrases in source_note or body_copy

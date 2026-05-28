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

## Output

`industry_storyboard.json` — a single JSON file conforming to `templates/storyboard_schema.json`, containing:

1. **section_meta**: target name, industry, geography, language, source memo path
2. **storyline_strategy**: one-sentence thesis, transaction relevance, investor questions (3–5), key messages (5–8), known data gaps, tone guidance
3. **slides** (×8): slide role, selected page type, decision rationale, headline, main message, body copy, visual direction, optional chart_data, target link, source note, data gaps
4. **template_binding**: final variant selections for slides 2/6/7, list of inactive variants to remove
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
| 1 — `industry_overview` | `summary_page` |
| 4 — `value_chain_profit_pool` | `value_chain_page` |
| 5 — `key_barriers_value_drivers` | `moat_page` |
| 8 — `key_takeaways_for_target` | `summary_page` |

### Controlled-Variant Slides (must choose)

| Slide / canonical `slide_role` | Options | Selection Priority |
|-------|---------|-------------------|
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
- **evidence_ids**: Evidence IDs from the memo that support this answer (at least 2 distinct IDs).
- **forbidden_topics**: Content types that must NOT appear on this slide (MECE enforcement). Be explicit.
- **visual_role**: What the visual area should communicate, in one sentence.

This contract is validated by `validate_storyboard.py`. If `forbidden_topics` overlap with body_copy content, the validator will flag a MECE violation.

### Use Page Evidence Packs

Before writing each slide, read that page's `Page Evidence Pack` in `industry_input_memo.md`.

- Select the strongest 2-4 memo arguments for the slide.
- Convert selected arguments into active `body_copy` fields.
- Preserve `Fact / data` -> `So what` -> `Target relevance`.
- Do not add new facts or do second-pass research in storyboard or PPT fill. If the memo evidence pack is thin, flag `data_gaps` instead of filling with generic copy.

## Storyline Discipline

### One Story Per Slide

Each slide must cover **one core story dimension**. Do not mix unrelated topics on the same slide. If a fact does not fit the slide's role, it belongs on a different slide or should be dropped.

Bad: Slide 2 mixing channel trends, sub-segment growth, AND CR5 concentration changes — three different stories competing for space.
Good: Slide 2 focusing on market size + one clear segmentation angle (channel OR sub-segments, not both).

### MECE Content Allocation

Allocate content to slides so that the 8 slides together form a **complete, non-overlapping** story. Before drafting copy, map each major insight from the memo to exactly one slide:

| Content Type | Belongs On | Do NOT Put On |
|---|---|---|
| Overall market size, growth, TAM | Slide 1 or 2 (not both) | — |
| Channel structure / distribution shifts | Slide 2 (if chosen focus) | Slide 1, 3 |
| Sub-segment breakdown / category trends | Slide 2 (if chosen focus) | Slide 1, 3 |
| Industry concentration (CR5/CR10) | Slide 6 (competitive landscape) | Slide 2 |
| Growth drivers / demand factors | Slide 3 | Slide 1, 2 |
| Value chain / margin structure | Slide 4 | Slide 5 |
| Entry barriers / moats | Slide 5 | Slide 4 |
| Competitor positioning / peer comparison | Slide 6 | Slide 3 |
| Regulatory / tech / ESG trends | Slide 7 | Slide 1–6 |
| Target-specific implications / recommendations | Slide 8 | Slide 1–7 |

### Slide 1: Three-Layer Funnel

Slide 1 is the industry overview. It must follow a **top-down funnel** — never skip layers:

1. **Layer 1 — Parent category scope**: Set the scene with the broadest relevant category (e.g., 整体化妆品市场)
2. **Layer 2 — Target category**: Narrow to the specific industry (e.g., 底妆市场)
3. **Layer 3 — Focused segment**: Zoom into the actionable segment (e.g., 线上底妆)

Each layer should be one bullet or one panel point. The funnel should feel natural, not forced.

### Slide 2: Single Focus Axis

Slide 2 covers market size AND segmentation. The segmentation angle must be **one clear axis**, not a grab-bag:

- Choose **channel structure** (online/offline, DTC/retail) OR **sub-segments** (by category, price tier, consumer segment) — not both.
- If the memo has strong data on both, pick the one that best serves the transaction thesis.
- CR5 / concentration data does NOT belong on Slide 2 — it belongs on Slide 6 (competitive landscape).

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
| ❌ Label only | "渠道结构：线上占比提升" |
| ❌ Data dump | "2023年线上占比62%，2024年预计65%，2025年预计68%" |
| ❌ Source in body | "线上渠道占比达65%（EV-005），增长迅速" |
| ✅ Pyramid | "线上渠道主导增长：占比从62%→65%→68%（2023-25E），驱动底妆品牌加速DTC转型" |

## Copy Rules

- **Headlines must be conclusion-led**: "The addressable market is a ¥XXX bn structural growth opportunity" — not "Market Size Overview."
- **Main messages must be one sentence**: The slide's thesis in a single investment-grade sentence.
- **Main messages are subtitles**: They must target one line, never exceed two lines, and must not end with terminal punctuation.
- **Body copy must be PPT-ready**: Bullets, cards, or panels — scannable, not paragraph-length. Use the field names from `ppt_copy_schema.json` for each slide role.
- **Body copy must fit the layout budget**: Apply `templates/layout_budget.json` before drafting; use slide-specific budgets when present (`1:summary_page`, `8:summary_page`), and keep table cells as compact labels, figures, or short judgments, not prose.
- **Chart-ready slides should carry data, not only chart ideas**: when a slide depends on a quantitative visual, include `chart_data` with chart type, categories, series, unit, and source-row notes.
- **Executable chart_data is mandatory for quantitative layouts**: `chart_page`, `chart_plus_mini_table_page`, and Slide 1 must include a `chart_data.chart_type` supported by the deterministic renderer.
- **Chart schema by type**:
  - `bar`, `clustered_column`, `stacked_bar`, `stacked_column`, `line`: require `categories`, `series[].name`, numeric `series[].values`, `unit`, and `source_rows`.
  - `metric_cards`: require at least 3 `source_rows` for Slide 1 and at least 2 for any other slide; every row needs `label`, `value`, `period`, and `source`.
  - `none` is allowed only for non-quantitative layouts with no verified visual data.
- **Slide 1 visual anchor is executable**: Slide 1's right-side `CHART / VISUAL` area is rendered from `chart_data`. Use a clean `metric_cards` payload when the best visual is KPI cards; do not describe a funnel if the actual `chart_data.chart_type` is `metric_cards`.
- **Matrix slides need coordinates**: for `matrix_page`, include numeric x/y coordinates per plotted player in `chart_data.source_rows`, or provide two numeric series that map to the x and y axes.
- **`chart_title` must stay client-facing downstream**: quantitative slides should make `chart_data.title` usable as the on-slide chart label; execution notes belong in `visual_direction` or `chart_data.notes`.
- **Target link is mandatory on every slide**: If a slide doesn't connect to the target, it's a generic industry slide — fix it or flag it.
- **Source notes are mandatory**: Reference memo Evidence IDs (e.g., EV-001), memo sections, or named sources. Never write "industry reports" or similarly vague attributions.
- **Weak sources are not formal evidence**: Do not use Zhihu, Baijiahao, repost/content-farm pages, document-sharing sites, SEO research pages, or generic company-info pages in slide `source_note` or as direct evidence. If they informed discovery, leave them in the search log as lead-only/rejected sources.

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

Density and generic-copy warnings are advisory by default. Source warnings and title/subtitle line-fit breaches are blocking because they affect diligence quality and final PPT readability. Review the output and address warnings before proceeding to PPT filling.

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

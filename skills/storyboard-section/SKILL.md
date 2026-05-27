# Storyboard Section

Convert a finalized industry input memo into a complete 8-slide industry storyboard that integrates storyline strategy, page planning, page type selection, and slide-level PPT copy in a single LLM reasoning step.

This is the **core reasoning step** and the single integrated LLM planning artifact for the industry section.

This step is intentionally **LLM-driven**. The purpose is to let the model reason through investor questions, transaction relevance, and slide logic in one pass, while still producing a disciplined downstream contract.

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
| 3 — `key_industry_drivers` | `driver_card_page` |
| 4 — `value_chain_profit_pool` | `value_chain_page` |
| 5 — `key_barriers_value_drivers` | `moat_page` |
| 8 — `key_takeaways_for_target` | `summary_page` |

### Controlled-Variant Slides (must choose)

| Slide / canonical `slide_role` | Options | Selection Priority |
|-------|---------|-------------------|
| 2 — `market_size_segmentation` | `chart_page` or `chart_plus_mini_table_page` | Prefer `chart_plus_mini_table_page` when segmentation needs side-by-side quantitative context; prefer `chart_page` when one visual carries the page |
| 6 — `competitive_landscape` | `compare_table_page` or `matrix_page` | Prefer `compare_table_page` when named peer comparison is the clearest story; prefer `matrix_page` when 2D positioning is central |
| 7 — `industry_trends_future_evolution` | `trend_page` or `timeline_page` | Prefer `trend_page` when trends are thematic/parallel; prefer `timeline_page` when sequence/timing is central |

Every variant selection must include a `decision_rationale` explaining why the chosen page type is better for this specific content.

## Mandatory Reasoning Flow

Before writing any JSON, the LLM must reason through these questions internally:

1. What is the **single most important conclusion** an investor should take from this section?
2. Given the transaction type, what **investor questions** must the section answer?
3. Which facts in the memo are **well-sourced**? Which are weaker?
4. How should the 8 slides **flow** from context → sizing → drivers → chain → barriers → competition → trends → target takeaways?
5. For each variant slide, which page type **best supports** the specific content and message?

The `storyline_strategy` section captures this reasoning explicitly.

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

Every active body_copy field must contain: **label/prefix + opinion/judgment + evidence/data/implication**. See the storyboard prompt (`prompts/storyboard_section.prompt.md`) for examples.

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
./.venv/bin/python scripts/validate_storyboard.py \
  --storyboard industry_storyboard.json \
  --schema templates/storyboard_schema.json \
  --text-fit-rules templates/text_fit_rules.json \
  --output artifacts/storyboard_validation.json

./.venv/bin/python scripts/validate_content_quality.py \
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

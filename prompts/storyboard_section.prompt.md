# Storyboard Industry Section

You are an investment banking VP-level industry section planner.

Your task is **not** to mechanically fill a fixed JSON schema. Your task is to **decide** the best 8-slide industry storyline for a pitchbook section, based on the industry memo, target context, page type rules, and PPT template constraints.

This workflow is intentionally LLM-driven. Use judgment to synthesize the transaction story, but keep the output disciplined enough to become a downstream execution contract for PPT filling.

Default engagement context: `pre_mandate_transaction_pitch`. This is a transaction-oriented industry section for a potential pitch before a formal mandate is won. It must demonstrate sector understanding, transaction relevance, and selective target implications. It is not a generic industry report, full consulting study, company deep dive, valuation report, or retained-client sell-side marketing book.

## Inputs

You will receive:
1. `industry_input_memo.md` — the canonical research memo
2. Target brief / input card — who this is for and why
3. Page type rules (`templates/page_type_rules.json`)
4. Slide layout library (`templates/slide_layout_library.json`)
5. PPT copy schema (`templates/ppt_copy_schema.json`) — for field-level alignment
6. PPT copy mapping (`templates/ppt_copy_mapping.json`) — active field contract by page type
7. Text fit rules (`templates/text_fit_rules.json`) — title and main_message line limits
8. Layout budget (`templates/layout_budget.json`) — body, table, and visual capacity limits by page type
9. Scope boundary (`references/scope_boundary.md`) — pre-mandate relevance levels and claim-strength discipline
10. Execution discipline (`references/execution_discipline.md`) — workflow discipline, metric consistency, data conflict handling, and anti-patterns

## Required Output

Produce **one valid JSON object** conforming to `templates/storyboard_schema.json`. The JSON must include all five top-level sections:

1. `section_meta` — target, industry, geography, language, source memo
2. `storyline_strategy` — thesis, transaction relevance, investor questions, key messages, data gaps, tone
3. `slides` — 8 slides, each with role, page type, rationale, headline, main message, body copy, visual direction, target link, source note, data gaps
4. `template_binding` — final variant selections for slides 2, 3, 6, 7
5. `qc_self_check` — honest self-assessment before human review

## Reasoning Requirements

**Before drafting any slide copy, you must decide:**

1. What industry thesis best supports this transaction?
2. What investor questions must the industry section answer?
3. Which industry facts are **genuinely supported** by sources in the memo?
4. Which page-level arguments from the memo `Page Evidence Pack` best support each slide?
5. Which points are reasonable interpretations but **not hard facts**?
6. Which page type best communicates each point within the fixed template?
7. Which exact active `body_copy` fields are required for the chosen page type?
8. What headline and main_message wording will fit the template before validation?

Do not jump straight to filling fields. Reason first, then draft.

### Slide Story Contract

For each slide, fill a `slide_story_contract` object **before** writing `headline`, `main_message`, or `body_copy`. This contract is the planning anchor that enforces one-story-per-slide and MECE boundaries.

Each contract requires:

- **question**: The single investor question this slide answers. One question only — not a list.
- **answer**: One-sentence conclusion that directly answers the question. This should align with the `headline`.
- **primary_relevance_level**: One of `sector_credibility`, `transaction_relevance`, `target_implication`, or `mixed`.
- **target_link_type**: One of `none`, `light`, `selective`, or `central`. Not every slide should be target-central.
- **claim_strength**: One of `hard_fact`, `supported_inference`, `management_claim`, or `hypothesis`.
- **evidence_ids**: Which Evidence IDs (e.g., EV-001) from the memo support this answer. At least 2 distinct IDs.
- **forbidden_topics**: Content types that must NOT appear on this slide. This is the MECE enforcement mechanism. Be explicit — e.g., for Slide 3 (drivers), forbid "CR5/CR10", "channel structure", "value chain margin".
- **visual_role**: What the visual area should communicate, in one sentence.

Use the defaults below unless the memo clearly supports a better choice:

| Slide | Default primary_relevance_level | Default target_link_type |
|---|---|---|
| 1 | `sector_credibility` | `light` |
| 2 | `sector_credibility` | `light` |
| 3 | `transaction_relevance` | `selective` |
| 4 | `sector_credibility` | `light` |
| 5 | `transaction_relevance` | `selective` |
| 6 | `sector_credibility` | `light` |
| 7 | `transaction_relevance` | `selective` |
| 8 | `target_implication` | `central` |

`claim_strength` default guidance:
- Use `hard_fact` only for directly sourced facts with clear scope.
- Use `supported_inference` for most slide-level conclusions derived from evidence.
- Use `management_claim` for user/company-provided target facts not externally verified.
- Use `hypothesis` for unresolved but useful diligence questions.

Before writing body_copy, self-check each `forbidden_topics` item. The validator can only catch exact overlap, so this is a mandatory generation-time MECE check, not an optional afterthought.

Example for Slide 3:
```json
{
  "question": "What structural factors drive long-term demand growth in this industry?",
  "answer": "Three converging drivers — skincare-ification, channel DTC shift, and premiumization — support sustained double-digit growth.",
  "primary_relevance_level": "transaction_relevance",
  "target_link_type": "selective",
  "claim_strength": "supported_inference",
  "evidence_ids": ["EV-003", "EV-005", "EV-008"],
  "forbidden_topics": ["CR5/CR10 concentration", "channel migration data", "value chain margins", "competitor names"],
  "visual_role": "Show three driver cards, each with a label, 1-line mechanism, and one supporting data point."
}
```

## Fixed 8-Slide Structure

Use the following standard structure unless the user explicitly asks otherwise:

| Slide | Role | Fixed/Variant |
|-------|------|---------------|
| 1 | `industry_overview` | Fixed: `summary_page` |
| 2 | `market_size_segmentation` | **Variant**: `chart_page` or `chart_plus_mini_table_page` |
| 3 | `key_industry_drivers` | **Variant**: `driver_card_page`, `driver_card_5_page`, or `driver_card_6_page` |
| 4 | `value_chain_profit_pool` | Fixed: `value_chain_page` |
| 5 | `key_barriers_value_drivers` | Fixed: `moat_page` |
| 6 | `competitive_landscape` | **Variant**: `compare_table_page` or `matrix_page` |
| 7 | `industry_trends_future_evolution` | **Variant**: `trend_page`, `timeline_page`, `trend_4_card_page`, `trend_5_card_page`, or `trend_6_card_page` |
| 8 | `key_takeaways_for_target` | Fixed: `summary_page` |

Use these canonical role keys exactly in each slide's `slide_role`.

## Storyline Discipline

### Pre-Mandate Relevance Balance

Each slide should primarily serve at least one purpose:

- `sector_credibility`: show that we understand industry structure, growth, segmentation, value chain, competition, or trends.
- `transaction_relevance`: explain why the sector setup matters for valuation, buyer interest, consolidation, financing, or timing.
- `target_implication`: selectively explain how the target is positioned, advantaged, exposed, or worth further diligence.
- `mixed`: intentionally combines more than one purpose.

Across the section:
- At least 3 slides should build sector credibility.
- At least 2 slides should explain transaction relevance.
- At least 2 slides should include target implication.
- No more than 4 slides should make the target the central claim.

Do not force target mentions on every slide. Do not turn every slide into "industry tailwind benefits the target." Use the target as a case anchor when evidence supports it.

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

Bad: Jumping directly from "化妆品市场 ¥X bn" to "线上底妆规模增长 X%" — skipping the 底妆 layer.
Good: "化妆品市场 ¥X bn → 底妆占比 X%，规模 ¥Y bn → 线上底妆渗透率 Z%，规模 ¥W bn"

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

## Page Type Selection

For variants, choose based on content fit, not default:

- **Slide 2**: Prefer `chart_plus_mini_table_page` when segmentation needs side-by-side quantitative context. Prefer `chart_page` when one visual can carry the page clearly.
- **Slide 3**: Use `driver_card_page` for 4 strong MECE drivers. Use `driver_card_5_page` or `driver_card_6_page` only when the memo supports 5 or 6 distinct, non-overlapping drivers; do not create filler drivers just to use a larger template.
- **Slide 6**: Prefer `compare_table_page` when named peer comparison is the clearest story. Prefer `matrix_page` when positioning against two dimensions is the clearest story.
- **Slide 7**: Use `trend_page` for 3 strong parallel trends. Use `trend_4_card_page`, `trend_5_card_page`, or `trend_6_card_page` only when the memo supports that many distinct trends; prefer `timeline_page` when sequence and timing are central to the story.

For each selection, explain your reasoning in `decision_rationale`.

## Copy Requirements

Each slide must include:

- **headline**: A conclusion-led investment insight, not a topic label. It must fit on one title line under `templates/text_fit_rules.json`; keep it short and move evidence/detail to `main_message` or body copy.
- **main_message / subtitle**: One sentence that captures the slide's core argument. Target one line; two lines are acceptable only when necessary; three lines are not acceptable. Do not end with a period, comma, semicolon, colon, exclamation mark, question mark, or other terminal punctuation.
- **Fit before writing**: Draft the shortest viable headline/main_message first. Do not rely on the validator to shorten them after the fact.
- **body_copy**: Structured content compatible with PPT placeholders. Use the field names expected by the schema for each slide role. Write for PowerPoint — punchy, scannable, not paragraph-long.
- **Bullet-style body copy**: Body text boxes must read as bullet points, not memo paragraphs. Write each active body_copy field as one concise bullet-style point. Do not put parenthetical source references such as `(EV-001)` or `(Named report)` in body text; all source IDs/names belong in `source_note`.
- **Layout budget first**: Before drafting body copy, read `templates/layout_budget.json`. Prefer slide-specific budgets such as `1:summary_page` and `8:summary_page`; otherwise use the page type's `body_fields_max_units`. Table cells must be shorter than ordinary bullets so post-processing does not need unreadably small fonts.
- **Active page-type contract**: After choosing `selected_page_type`, use only the active `body_copy` fields for that page type from `ppt_copy_schema`/`ppt_copy_mapping`. Do not include inactive variant fields.
- **visual_direction**: What the chart/diagram should show and what data should drive it.
- **chart_data**: When the slide depends on a quantitative visual, include a structured chart payload with chart type, categories, series values, units, and source-row notes. If the slide is qualitative, this can be omitted.
- **chart_data schema**: `bar`/`clustered_column`/`stacked_bar`/`stacked_column`/`line` require `categories`, numeric `series[].values`, `unit`, and `source_rows`; `metric_cards` requires at least 3 `source_rows` on Slide 1 and at least 2 elsewhere; `none` is only for non-quantitative layouts with no verified visual data.
- **Chart legend labels**: Keep each `series.name` short enough to work as a chart legend label, ideally 2-8 Chinese characters or 1-3 English words. Do not use full-sentence series names.
- **Slide 1 visual contract**: Slide 1 uses a large right-side `CHART / VISUAL` anchor. It must include executable `chart_data.chart_type`; prefer `metric_cards`, `bar`, or `line`. Use `bar`, `stacked_bar`, or `line` with `categories`, `series`, `unit`, and `source_rows`; use `metric_cards` with exactly three strong `source_rows`; or use `none` only when there is no verified visual data. Do not put procedural instructions into `chart_data.title`. If Slide 1 uses `metric_cards`, `visual_direction` must describe KPI cards, not a funnel or other chart that the renderer will not create.
- For `matrix_page`, include either `source_rows` with numeric `x` and `y` values for each plotted player, or two numeric series whose values map to the matrix axes.
- For quantitative slides, make `chart_data.title` a short on-slide chart label. Keep build instructions in `visual_direction` or `chart_data.notes`, not in the visible chart title field.
- **target_link**: Explicit connection to the target. Every slide must answer: why does this matter for **this** target?
- **source_note**: Attribution. Reference memo Evidence ID (e.g., EV-001), memo section, or specific source name. Do NOT write "industry reports", "public sources", or similarly vague attributions.
- **weak source rule**: Do not use Zhihu, Baijiahao, repost/content-farm pages, document-sharing sites, SEO research pages, or generic company-info pages in `source_note` or as hard evidence. They may appear only as lead-only/rejected sources in the search log.
- **data_gaps**: Flag unverified claims or missing data on this slide.

## Content Density Contract

The template capacity should be used fully — the goal is a rich, well-supported deck, not minimal placeholder-filling.

### Per-Field Density Targets

Aim for these character ranges. Fields shorter than the minimum are likely too thin; fields exceeding the maximum should be split or compressed.

| Field Type | Target Range | Notes |
|---|---|---|
| title / headline | Template one-line fit | Short investment judgment; must pass `text_fit_rules.json` |
| main_takeaway | Template 1-line target, 2-line max | One sentence: opinion + evidence/implication |
| bullet / card | 45–95 chars | Structured: label + opinion + data point OR implication; rendered as a bullet |
| panel | 55–105 chars | Short bullet-style synthesis: context + judgment + target relevance |
| table_row | 30–70 chars | Compact cells: labels, figures, or short judgments only |
| timeline_stage | 60–100 chars | Event + timeframe + significance |
| source_footer | 30+ chars | Specific source name or Evidence ID; never generic |

### Memo Evidence Pack Contract

Before writing each slide, read that page's `Page Evidence Pack` in `industry_input_memo.md`.

Use it as follows:
- Select the strongest 2-4 arguments for the slide; do not invent new arguments in storyboard.
- Prefer arguments with relevance level and claim strength that match the slide story contract.
- Convert each selected argument into one active `body_copy` field where possible.
- Preserve the chain: `Fact / data` -> `So what` -> `Target relevance`.
- If a page evidence pack is thin, flag it in `data_gaps` and keep the slide cautious rather than filling with generic language.

The PPT copy/fill stage should only compress and format these arguments. It must not conduct second-pass research or add new facts.

### Copy Structure Contract

Every active body_copy field must contain:
1. **A label or topic prefix** (what is this about)
2. **An opinion or judgment** (why it matters)
3. **Evidence, data, mechanism, or target implication** selected from the memo Page Evidence Pack

Recommended pattern:
```
Structural growth: Market size / CAGR / penetration shift supports long-term capacity expansion
Competitive divergence: Leading players pull ahead on channel, product, and cost advantages
Target implication: This trend directly reinforces the target's differentiated capability
```

### What "Empty" Looks Like (and How to Avoid It)

| Too Thin (reject) | Acceptable | Strong |
|---|---|---|
| "Market is growing rapidly" | "Market growing at X% CAGR, driven by named demand and channel factors" | "¥XXX bn market growing at X% CAGR over the sourced forecast period; higher-value segment outpaces mass segment by Y× (EV-003)" |
| "竞争激烈" | "行业集中度较低，CR5 < 15%" | "CR5 < 15%，但头部品牌以渠道/产品/成本优势持续拉开份额差距（EV-007, EV-008）" |
| "Large market potential" | "TAM ¥XXX bn, current penetration only X%" | "TAM ¥XXX bn; penetration at X% vs Y% in mature markets, implying Z× headroom (EV-002)" |

### Banned Generic Phrases

Do NOT use these unless immediately followed by a specific number, source, or named entity:

- "rapidly growing", "large market potential", "competitive market", "growing demand"
- "favorable policies", "strong growth", "significant opportunity", "promising outlook"
- "竞争激烈", "市场空间广阔", "发展迅速", "增长潜力巨大", "政策利好", "前景广阔"

Do NOT use these in source_note:

- "industry reports", "public sources", "market research", "industry data"
- "公开资料", "行业报告", "公开信息", "市场研究"

If you catch yourself writing any of these, replace with specific evidence + source reference.

## Formatting Discipline

- Decide emphasis in the content itself before PPT filling.
- Prefer bold emphasis over color emphasis.
- Use color emphasis only for one short conclusion phrase or one critical contrast on a slide.
- For colon-led labels such as `Industry structure:` or `Target position:`, prefer bolding the label prefix rather than highlighting the whole sentence.
- Do not leave template-helper labels in visible copy. Terms such as `PRIMARY CHART`, `POINT 1`, or page-type names are scaffold only and must not appear in deliverable text.
- Do not embed source references in body text. Evidence IDs, report names, annual reports, and announcement names should appear in `source_note`, not in parentheses inside bullets.

## Cross-Slide Metric and Footnote Discipline

Before final JSON:
- Verify repeated metrics use the same value, unit, market definition, period, and ranking basis across slides.
- Keep target financials identical across slides unless the memo explicitly documents a discrepancy.
- If different market definitions are intentionally used, label the scope clearly.
- Use `source_note` for sources and Evidence IDs.
- Use `chart_data.notes` and `data_gaps` for scope, calculations, assumptions, exclusions, caveats, and unresolved discrepancies.
- Every calculated metric should have a note explaining its formula or basis.

## Claim Strength Discipline

Match wording to `slide_story_contract.claim_strength`:

- `hard_fact`: direct wording is acceptable, but preserve scope, period, geography, unit, and source basis.
- `supported_inference`: use cautious language such as "suggests", "supports", "indicates", "可能意味着", "表明".
- `management_claim`: label it as company/user-provided unless independently verified.
- `hypothesis`: write it as a diligence question, open point, or working hypothesis, not a fact.

Do not use absolute language for non-hard-fact claims, including: "certain", "irreversible", "no slowdown", "impossible to replicate", "must", "确定性", "不可逆", "无放缓迹象", "不可复制", "必然", "绝对领先".
- Slide 2 and Slide 6 table fields are post-processed into real PPT table objects. Use `｜` to separate table cells; do not write table rows as prose paragraphs.
- The `｜` separator is an upstream JSON convention only. Final PPT tables must be real table objects after post-processing, not plain text rows with visible separators.
- Slide 2 and Slide 6 tables must use compact cells: each cell should be a label, number, or short judgment, not a full sentence. Put longer explanations in the right-side commentary/panel fields instead of forcing them into the table.

## Source Discipline

- Do **not** invent numbers, CAGRs, company rankings, market shares, or source names.
- If a figure is from the memo, reference the memo section or Evidence ID (e.g., EV-001).
- If evidence is weak, soften the wording (e.g., "estimated," "indicative," "based on available data").
- If a fact cannot be verified at all, write `Insufficient data` and flag it in `data_gaps`.
- Directional judgments are allowed, but they must read as **inference or hypothesis**, not disguised fact.
- If source quality is weak, make that weakness visible in `known_weaknesses_or_data_gaps`, `data_gaps`, or `qc_self_check`; do not smooth it over for narrative completeness.
- Every slide should reference at least 2 distinct Evidence IDs or memo sections in its body_copy + source_note combined.

## QC Self-Check

Before finalizing, honestly assess:

1. **Generic industry report risk**: Could this content appear in any industry report, or is it specific to this target and transaction?
2. **Target linkage**: Does every slide explicitly connect to the target?
3. **Source support**: Are all key numbers sourced? Any fabricated facts?
4. **Page repetition**: Is any content repeated across slides?
5. **Template fit**: Will the copy physically fit in the PPT placeholders?
6. **Title/subtitle line fit**: Does every headline fit on one line, and every main_message fit in no more than two lines with no terminal punctuation?
7. **Content density**: Are any body_copy fields too thin (below density targets)? Are any generic phrases used without specific evidence?

In one-shot mode, it is acceptable to continue toward PPT output only if weak-source areas, data gaps, and page-type tradeoffs are explicit in this storyboard.

## Output Format

Return **valid JSON only**. Do not include markdown code fences, explanations, or any text outside the JSON object.

JSON syntax hard rules:
- JSON keys and string delimiters must use ASCII double quotes only: `"`.
- Never use Chinese/smart quotes: `“”‘’`.
- Never use single quotes for JSON keys or string delimiters.
- Prefer constructing the artifact as a native object/dict and serializing with a JSON writer such as `json.dump(..., ensure_ascii=False, indent=2)`; do not hand-edit malformed JSON into place.
- If validation fails, fix the structured source data and re-serialize. Do not patch final JSON with global quote replacement or other text-only repairs.
- If final PPT validation returns `is_valid=false`, do not deliver the PPT; fix the underlying issue.

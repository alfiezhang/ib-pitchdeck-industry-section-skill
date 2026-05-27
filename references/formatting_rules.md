# Formatting Standards

Use this file before generating `industry_section_ppt_copy.json` and before reviewing a filled deck.

## Objective

The final output should look like a finished investment-banking presentation, not a template with text inserted into boxes. Formatting discipline is a first-order requirement, not a cleanup step.

## Non-Negotiables

1. **Same-level text must keep the same size.**
   If two boxes are the same hierarchy level on the slide, do not create emphasis by changing font size inside one of them.

2. **Emphasis is selective, not decorative.**
   Emphasis should come from:
   - bold
   - restrained color highlight
   - placement / page structure

   Do not create emphasis through ad hoc font-size changes inside same-level body text.

   Default preference:
   - use **bold first**
   - use color highlight only when a short conclusion phrase truly needs stronger contrast

3. **One focal point per slide.**
   Each slide should have one dominant conclusion the reader notices first.

4. **Content density: fill the template, don't just occupy it.**
   - Use the available template capacity fully. Thin copy that barely fills placeholders is as much a quality issue as overflow.
   - Prefer at most 6-7 bullets in a box.
   - Prefer each bullet to fit within 2 lines.
   - If copy looks like memo prose, compress it.
   - If copy is a single generic sentence, expand it with evidence.
   - See `templates/content_quality_rules.json` for per-field density targets.

5. **Comparisons must read like structured comparisons.**
   Comparison pages should not feel like long descriptive sentences stacked vertically.

6. **Quantitative pages need real data structure.**
   If a slide depends on a chart or number-led visual, the upstream artifact should include `chart_data`, not only visual commentary.

7. **Chart titles must be presentation-ready labels, not execution notes.**
   `chart_title` is what appears on the slide. It should read like a short chart heading, not a sentence explaining how to build the chart.

8. **Scaffold labels must not survive into the final deck.**
   Template-helper text such as `PRIMARY CHART`, `POINT 1`, `STANDARD`, page-type names, or slide-key tags must be removed before delivery.

## Content Density by Field Type

The following are target character ranges for body_copy fields. They are enforced by `validate_content_quality.py` as advisory warnings. See `templates/content_quality_rules.json` for the canonical thresholds.

| Field Type | Target Range | Description |
|---|---|---|
| title / headline | Must fit one title line | Complete investment insight, not a topic label |
| main_takeaway | Target one line; hard max two lines | One sentence: opinion + evidence or implication; no terminal punctuation |
| bullet / card | 45–95 chars, subject to `layout_budget.json` | Label + opinion + data point or implication |
| panel | 55–105 chars, subject to `layout_budget.json` | Context synthesis + judgment + target relevance |
| table_row | 30–70 chars; cells must stay compact | Metric-led, label prefix bolded |
| timeline_stage | 60–100 chars | Event + timeframe + significance |
| source_footer | 30+ chars | Specific source name or Evidence ID |

Each active field should contain: **label/prefix + opinion/judgment + evidence/implication**.

### Anti-Patterns That Produce Thin Copy

| Too Thin | Problem | Fix |
|---|---|---|
| "Market growing rapidly" | No data, no source | Add CAGR, size, source: "Market growing at X% CAGR (EV-003)" |
| "竞争激烈" | Label only | Add structure: "CR5 < 15%，头部品牌靠渠道/产品拉开差距（EV-007）" |
| "Industry reports" as source_note | Generic | Use Evidence ID or named source: "Named source, latest available report (EV-003)" |

## Emphasis Rules

Use inline markers only when they improve scanability without breaking layout discipline:

- `[[b]]...[[/b]]` for key metrics, proof points, or a short decisive phrase
- `[[hl]]...[[/hl]]` for the single most important conclusion phrase or contrast

### Preferred Uses

- If a sentence contains a label structure such as `行业结构：...`, `标的位置：...`, or `关键尽调问题：...`, prefer bolding the label prefix before the colon rather than coloring the whole phrase.
- On comparison and summary pages, prefer bolding the label prefix and the single key proof point.
- Reserve color highlight for one short headline phrase or one critical contrast on the page.

### Limits

- Prefer at most **1 highlighted phrase** per slide
- Prefer at most **2 bolded numbers / proof points** per slide
- Do not highlight full sentences unless the sentence is very short
- Do not highlight every peer, every metric, or every box

## Slide-Specific Guidance

### Slide 1 — Industry Overview
- Highlight the structural conclusion, not every supporting fact
- Bold one anchor metric at most

### Slide 2 — Market Size & Segmentation
- Bold the 2-3 most decision-relevant datapoints
- Highlight the one sentence or phrase that explains why the market matters for the target
- Keep the mini-table crisp and metric-led
- `chart_title` should be a short client-facing label, ideally one line
- `visual_direction` and `chart_data.notes` should carry build instructions, not the on-slide title
- The left chart box should contain an actual chart object where feasible, not a prose description of the intended visual

### Slide 6 — Competitive Landscape
- Visually prioritize the target
- At most 1-2 peers may receive secondary emphasis
- Right-panel conclusion should read like a synthesis, not another data dump
- Prefer `标的公司：`, `行业结构：`, `行业演化：`, `标的位置：` style bold prefixes over color

### Slide 8 — Key Takeaways for Target
- Highlight the investment conclusion
- Bold one synergy or proof point
- Keep diligence questions concise and decision-oriented
- Prefer bold label prefixes such as `行业吸引力：`, `标的公司为什么能赢：`, `买方协同空间：`, `关键尽调问题：`

## Anti-Patterns

- Changing font size within same-level body text to force emphasis
- Bolding every number on the page
- Highlighting all peers in a comparison table
- Turning summary boxes into memo paragraphs
- Making a chart page text-heavy because the chart inputs were not structured upstream
- Treating placeholder fill success as a proxy for presentation quality
- Leaving scaffold labels such as `PRIMARY CHART`, `POINT 1`, or `STANDARD` visible in the final deck
- Writing thin single-sentence copy that barely fills placeholders
- Using generic source attributions ("industry reports", "public sources") instead of named sources or Evidence IDs
- Writing vague claims ("market growing rapidly") without specific data and source references

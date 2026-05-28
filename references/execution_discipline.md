# Execution Discipline

Use this reference at task start. It prevents skipped steps, late rule discovery, metric drift, and generic output.

## Required References at Task Start

Before generating research, storyboard, or PPT output, read the references needed for the requested task:

- `references/scope_boundary.md`
- `references/research_policy.md`
- `templates/research_plan.template.json`
- `templates/source_registry.json`
- `templates/page_type_rules.json`
- `templates/content_quality_rules.json`
- `templates/layout_budget.json`
- `templates/text_fit_rules.json`

If PPT generation or PPT repair is requested, also read:

- `references/formatting_rules.md`
- `references/ppt_visual_qc.md`
- `templates/ppt_copy_schema.json`
- `templates/ppt_copy_mapping.json`
- `templates/slide_layout_library.json`

Do not wait until after drafting to discover these rules.

## Workflow Decision Tree

Choose the smallest workflow that satisfies the user request:

1. New industry section from a brief or attachments:
   - Run full workflow: intake -> scope boundary -> broad research -> research emphasis -> formal memo -> gap audit -> supplemental research if needed -> storyboard -> PPT copy -> PPT fill -> QC.
2. Existing industry PPT improvement:
   - Extract current storyline and slide content; audit content gaps, source gaps, metric consistency, and template fit; regenerate only necessary pages unless the user asks for a full rebuild.
3. Research-only update:
   - Run research plan, search log, memo, gap audit, and supplemental research if needed; stop before storyboard/PPT.
4. Storyboard-only update:
   - Use an existing validated memo; do not add new research facts; regenerate storyboard and validations.
5. PPT formatting-only fix:
   - Skip research and storyboard changes; run PPT fill/clean/postprocess/validation or targeted formatting repair.

## Progress Checklist

Maintain this internally for one-shot runs:

- [ ] Intake and input-card validation
- [ ] Scope boundary read
- [ ] Broad research
- [ ] Research emphasis / hypothesis plan
- [ ] Formal research plan validation
- [ ] Formal research memo
- [ ] Memo validation
- [ ] Research gap audit
- [ ] Supplemental research if critical gaps exist
- [ ] Fixed 8-slide storyboard
- [ ] Storyboard validation
- [ ] Content quality validation
- [ ] PPT copy / deterministic conversion
- [ ] PPT fill, clean, and visual postprocess
- [ ] Final delivery validation and runs index update

## Validation Fix-Cycle Limit

Use validation as a repair loop, but do not loop indefinitely.

- Run each validator after its upstream artifact changes.
- Fix the upstream artifact, not the downstream output.
- Try at most 3 validation/fix cycles for the same gate.
- After 3 failed cycles, stop and report: failed gate, remaining errors, likely root cause, and the smallest next action.
- Do not bypass failed validation for a deliverable deck.

## Data Conflict Handling

When user-provided data conflicts with external sources:

1. Use user-provided data for target-specific facts unless clearly impossible.
2. Use external sources for industry, market, peer, and transaction context.
3. Do not overwrite user-provided target facts with external assumptions.
4. If the same metric differs across sources, document the discrepancy and explain which source is used and why.
5. Add a note in memo, source_note, or data_gaps when the discrepancy is material to a slide.

## Cross-Slide Metric Consistency

Before final storyboard and PPT output, verify:

- same metric uses the same value across slides;
- same metric uses the same unit and scale;
- same market definition is used consistently;
- different market definitions are explicitly labeled;
- CAGR period is stated consistently;
- target financials are identical across slides;
- rankings preserve platform, period, and metric basis;
- chart values match headline, main_message, and body copy.

## Sources vs Notes Discipline

Sources and Notes serve different purposes.

Source notes should identify origins:

```text
Sources: Source 1 (Year), Source 2 (Year), company-provided materials
```

Notes should explain scope, calculations, assumptions, exclusions, and caveats:

```text
Notes: (1) Market definition; (2) Calculation basis; (3) User-provided target data
```

Rules:

- Sources are for external documents, databases, reports, filings, or user-provided materials.
- Notes are for scope, calculations, assumptions, exclusions, and caveats.
- Every calculated metric must have a note explaining formula or basis.
- Every user-provided target-specific fact should be marked as company/user-provided unless externally verified.
- Do not put Evidence IDs or source names in body text; use `source_note`.

## Real Table Object Discipline

For PPT output:

- Slide 2 `chart_plus_mini_table_page` and Slide 6 `compare_table_page` must render as real PPT table objects during post-processing.
- Do not use `|`, tabs, or aligned plain text as a fake final table.
- The `｜` separator is allowed only in upstream JSON/table fields so `scripts/postprocess_ppt_visuals.py` can split cells.
- If post-processing cannot render a required table, treat it as a PPT QC failure and fix upstream fields or renderer inputs.

## Critical Anti-Patterns for Industry Sections

Never do these:

1. Generic industry report
   - Problem: slide explains the industry but has no transaction relevance.
   - Fix: add why this matters for valuation, buyer interest, consolidation, financing, timing, or target positioning.

2. Forced target linkage
   - Problem: every slide says the trend benefits the target.
   - Fix: use target implications selectively; some slides should only build sector credibility.

3. Overclaiming
   - Problem: uses words like 确定性, 不可逆, 无放缓, 绝对领先 without hard evidence.
   - Fix: downgrade to evidence-supported phrasing or mark as a hypothesis.

4. Metric scope mixing
   - Problem: mixes TAM, online GMV, platform ranking, category sales, and company revenue without labels.
   - Fix: preserve scope, period, source, and metric basis.

5. Evidence decoration
   - Problem: many sources are listed, but the cited source does not actually support the claim.
   - Fix: every key claim must map to specific Evidence IDs or source rows.

6. Research dump
   - Problem: slides contain many facts but no governing takeaway.
   - Fix: each slide must answer one investor question.

7. Consulting-style answer
   - Problem: turns the industry section into market entry strategy or an operating plan.
   - Fix: keep the output as a pitchbook industry section with transaction relevance.

8. Template-fill success as quality proxy
   - Problem: placeholders are filled, but the page is thin, inconsistent, or visually weak.
   - Fix: run content quality, visual QC, final delivery validation, and inspect major warnings.

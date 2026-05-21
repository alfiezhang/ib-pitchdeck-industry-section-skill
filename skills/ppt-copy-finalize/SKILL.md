# PPT Copy Finalize

Convert `industry_storyboard.json` into the canonical `industry_section_ppt_copy.json` format required by the deterministic PPT filling scripts.

This step is **optional by default**. Run it only when:
- Storyboard copy is too long for PPT placeholders
- Copy is verbose rather than punchy (needs compression for PowerPoint)
- The `fill-ppt` scripts require the canonical `industry_section_ppt_copy.json` format as input
- The user requests a cleaner, more PPT-aligned copy file

## Purpose

Bridge the gap between the reasoning-rich `industry_storyboard.json` (optimized for LLM reasoning and human review) and the script-optimized `industry_section_ppt_copy.json` (optimized for deterministic token replacement).

## Inputs

| Input | Required | Purpose |
|-------|----------|---------|
| `industry_storyboard.json` | Yes | Source storyboard with all slide content |
| `templates/ppt_copy_schema.json` | Yes | Target schema — the output contract |
| `templates/ppt_copy_mapping.json` | Yes | Field-level mapping guidance for each slide role and page type |

## Output

`industry_section_ppt_copy.json` — a single JSON file conforming to `templates/ppt_copy_schema.json`.

Must include:
- `meta` block (target_company, transaction_type, industry, subsector, geography, language)
- `ppt_copy_slides` array (8 items, one per slide)
- Each slide: `slide_no`, `slide_key`, `selected_page_type`, `slide_title`, `main_takeaway`, `content` (role-appropriate fields), `chart_title`, `source_footer`, `speaker_note`
- `rules` block matching the schema

## Conversion Rules

1. **No new facts.** The storyboard is the sole source of truth. Do not add data, claims, or interpretations that were not in the storyboard.
2. **No page type changes.** The `selected_page_type` for each slide must exactly match the storyboard's `template_binding` decisions.
3. **Compress for PPT.** Headlines and bullets should be concise, scannable, and fit within PPT placeholder character limits. Prefer punchy investment language over descriptive prose.
4. **Preserve source notes.** Every slide's `source_footer` must carry forward the storyboard's `source_note`.
5. **Preserve target linkage.** Every slide's `main_takeaway` should reflect the storyboard's `target_link` intent.
6. **Field alignment.** Map storyboard `body_copy` fields to the exact field names expected by `ppt_copy_schema.json` for each slide role. Use `templates/ppt_copy_mapping.json` for guidance.
7. **Controlled variants.** Slides 2, 6, and 7 must carry the correct `selected_page_type` from the storyboard's `template_binding`.
8. **Use lightweight emphasis markup when useful.** The deterministic filler now supports `[[b]]...[[/b]]` for bold emphasis and `[[hl]]...[[/hl]]` for brand-color highlight in text placeholders.
   Prefer `[[b]]` by default.
   Use `[[hl]]` only for one short conclusion phrase or one critical contrast on a slide.
   On colon-led labels such as `行业结构：...` or `关键尽调问题：...`, prefer bolding the prefix before the colon.
9. **Follow formatting discipline.** Use `references/formatting_rules.md` to decide where emphasis should and should not appear.
10. **Keep `chart_title` client-facing.** If a slide has `chart_data.title`, use that as the default `chart_title`. Do not copy procedural instructions such as “show a bar chart...” into the on-slide chart title field.
11. **Keep build notes upstream.** Execution notes belong in `visual_direction`, `chart_data.notes`, or speaker notes, not in visible PPT placeholders.

## When to Skip

Skip this step when:
- The storyboard copy is already concise and PPT-ready
- The user is doing a dry run (storyboard review only)
- A deterministic `convert_storyboard_to_ppt_copy.py` script is available and preferred

When skipped, the `fill-ppt` scripts should be fed `industry_storyboard.json` with appropriate field mapping, or this step should be run by the `ppt-copy-finalize` LLM prompt.

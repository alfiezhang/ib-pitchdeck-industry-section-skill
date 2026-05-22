# Finalize PPT Copy

## Input
- `industry_storyboard.json` — the source storyboard
- `templates/ppt_copy_schema.json` — target schema
- `templates/ppt_copy_mapping.json` — field-level mapping guidance

## Task
Convert the reasoning-rich `industry_storyboard.json` into the canonical `industry_section_ppt_copy.json` format required by deterministic PPT filling scripts.

## Rules

1. **Do not introduce new facts.** The storyboard is the sole source of truth. No new data, claims, or interpretations beyond what is already in the storyboard.
2. **Do not change the selected page types.** Use exactly the variants specified in the storyboard's `template_binding`:
   - Slide 2: `{slide_2_variant}`
   - Slide 6: `{slide_6_variant}`
   - Slide 7: `{slide_7_variant}`
   Unless the storyboard is internally inconsistent (e.g., a slide's `selected_page_type` conflicts with `template_binding`), in which case flag the inconsistency and use the `template_binding` value as authoritative.
3. **Compress text to fit PPT placeholders.** Bullets should be scannable, not paragraph-length. Headlines should be conclusion-led one-liners. Main takeaways should be single sentences.
4. **Preserve source notes.** Every slide's `source_footer` must carry forward the storyboard's `source_note`.
5. **Preserve target linkage.** Every slide's `main_takeaway` should reflect the storyboard's `target_link` intent.
6. **Ensure the output conforms to `templates/ppt_copy_schema.json`.** All required fields must be present. Use `ppt_copy_mapping.json` for field-level role-to-field mapping.
7. **If text must be shortened, preserve the investment message over descriptive detail.** A punchy "Market is X, growing at Y" beats a wordy "The market for Z has been observed to grow at approximately Y% per annum."
8. **Preserve uncertainty.** If the storyboard flags weak sourcing or data gaps, carry those caveats into source footers, speaker notes, or concise wording rather than making claims sound more certain.

## Content Field Mapping

For each slide, map storyboard `body_copy` fields to `ppt_copy_schema.json` content fields as guided by `ppt_copy_mapping.json`. The mapping varies by slide role and page type:

- **Slide 1** (industry_overview): `bullet_1`, `bullet_2`, `bullet_3`
- **Slide 2** (market_size_segmentation): `bullet_1`–`bullet_3` + optional `table_header_1`–`table_row_3` (chart_plus_mini_table_page only)
- **Slide 3** (key_industry_drivers): `card_1`–`card_4`
- **Slide 4** (value_chain_profit_pool): `top_left`–`bottom_right` (6 panels)
- **Slide 5** (key_barriers_value_drivers): `card_1`–`card_3`
- **Slide 6** (competitive_landscape): variant-dependent (table + panels for compare_table_page; matrix + panels for matrix_page)
- **Slide 7** (industry_trends): variant-dependent (cards for trend_page; stages for timeline_page)
- **Slide 8** (key_takeaways): `left_panel`, `right_top`, `right_mid`, `right_bottom`

## Output Format
Return **valid JSON only**. No markdown fences, no explanations.

JSON syntax hard rules:
- JSON keys and string delimiters must use ASCII double quotes only: `"`.
- Never use Chinese/smart quotes: `“”‘’`.
- Never use single quotes for JSON keys or string delimiters.

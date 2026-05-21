# PPT Naming Convention

Use these canonical names consistently across:
- `templates/ppt_copy_schema.json`
- `templates/ppt_copy_mapping.json`
- `templates/ppt_mapping.json`
- any future script that transforms PPT copy into replacement dictionaries

## Top-level PPT copy fields
- `slide_title`
- `main_takeaway`
- `chart_title`
- `source_footer`
- `speaker_note`
- `content`

Do not use `title` when you mean `slide_title`.
Do not use `takeaway` when you mean `main_takeaway`.

## Content field naming
Use `content.<slot_name>` for page-body fields.

Allowed slot families:
- bullet slots: `content.bullet_1`, `content.bullet_2`, `content.bullet_3`
- card slots: `content.card_1`, `content.card_2`, `content.card_3`, `content.card_4`
- panel slots: `content.left_panel`, `content.right_top`, `content.right_mid`, `content.right_bottom`
- grid slots: `content.top_left`, `content.top_center`, `content.top_right`, `content.bottom_left`, `content.bottom_center`, `content.bottom_right`

## Mapping rules
- In `templates/ppt_copy_mapping.json`, `target_field` should match a key inside `content` unless it is a top-level field such as `slide_title` or `main_takeaway`.
- In `templates/ppt_mapping.json`, `field_name` should match the canonical PPT copy field name expected by the replacement layer.
- `layout_binding_by_slide.field_roles` should use the same canonical names for top-level fields: `slide_title`, `main_takeaway`, `chart_title`, `source_footer`.

## Script guidance
When generating a replacement dictionary from `industry_section_ppt_copy.json`:
1. Read top-level fields directly from each slide object.
2. Read body content from `content`.
3. Never infer `title` from `slide_title` or `takeaway` from `main_takeaway`; use the canonical names directly.

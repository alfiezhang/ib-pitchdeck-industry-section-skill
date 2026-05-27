# Fill PPT

Convert finalized PPT copy into a populated PowerPoint deck using deterministic Python scripts.

This is a **deterministic script-driven step**. The LLM does not hand-write `replacement_dict.json`. It orchestrates the existing script pipeline and reports results.

Default interpreter: `./.venv/bin/python` after running `bash ./setup.sh`. If the virtualenv is missing, pass `--python /path/to/python` explicitly or fix the environment before continuing.

All user-facing inputs and outputs should be resolved relative to the user's working materials, not the skill package directory. Only the bundled scripts, templates, assets, and references should be resolved relative to the skill itself.

Formatting rules live in `references/formatting_rules.md`.
Visual review rules live in `references/ppt_visual_qc.md`.

Object-level post-processing for charts / cleanup lives in `scripts/postprocess_ppt_visuals.py`.

## Inputs

| Input | Required | Purpose |
|-------|----------|---------|
| `industry_storyboard.json` | Yes | Slide control file and chart/post-processing source |
| `industry_section_ppt_copy.json` | Yes | Canonical PPT copy with 8 slides, each with selected_page_type and content fields |
| `assets/industry_section_template_master.pptx` | Yes | 11-physical-slide PPTX template with `{{...}}` tokens |
| `templates/ppt_mapping.json` | Yes | Token-to-slide mapping for replacement |

## Supported Text Markup

The deterministic filler supports lightweight inline emphasis markers inside `industry_section_ppt_copy.json` values:

- `[[b]]...[[/b]]` → bold
- `[[hl]]...[[/hl]]` → brand-color text highlight

Use these markers sparingly for key numbers, one short takeaway phrase, or a single comparison point. Prefer `[[b]]` by default. On label-style text before a colon, prefer bolding the prefix instead of coloring the whole sentence.

## Script Order

Run these scripts in order. Do not skip steps.

### 1. Validate Storyboard Contract

Check that `industry_storyboard.json` is executable before converting or filling the deck.

```bash
./.venv/bin/python scripts/validate_storyboard.py \
  --storyboard industry_storyboard.json \
  --schema templates/storyboard_schema.json \
  --output artifacts/storyboard_validation.json
```

If this step fails, fix the storyboard contract before proceeding.

### 2. Check Template Tokens

Verify the PPT template's placeholder tokens are consistent with `ppt_mapping.json`.

```bash
./.venv/bin/python scripts/check_template_tokens.py \
  --template assets/industry_section_template_master.pptx \
  --ppt-mapping templates/ppt_mapping.json \
  --output artifacts/template_token_check.json
```

If this step fails, fix the template or mapping before proceeding.

### 3. Generate Replacement Dictionary

Convert `industry_section_ppt_copy.json` into a `replacement_dict.json` mapping tokens to values.

```bash
./.venv/bin/python scripts/generate_replacement_dict.py \
  --ppt-copy industry_section_ppt_copy.json \
  --ppt-mapping templates/ppt_mapping.json \
  --output replacement_dict.json
```

### 4. Fill PPT Tokens

Replace `{{...}}` tokens in the PPTX template with values from `replacement_dict.json`.

```bash
./.venv/bin/python scripts/fill_ppt_tokens.py \
  --template assets/industry_section_template_master.pptx \
  --replacement-dict replacement_dict.json \
  --output industry_section_filled.pptx \
  --log artifacts/fill_ppt_tokens.log.json
```

### 5. Clean Inactive Variants

Remove physical slides for unselected page type variants (e.g., if Slide 2 chose `chart_page`, remove the `chart_plus_mini_table_page` slide).

```bash
./.venv/bin/python scripts/clean_filled_ppt.py \
  --input industry_section_filled.pptx \
  --control-file industry_storyboard.json \
  --output industry_section_filled_clean.pptx \
  --log artifacts/clean_filled_ppt.log.json
```

Note: `--control-file` accepts `industry_storyboard.json` (`slides` key) or `industry_section_ppt_copy.json` (`ppt_copy_slides` key).

### 6. Post-Process Visuals

Apply object-level visual cleanup after token fill. This step is where real chart objects, scaffold-label removal, or similar slide-object fixes should happen.

```bash
./.venv/bin/python scripts/postprocess_ppt_visuals.py \
  --input-ppt industry_section_filled_clean.pptx \
  --storyboard industry_storyboard.json \
  --output industry_section_filled_clean.pptx \
  --render-layouts templates/render_layouts.json \
  --log artifacts/postprocess_ppt_visuals.log.json
```

Current scope:
- removes template scaffold labels such as `PRIMARY CHART`, `POINT 1`, `STANDARD`
- renders real visual objects on Slide 1, Slide 2, and selected Slide 6 variants when executable data is present
- reads deterministic render coordinates from `templates/render_layouts.json`

### 7. Validate Filled PPT

Run the final validation gate.

```bash
./.venv/bin/python scripts/validate_filled_ppt.py \
  --filled-ppt industry_section_filled.pptx \
  --clean-ppt industry_section_filled_clean.pptx \
  --control-file industry_storyboard.json \
  --replacement-dict replacement_dict.json \
  --ppt-mapping templates/ppt_mapping.json \
  --output filled_ppt_validation.json \
  --fail-on-issue
```

If `filled_ppt_validation.json` has `summary.is_valid=false`, do not deliver the PPT. Fix the underlying issue. Do not reinterpret failed validation as a harmless warning.

## Outputs

| File | Description |
|------|-------------|
| `replacement_dict.json` | Token → value mapping for all active placeholders |
| `industry_section_filled.pptx` | Raw filled 11-slide deck |
| `industry_section_filled_clean.pptx` | Cleaned 8-slide deck (inactive variants removed) |
| `filled_ppt_validation.json` | Validation report: unreplaced tokens, slide counts, issues |
| `artifacts/storyboard_validation.json` | Storyboard contract validation report |
| `artifacts/template_token_check.json` | Template token consistency report |
| `artifacts/fill_ppt_tokens.log.json` | Token filling log |
| `artifacts/clean_filled_ppt.log.json` | Slide cleaning log |
| `artifacts/postprocess_ppt_visuals.log.json` | Object-level post-processing log |

## Rules

- **Do not manually edit `replacement_dict.json`** unless debugging a script bug.
- **Do not bypass validation.** If validation fails, fix the upstream PPT copy or mapping, not the final PPT manually.
- **Do not let the LLM hand-write `replacement_dict.json`.** This is a deterministic script step.
- **Fail fast:** if any script exits with a non-zero code, stop and report the error. Do not continue to the next step.
- **Preserve intentional line breaks** in the PPT copy; the filling scripts handle them correctly.
- **Apply emphasis with restraint:** use `[[b]]...[[/b]]` and `[[hl]]...[[/hl]]` according to `references/formatting_rules.md`.
- **Do visual QC after structural validation:** use `references/ppt_visual_qc.md`, especially on Slides 2 / 6 / 8.
- **Do not leave scaffold labels in the final deck.** If the template contains helper text such as `PRIMARY CHART` or `STANDARD`, remove it in the post-process step.

## Control File Note

`clean_filled_ppt.py` and `validate_filled_ppt.py` use a slide control file to identify selected layout variants. Prefer `industry_storyboard.json`; `industry_section_ppt_copy.json` is also accepted when it contains `ppt_copy_slides`. The control file must contain `slide_no` and `selected_page_type` for all 8 slides.

## Run Directory Convention

Prefer running the packaged pipeline instead of invoking the six scripts manually:

```bash
/path/to/skill/run_pipeline.sh /path/to/work/industry_section_ppt_copy.json /path/to/work/industry_storyboard.json
```

If no explicit output directory is provided, the pipeline stages the input JSON files and writes generated artifacts under `<work_root>/runs/attempt_<timestamp>/` by default, where `work_root` is inferred from the input file location or set explicitly with `--work-root`.

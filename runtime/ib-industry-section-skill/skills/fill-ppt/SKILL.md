---
name: ib-industry-fill-ppt
description: Run the deterministic PowerPoint filling and post-processing pipeline for the IB industry section skill using the bundled template, mappings, and validators.
---

# Fill PPT

Convert a validated deck-blueprint package into a populated PowerPoint deck using deterministic Python scripts.

This sub-skill is **not** an entrypoint for a new project brief. If the user provides only a brief, return to the root `ib-industry-section` workflow and complete research, research pack, issue analysis, deck blueprint, compiled evidence contract / renderer spec, and gates before using this step.

This is a **deterministic script-driven step**. The LLM does not hand-write `replacement_dict.json`. It orchestrates the existing script pipeline and reports results.

Formal delivery has exactly one PPT generation path: the packaged deterministic pipeline using the
compiled `renderer_spec.json`, `page_evidence_contract.json`, bundled template,
and final delivery validator. Do not create `generate_ppt.py`, do not use
ad-hoc `python-pptx` / PptxGenJS / LibreOffice / Keynote drawing scripts, and do
not hand-build a PPT when the formal pipeline fails. A custom PPT file is a
bypass artifact, not a skill delivery.

Default interpreter: set once at the skill root and keep it consistent:

```bash
PYTHON_CMD="$(bash setup.sh --print-python)"
```

Use the same interpreter for all `scripts/pipeline.py` calls. Do not run
different pipeline steps with different Python interpreters.

This step should require only PPT/runtime dependencies (`python-pptx`, `lxml`, etc.). Web-search providers are research-stage dependencies and must not block an already validated PPT package from rendering.

Before running direct scripts, select the runtime once:

```bash
PYTHON_CMD="$(bash setup.sh --print-python)"
```

If `pptx` or `lxml.etree` fails to import on macOS with Python 3.13/3.14, rerun bootstrap with Python 3.9-3.11, for example:

```bash
PYTHON_CMD="$(bash setup.sh --print-python --python python3.11 --force)"
```

Do not work around this by ad-hoc installing packages into unrelated system or
Node environments, and do not edit deterministic scripts to bypass runtime
errors.

All user-facing inputs and outputs should be resolved relative to the user's working materials, not the skill package directory. Only the bundled scripts, templates, assets, and references should be resolved relative to the skill itself.

Formatting rules live in `references/formatting_rules.md`.
Visual review rules live in `references/ppt_visual_qc.md`.

Object-level post-processing for charts / cleanup lives in `scripts/postprocess_ppt_visuals.py`.

## Inputs

| Input | Required | Purpose |
|-------|----------|---------|
| `deck_blueprint.json` | Formal mode | LLM-authored page design and copy source |
| `renderer_spec.json` | Yes | Compiled slide control file and chart/post-processing source |
| `page_evidence_contract.json` | Formal mode | Compiled page evidence boundary |
| `assets/industry_section_template_master.pptx` | Yes | 11-physical-slide PPTX template with `{{...}}` tokens |
| `templates/ppt_mapping.json` | Yes | Token-to-slide mapping for replacement |

## Supported Text Markup

The deterministic filler supports lightweight inline emphasis markers inside renderer spec text values:

- `[[b]]...[[/b]]` → bold
- `[[hl]]...[[/hl]]` → brand-color text highlight

Use these markers sparingly for key numbers, one short takeaway phrase, or a single comparison point. Prefer `[[b]]` by default. On label-style text before a colon, prefer bolding the prefix instead of coloring the whole sentence.

## Script Order

For one-shot or delivery runs with an existing validated attempt, use only the Python orchestrator:

```bash
"$PYTHON_CMD" scripts/pipeline.py render --run-dir "$RUN_DIR"
```

This operates inside the current attempt directory. It does not create a new
attempt, does not perform research, and does not write page judgments.

`run_pipeline.sh` remains a compatibility wrapper for older command surfaces,
but it only delegates to the Python orchestrator for an existing attempt:

```bash
/path/to/skill/run_pipeline.sh \
  --run-dir /path/to/runs/<case_slug>/attempt_<timestamp>
```

The deterministic pipeline owns the PPT stage sequence:

1. refresh upstream validations;
2. run the pre-PPT stage gate;
3. generate and validate `replacement_dict.json`;
4. fill tokens;
5. clean inactive variants;
6. post-process real PPT chart/table objects;
7. validate the filled PPT;
8. run final delivery validation.

Do not manually reproduce these steps during formal delivery. Direct script calls
are diagnostic only, because they are easy to run from the wrong working
directory or with stale relative paths. If a direct script is used for diagnosis,
run exactly one failing step, use absolute paths, write outputs under a temporary
diagnostic directory, and return to `scripts/pipeline.py render --run-dir "$RUN_DIR"` for the formal rerun.

If the packaged pipeline exits non-zero, stop at the failed gate and report the
error. Do not continue with later scripts, do not create an `artifacts/`
validation file by hand, and do not describe any generated PPT as complete. In
formal mode, failed PPT outputs are renamed with `NOT_CLIENT_READY_`.
Do not replace this blocked state with a manually generated PPT.

When the failed gate is content quality, open
`artifacts/content_quality_validation.json` and follow `repair_plan`:
`primary_repair_targets` tells which upstream artifact to edit, `targets[]`
names the fields, and `rerun_steps` gives the recovery sequence. In normal runs,
this means fixing `deck_blueprint.json`, recompiling, and rerunning the pipeline.
Do not fix content-quality failures by editing `replacement_dict.json`, the
filled PPT, or a hand-made PPT.

The PPT-producing scripts (`generate_replacement_dict.py`,
`fill_ppt_tokens.py`, `clean_filled_ppt.py`, and
`postprocess_ppt_visuals.py`) enforce the pre-PPT gate when called directly. Do
not bypass it with `--allow-ungated-debug` except for local diagnostics; an
ungated PPT is a debug artifact, not a deliverable.

Current post-processing scope:
- removes template scaffold labels such as `PRIMARY CHART`, `POINT 1`, `STANDARD`
- renders real visual objects on Slide 1, Slide 2, and selected Slide 6 variants when executable data is present
- renders Slide 1 `industry_overview_dynamic_page` on the existing slide 1 canvas by preserving the left-side `KEY MESSAGES` area and replacing only the right-side `CHART / VISUAL` area with a real chart
- renders Slide 2 mini-table and Slide 6 compare table as real PPT table objects when those page types are selected
- final validation checks that selected Slide 2 mini-table / Slide 6 compare-table layouts contain real, populated PPT table objects
- reads deterministic render coordinates from `templates/render_layouts.json`

Try at most 3 validation/fix cycles for the same failed gate. After 3 failed
cycles, stop and report the remaining errors, likely root cause, and smallest
next action.

## Outputs

| File | Description |
|------|-------------|
| `replacement_dict.json` | Token → value mapping for all active placeholders |
| `industry_section_filled.pptx` | Raw filled 11-slide deck |
| `industry_section_filled_clean.pptx` | Cleaned 8-slide deck (inactive variants removed) |
| `filled_ppt_validation.json` | Validation report: unreplaced tokens, slide counts, issues |
| `artifacts/renderer_spec_validation.json` | Renderer spec contract validation report |
| `artifacts/template_token_check.json` | Template token consistency report |
| `artifacts/replacement_dict_validation.json` | Replacement dictionary semantic and staleness audit |
| `artifacts/fill_ppt_tokens.log.json` | Token filling log |
| `artifacts/clean_filled_ppt.log.json` | Slide cleaning log |
| `artifacts/postprocess_ppt_visuals.log.json` | Object-level post-processing log |

## Rules

- **Do not manually edit `replacement_dict.json`** unless debugging a script bug.
- **Do not bypass validation.** If validation fails, fix the upstream deck blueprint, compiled renderer spec, evidence contract, or mapping, not the final PPT manually.
- **Do not let the LLM hand-write `replacement_dict.json`.** This is a deterministic script step.
- **Fail fast:** if any script exits with a non-zero code, stop and report the error. Do not continue to the next step.
- **Preserve intentional line breaks** in renderer spec text fields; the filling scripts handle them correctly.
- **Apply emphasis with restraint:** use `[[b]]...[[/b]]` and `[[hl]]...[[/hl]]` according to `references/formatting_rules.md`.
- **Do visual QC after structural validation:** use `references/ppt_visual_qc.md`, especially on Slides 2 / 6 / 8.
- **Do not leave scaffold labels in the final deck.** If the template contains helper text such as `PRIMARY CHART` or `STANDARD`, remove it in the post-process step.

## Run Directory Convention

Prefer running the Python orchestrator instead of invoking the seven scripts manually:

```bash
"$PYTHON_CMD" scripts/pipeline.py render --run-dir "$RUN_DIR"
```

If an older command surface requires the shell wrapper, pass an explicit package-of-record attempt:

```bash
/path/to/skill/run_pipeline.sh \
  --run-dir /path/to/runs/<case_slug>/attempt_<timestamp>
```

The shell wrapper no longer creates attempts, stages artifacts, or continues
`ACTIVE_ATTEMPT.txt`. If `--deck-blueprint` is passed, it is used only to infer
the enclosing `attempt_*` directory.

The pipeline writes `artifacts/stage_gate_pre_ppt_validation.json` and exits
before PPT generation when the formal search plan, research pack, renderer spec, content
quality, or MET-ID evidence chain is invalid. A user asking to generate an
industry-section PPT from a project brief is asking for the formal path, not a
rendering shortcut. `--no-research-gate` is not a delivery path.

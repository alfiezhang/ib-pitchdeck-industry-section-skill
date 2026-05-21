---
name: ib-industry-section
description: Generate a transaction-oriented investment banking industry section for a pitchbook, with structured draft, controlled page planning, PPT-ready copy, and optional fixed-template PPT filling. Use when the user explicitly asks for this skill or asks for an industry chapter linked to a specific target company. Supports Chinese or English output.
---

# IB Industry Section

Generate a transaction-oriented industry section for an investment banking pitchbook and, if requested, populate the bundled PowerPoint template.

This skill uses a lightweight agent-style workflow with LLM reasoning at the center, not a rigid serial JSON pipeline. The default workflow has two human review gates and four encapsulated sub-skills.

Design principle:
- This workflow is intentionally **LLM-driven** for research synthesis, storyline design, and slide drafting.
- Deterministic scripts should constrain execution and validation, not replace high-judgment reasoning.
- The goal is not to reduce model freedom, but to define clear stage contracts, review gates, and downstream execution rules.

## Purpose

Produce a target-linked, source-disciplined 8-slide industry section that tells a coherent transaction story — not a generic industry report. LLM reasoning drives storyline strategy, page planning, page type selection, and slide-level copy in one integrated step (`industry_storyboard.json`), while deterministic scripts handle PPT token filling.

## Inputs

- **Target brief** or **input card** (`templates/input_card.template.json`)
- **User attachments** (optional — pitchbook drafts, CIM extracts, research notes)
- **Existing `industry_input_memo.md`** (optional — treated as canonical input if provided and user says "do not expand")

## Runtime Bootstrap

Before starting from a brief or running PPT scripts, ensure the runtime is ready:

```bash
bash ./setup.sh
./.venv/bin/python scripts/check_runtime_dependencies.py
```

If `.venv` creation fails because Python lacks `ensurepip` / `venv`, stop and install the matching system package (for example `python3-venv` or `python3.14-venv` on Debian/Ubuntu) or rerun with `PYTHON_BIN` pointing to a Python installation that supports `venv`.

Do not proceed to research, storyboard, or PPT generation if mandatory runtime dependencies are missing.

## Default Workflow

### 1. Research Memo
Use `skills/research-memo/SKILL.md`.

Output: `industry_input_memo.md`

**Stop for human review** unless the user explicitly requests one-shot generation.

Reviewer should confirm: industry definition, market sizing logic, growth drivers, competitive landscape, target linkage, data sources and gaps.

If this run starts from only a brief or attachments and verified online research cannot be completed, stop after reporting the failure. Continue only if the operator explicitly chooses a degraded mode; any degraded output must label unsupported facts as `training_data` and must not be treated as diligence-grade.

### 2. Storyboard Section
Use `skills/storyboard-section/SKILL.md`.

Input: `industry_input_memo.md` + target brief + page type rules + slide layout library

Output: `industry_storyboard.json`

This is the **main LLM reasoning step**. It generates, in one pass: storyline strategy, 8-slide page plan, selected page types (with rationale), slide-level PPT copy, source notes, and template binding decisions.

**Stop for human review** unless the user explicitly requests one-shot generation.

### 3. Storyboard Contract Validation

Run `scripts/validate_storyboard.py` before conversion or PPT filling.

Output: `artifacts/storyboard_validation.json`

This is deterministic validation of page type choices, `template_binding`, and active `body_copy` fields. If it fails, fix `industry_storyboard.json` upstream.

### 4. PPT Copy Finalize *(optional)*
Use `skills/ppt-copy-finalize/SKILL.md`.

Run only if: storyboard copy is too long, not PPT-ready, or `fill-ppt` requires the canonical `industry_section_ppt_copy.json` format.

Output: `industry_section_ppt_copy.json`

Do **not** introduce new facts. Only compress, reword, and align fields to `templates/ppt_copy_schema.json`.

In standard runs, if `industry_storyboard.json` already uses canonical `body_copy` field names, the deterministic converter may generate `industry_section_ppt_copy.json` directly. Use the LLM finalize step only when copy needs compression or field repair.

### 5. Fill PPT
Use `skills/fill-ppt/SKILL.md`.

This is a **deterministic script-driven step**. The LLM does not hand-write `replacement_dict.json`.

Outputs: `replacement_dict.json` → `industry_section_filled.pptx` → `industry_section_filled_clean.pptx` → `filled_ppt_validation.json`

Operational note:
- Recommended dependency install command: `bash ./setup.sh`
- `run_pipeline.sh` can now start from `industry_storyboard.json` alone and auto-generate `industry_section_ppt_copy.json` when it is missing.

## Human Review Gates

| Gate | After | Artifact to Review |
|------|-------|--------------------|
| Gate 1 | Research Memo | `industry_input_memo.md` |
| Gate 2 | Storyboard Section | `industry_storyboard.json` |

Do **not** require separate manual review for intermediate debug files; the workflow checkpoints are the memo and storyboard.

## One-Shot vs Review Mode

- **Default mode**: stop after `industry_input_memo.md`, then stop again after `industry_storyboard.json`.
- **One-shot mode**: continue through storyboard, ppt_copy, and PPT filling only when the user explicitly asks for one-shot generation, full draft generation, or direct PPT output.
- **Weak-source caution**: if source quality is clearly weak or key facts remain unverified, it is still acceptable to continue in one-shot mode, but generated outputs must flag gaps explicitly rather than smoothing them over.

## Required Outputs

- `industry_input_memo.md`
- `industry_storyboard.json`
- `industry_section_ppt_copy.json` (canonical input to deterministic PPT filling)
- `replacement_dict.json`
- `industry_section_filled_clean.pptx` (when PPT output is requested)
- `<run_dir>/artifacts/storyboard_validation.json` (when PPT output is requested)
- `filled_ppt_validation.json`

## Input Resolution

This skill is meant to run inside a user's arbitrary workspace. Do not assume the current directory is clean, relevant, or already organized for this workflow.

Resolve inputs in this order:
1. explicit user-named files or folders
2. files attached or explicitly referenced in the conversation
3. user-provided text brief
4. limited current-directory discovery, only when the user did not specify inputs

Hard rules:
- Treat a user-specified folder as the effective work root.
- Do not silently adopt discovered files; use them only after explicit user confirmation.
- Do not treat the skill package directory as user source material.

## Output Convention

Generated working files should live near the resolved user materials. By default, deterministic pipeline outputs should be written under:

- `<work_root>/runs/attempt_<timestamp>/`

Only static skill assets should be resolved relative to the skill package itself, such as `scripts/`, `templates/`, `assets/`, `references/`, and `prompts/`.

## Non-Negotiable Rules

- Do **not** fabricate market data, source names, CAGRs, market sizes, or company facts.
- Separate facts from interpretations. Directional judgments must read as inference, not disguised fact.
- Every important number must have a source note. If a fact cannot be verified, write `Insufficient data`.
- If source data conflicts, state the conflict — do not average without explanation.
- The PPT template (8 logical slides, 11 physical slides with controlled variants on Slides 2/6/7) is a **delivery constraint**, not a reasoning constraint.
- `replacement_dict.json` must be generated **deterministically** from final PPT copy — never hand-written by the LLM.
- `industry_storyboard.json` is the main LLM reasoning artifact.
- `industry_section_ppt_copy.json` remains the canonical input to deterministic PPT filling.
- Web research is mandatory when starting from a brief or attachments.

## When to Run Optional Steps

- **PPT Copy Finalize**: run when storyboard copy exceeds PPT placeholder limits, when copy is verbose rather than punchy, or when the user requests a cleaner `industry_section_ppt_copy.json`.
- **Storyboard validation**: always run before deterministic PPT filling. Fix the storyboard contract before attempting PPT execution.

## Failure Handling

- If a step fails, stop the chain, preserve completed run outputs, and report the failed step plus the next recommended action.
- If `fill-ppt` scripts fail, fix the upstream PPT copy or mapping — never patch the final PPT manually.
- If validation fails, diagnose and fix upstream rather than bypassing validation.

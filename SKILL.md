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

Produce a target-linked, source-disciplined 8-slide industry section that tells a coherent transaction story — not a generic industry report. LLM reasoning drives storyline strategy, page planning, page type selection, and slide-level copy in one integrated step (`industry_storyboard.json`), while deterministic scripts handle PPT token filling and quality validation.

## Inputs

- **Target brief** or **input card** (`templates/input_card.template.json`)
  - Now supports `research_direction` with priority websites, source domains, source packs, topics, peer set, and exclusions.
- **User attachments** (optional — pitchbook drafts, CIM extracts, research notes)
- **Existing `industry_input_memo.md`** (optional — treated as canonical input if provided and user says "do not expand")

## Source Registry

`templates/source_registry.json` contains default priority-source packs and domain lists for research.

Source priority options:
1. User-specified domains from `input_card.research_direction`
2. User-specified source packs
3. Default source packs (`source_registry.json` → `default_packs`) only when `--use-default-packs` is requested
4. Unrestricted web search, which remains the default when no site or source-pack option is passed

Source packs include: `china_official`, `china_capital_markets`, `global_official`, `global_company_filings`, `consulting_reports`, `business_media`.

The enhanced `scripts/web_search.py` supports `--site`, `--sites`, `--site-mode priority|only`, `--source-registry`, `--source-pack`, and `--use-default-packs` flags. Site-constrained search forces DuckDuckGo (Tavily API does not support `site:` syntax). Do not use `--use-default-packs` for every query; reserve it for a deliberate source-discovery pass or targeted validation pass.

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

The research phase now includes:
- **Source priority resolution**: apply the chain described in Source Registry above.
- **Multi-round search**: cover all 9 dimensions (definition, size, segmentation, drivers, value chain, barriers, competition, trends, target implications).
- **Search log**: write `artifacts/search_log.md` incrementally during research.
- **Evidence Ledger**: assign an Evidence ID (EV-001, EV-002, ...) to each important claim or metric.
- **Chart-ready data**: mark quantitative Key Data Points with `chart_ready: true`.
- **Per-page Evidence Rows**: at least 2-3 per page.

Output: `industry_input_memo.md` (following updated `references/industry_input_memo_template.md`)

**Stop for human review** unless the user explicitly requests one-shot generation.

Reviewer should confirm: industry definition, market sizing logic, growth drivers, competitive landscape, target linkage, data sources and gaps, Research Plan coverage, Evidence Ledger completeness.

If this run starts from only a brief or attachments and verified online research cannot be completed, stop after reporting the failure. Continue only if the operator explicitly chooses a degraded mode; any degraded output must label unsupported facts as `training_data` and must not be treated as diligence-grade.

### 2. Storyboard Section
Use `skills/storyboard-section/SKILL.md`.

Input: `industry_input_memo.md` + target brief + page type rules + slide layout library + content quality rules

Output: `industry_storyboard.json`

This is the **main LLM reasoning step**. It generates, in one pass: storyline strategy, 8-slide page plan, selected page types (with rationale), slide-level PPT copy, source notes (with Evidence IDs), and template binding decisions.

**Content density requirements** (enforced by `templates/content_quality_rules.json`):
- Every body_copy field: label + opinion + evidence/implication
- Per-field density targets (see storyboard prompt for ranges)
- No banned generic phrases in body_copy or source_note
- At least 2 Evidence IDs or memo section references per slide

**Stop for human review** unless the user explicitly requests one-shot generation.

### 3. Storyboard Contract Validation

Run `scripts/validate_storyboard.py` before conversion or PPT filling.

Output: `artifacts/storyboard_validation.json`

This is deterministic validation of page type choices, `template_binding`, and active `body_copy` fields. If it fails, fix `industry_storyboard.json` upstream.

### 3b. Content Quality Validation (advisory)

Run `scripts/validate_content_quality.py` after storyboard validation. This is advisory by default — it produces warnings, not hard errors.

```bash
./.venv/bin/python scripts/validate_content_quality.py \
  --storyboard industry_storyboard.json \
  --memo industry_input_memo.md \
  --rules templates/content_quality_rules.json \
  --output artifacts/content_quality_validation.json
```

Review the output. Address density_warnings, source_warnings, chart_data_warnings, generic_copy_warnings, and evidence_warnings before proceeding. Use `--quality-gate` to make this a hard gate when desired.

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
- `artifacts/search_log.md` (written incrementally during research)
- `industry_storyboard.json`
- `artifacts/storyboard_validation.json`
- `artifacts/content_quality_validation.json` (advisory)
- `industry_section_ppt_copy.json` (canonical input to deterministic PPT filling)
- `replacement_dict.json`
- `industry_section_filled_clean.pptx` (when PPT output is requested)
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
- Source attribution must reference specific sources or Evidence IDs, not "industry reports" or "public sources."
- Every body_copy field must contain opinion + evidence, not just a topic label or vague claim.

## When to Run Optional Steps

- **PPT Copy Finalize**: run when storyboard copy exceeds PPT placeholder limits, when copy is verbose rather than punchy, or when the user requests a cleaner `industry_section_ppt_copy.json`.
- **Content Quality Validation**: always run before PPT filling. Review warnings and fix issues in the storyboard before proceeding.
- **Storyboard validation**: always run before deterministic PPT filling. Fix the storyboard contract before attempting PPT execution.

## Failure Handling

- If a step fails, stop the chain, preserve completed run outputs, and report the failed step plus the next recommended action.
- If `fill-ppt` scripts fail, fix the upstream PPT copy or mapping — never patch the final PPT manually.
- If validation fails, diagnose and fix upstream rather than bypassing validation.
- If content quality validation produces warnings, address them before PPT filling — thin copy will produce thin slides.

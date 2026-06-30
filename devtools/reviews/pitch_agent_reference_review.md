# pitch-agent Reference Review

Source reviewed: external `pitch-agent` reference materials.

Purpose: identify ideas worth borrowing for the `ib-pitchdeck-agent-industry-section` skill without importing irrelevant valuation-model complexity.

## Overall Read

The external `pitch-agent` is a lighter Claude plugin: one orchestrating agent plus specialized skills. It relies mostly on natural-language operating playbooks, with only narrow scripts for DCF validation and deck number extraction. It is not a deterministic artifact pipeline like this repo.

The strongest transferable pattern is not a specific script. It is the operating posture:

- use templates as starting style/structure, not as a reason to overfit every placeholder;
- preserve user/template preferences ahead of defaults;
- cite or trace every number;
- check cross-page number consistency before delivery;
- separate read/report QC from editing;
- stop after major artifacts for review instead of silently pushing through.

## Writing-Style Findings

This section focuses on how their prompts, reference files, and `SKILL.md` files are written, independent of the finance content.

### Agent Prompt Writing

Observed in `agents/pitch-agent.md`.

What works:

- **Short frontmatter with sharp trigger scope.** The description names the target user request and says when not to use the agent.
- **Immediate role identity.** It opens with a concrete persona: senior banking associate owning a first draft end to end.
- **Output contract first.** It lists the two deliverables before discussing process.
- **Numbered workflow.** The agent sees a simple ordered chain, not a complex state machine.
- **Guardrails are few and hard.** No external communications, cite every number, stop for review after major artifacts.
- **Specialist skills are named explicitly.** This gives the orchestrator a delegation map without bloating the prompt.

What to borrow:

- Our top-level prompt should stay short and banker/editor oriented.
- It should name deliverables, stop points, and non-negotiables before implementation detail.
- It should distinguish "first-draft creation" from "editing an existing deck" or "template refresh" as different modes.

What not to borrow:

- The end-to-end valuation-agent persona is too broad for this skill.
- The prompt assumes institutional data tools and Excel valuation outputs that are not always available.

### `SKILL.md` Writing

Observed across `pitch-deck`, `deck-refresh`, `ib-check-deck`, `pptx-author`, `sector-overview`, `comps-analysis`, `dcf-model`, `lbo-model`, `3-statement-model`, `audit-xls`, and `xlsx-author`.

Strong patterns:

- **Trigger-focused descriptions.** Most skill frontmatter explains the user situations that should invoke the skill.
- **Mode split early.** Several skills distinguish live Office add-in vs headless file generation, or Office JS vs Python, before giving instructions.
- **Workflow phases with verbs.** Examples: get data, read everything, present plan, execute, report.
- **Hard constraints are visually prominent.** Critical rules are near the top and repeated where failure is costly.
- **"When not to use" sections.** These keep skills from hijacking adjacent tasks.
- **Checklists and tables.** They make recurring constraints scannable and reduce prose ambiguity.
- **Small scripts are subordinate.** Scripts support narrow verification; they do not become the main workflow.
- **User/template preference hierarchy.** Defaults are explicitly below user instructions and provided templates.

Weak patterns:

- Some model-building skills are very long and repetitive.
- Some skills instruct agents to read all references at task start, which can waste context and import irrelevant rules.
- Finance-model constraints can become too domain-specific to generalize.
- Some wording is internal-process-heavy; that is acceptable for model workbooks but dangerous for client-facing slides.

What to borrow:

- Main skill files should be short, front-loaded with role, output, workflow, and guardrails.
- Each skill/reference should include "not for" boundaries.
- Use phase names and checklists for execution, but keep complex detail in references.
- Add explicit "operator/user/template preference beats defaults" language.

What not to borrow:

- Do not make every workflow read every reference.
- Do not embed long domain formula manuals into the main industry-section skill.
- Do not use skill text as a dumping ground for validators, schema, and scripts.

### Reference File Writing

Observed in `pitch-deck/reference/*`, `ib-check-deck/references/*`, and `3-statement-model/references/*`.

Strong patterns:

- **One reference file per job.** Formatting, slide mapping, calculations, XML, report format, terminology, formulas, and source extraction are separated.
- **Each file says what it is for.** The better references are narrow and task-specific.
- **Reusable structures.** Tables, checklists, example formats, verification questions, and red flags are easier for an LLM to apply than dense prose.
- **Principle plus concrete recognition test.** The placeholder anti-pattern sections explain what happens, why it is wrong, how to recognize it, and what to do instead.
- **"Typical, adjust to template" phrasing.** This avoids turning examples into rigid rules.
- **Severity-based report formats.** QC output is easier to action when Critical / Important / Minor categories are defined.

Weak patterns:

- Some references are generic enough to be interpreted as research-report guidance rather than pitchbook guidance.
- Some examples include language we would not want in visible client slides if repeated blindly.
- Calculation/model references are useful for Excel but too detailed for industry deck generation.

What to borrow:

- Keep reference files task-sized: content quality, template handling, visual QC, evidence handling, client language, final QC.
- Include failure-mode recognition tests, especially for placeholder-looking slides, text tables, sparse exhibits, and number drift.
- Use report templates for QC outputs.
- Put formulas/calculations in references only when they are actually used by the workflow.

What not to borrow:

- Do not put banned client-facing phrases repeatedly in LLM-facing references. Store hard forbidden strings in validators instead.
- Do not let examples become fixed templates; mark them as illustrative.

### Anti-Pattern Writing

The external `pitch-deck` skill is strongest where it describes anti-patterns.

Best structure:

1. name the anti-pattern;
2. explain what happens;
3. explain why it is wrong;
4. give a recognition test;
5. state the correct approach.

This structure is more useful than saying "do better formatting" because it teaches the agent to detect the failure before final delivery.

Already reflected in this repo:

- `references/critical-anti-patterns.md` now includes instruction-like template elements and number drift.
- visible internal workpaper language is now a deterministic failure in client-facing copy.

### Command / Validation Writing

The external files often include exact commands and expected validation loops.

Useful writing pattern:

- tell the agent what command to run;
- say what the command can and cannot prove;
- define when to stop cycling and escalate.

For this repo:

- keep `scripts/pipeline.py` as the public command surface;
- avoid exposing internal role scripts in routine instructions;
- make validation language clear that Python checks mechanics, while LLM QC checks judgment.

### Recommended Writing Model For This Skill

Use this hierarchy:

1. **Top-level `SKILL.md`:** short role, output contract, natural workflow, guardrails, and reference map.
2. **Role references:** task-sized, focused on what the LLM must judge.
3. **Anti-pattern references:** failure recognition and correct repair routing.
4. **Schemas/validators:** machine checks, IDs, cross-references, hard forbidden visible strings.
5. **Scripts:** deterministic helpers only, not the source of banker judgment.

The practical takeaway: borrow their concise, task-oriented writing style and anti-pattern format, but keep our stricter separation between client-facing language, internal artifacts, and deterministic validation.

## File-by-File Findings

### `.claude-plugin/plugin.json`

Small plugin manifest only. No direct borrowing needed.

### `agents/pitch-agent.md`

Useful pattern: a short orchestrator that names what it produces, its workflow, and the specialist skills it invokes. It is much less elaborate than our current workflow, but its artifact clarity is good.

Borrowable:

- keep the top-level skill contract short and banker-oriented;
- explicitly stop for review after major artifacts;
- make every number traceable.

Not directly portable:

- CapIQ / valuation / football-field workflow is outside this industry-section skill.

### `skills/pitch-deck/SKILL.md`

Most relevant file.

Useful patterns:

- "Not for creating presentations from scratch" as the mental model when a template exists.
- Instruction boxes tell the agent what content to create, not how final formatting should look.
- Tables must be real PowerPoint table objects, not text pretending to be columns.
- Validate-render-fix loop with a clear stopping point.
- Warn that LibreOffice visual validation may not match Microsoft PowerPoint exactly.
- Cross-slide consistency for repeated metrics.

Already borrowed in this repo:

- style-guided rendering now starts from the selected PPTX package and records that behavior in render logs;
- template guidance now says sample boxes/columns are not binding unless strict layout is requested;
- internal workpaper language is blocked in visible slide copy and final PPT text.

Potential future borrow:

- add a richer deck text extraction / cross-page number report similar to the external checker.

### `skills/pitch-deck/reference/formatting-standards.md`

Useful patterns:

- concrete table, bullet, chart, alignment, and text-density standards;
- charts and tables should fill their visual area;
- text arrows should be shape objects when possible.

Current repo already covers most of this in `ppt_visual_qc.md`, `critical-anti-patterns.md`, and renderer table logic.

Small borrow applied:

- critical anti-patterns now explicitly call out instruction-like template elements as content intent, not final visual style.

### `skills/pitch-deck/reference/slide-templates.md`

Useful patterns:

- inventory template areas before populating;
- map source data to each section;
- detect gaps before slide authoring;
- distinguish instruction boxes, placeholder text, and output areas.

This supports our style-guided template stance. It argues against over-relying on fixed template roles.

### `skills/pitch-deck/reference/calculation-standards.md`

Useful patterns:

- verify CAGR, market share, growth rates, and projection formulas;
- keep rounding from changing the meaning;
- document consensus methodology when multiple sources disagree.

Current repo has metric audit rows and source reconciliation. No code copy needed, but the review reinforces that important chart numbers should have auditable calculation notes.

### `skills/pitch-deck/reference/xml-reference.md`

Useful pattern:

- use `python-pptx` APIs where possible; use direct OOXML only for targeted edits.

This supports reducing fragile direct XML work. Our renderer already uses `python-pptx` for dynamic tables/charts and only uses package inspection for validation.

### `skills/deck-refresh/SKILL.md`

Useful patterns:

- read every slide before changing values;
- build a change list first;
- flag derived numbers that may become stale;
- preserve existing formatting and perform the smallest edit.

Borrowable mainly for deck update mode, not the default first-draft industry-section workflow.

Small borrow applied:

- QC guidance now explicitly checks repeated numbers, units, periods, and source labels across pages.

### `skills/ib-check-deck/SKILL.md`

Very relevant to final QC.

Useful patterns:

- read-and-report only before edits;
- number consistency, data-narrative alignment, language polish, and visual QC as separate dimensions;
- findings ranked Critical / Important / Minor;
- use script-assisted number extraction but do not pretend it replaces judgment.

Borrowed:

- QC guidance now includes cross-page number consistency and data-vs-narrative direction checks.

Potential future borrow:

- adapt `extract_numbers.py` into a final-delivery advisory report for PPT text. It should be advisory at first because industry decks contain mixed metrics and context labels that need semantic grouping.

### `skills/ib-check-deck/scripts/extract_numbers.py`

Useful but not directly copy-ready.

Pros:

- simple markdown slide-text input;
- extracts numbers with slide refs, normalizes units, groups by category, flags conflicts.

Limits:

- category detection is finance-centric and English-heavy;
- industry decks include market size, GMV, unit sales, CAGR, rankings, penetration, and platform metrics with more varied Chinese units;
- a hard gate would create false positives.

Recommendation:

- later build a China/industry-aware number inventory report that is warning-only, then use LLM QC to adjudicate.

### `skills/ib-check-deck/references/report-format.md`

Useful severity taxonomy. Our QC reference now has similar routing, but a future final report could use the same Critical / Important / Minor layout.

### `skills/ib-check-deck/references/ib-terminology.md`

Useful concept: client-facing IB register matters. Current repo now hard-blocks internal workflow wording in visible slide copy and final PPT text. A broader professional-language checker could be added later, but should stay LLM-owned.

### `skills/sector-overview/SKILL.md`

Relevant but less refined.

Useful:

- market overview, industry structure, trends, competitive landscape, valuation context, and sector "so what" map closely to our industry-section content universe.

Not directly portable:

- it is more generic research-report oriented and includes investment implications language that can drift away from pre-mandate client pitch style.

### `skills/pptx-author/SKILL.md`

Useful mainly as a fallback: headless file generation with `python-pptx`, use template when available, every number traces to source/model. Our output layer already follows this file-artifact model.

### `skills/comps-analysis/SKILL.md`

Useful principles:

- data source hierarchy;
- avoid web search as primary source when institutional data exists;
- use the right metric for the decision question;
- document comparability choices;
- formulas and sources over opaque hardcodes.

Not directly portable:

- public-company valuation spread details do not belong in an industry overview deck unless the user asks for valuation pages.

### `skills/dcf-model/SKILL.md`

Useful principles:

- environment-specific implementation path;
- formulas over hardcodes;
- cell comments/sources on inputs;
- section-by-section review instead of end-to-end silent generation;
- validation before delivery.

Not directly portable:

- DCF-specific model structure, WACC, terminal value, and sensitivity mechanics are out of scope.

### `skills/dcf-model/TROUBLESHOOTING.md`

Useful pattern:

- short troubleshooting guide keyed to common error symptoms and unreasonable output.

Borrowable only as a concept. If our PPT renderer repeatedly fails in the same ways, a short symptom-to-repair guide would be more useful than another validator.

### `skills/dcf-model/requirements.txt`

Only declares `openpyxl` and `requests`. No direct borrowing.

### `skills/dcf-model/scripts/validate_dcf.py`

Useful pattern:

- narrow validator for a specific artifact type, with errors / warnings / info output.

Not directly portable because it is DCF-specific and assumes workbook sheets and valuation concepts. The broader lesson is to keep deterministic validators narrow and explicit rather than asking them to decide banker judgment.

### `skills/lbo-model/SKILL.md`

Useful principle:

- when a template is provided, copy/adapt the template rather than inventing a new structure.

This directly supports our style-guided PPT rendering rule.

Not directly portable:

- LBO mechanics and debt schedule checks are irrelevant to industry pages.

### `skills/3-statement-model/SKILL.md`

Useful principles:

- understand template structure before entering data;
- only edit input cells in a model;
- validate cross-tab consistency;
- final review before delivery.

Not directly portable:

- statement-linking mechanics are outside this skill.

### `skills/3-statement-model/references/formatting.md`

Useful pattern:

- consistent formatting conventions make model semantics visible.

For this PPT skill, the analogue is consistent hierarchy: title, takeaway, exhibit, body modules, and source notes should not look interchangeable.

### `skills/3-statement-model/references/formulas.md`

Useful pattern:

- formula references encode the core integrity checks of the artifact.

For this PPT skill, the analogue is evidence integrity: visible numbers should tie to MET rows, and repeated metrics should reconcile across pages.

### `skills/3-statement-model/references/sec-filings.md`

Useful pattern:

- source extraction starts with currency, scale, period, and filing location before numbers are used.

This is already aligned with our metric audit table requirements.

### `skills/audit-xls/SKILL.md`

Useful pattern:

- report findings first, categorized by severity, and do not edit without request.

Borrowable for QC role packets and final deck review.

### `skills/xlsx-author/SKILL.md`

Useful pattern:

- headless output contract and named ranges for deck-linked values.

Potential future borrow:

- if this skill later generates supporting Excel exhibits, use named ranges for every number that appears in the PPT.

## What We Should Borrow

1. **Template as style/source package, not a rigid placeholder contract.**
   Already reinforced in `references/template.md`, `references/output.md`, and render logs.

2. **Instruction boxes are content intent, not final formatting.**
   Added to `references/critical-anti-patterns.md`.

3. **Cross-page number consistency review.**
   Added to `references/qc.md` and `references/critical-anti-patterns.md` as an LLM QC responsibility.

4. **Client-facing language guardrails.**
   Already strengthened in deterministic validation for visible copy and final PPT text.

5. **Severity-based QC reports.**
   Worth adding later as a structured final review artifact if we want more formal handoff.

6. **Optional number inventory report.**
   Worth adding later, but should be advisory first and Chinese/industry-unit aware.

## What We Should Not Borrow

- CapIQ/DCF/LBO/comps workflow as default industry-section scope.
- Heavy Excel model building inside this PPT skill.
- Hard gates based on naive number extraction.
- Direct XML construction as a primary PPT authoring method.
- A template-population mindset that treats every placeholder as binding.

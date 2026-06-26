---
name: ib-pitchdeck-agent-industry-section
description: Build pre-mandate investment banking pitchbook industry sections from target briefs, PDFs, PPTs, Excel files, URLs, user-curated industry reports, public evidence, and optional PPT templates. Use when asked to create or improve an IB industry section, sector pages, or pitchbook PPT for a potential client.
---

# IB Pitchdeck Industry Section

## What This Skill Is For

Use this skill to create the industry section of a **pre-mandate client pitchbook**. The user may only have a rough target brief, a few project facts, a report, or a template. Treat that material as context for choosing the right industry lens, not as permission to write a target marketing deck.

The section should make a potential client feel that the bank understands the industry first, the pre-mandate transaction logic second, and the target context only where it sharpens the industry view. It should not read like a CIM, execution workplan, buyer memo, signed-engagement report, or generic market report unless the user explicitly asks for that.

The scripts are here to handle deterministic work: intake, artifact synchronization, validation, style extraction, rendering, and packaging. They are rails, not the analyst. Source quality, evidence readiness, claim strength, page density, page composition, and deck permission are LLM judgments that belong in the source-of-truth artifacts.

## Working Mindset

Start like a banker/editor, not a form filler.

- Use the brief to understand market boundary, geography, transaction setting, and research priorities.
- Keep user-provided target facts clearly labeled. They can frame relevance, but they should not become the page story unless independently verified and genuinely needed for the industry argument.
- Use public evidence or user-curated materials with clear provenance. Never imply confidential company access or a signed mandate.
- Prefer a dense, evidence-backed page with a clear exhibit. If evidence is thin, write a structured, caveated page or stop before client-ready rendering; do not create an empty-looking deck just because the template can be filled.
- Keep the output industry-led. Project relevance is a short bridge from the industry view to the conversation, not a target profile paragraph.

## Natural Workflow

Capture the user's material first. Preserve the original brief, register any PDFs/PPTs/Excel files/URLs/reports/templates, and separate explicit user facts from external evidence. For a short text brief, use:

```bash
python3 scripts/pipeline.py start-brief --case-name "<case>" --run-dir "<run_dir>" --brief-text "<exact user brief>"
```

Define the industry boundary before researching. The scope pack is a short boundary card: working market, parent market, broader market, core/broad/adjacent/excluded categories, and reconciliation rules. It is not an industry memo and should not contain market size, growth, rankings, valuations, or page conclusions.

Research from the boundary outward. Treat `formal_search_plan.json` as a coverage and evidence-need map, `executable_search_batch.json` as the query workbench, and `research_graph_state.json` as the execution record. Search results are leads only. Evidence requires opened or archived sources, locators, excerpts, and clear source-use limits. Key numbers need audit-grade metric rows.

Build the evidence database honestly. `scripts/pipeline.py evidence-build` creates candidate extracts; Knowledge LLM decides what becomes formal EV/MET evidence and what remains context, conflict, or gap. The Markdown research pack is an export of the DB, not a place to patch facts by hand.

Write one `banker_page_pack.json`. This is the main LLM-authored page artifact. Choose the page count from the evidence and the pitch need; a stronger concise section is better than a padded template fill. Each page should have an industry-first headline, banker judgment, page argument, exhibit, body blocks, evidence/metric bindings where available, source note, caveats, and explicit `allowed_deck_usage`. Important visible numbers need `key_data_audit` rows.

Compile only after the page pack is ready:

```bash
python3 scripts/pipeline.py compile --run-dir "<run_dir>"
```

The compile step derives `deck_blueprint.json`, `page_evidence_contract.json`, and `renderer_spec.json`. Treat them as renderer artifacts. If the compiled deck is sparse, unsupported, or data-light, repair `banker_page_pack.json` or the evidence DB and compile again.

Render only through the formal output path after the evidence, page pack, template, and QC surfaces are ready. Templates are style references by default: colors, fonts, page size, title hierarchy, and source-note treatment. A template's example text boxes or table columns are not a default structure contract. Use strict layout only when the operator explicitly asks for placeholder-level conformity.

## Evidence And Judgment Loops

Use the industry boundary loop when the market itself may be wrong, too broad, too narrow, or confused with a channel, application, parent market, or adjacent theme:

```text
Knowledge -> Industry Scoping -> Boundary Check -> Knowledge -> Updated Scope
```

Use the public evidence loop when a page needs stronger support before its claim or exhibit is ready:

```text
Banker Page Pack -> Research Request Queue -> Research -> Knowledge -> Banker Page Pack
```

The `Research Request Queue` is LLM-authored. Validate its structure, but do not generate it mechanically from every caveat or evidence-boundary note.

## Useful Commands

Run from the skill root, or resolve paths relative to this `SKILL.md`.

```bash
python3 scripts/pipeline.py next --run-dir "<run_dir>"
python3 scripts/pipeline.py gate --run-dir "<run_dir>" --output "<run_dir>/artifacts/status_report.json" --markdown-output "<run_dir>/artifacts/status_report.md"
python3 scripts/pipeline.py validate --artifact <artifact> --run-dir "<run_dir>"
python3 scripts/pipeline.py template-registry --run-dir "<run_dir>"
```

Use `next` or `gate` to understand run state and repair routing. Use `validate` for mechanical checks only. LLM review owns source quality, evidence sufficiency, page density, transaction relevance, and banker judgment.

## Reference Map

Read only the reference that matches the current work.

- `references/material-intake.md`: capture briefs, documents, URLs, reports, and templates.
- `references/knowledge-repository.md`: maintain facts, metrics, sources, conflicts, unknowns, and the evidence DB.
- `references/industry-scoping.md`: define and validate the industry boundary.
- `references/research-external-evidence.md`: plan searches, archive sources, extract public evidence, and account for coverage.
- `references/reasoning.md`: sharpen banker judgment and bounded research requests inside the page-pack workflow.
- `references/generation.md`: write `banker_page_pack.json` and compile it into renderer artifacts.
- `references/content-quality.md`: LLM-only page-density, target-drift, exhibit, and slide-quality review guidance.
- `references/drilldown-roles.md`: choose the Slide 2 drilldown without hard-coding by industry.
- `references/template.md`: analyze and fit PPT templates without changing page judgment.
- `references/qc.md`: review quality, interpret validators, and route repairs.
- `references/output.md`: render, postprocess, package, and report final status.
- `references/role_job_packets.md`: delegate narrow role work without losing parent-agent control.
- `references/research_policy.md`: evidence discipline and public research handling.
- `references/operating_model.md`: full architecture and artifact flow.
- `references/critical-anti-patterns.md`: common formatting and content failure modes.
- `references/ppt_visual_qc.md`: visual review expectations for PPT output.

Directory note: `schemas/` holds machine-readable schemas, `configs/` holds deterministic registries and templates, `references/` holds LLM judgment guidance, and `assets/` holds the bundled PPT template.

## What Good Looks Like

- The industry boundary is explicit and not confused with a parent market, channel, application, or adjacent theme.
- User-provided facts, public evidence, assumptions, and hypotheses are visibly separate.
- Claims in the page pack trace back to opened or archived sources, not search snippets.
- Pages are banker-dense: clear judgment, mechanism, data, exhibit, source note, and caveat where needed.
- The deck is industry-led, with selective project context rather than target promotion.
- Exhibits have enough chart/table/card density; chart-led pages are not single-datapoint placeholders.
- Transaction relevance is visible where appropriate, without pretending confidential access or a signed mandate.
- The selected PPT template's style is honored without forcing the page story into example placeholders.
- Final status is honest: client-ready, evidence-limited, or blocked with a clear repair owner.

## Common Failure Modes

- Treating a planned query, search snippet, or unopened URL as evidence.
- Creating fake S/SRC/EV/MET IDs to satisfy a format check.
- Moving unexecuted or low-relevance research coverage into the evidence binder.
- Turning hypotheses into headlines.
- Rendering directly from raw research without a banker page pack.
- Filling sparse token-only pages when the slide needs a real exhibit.
- Letting the target brief become eight pages of target promotion.
- Editing derived renderer artifacts or final flags to hide upstream content problems.
- Calling a draft client-ready after QC has found unresolved readiness problems.

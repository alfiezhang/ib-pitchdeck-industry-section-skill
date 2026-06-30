---
name: ib-pitchdeck-agent-industry-section
description: Build pre-mandate investment banking pitchbook industry sections from target briefs, PDFs, PPTs, Excel files, URLs, user-curated industry reports, public evidence, and optional PPT templates. Use when asked to create or improve an IB industry section, sector pages, or pitchbook PPT for a potential client.
---

# IB Pitchdeck Industry Section

## What This Skill Is For

Use this skill to create the industry section of a **pre-mandate client pitchbook**. Treat the user's brief as context for choosing the industry lens, not as permission to write a target marketing deck.

The section should prove industry understanding first, transaction logic second, and target relevance only where it sharpens the industry view. It should not read like a CIM, execution workplan, buyer memo, signed-engagement report, or generic market report unless the user explicitly asks for that.

Scripts handle deterministic work: intake records, file synchronization, debug structure checks, style extraction, rendering, and packaging. They are rails, not the analyst. Source quality, evidence readiness, claim strength, page density, page composition, and delivery readiness are LLM judgments captured in the authored work product.

## Output Contract

Produce an editable PowerPoint industry section plus a supporting evidence/page record. The record can be concise: enough to show sources, key-data audit, page intent, and repair routing. Do not create every possible intermediate file just because a helper can read it. The deliverable should make an industry-led pre-mandate pitch case, show traceable data, and leave an actionable handoff: send the deck, improve the page pack, run one narrow research loop, or create a clearly labeled review copy only after the loop cap/source limit is real.

Do not turn this skill into a full valuation model, CIM, process report, buyer list, or operating plan unless the user explicitly changes the assignment. If the user asks only to update an existing deck, preserve the deck and make the smallest reliable change.

## Operating Modes

- **First-draft industry section:** LLM-led framing, research judgment, evidence record, banker page brief, style-guided/direct PPT output, and final QC.
- **Existing deck improvement:** read the current deck first, preserve client-facing style, and repair the requested pages.
- **Template/style adaptation:** treat templates as style sources unless strict placeholder conformity is explicitly requested.
- **Direct PPT composition:** copy the selected PPTX, duplicate a low-content or blank page, and build editable text boxes, tables, charts, cards, or shapes directly when that better preserves the user's style. Keep the evidence/page-pack judgment record, but do not force every derived renderer artifact.
- **Research-limited review copy:** Do not create a review copy as the first stopping point. Route to targeted research first; create a `RESEARCH_LIMITED_REVIEW_` PPT only after loop cap, clear source unavailability, or explicit operator direction.

## Preference Hierarchy

When instructions conflict, apply this order:

1. explicit user instruction for this run;
2. user-provided template, style guide, source material, or approved deck;
3. reviewed evidence and metric audit records;
4. this skill's default workflow and bundled template assumptions.

Do not let a default page role, sample text box, or example table column override the actual page argument or the user's provided style.

## Working Mindset

Start like a banker/editor, not a form filler.

- Use the brief to understand market boundary, geography, transaction setting, and research priorities.
- Keep user-provided target facts clearly labeled. They can frame relevance, but they should not become the page story unless independently verified and needed for the industry argument.
- Use public evidence or user-curated materials with clear provenance. Never imply confidential company access or a signed mandate.
- Prefer dense, evidence-backed pages with clear exhibits. If evidence is thin, write a structured, caveated page or route to targeted research; do not create an empty-looking deck because a template can be filled.
- Keep the output industry-led. Project relevance is a short bridge from the industry view to the conversation, not a target profile paragraph.

## Natural Workflow

The named files are records and helper interfaces, not a form sequence. Start from the business question, evidence, page argument, and final slide experience. Write or refresh only the records needed to preserve traceability, route a repair, or render reliably.

Capture the user's material first. Preserve the original wording, register files/URLs/reports/templates, and separate explicit user facts from external evidence. Translate target facts into research priorities, not slide copy.

Define the industry boundary before researching. The scope pack is a short boundary card: the market lens for this pitch, broader context, categories to include/exclude, and reconciliation rules. It is not an industry memo and should not contain market size, growth, rankings, valuations, or page conclusions.

Research from the boundary outward. Treat search plans and query batches as workbenches, not page evidence. Search results are leads only; evidence requires opened or archived sources, locators, excerpts, and clear source-use limits. During Research, key numbers are candidate metrics; Knowledge promotes only reviewed numbers into formal metric rows.

Author the evidence record honestly. Knowledge decides what becomes formal EV/MET evidence and what remains context, conflict, or gap. The record may be compact when the source base is small, but important visible numbers still need source detail. The Markdown research pack is an export of the DB, not a place to patch facts by hand. Once the authored evidence DB exists, do not backfill early research workbench files solely to make status look linear.

Author one banker page pack (`banker_page_pack.json`) as a client-facing page brief, not as a slot-filling file. In direct PPT composition runs, this can be a concise slide-by-slide judgment record rather than a renderer-shaped JSON object. Choose page count from the evidence and pitch need. For each page, decide the argument, visible title or title-ready argument, exhibit/body payload, source bindings, source note/caveat, and deck-use note where useful. Use `main_message` only when a subtitle helps; otherwise omit it so helpers do not repeat the page argument as a subtitle. Important visible numbers need `key_data_audit` rows with known source detail. For final handoff, state the decision in prose and use `deliverable_readiness.business_action` only as a short helper label when needed.

Before output, read visible slide copy as if you were the client. If it sounds like workflow language, a scope-card label, a research task, an internal deck-use discussion, a readiness label, or a post-mandate workstream phrase, rewrite it into market framing, category economics, channel behavior, peer benchmark, source limitation, or transaction relevance.

Render or directly compose the PPT only after evidence, page pack, template style, and review signals are ready. Templates are style references by default: colors, fonts, page size, title hierarchy, source-note treatment, and density. Prefer direct editable composition when a user template is simple, when structured rendering would force awkward slot choices, or when the LLM can make a better page by drawing the right text boxes, tables, charts, or cards itself. Always start from the selected PPTX package; do not create an unrelated new presentation and approximate the style. A template's example text boxes or table columns are not a default structure contract.

Use review points rather than silent forward motion. After evidence DB authoring, page-pack authoring, and final rendering, the next step should be clear from the authored work product and QC: continue, repair the owning file, send a targeted research queue, or ask for QC/user decision after bounded research is exhausted. Helper checks can confirm structure and file consistency; they do not decide whether the section is persuasive.

## Evidence And Judgment Loops

Use the industry boundary loop when the market itself may be wrong, too broad, too narrow, or confused with a channel, application, parent market, or adjacent theme:

```text
Knowledge -> Industry Scoping -> Boundary Check -> Knowledge -> Updated Scope
```

Use the public evidence loop when a page needs stronger support before its claim or exhibit is ready:

```text
Banker Page Pack -> Research Request Queue -> Research -> Knowledge -> Banker Page Pack
```

The `Research Request Queue` is LLM-authored. Use helper checks for structure and loop caps, but do not auto-generate it from every caveat or internal source-use note. Caps are ceilings, not quotas; ask for the one piece of evidence that could change page inclusion, headline assertiveness, key-data audit, or exhibit design.

## Helper Tools

Use helpers after the owning LLM work product exists or when diagnosing a concrete failure. Run them from the skill root, or resolve paths relative to this `SKILL.md`. Use status helpers to understand run state and repair routing, structure helpers for file consistency, and template helpers only when a template needs to be inspected. Do not start a run by chasing helper output for artifacts that have not been authored yet, and do not turn one helper warning into a new hard rule unless the failure is deterministic and repeatable. Default status should show owner-facing milestones, not every derived helper file. Use debug status only when exact helper commands are needed.

Treat helper output as instrumentation. LLM review owns source quality, evidence sufficiency, page density, transaction relevance, banker judgment, and whether direct editable PPT composition is better than structured rendering for this run.

## Reference Map

Load only the reference needed for the current decision. Do not load a full role bundle just because the workflow has many stages; extra process language makes the page pack worse.

- Intake / boundary / evidence: read only the active stage reference: `references/material-intake.md`, `references/industry-scoping.md`, `references/research-external-evidence.md`, `references/research_policy.md`, or `references/knowledge-repository.md`.
- Page writing: read `references/generation.md`; add `references/reasoning.md` only when deciding claim strength or targeted research. Add `references/content-quality.md` only for an editorial quality pass.
- Specific page idea: read `references/drilldown-roles.md` only when a structural drilldown page needs a deeper market view.
- Style and delivery: read `references/template.md` for style/template interpretation, `references/output.md` for output path/final delivery, and `references/ppt_visual_qc.md` for visual review.
- Review: read `references/qc.md`; add `references/critical-anti-patterns.md` only when diagnosing repeated or subtle failures.
- Subagent packet: read `references/role_job_packets.md` only when delegating one bounded task to a worker.
- Workflow architecture: read `references/operating_model.md` only when debugging or changing the workflow itself.

Directory note: `references/` holds LLM judgment guidance, `configs/` holds deterministic render/review settings, and `assets/` holds the bundled PPT template. Do not treat config files as prompt templates or authoring instructions.

## What Good Looks Like

- The industry boundary is explicit and not confused with a parent market, channel, application, or adjacent theme.
- User-provided facts, public evidence, assumptions, and hypotheses are visibly separate.
- Claims in the page pack trace back to opened or archived sources, not search snippets.
- Pages are banker-dense: clear judgment, mechanism, data, exhibit, source note, and caveat where needed.
- The deck is industry-led, with selective project context rather than target promotion.
- Exhibits have enough chart/table/card density; chart-led pages are not single-datapoint placeholders.
- Transaction relevance is visible where appropriate, without pretending confidential access or a signed mandate.
- The selected PPT template's style is honored without forcing the page story into example placeholders.
- Final handoff is actionable: send, targeted research, page-pack repair, or a clearly labeled review copy after loop cap / source unavailability / explicit operator direction.

## Common Failure Modes

- Treating a planned query, search snippet, or unopened URL as evidence.
- Creating fake S/SRC/EV/MET IDs to satisfy a format check.
- Moving unexecuted or low-relevance research coverage into the evidence binder.
- Turning hypotheses into headlines.
- Rendering directly from raw research without a banker page pack.
- Filling sparse token-only pages when the slide needs a real exhibit.
- Letting the target brief become a full section of target promotion.
- Editing helper render files or final flags to hide upstream content problems.
- Sending a draft as final after QC has found unresolved evidence, wording, or visual problems.

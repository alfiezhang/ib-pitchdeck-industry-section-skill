---
name: ib-pitchdeck-agent-industry-section
description: Build pre-mandate investment banking pitchbook industry sections from target briefs, PDFs, PPTs, Excel files, URLs, user-curated industry reports, public evidence, and optional PPT templates. Use when asked to create or improve an IB industry section, sector pages, or pitchbook PPT for a potential client.
---

# IB Pitchdeck Industry Section

## Overview

This skill helps create the **industry section of a pre-mandate client pitchbook**. The user may provide only a short target brief, a PDF/PPT, a link, an industry report, or a rough project lead. Your job is to behave like the banker/editor responsible for the section: understand the material, define the right industry boundary, collect public evidence, form defensible banker page judgments, and produce an editable PPT.

The default engagement setting is **pre-mandate client pitch**. The output is an **industry section**, not a target marketing section: it should prove that the bank understands the industry first, the transaction logic second, and only the selective target context needed to make the industry view relevant. Do not write it like a CIM, signed-engagement report, investor memo, target profile, diagnostic checklist, or execution workplan unless the user explicitly changes the deliverable.

Scripts in this skill are helpers for deterministic work: parsing, synchronization, rendering, token checks, and mechanical validation. They do not replace your judgment. Treat `scripts/pipeline.py` as the main public controller; internal scripts are implementation details, not alternate workflow routes.

When a task is narrow enough to delegate or isolate, use a role job packet: the parent agent prepares the packet, the worker handles only that packet, and the parent integrates the result. Do not hand off the whole workflow.

## Default Workflow

1. Establish the engagement context.
   - Treat the work as a pre-mandate client pitch unless told otherwise.
   - Treat a short target brief primarily as classification and context input: use it to define the market, geography, transaction setting, and research priorities.
   - Do not let user-provided target facts become the page storyline. Target facts belong in labeled project context, caveats, or a short relevance note unless independently verified and needed for the industry argument.
   - Use only user materials and public evidence. Do not imply confidential company access or a signed mandate.
   - Decide whether the user expects a formal client-ready PPT. If evidence is not ready, report the missing owner-role repair instead of rendering a shortcut deck.

2. Ingest the material.
   - Preserve the user's brief exactly before summarizing it.
   - Register user-provided PDFs, PPTs, Excel files, URLs, industry reports, notes, and templates.
   - Classify each source as project-specific material, user-curated industry report, public web result, company material, market data, or template material.
   - For a short text brief, use the bundled intake helper rather than hand-building intake files:

   ```bash
   python3 scripts/pipeline.py start-brief --case-name "<case>" --run-dir "<run_dir>" --brief-text "<exact user brief>"
   ```

3. Build the current-project knowledge base.
   - Extract target facts, transaction context, source provenance, metrics, unknowns, conflicts, and access level only to support scope, research prioritization, and selective project relevance.
   - Keep user-provided claims separate from externally verified evidence.
   - Do not search from the knowledge layer. New public evidence enters through the research layer, then returns to knowledge.

4. Define the target industry boundary before researching the industry.
   - Specify working market, parent market, broader market, core/broad/adjacent/excluded categories, and reconciliation rules.
   - The scope pack should be short. It defines the research boundary and reconciliation rules; it does not summarize the industry.
   - Use a small boundary-check search when the category could be too broad, too narrow, or confused with an application, channel, parent market, or adjacent market.
   - Boundary checking is not full industry research.
   - Do not start formal research planning or formal search execution until Industry Boundary QC has passed or routed a repair.

5. Collect public evidence.
   - Use the host's web search, SearXNG/manual URL ingestion, or user-provided reports as available.
   - If formal search or PDF extraction capability is unavailable, do not continue to a formal client-ready PPT; route to runtime setup or an evidence-limited outline.
   - Prepare the research graph in one operator-facing step: `formal_search_plan.json` remains the coverage/evidence-need map, `executable_search_batch.json` is the only query workbench, and `research_graph_state.json` is the editable execution state.
   - Treat search results as leads. A search snippet is not evidence.
   - Keep ordinary background as `research_context`; promote only hard facts and key numbers into EV/MET evidence.
   - Open/archive or manually verify a source before using it for EV/MET evidence. Key numbers require audited metric fields.
   - If a page supports EV/MET but full-page archive fails, Research must perform secondary verification, record `verification_method`, and explicitly declare the Research Archive Status before Knowledge promotes the excerpt; QC only checks that the verification and status decision are clear and credible.
   - Separate coverage accounting from the evidence binder: unexecuted searches and research gaps belong in coverage/gap audit, not in the usable evidence body.

6. Author one banker page pack.
   - After Knowledge validates `artifacts/research_evidence_db.json`, write `banker_page_pack.json` as the single LLM-authored page artifact.
   - This pack is the only default LLM-authored page-judgment artifact.
   - Each page must be industry-first: the headline, main message, banker judgment, page argument, exhibit, and body blocks should primarily explain market structure, growth, demand, economics, competition, or trends.
   - Each page should show `page_primary_subject`, `page_question`, banker judgment, page argument, substantive headline/main message, exhibit, multiple body blocks, traceable EV/MET bindings where available, and source note.
   - Use `project_relevance_note` only as a short bridge from an industry finding to the pre-mandate discussion. It is optional on pages where the industry point is self-evident, and it must not become a target profile paragraph.
   - Pages should look banker-dense, not empty: use specific industry mechanisms, quantitative evidence, competitive comparisons, profit-pool logic, transaction framing angles, and proof points. Prefer metric-supported pages and chart/table-grade exhibits when evidence supports them; use evidence-boundary exhibits when it does not.
   - Important numbers require `key_data_audit` rows with indicator, value, unit, period, geography, source type/name, original locator, short excerpt, and deck usage. Normal prose needs standard EV/source linkage but does not need audit-grade treatment.
   - When public sources conflict, choose a working number for the page, disclose why it was selected, and record the conflicting values in `conflict_data_notes`. Do not postpone all judgment merely because sources differ.
   - The mission is pre-mandate: show industry understanding, transaction understanding, and professional judgment without pretending confidential access or a signed mandate.
   - Keep target context selective: the default page subject is `industry`; `target_context` pages and target-specific terms should be exceptional and clearly source-labeled.
   - If evidence is thin, make the page structured and caveated; do not render empty pages or invent numbers.
   - Management-provided target metrics from the brief are unaudited project context unless externally verified; do not treat them as audited/chart-ready industry MET data.
   - If a page needs more public evidence before claim promotion or exhibit readiness, have Reasoning LLM author `artifacts/research_request_queue.json` directly from the queue template. Do not run a script that mechanically converts every open question into a research request.

7. Compile the page pack.
   - Run `scripts/pipeline.py compile` to create derived `deck_blueprint.json`, `page_evidence_contract.json`, and `renderer_spec.json`.
   - Treat those files as deterministic renderer artifacts. Do not hand-edit them to change judgment or fill missing content.
   - If a derived validation fails because content is sparse, unsupported, or data-light, repair `banker_page_pack.json` or the evidence DB, then recompile.

8. Use the right template.
   - If the user provides a PPT/POTX template, use it.
   - If not, use the bundled template in `assets/`.
   - Analyze colors, fonts, layouts, source-note zones, chart style, and information density before fitting slides.
   - Build the template registry through `scripts/pipeline.py template-registry`; do not call internal template analyzers as role workflow steps.

9. Review quality before final output.
   - Use deterministic checks for file presence, JSON validity, IDs, template tokens, stale artifacts, and render mechanics.
   - Use LLM review for source quality, evidence sufficiency, industry-boundary quality, reasoning strength, page density, pitch relevance, and template fit.
   - When warnings appear, route the repair to the owner of the problem. Do not patch derived artifacts just to quiet a report.

10. Render and report.
   - Formal delivery should go through the evidence, banker page pack, template, QC, and output path.
   - Do not create ad-hoc render scripts in the user's run directory.
   - Do not create fake formal artifacts just to make a deck visible. If formal research, evidence DB, banker page pack, renderer spec, or replacement dict are not ready, leave them absent or clearly incomplete and report the current blocker.
   - There is no alternate renderer. A visible PPT should come only from the formal render path after required upstream artifacts are ready.

## Two Loops To Use

**Industry boundary loop**

```text
Knowledge -> Industry Scoping -> Boundary Validation Search -> Knowledge -> Updated Scope
```

Use this when the researched market might be wrong, too broad, too narrow, or mixed with adjacent themes.

**Public evidence loop**

```text
Banker Page Pack -> Research Request Queue -> Research -> Knowledge -> Banker Page Pack
```

Use this when a page argument, caveat, transaction framing angle, or exhibit needs more public evidence before it can be used.

`Research Request Queue` is an LLM-authored control artifact. Validate its structure with `scripts/pipeline.py validate --artifact research_request_queue`, but do not generate it with a builder script.

## Practical Dashboard Commands

Run bundled scripts from the skill root, or resolve them relative to this `SKILL.md`.

Use the status dashboard when you need a snapshot of what exists and what looks mechanically invalid:

```bash
python3 scripts/pipeline.py next --run-dir "<run_dir>"
```

Use the same entrypoint for gate-style or repair-routing views:

```bash
python3 scripts/pipeline.py gate --run-dir "<run_dir>" --output "<run_dir>/artifacts/status_report.json" --markdown-output "<run_dir>/artifacts/status_report.md"
```

Use `scripts/pipeline.py validate --artifact <artifact>` for one mechanical artifact check. LLM review owns source quality, page density, pitch relevance, and banker judgment. The default public Python surface is `scripts/pipeline.py`; role-specific scripts under `scripts/<role>/` are internal implementation details unless you are editing the skill itself.

Use `scripts/pipeline.py template-registry --run-dir <run_dir>` to create or refresh `template_registry.json`.

## Reference Map

Read only the reference that matches the current work.

- `references/material-intake.md`: ingest briefs, documents, URLs, reports, and templates.
- `references/knowledge-repository.md`: maintain facts, metrics, sources, conflicts, unknowns, and evidence DB.
- `references/industry-scoping.md`: define and validate broad/core/adjacent/excluded industry scope.
- `references/research-external-evidence.md`: plan searches, archive sources, extract public evidence, and account for coverage.
- `references/reasoning.md`: sharpen banker judgments inside `banker_page_pack.json` and route bounded research requests.
- `references/generation.md`: author the banker page pack and compile it into renderer artifacts.
- `references/content-quality.md`: LLM-only page-density, target-drift, exhibit, and slide-quality review guidance.
- `references/drilldown-roles.md`: select the Slide 2 drilldown role without hard-coding by industry.
- `references/template.md`: analyze and fit PPT templates without changing the page judgment.
- `references/qc.md`: run deterministic checks, perform LLM quality review, and route repairs.
- `references/output.md`: create replacement dictionaries, render PPT, postprocess, and finalize.
- `references/role_job_packets.md`: standard packet/result shape for narrow role work and subagent-style delegation.
- `references/research_policy.md`: evidence discipline and public research handling.
- `references/operating_model.md`: full role-based architecture and artifact flow.
- `references/critical-anti-patterns.md`: common formatting and content failure modes for final review.
- `references/ppt_visual_qc.md`: visual review expectations for PPT output.

Directory note: `schemas/` contains machine-readable JSON schemas. `configs/` contains deterministic registries, layout configuration, and artifact templates. LLM judgment guidance belongs in `references/`. `assets/` contains the bundled PPT template and other output resources.

## Acceptance Criteria

- The industry boundary is explicit and not confused with parent markets, channels, applications, or adjacent sectors.
- User-provided facts, public evidence, assumptions, and hypotheses are clearly separated.
- Evidence used in banker page pack claims is traceable to archived/opened sources, not search snippets.
- The deck contains real banker judgments and transaction readthrough, not a thin list of caveats.
- The deck is industry-led: target/project context is selective and labeled, not the main storyline.
- The deck has visible exhibits with adequate data/table/card density; chart-led pages are not single datapoint placeholders.
- Buyer perspective and transaction relevance are visible where appropriate.
- A user-provided PPT template is honored; otherwise the bundled template is used.
- Final output status is honest: client-ready or blocked/not client-ready.
- If output is not final client-ready, the handoff includes the current `pipeline.py next` stage and the owner role that must repair the run.

## Failure Modes To Avoid

- Treating a planned search, query, or search snippet as evidence.
- Hand-writing deterministic derived artifacts instead of repairing the LLM-owned source artifact and recompiling.
- Creating fake S/SRC/EV/MET IDs to satisfy a format check.
- Moving unexecuted or not-material research coverage into the evidence binder.
- Turning hypotheses into headlines.
- Rendering a PPT directly from raw research without a banker page pack.
- Rendering sparse token-only pages when a slide needs a visual exhibit.
- Turning a target brief into eight pages of target promotion instead of using it for industry classification and selective relevance.
- Writing draft-only or off-schema formal artifacts to bypass the formal workflow.
- Hand-editing derived `deck_blueprint.json`, `template_profile.json`, `renderer_spec.json`, `replacement_dict.json`, or final flags to hide upstream issues.
- Claiming a formal delivery when the run is only a draft or when QC has identified unresolved client-readiness problems.

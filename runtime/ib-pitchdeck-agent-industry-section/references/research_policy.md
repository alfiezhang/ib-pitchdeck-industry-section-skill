# Research Policy

Use this as the evidence discipline behind public research and Knowledge handoff. It is here to protect traceability and honesty, not to turn research into a script.

## Core Principles

Final client delivery needs reviewable evidence unless the user explicitly limits the work to user-provided or manually supplied sources. Search snippets, model memory, root domains, and unopened URLs are leads only.

Planned `FS-xxx` rows describe evidence needs. Real evidence flows from executed attempts, opened or reviewed sources, and Knowledge-promoted `EV-xxx` / `MET-xxx` rows. User-provided target metrics remain unaudited project context unless an external reviewable source verifies them.

Keep execution records separate from evidence judgment. Research records what was searched, opened, captured, and still missing; helper outputs such as search logs, archives, and execution reports only summarize that record. The Knowledge LLM-authored evidence DB is the source of truth for usable facts, metrics, source limits, conflicts, and claim-use scope; the markdown research pack is only a readable export.

## Source Priority

Start with reviewable user-provided sources, then agent-native web search, then configured graph/manual search connectors only when they help, then manual URL ingestion when exact sources are available. Use unrestricted web search for exploration. Add domain constraints only for explicit user domains or deliberate source-specific passes.

Choose sources by evidence need rather than from a fixed source-pack registry. Typical high-quality directions include official statistics and regulators, company filings and prospectuses, industry associations, platform category pages or rankings, named market reports with visible methodology, reputable trade media with cited data, and user-provided reports. Use `site:` constraints, publisher names, geography terms, and period terms when they improve precision, but do not treat any bundled domain list as a required checklist.

Python search connectors are optional. Do not stop merely because Tavily, DDGS, or SearXNG is unavailable if the agent can use native web search or exact reviewable sources. If no search, PDF, or source-reading route is available for a claim that could change the deck, route one bounded research request or record the source limit; do not fabricate evidence.

## Boundary And Planning

Research starts after a short `industry_scope_pack.json` boundary card. Use `industry_boundary_qc.json` as an optional LLM review signal when the boundary is ambiguous or high impact; it is not a default file to fill before every planning pass. If a boundary review exists, use natural prose for the decision. Add `business_action` only when a helper needs a short action label; otherwise the review remains advisory prose and Python does not infer routing from it. The scope pack handles definitions and reconciliation rules; it should not contain market size, growth, share, ranking, valuation, competitive conclusions, or page-ready claims.

Seed the planning files only after the LLM has translated the scope card into the few evidence questions that matter for the pitch. The planning helper can create workbench files, but it does not decide the research strategy. Do not start from a blank JSON shape or field list. Treat `formal_search_plan.json` as compact core research threads plus optional LLM expansion, not as a required taxonomy checklist. Let the LLM author concrete query strings only in `executable_search_batch.json`.

Query authoring is selective. For searches you intend to run now, set `active: true` and write the smallest useful set of concrete queries in `queries[]` or `query_text`. Use English, Chinese, site-constrained, named-source, or source-specific phrasing only when it materially improves recall or precision; do not fill fixed language columns. One strong query is acceptable for a targeted source; several variants are appropriate for broad discovery. Add or rewrite rows when the industry needs it. For low-priority or non-material rows, set `active: false`, leave query fields blank, and write a short natural reason; Python uses only the boolean for execution intent and does not infer from the reason text.

Starter threads and optional coverage prompts are only reminders. Add material industry-specific evidence needs, merge overlapping questions, and defer low-relevance rows with a short reason rather than forcing equal-depth searches.

## Execution And Archive

Record what actually happened: searches run, sources opened, locators, archive status, excerpts, candidate facts, candidate metrics, limitations, conflicts, and unavailable results.

Synchronize execution records after meaningful state updates when the run needs searchable logs, archive index, execution report, or coverage accounting. The helper only normalizes records; it must not author the Knowledge DB or decide claim strength.

Use plain execution facts instead of trying to make every row look supported. A row can be treated as source-backed only when it names real searches or manual-source reviews, opened/reviewed sources, locators or excerpts, and candidate facts or metrics. If the work produced only background context, repeated sources, unavailable pages, conflicting evidence, or an unexecuted backlog item, say that directly in the row notes. A clean gap is better than fake `S-xxx`, `SRC-xxx`, `EV-xxx`, or `MET-xxx` IDs.

## What Becomes Evidence

Promote only two kinds of hard evidence:

- `EV-xxx`: source-backed factual evidence with locator, excerpt, scope, and limitation;
- `MET-xxx`: audited metric evidence for visible/key numbers, with indicator, value, unit, period, geography, source, original locator, short excerpt, and audit note.

Background notes can remain `research_context`. They may guide wording and source discovery, but they cannot support key numbers, chart data, hard claims, or source notes unless Knowledge promotes them.

For archive status:

- `saved_text`, `saved_html`, and `saved_pdf` mean full source capture or equivalent archived source with explicit capture method.
- `manual_verified_excerpt` means Research reopened or reviewed the source or an equivalent trusted copy, recorded `verification_method`, and explained secondary verification.
- Search snippets, long copied excerpts, and unavailable pages remain leads or gaps.

After execution/archive review, prepare a Knowledge candidate workspace only when starting or intentionally refreshing DB authoring. Knowledge LLM then edits the evidence DB, promoting only supported candidates into formal evidence and metric rows.

Do not fill source usability, verification, or downstream-use fields merely to satisfy a check. If evidence is thin, mark it as thin, caveated, directional, or research-required.

## Conflicting Data

When sources disagree on market size, growth, share, margin, valuation, or peer metrics, keep the conflict visible. Preserve scope, period, unit, geography, denominator, and source authority. Choose a preferred number only when the source hierarchy and scope support it; otherwise use a range, caveat, or conflicting status.

## Helper Tools

Use pipeline helpers only when they make a record easier to preserve, review, or export:

- Planning helper: create workbench files after the LLM has chosen the evidence questions.
- Research synchronization helper: normalize execution records after real searches or manual-source reviews.
- Knowledge helper: prepare or export the evidence DB, not decide evidence usability.

Do not run a command list as proof that research is complete. Research is complete only when the opened sources, unresolved gaps, and promoted EV/MET rows are strong enough for the intended page decisions.

# Research Memo

Generate or expand a structured industry research memo that serves as the canonical factual input for all downstream steps.

This skill is called at the start of every standard workflow run. It ensures the LLM has a complete, well-sourced, well-structured research base before any storyline or copy drafting begins.

This step is intentionally **LLM-driven**. The purpose is not to reduce research into a fixed template search routine, but to ensure the model leaves behind a memo that downstream steps can treat as the factual contract.

## Purpose

Produce `industry_input_memo.md` — a comprehensive, source-disciplined research memo covering the industry definition, market sizing, growth drivers, value chain, competitive landscape, trends, and target-specific implications.

The memo is the **single source of truth** for all facts used in the storyboard. The storyboard skill does not introduce new facts beyond what is in the memo.

## Inputs

| Input | Required | Purpose |
|-------|----------|---------|
| Target brief / input card | Yes | Transaction context: target name, industry, transaction type, and optional `research_direction` |
| User attachments | No | Pitchbook drafts, CIM extracts, equity research, consultant reports |
| Existing `industry_input_memo.md` | No | If provided, this becomes expansion mode (refresh and deepen, don't start from scratch) |
| `templates/source_registry.json` | Optional | Source packs and domains for explicit priority search |
| `templates/research_plan.template.json` | Yes | Planning artifact for broad discovery, source selection, and targeted validation |

## Starting Modes

- **Brief-only mode**: create `input_card.json` in transcription mode, then run broad discovery before formal research planning.
- **Input-card mode**: validate the provided card first; do not add inferred facts to make validation pass.
- **Existing-memo mode**: treat the memo as canonical if the user asks for refinement or PPT generation from it; refresh research only when requested or when freshness checks require it.

Before running any script in this skill, select one runtime and reuse it:

```bash
PYTHON_CMD="$(python3 scripts/bootstrap_runtime.py --print-python)"
```

## Input Card Discipline

Do not enrich or rewrite `input_card.json` with inferred facts before research.

Build `input_card.json` in transcription mode:
- copy the user's brief faithfully into `target_business_summary`
- do not split user text into investment highlights, risks, peers, topics, or source preferences unless the user explicitly provided those as separate requirements
- leave `research_direction` empty unless the user explicitly supplied preferred websites, domains, packs, topics, peers, or exclusions
- set `language` to the user's request language by default; use another language only when explicitly requested
- if unsure whether a value is user-provided or inferred, leave the field blank and handle it in `research_plan.json`

Allowed in input card:
- user-provided facts and explicit user requirements
- safe normalized metadata such as industry, geography, language, and transaction type, marked in `_provenance.normalized_metadata_paths`

Not allowed in input card unless explicitly provided by the user and marked in `_provenance.user_provided_paths`:
- peer set
- priority websites or preferred domains
- preferred source packs
- investment highlights
- risks/open questions
- must-cover topics

Planner-generated peers, sources, risks, and research topics belong in `artifacts/research_plan.json`, then in `industry_input_memo.md` once researched.

Validate before research when an input card is generated:

```bash
"$PYTHON_CMD" scripts/validate_input_card.py \
  --input-card input_card.json \
  --output artifacts/input_card_validation.json
```

If this validation fails, restart from the original user brief and regenerate the card in transcription mode. Do not patch the failed card by adding new inferred content.

### Memo Generation Mode
- Trigger: brief only, or brief + attachments
- Process: mandatory Web research → synthesize into structured memo
- Always perform Web research, even when attachments are present

### Memo Expansion Mode
- Trigger: existing `industry_input_memo.md` is provided
- Default behavior: expand with Web research (refresh stale data, deepen weak sections, fill gaps)
- If user explicitly says "do not expand": treat memo as canonical, skip research

## Source Priority

Use unrestricted web search by default. Add domain constraints only when the user provides preferred sources, the research plan selects a source pack, or a deliberate default-pack source pass is needed.

1. **User-specified**: `input_card.research_direction.preferred_source_domains` or `priority_websites`
2. **User-specified source packs**: `input_card.research_direction.preferred_source_packs`
3. **Default source packs**: `templates/source_registry.json` → `default_packs`, only with `--use-default-packs`
4. **Unrestricted web search**, the normal default

Use `scripts/web_search.py --site` / `--source-pack` / `--source-registry` / `--use-default-packs` for domain-constrained search.
Site mode forces DuckDuckGo because Tavily API does not support `site:` syntax.

## Research Plan Sequence

Before memo synthesis, create `artifacts/research_plan.json` using `templates/research_plan.template.json`. This begins as a lightweight discovery plan and becomes the formal research plan after broad discovery. It is not a post-hoc summary.

Execution order:
1. Read `templates/source_registry.json` as a source menu only. Do not execute default packs yet.
2. Fill `meta.research_as_of_date` with the run date and `meta.user_material_data_cutoff` with the latest period found in user-provided materials, or `not specified`.
3. Draft broad discovery queries in the plan before running them. Do not lock industry boundaries, peer sets, source packs, or priority domains yet unless the user explicitly provided them.
4. Create `artifacts/search_log.md` from `references/search_log_template.md` before the first search attempt.
5. Run 3-6 unrestricted broad discovery queries to learn industry vocabulary, data terms, peer names, source leads, and geography-specific terminology. Record each attempt immediately in `search_log.md`.
6. Update the plan with broad-discovery findings: industry definition candidates, vocabulary, metric names, peer categories, and discovered source leads.
7. Select source packs/domains by research dimension. For each dimension, use 1-3 relevant source packs/domains when appropriate; across the full memo, aim for 6-15 distinct high-priority domains.
8. Add 0-5 industry-specific domains if broad discovery reveals authoritative associations, regulators, databases, or vertical publications not covered by the registry.
9. Add targeted validation queries and latest/current queries based on the discovered industry vocabulary and source leads.
10. Run targeted validation queries against selected sources, not every default pack against every query.

Validate the formal plan before memo synthesis:

```bash
"$PYTHON_CMD" scripts/validate_research_plan.py \
  --plan artifacts/research_plan.json \
  --source-registry templates/source_registry.json \
  --stage formal \
  --output artifacts/research_plan_validation.json
```

The validated research plan and `artifacts/search_log.md` must live in the same run directory as the memo, storyboard, and PPT outputs. Do not proceed to memo synthesis, storyboard, or PPT generation if the research plan validation artifact or search log is missing.

Formal validation is an audit gate, not a cosmetic format check. If it reports missing targeted validation queries, missing latest/current queries, or missing selected source packs/domains, update `research_plan.json` first. Search attempts recorded in `search_log.md` prove execution; `research_plan.json` is the control record and must reflect the actual targeted validation and source-selection logic.

## Multi-Round Search

Research must cover all 9 dimensions. See `references/research_policy.md` for the detailed search matrix.

Each of the 9 dimensions requires at minimum:
- 1 broad query
- 1 domain-constrained query when a preferred domain, relevant source pack, or default-pack pass is appropriate
- 1 latest/current query (for time-sensitive dimensions)

For one-shot PPT delivery, at least 6 dimensions must have filled targeted validation queries in `dimension_plan`, and the full plan should resolve 6-15 high-priority domains across selected packs/domains.

If the user provides a peer set, search each core peer for:
- Company disclosure / annual report / prospectus
- Market positioning
- One financial or operating metric

Write `artifacts/search_log.md` incrementally during the research phase using `references/search_log_template.md`. Preserve these machine-readable headings exactly: `## Search Attempts`, `### Search N`, `Search Stage`, and `## Coverage Checklist`.

## Output

`industry_input_memo.md` following the structure defined in `references/industry_input_memo_template.md`.

This memo is the stage contract for downstream reasoning:
- storyboard should not introduce new facts beyond it
- weak, missing, or conflicting data should be visible here rather than silently corrected later

Required sections:
- Project meta (target, industry, geography, transaction type, date)
- **Research Plan** (source priority, search coverage checklist)
- **Source Selection Rationale** (why selected packs/domains are relevant, and what was intentionally excluded)
- Deal context (why this industry section matters for this transaction)
- Target business summary
- Industry definition and scope
- Source materials (user-provided vs. web-researched, with attribution)
- **Evidence Ledger** (table: Evidence ID → claim → source → reliability → confidence)
- Page-by-page content notes (1–8)
- Per page: `Evidence Rows` (at least 2-3 items), `Page Evidence Pack` (at least 3 arguments), `Key Data Points` with `chart_ready` flags, `Chart-ready Data` where applicable
- `Presentation Hint`, `Visual Candidate`
- For every `Key Data Points` entry: `Definition`, `Source Name`, `Source Date`, `Confidence`, and `chart_ready` (true/false)

After writing the memo, validate it before storyboard generation:

```bash
"$PYTHON_CMD" scripts/validate_memo.py \
  --memo industry_input_memo.md \
  --run-dir . \
  --output artifacts/memo_validation.json
```

If validation fails, fix the memo first. Do not proceed to storyboard with an incomplete memo, missing page-by-page notes, missing Evidence Ledger rows, missing research artifacts, or weak sources promoted into formal evidence.

### Evidence Ledger

Every important claim or metric must have an Evidence ID (EV-001, EV-002, ...). These IDs are the anchor points for downstream:
- Storyboard `source_note` fields reference them
- Phase 2/3 fact-grounding harness traces them

### Evidence Rows per Page

Each page must have at least 2-3 evidence rows. If a page cannot meet this, flag `HIGH PRIORITY GAP`.

### Page Evidence Pack

Each page must contain a `Page Evidence Pack` before storyboard generation. This is the main fix for thin PPT output.

For every page, write at least 3 arguments. Each argument must include:
- `Evidence IDs`: one or more EV IDs from the Evidence Ledger
- `Fact / data`: the concrete fact, metric, named source observation, or sourced qualitative finding
- `So what`: the investment implication or industry mechanism
- `Target relevance`: why this supports the target-specific storyline

Do not save expansion for the final PPT stage. The storyboard step should select and compress arguments from this pack; the PPT fill step should not add new facts.

### Chart-ready Data

For quantitative pages (especially Slide 2), mark chart-ready Key Data Points with `chart_ready: true` and add a `Chart-ready Data` block with categories, values, units, periods, and source Evidence IDs.

## Research Rules

See `references/research_policy.md` for the full source hierarchy and verification rules.

Key principles:
- **Web research is mandatory** when starting from a brief or attachments.
- **Broad discovery precedes default-pack search**: read the source registry first, but do not run `--use-default-packs` until broad discovery has identified which source families are likely useful.
- **Research plan validation is mandatory** before memo synthesis. Fix errors first; warnings require judgment and should be recorded if accepted.
- **Formal research plan warnings are not harmless** in one-shot delivery. Missing targeted queries, latest/current queries, selected source packs, or selected domains must be fixed before memo synthesis.
- **Search log is procedural, not post-hoc**: create it before the first search attempt and update it after each search. Do not reconstruct a clean log only after the memo is complete.
- **Discovery plan is intentionally lightweight**: before broad discovery, avoid filling unknown peer sets, source packs, and industry boundaries from model prior knowledge. Let broad discovery inform the formal plan.
- **Runtime bootstrap is mandatory before fallback search**: run `python3 scripts/bootstrap_runtime.py --print-python` and use the returned interpreter for `scripts/web_search.py`.
- **Fail closed on mandatory research failure**: if built-in WebSearch/WebFetch and fallback search cannot return verified online sources, stop the workflow. Do not generate storyboard or PPT from `training_data` unless the operator explicitly chooses degraded mode.
- **Weak sources stay outside formal evidence**: Zhihu, Baijiahao, repost/content-farm pages, document-sharing sites, SEO research pages, and generic company-info pages may be used only as leads or rejected-source notes. Do not place them in `Evidence Ledger`, `Selected Sources`, `Online Research Sources`, or slide `source_note` unless no stronger source exists and the limitation is explicitly disclosed.
- **Do not overstate source confidence**: data aggregators, reposted report summaries, SEO research pages, and generic company-info pages are not `verified` evidence by themselves. Mark them `inferred` or `secondary` unless independently validated by an official source, filing, primary report, or reputable media/source owner.
- **Record user-provided materials separately** from online research in `Source Materials`.
- **Use the source hierarchy**: primary (government/regulatory filings) > secondary (industry association reports) > tertiary (consulting firm summaries) > lowest (news articles).
- **Keep weak sources out of core evidence**: Q&A sites, repost platforms, document-sharing sites, generic company-info pages, SEO research portals, and unsourced media roundups can suggest search terms but should be recorded as `Rejected Sources` or lead-only sources unless no stronger source exists.
- **Cross-check**: verify key numbers across multiple sources where possible.
- **Date everything**: note the period, geography, and source for every numeric fact.
- **Label confidence explicitly** in every `Key Data Points` row:
  - `verified`: directly supported by cited search/user-provided sources
  - `inferred`: calculated or synthesized from cited facts with a clear reasoning bridge
  - `training_data`: background knowledge not verified in this run and requiring follow-up
- **Search for the latest source first**: do not hard-code a year or period from user-provided materials into search queries unless the metric is inherently year-specific or you are verifying a source already known to be the latest available period.
- **Separate source date from data period**: the latest available disclosed datapoint may still be for an earlier period; search broadly first, then record the actual reporting period in the memo.
- **Capture chart-ready data, not only chart ideas**: when a page is likely to need a quantitative chart, preserve the underlying categories, series values, units, and source rows in the memo notes so downstream storyboarding can structure them.

## Search Tool Fallback

When the AI's built-in `WebSearch` / `WebFetch` tools are unavailable (e.g., third-party API proxy does not support them), use the project's fallback search script:

**Three-tier fallback:**
1. **First**: try the AI built-in `WebSearch` / `WebFetch`
2. **Detect failure**: if the response contains phrases like "I don't have a web search tool", "I'd be happy to help but", or returns no actual URLs/data — treat it as a hallucination, not a real search result
3. **Fallback 1 — Tavily** (requires `TAVILY_API_KEY` env var):
   ```bash
   python scripts/web_search.py --query "your search query" --provider tavily --output tmp/search_results.json
   ```
4. **Fallback 2 — DuckDuckGo** (free, no key needed):
   ```bash
   python scripts/web_search.py --query "your search query" --provider duckduckgo --output tmp/search_results.json
   ```
5. Or let auto mode handle it (Tavily first, DuckDuckGo fallback):
   ```bash
   python scripts/web_search.py --query "your search query" --output tmp/search_results.json
   ```
6. Read the results file and continue research with the data returned.

For priority site search:
```bash
"$PYTHON_CMD" scripts/web_search.py \
  --query "target industry market size" \
  --site cninfo.com.cn \
  --site-mode priority \
  --output tmp/search_results.json
```

For source-pack search:
```bash
"$PYTHON_CMD" scripts/web_search.py \
  --query "industry regulation policy" \
  --source-pack china_official \
  --source-registry templates/source_registry.json \
  --output tmp/search_results.json
```

For an explicit default-pack validation pass after broad discovery:
```bash
"$PYTHON_CMD" scripts/web_search.py \
  --query "industry market size latest official data" \
  --use-default-packs \
  --source-registry templates/source_registry.json \
  --output tmp/search_results.json
```

Use the default-pack command sparingly. It is useful for source discovery or validation, but it can fan out to many `site:` searches.

Run runtime bootstrap first with `PYTHON_CMD="$(python3 scripts/bootstrap_runtime.py --print-python)"`, then use `"$PYTHON_CMD"` for fallback search scripts. If bootstrap fails because Python lacks venv/ensurepip support, install the matching system package such as `python3-venv` or `python3.14-venv`, then rerun bootstrap. If `python-pptx` installs but `lxml.etree` fails to import on macOS Python 3.13/3.14, rerun with Python 3.9-3.11, for example `python3 scripts/bootstrap_runtime.py --python python3.11 --force`.

If all search providers fail or return zero results in a brief-only run, stop. Do not silently continue with `training_data` estimates.

## Expansion Rules (Memo Expansion Mode)

- Preserve useful transaction framing from the original memo.
- Refresh weak, stale, unsupported, or missing sections with new Web research.
- Do **not** carry unsupported claims from the old memo forward as facts.
- If the old memo conflicts with stronger new evidence, prefer the more reliable, more recent, and more definition-matched source.
- Directional judgments are allowed, but they must read as inference or hypothesis rather than disguised fact.

## Human Review Gate

After this skill produces `industry_input_memo.md`, **stop for human review** unless the user explicitly requested one-shot generation.

Operational rule:
- in default mode, stop here
- in one-shot mode, continue only after making data gaps and source strength explicit in the memo rather than hiding uncertainty

The reviewer should confirm:
- Industry definition is accurate and appropriately scoped
- Market sizing and segmentation logic is sound
- Key growth drivers are well-identified and sourced
- Competitive landscape is correctly characterized
- Target linkage is explicit and transaction-relevant
- Data sources are credible and gaps are acknowledged
- Research Plan shows coverage of all 9 dimensions
- Evidence Ledger entries are present for key claims
- Chart-ready data has been preserved for quantitative pages

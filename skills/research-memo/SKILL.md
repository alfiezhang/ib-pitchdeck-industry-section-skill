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
| `templates/source_registry.json` | Auto | Default source packs and domains for priority search |

## Starting Modes

### Memo Generation Mode
- Trigger: brief only, or brief + attachments
- Process: mandatory Web research → synthesize into structured memo
- Always perform Web research, even when attachments are present

### Memo Expansion Mode
- Trigger: existing `industry_input_memo.md` is provided
- Default behavior: expand with Web research (refresh stale data, deepen weak sections, fill gaps)
- If user explicitly says "do not expand": treat memo as canonical, skip research

## Source Priority

Before starting search, resolve the source domain priority chain:

1. **User-specified**: `input_card.research_direction.preferred_source_domains` or `priority_websites`
2. **User-specified source packs**: `input_card.research_direction.preferred_source_packs`
3. **Default source packs**: `templates/source_registry.json` → `default_packs`
4. **Unrestricted web search**

Use `scripts/web_search.py --site` / `--source-pack` / `--source-registry` for domain-constrained search.
Site mode forces DuckDuckGo because Tavily API does not support `site:` syntax.

## Multi-Round Search

Research must cover all 9 dimensions. See `references/research_policy.md` for the detailed search matrix.

Each of the 9 dimensions requires at minimum:
- 1 broad query
- 1 domain-constrained (source-pack or preferred-domain) query
- 1 latest/current query (for time-sensitive dimensions)

If the user provides a peer set, search each core peer for:
- Company disclosure / annual report / prospectus
- Market positioning
- One financial or operating metric

Write `artifacts/search_log.md` incrementally during the research phase using `references/search_log_template.md`.

## Output

`industry_input_memo.md` following the structure defined in `references/industry_input_memo_template.md`.

This memo is the stage contract for downstream reasoning:
- storyboard should not introduce new facts beyond it
- weak, missing, or conflicting data should be visible here rather than silently corrected later

Required sections:
- Project meta (target, industry, geography, transaction type, date)
- **Research Plan** (source priority, search coverage checklist)
- Deal context (why this industry section matters for this transaction)
- Target business summary
- Industry definition and scope
- Source materials (user-provided vs. web-researched, with attribution)
- **Evidence Ledger** (table: Evidence ID → claim → source → reliability → confidence)
- Page-by-page content notes (1–8)
- Per page: `Evidence Rows` (at least 2-3 items), `Key Data Points` with `chart_ready` flags, `Chart-ready Data` where applicable
- `Presentation Hint`, `Visual Candidate`
- For every `Key Data Points` entry: `Definition`, `Source Name`, `Source Date`, `Confidence`, and `chart_ready` (true/false)

### Evidence Ledger

Every important claim or metric must have an Evidence ID (EV-001, EV-002, ...). These IDs are the anchor points for downstream:
- Storyboard `source_note` fields reference them
- Phase 2/3 fact-grounding harness traces them

### Evidence Rows per Page

Each page must have at least 2-3 evidence rows. If a page cannot meet this, flag `HIGH PRIORITY GAP`.

### Chart-ready Data

For quantitative pages (especially Slide 2), mark chart-ready Key Data Points with `chart_ready: true` and add a `Chart-ready Data` block with categories, values, units, periods, and source Evidence IDs.

## Research Rules

See `references/research_policy.md` for the full source hierarchy and verification rules.

Key principles:
- **Web research is mandatory** when starting from a brief or attachments.
- **Dependency check is mandatory before fallback search**: run `bash ./setup.sh` and `./.venv/bin/python scripts/check_runtime_dependencies.py` before relying on `scripts/web_search.py`.
- **Fail closed on mandatory research failure**: if built-in WebSearch/WebFetch and fallback search cannot return verified online sources, stop the workflow. Do not generate storyboard or PPT from `training_data` unless the operator explicitly chooses degraded mode.
- **Record user-provided materials separately** from online research in `Source Materials`.
- **Use the source hierarchy**: primary (government/regulatory filings) > secondary (industry association reports) > tertiary (consulting firm summaries) > lowest (news articles).
- **Cross-check**: verify key numbers across multiple sources where possible.
- **Date everything**: note the period, geography, and source for every numeric fact.
- **Label confidence explicitly** in every `Key Data Points` row:
  - `verified`: directly supported by cited search/user-provided sources
  - `inferred`: calculated or synthesized from cited facts with a clear reasoning bridge
  - `training_data`: background knowledge not verified in this run and requiring follow-up
- **Search for the latest source first**: do not hard-code a data year such as `2024` into search queries unless the metric is inherently year-specific or you are verifying a source already known to be the latest available period.
- **Separate source date from data period**: the latest available disclosed datapoint may still be for 2024 or earlier; search broadly first, then record the actual reporting period in the memo.
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
./.venv/bin/python scripts/web_search.py \
  --query "target industry market size" \
  --site cninfo.com.cn \
  --site-mode priority \
  --output tmp/search_results.json
```

For source-pack search:
```bash
./.venv/bin/python scripts/web_search.py \
  --query "industry regulation policy" \
  --source-pack china_official \
  --source-registry templates/source_registry.json \
  --output tmp/search_results.json
```

Install dependencies first with `bash ./setup.sh` and verify them with `./.venv/bin/python scripts/check_runtime_dependencies.py`. If setup fails because Python lacks venv/ensurepip support, install the matching system package such as `python3-venv` or `python3.14-venv`, then rerun setup.

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

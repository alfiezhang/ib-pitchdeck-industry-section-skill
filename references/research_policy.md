# Research Policy

Use this file when the workflow starts from a brief, attachments, or an existing memo that the user wants to expand.

## Research Baseline
- Web research is mandatory unless the user already provided `industry_input_memo.md` and explicitly said not to expand it.
- Provided materials are high-priority inputs, but they do not replace Web research.
- Do not treat planner-inferred peers, sources, risks, or research topics as user-provided input. Keep them in `research_plan.json` until supported by research.
- The memo must stay transaction-oriented and target-linked. Do not drift into a generic industry report.
- If Web research is not actually completed, do not silently finish the memo. Record `HIGH PRIORITY GAP: online research not completed`.
- Search for the latest source first. Do not anchor queries to the year or period mentioned in user-provided materials unless the task is explicitly limited to that period or you are checking a known year-specific source.
- Treat `source freshness` and `data period` separately: the freshest available source may still report an earlier data period, and that is acceptable if it is the latest available disclosure.

## Source Priority Chain

Use unrestricted web search by default. Add domain constraints only when the user provided preferred sources, the research plan selected a source pack, or the operator deliberately requests a default-pack source pass.

1. **User-specified domains** from `input_card.research_direction.preferred_source_domains` or `priority_websites`
2. **User-specified source packs** from `input_card.research_direction.preferred_source_packs`
3. **Default source packs** from `templates/source_registry.json` → `default_packs`, only when explicitly enabled with `--use-default-packs`
4. **Unrestricted web search** (no domain constraint), the normal fallback and default

Use `--site-mode priority` for explicit domain-constrained searches (site-constrained first, unrestricted fallback if sparse).
Use `--site-mode only` when the user explicitly requires domain-only search.

## Research Plan Sequence

Before writing the memo, create `artifacts/research_plan.json` using `templates/research_plan.template.json`.

Follow this sequence:
1. Read `templates/source_registry.json` as a menu of possible source packs/domains. Do not execute searches from default packs yet.
2. Run 3-6 unrestricted broad discovery queries before default-pack or source-pack searches. Use them to learn industry vocabulary, metric names, player names, source leads, and jurisdiction-specific terminology.
3. Select sources by research dimension. For each dimension, choose 1-3 relevant source packs/domains when appropriate. Across the full memo, aim for 6-15 distinct high-priority domains.
4. Add 0-5 industry-specific domains discovered during broad search if they are authoritative for the target industry.
5. Explain every selected pack/domain in `source_selection.reason`.
6. Run targeted validation queries against selected packs/domains. Do not run every default pack against every query.

Validate the plan before memo synthesis:

```bash
./.venv/bin/python scripts/validate_research_plan.py \
  --plan artifacts/research_plan.json \
  --source-registry templates/source_registry.json \
  --output artifacts/research_plan_validation.json
```

## Multi-Round Search Matrix

When starting from a brief or attachments, search coverage must span all 9 dimensions below. Each dimension requires at least one broad query. Use one domain-constrained query when a preferred domain, relevant source pack, or default-pack pass is appropriate for that dimension. For time-sensitive dimensions, add one latest/current query.

| # | Dimension | Broad Query Example | Domain-Constrained | Latest/Current |
|---|---|---|---|---|
| 1 | Industry definition / scope | "industry definition scope classification" | stats.gov.cn / oecd.org | Current year reports |
| 2 | Market size and growth | "market size growth rate forecast" | consulting reports / government stats | Latest fiscal year |
| 3 | Segmentation | "market segmentation by category channel" | iresearch.com.cn / consulting | Current period |
| 4 | Demand drivers | "demand drivers consumption trends" | 36kr.com / caixin.com | Recent quarters |
| 5 | Value chain / profit pool | "value chain profit pool margin distribution" | consulting reports | Latest reports |
| 6 | Barriers / value drivers | "entry barriers competitive moat" | consulting / media | Current landscape |
| 7 | Competitive landscape / peer set | "competitive landscape market share ranking" | cninfo.com.cn / sec.gov | Latest filings |
| 8 | Trends / regulation / technology | "industry trends regulation policy technology" | government / consulting | Recent 6 months |
| 9 | Target-specific implications | "[target name] strategy financial performance" | cninfo.com.cn / hkexnews.hk / sec.gov | Latest disclosure |

### Peer Set Search (when user provides peer_set)

For each core peer in the peer set, search at minimum:
- Company disclosure / annual report / prospectus
- Market positioning
- One financial or operating metric

### Site Search Usage

When running site-constrained search with `scripts/web_search.py`:

```bash
# Single domain, priority mode
./.venv/bin/python scripts/web_search.py \
  --query "target industry market size" \
  --site cninfo.com.cn \
  --site-mode priority \
  --output tmp/search_results.json

# Source pack with registry
./.venv/bin/python scripts/web_search.py \
  --query "industry regulation policy" \
  --source-pack china_official \
  --source-registry templates/source_registry.json \
  --site-mode priority \
  --output tmp/search_results.json
```

Note: `--site` / `--sites` forces DuckDuckGo provider because Tavily API does not support `site:` syntax.

Use `--use-default-packs` only after the research plan calls for an explicit default-pack validation pass:

```bash
./.venv/bin/python scripts/web_search.py \
  --query "target industry market size latest official data" \
  --use-default-packs \
  --source-registry templates/source_registry.json \
  --site-mode priority \
  --output tmp/search_results.json
```

## Search Log

Write `artifacts/search_log.md` incrementally during the research phase. Use `references/search_log_template.md` as the template. Record every search attempt (not just successful ones) to create an audit trail for downstream fact-checking.

## Search Tool Fallback

**Three-tier fallback** when built-in `WebSearch` / `WebFetch` are unreliable:

1. **First**: use AI built-in `WebSearch` / `WebFetch`
2. **Detect hallucination** (treat as failure):
   - Response contains "I don't have a web search tool", "I'd be happy to help but", "I can suggest"
   - No actual URLs in the response
   - Returns only general advice without specific data points
   - Data conflicts with known facts from user-provided materials
3. **Fallback 1 — Tavily**: `python scripts/web_search.py --query "..." --provider tavily --output tmp/search_results.json`
4. **Fallback 2 — DuckDuckGo**: `python scripts/web_search.py --query "..." --provider duckduckgo --output tmp/search_results.json`
5. **Auto mode**: `python scripts/web_search.py --query "..." --output tmp/search_results.json` (Tavily → DuckDuckGo)
6. Read the JSON results file and continue research

The fallback script is at `scripts/web_search.py`. Install deps with `bash ./setup.sh` or `python -m pip install -r requirements.txt`.

## Source Hierarchy
Prefer sources in this order when facts conflict:
1. user-provided primary materials, management materials, CIM excerpts, diligence materials
2. official company disclosures, annual reports, regulatory filings, regulator or industry-association publications
3. high-quality databases, broker research, and established industry reports
4. reputable media and second-hand commentary

When sources conflict, prefer the one that is:
- more reliable
- more recent
- more aligned with the exact geography, period, and metric definition in scope

## Fact Discipline
- Hard numbers such as market size, CAGR, market share, rankings, margins, pricing, and regulatory claims need direct support.
- If direct support is missing, use `Insufficient data` instead of inventing a number.
- For every `Key Data Points` item, fill `Confidence` as one of:
  - `verified`: directly supported by a cited source used in this run
  - `inferred`: reasoned synthesis or calculation from cited facts
  - `training_data`: background knowledge not verified in this run and requiring follow-up
- Directional judgments are allowed when they are useful for transaction framing, but label them as inference or management hypothesis rather than settled fact.
- Do not carry unsupported claims from an older memo forward as facts during memo expansion.
- If something is important and missing, use `HIGH PRIORITY GAP: ...`.
- If something should be improved but is not blocking, use `RECOMMENDED TO SUPPLEMENT: ...`.

## Memo Construction Rules
- Preserve the memo template headings, field names, and order exactly. Do not merge, rename, delete, or reorder fields.
- Always separate `Provided Material Sources` from `Online Research Sources`.
- If attachments are used to expand an existing memo, note that in `Source Materials` notes when useful.
- Infer `Industry`, `Subsector`, and `Geography` from the provided materials plus Web research rather than pre-setting them without support.
- If multiple industry-definition cuts are plausible, choose the one most suitable for a pitchbook industry chapter and note the boundary in `Industry Definition` or `Definition Risks`.
- If `Industry`, `Subsector`, or `Geography` still cannot be determined reliably, write `Insufficient data` or a `HIGH PRIORITY GAP`.
- `Output Language` must be either `English` or `Chinese`.
- `Source Reliability` must be one of `primary`, `secondary`, or `low-certainty`.
- Keep each page tied to the Target through implication, positioning, diligence questions, or strategic relevance.
- `Presentation Hint`, `What should dominate this page`, and `Visual Candidate` are soft guidance only.
- If a page is likely to require a quantitative chart, preserve chart-ready datapoints in the page notes:
  categories, series values, units, period, geography, and exact source row logic where possible.
- Mark chart-ready datapoints explicitly with `chart_ready: true` in `Key Data Points`.
- Do not let research notes or old memo language lock the final page type for Slides 2, 6, or 7.
- Fill `Additional Sector-Specific Notes`, `HIGH PRIORITY GAP`, `RECOMMENDED TO SUPPLEMENT`, and `Definition Risks` explicitly instead of omitting them.
- Fill the `Evidence Ledger` with an entry for each important claim or metric. Use the Evidence ID (e.g., EV-001) as a stable reference across the memo and downstream storyboard `source_note` fields.
- Fill `Evidence Rows` per page with at least 2-3 items. If a page cannot meet this minimum, flag it in `HIGH PRIORITY GAP`.

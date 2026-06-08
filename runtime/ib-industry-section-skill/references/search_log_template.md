# Search Log

> This file is written incrementally during the research phase. Record every search attempt — not just successful ones.
> Purpose: create an audit trail for downstream fact-checking and Phase 2/3 harness grounding.
> Search log records execution. `artifacts/formal_search_plan.json` is the control record: `FS-xxx` IDs are planned search instructions, not executed searches.
> After the formal search plan is written, run the actual formal/latest searches first. Each real tool call must create one `S-xxx` entry here before it can be referenced by `artifacts/formal_research_execution_report.json`.
> In the execution report, `search_instruction_ids` uses `FS-xxx`; `search_attempt_ids` uses actual `S-xxx` entries from this log. Never put `FS-xxx` in `search_attempt_ids`.
> Also write `artifacts/source_reviews.json` for every opened/reviewed formal source and archive usable formal evidence in `artifacts/source_archive/`. research pack synthesis is blocked until formal research execution, source archive/source review validation, and `scripts/validate_stage_gate.py --stage pre_research_pack` pass.
> Low-provenance discovery leads are lead-only by default. Put search snippets, reposts,
> unsourced summaries, generic profile pages, document mirrors, and pages without a
> clear original publisher/methodology in Rejected Sources or Lead-only Sources unless
> no stronger source exists and the limitation is disclosed.

## Research Configuration

Priority Websites:
Preferred Domains:
Preferred Source Packs:
Default Source Packs Used (explicit only):
Source Registry Read As Menu Before Search: # yes/no
Research As-Of Date:
User Material Data Cutoff:
Latest Search Rule: # treat user-provided years as data periods; latest/current queries must search the current or most recent available period first
Peer Set:
Avoid Topics / Sources:

---

## Source Plan Summary

Initial Broad Discovery Queries Completed:
search plan Validation:
Selected Source Packs:
Selected Domains:
Added Industry-Specific Domains:
Excluded Packs / Domains:
Source Selection Rationale:

---

## Search Attempts

Use `### Search N` as the canonical heading. The validator also accepts
`### S-00N` as an alias and normalizes both to `S-00N`.

### Search 1
- **Query**:
- **Provider**: # built-in WebSearch | Tavily | DuckDuckGo
- **Site / Domain Constraint**: # e.g., site:cninfo.com.cn or empty
- **Source Pack**: # e.g., china_capital_markets or empty
- **Search Stage**: # broad_discovery | source_planning | formal_research_execution | latest_check | peer_check
- **Search Instruction IDs**: # FS-xxx from artifacts/formal_search_plan.json for formal/latest/peer searches; blank for broad_discovery
- **Mode**: # priority | only | unrestricted
- **Dimension**: # e.g., market_size_growth
- **Selected Source Reason**:
- **Result Count**:
- **Selected Sources**: # exact article/report/PDF URLs only; source names or root domains are insufficient
- **Opened / Reviewed**: # yes/no; formal evidence requires opening the underlying page/report/PDF
- **Source Locator / Raw Excerpt**: # page/section/table/paragraph/URL anchor plus short excerpt or limitation note
- **Source Review IDs**: # SRC-xxx rows in artifacts/source_reviews.json for formal opened/reviewed sources
- **Source Archive IDs / Paths**: # artifacts/source_archive/SRC-xxx.md or PDF for usable formal evidence; blank for broad_discovery leads
- **Lead-only Sources**:
- **Rejected Sources** (with reason):
- **Notes**:

### Search 2
- **Query**:
- **Provider**:
- **Site / Domain Constraint**:
- **Source Pack**:
- **Search Stage**:
- **Search Instruction IDs**:
- **Mode**:
- **Dimension**:
- **Selected Source Reason**:
- **Result Count**:
- **Selected Sources**: # exact article/report/PDF URLs only
- **Opened / Reviewed**:
- **Source Locator / Raw Excerpt**:
- **Source Review IDs**:
- **Lead-only Sources**:
- **Rejected Sources** (with reason):
- **Notes**:

### Search 3
- **Query**:
- **Provider**:
- **Site / Domain Constraint**:
- **Source Pack**:
- **Search Stage**:
- **Search Instruction IDs**:
- **Mode**:
- **Dimension**:
- **Selected Source Reason**:
- **Result Count**:
- **Selected Sources**: # exact article/report/PDF URLs only
- **Opened / Reviewed**:
- **Source Locator / Raw Excerpt**:
- **Source Review IDs**:
- **Lead-only Sources**:
- **Rejected Sources** (with reason):
- **Notes**:

<!-- Add more Search N blocks as needed -->

---

## Execution Notes

<!-- Record execution issues that are not already captured in formal_research_execution_report.json or source_reviews.json. Do not maintain a separate coverage checklist here. -->

# Search Log

> This file is written incrementally during the research phase. Record every search attempt — not just successful ones.
> Purpose: create an audit trail for downstream fact-checking and Phase 2/3 harness grounding.
> Search log records execution. `artifacts/formal_search_plan.json` is the control record: `FS-xxx` IDs are planned search instructions, not executed searches.
> After the formal search plan is written, run the actual formal/latest searches first. Each real tool call must create one `S-xxx` entry here before it can be referenced by `artifacts/formal_research_execution_report.json`.
> In the execution report, `search_instruction_ids` uses `FS-xxx`; `search_attempt_ids` uses actual `S-xxx` entries from this log. Never put `FS-xxx` in `search_attempt_ids`.
> Archive every opened/reviewed formal source in `artifacts/source_archive/` before Knowledge extraction. Source review decisions are embedded in `artifacts/research_evidence_db.json`; standalone `artifacts/source_reviews.json` is compatibility/diagnostic only. Research pack synthesis is blocked until formal research execution, source archive validation, and the pre-research aggregate check pass. Use `scripts/state_report.py next` and `scripts/pipeline.py rebuild-stale`; do not choose raw gate scripts from memory.
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

Prefer the append helper for new entries so `S-xxx` numbering and field names
stay parseable:

```bash
"$PYTHON_CMD" skills/research-external-evidence/scripts/append_search_attempt.py \
  --search-log "$RUN_DIR/artifacts/search_log.md" \
  --query "<exact query actually searched>" \
  --stage formal_research_execution \
  --fs-id FS-001 \
  --selected-source "<exact opened/reviewed URL>" \
  --opened-reviewed yes \
  --locator-excerpt "<page/section/table plus short excerpt or limitation>"
```

Field reference for a helper-generated block:
- Query
- Provider
- Site / Domain Constraint
- Source Pack
- Search Stage
- Search Instruction IDs
- Mode
- Dimension
- Selected Source Reason
- Result Count
- Selected Sources
- Opened / Reviewed
- Source Locator / Raw Excerpt
- Source Review IDs
- Source Archive IDs / Paths
- Lead-only Sources
- Rejected Sources (with reason)
- Notes

<!-- Add real Search N blocks with skills/research-external-evidence/scripts/append_search_attempt.py. Do not leave blank Search headings in this file. -->

---

## Execution Notes

<!-- Record execution issues that are not already captured in formal_research_execution_report.json or source_archive/source_archive_index.json. Do not maintain a separate coverage checklist here. -->

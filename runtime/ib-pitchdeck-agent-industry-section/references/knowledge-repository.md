# Knowledge Repository

## Purpose

Knowledge is the evidence librarian. It turns captured research and materials into a clean evidence database that later roles can trust. Store facts before judgment: source, excerpt, metric scope, unit, period, geography, limitation, conflict, and unknown.

## Evidence Discipline

`artifacts/research_evidence_db.json` is the source of truth. `industry_research_pack.md` is only a readable export from that DB.

Use `research_graph_state`, `formal_research_execution_report`, and `source_archive` together when reading a Research handoff. Candidate IDs in `formal_research_extracts[].candidate_*_ids` are leads, not usable EV/MET rows. They become formal evidence only when Knowledge writes them into `evidence_ledger` or `metric_reconciliation`.

Preserve source-specific mappings. An EV/MET row should keep its `source_review_id`, locator, excerpt, limitation, and source-review fields. Do not union evidence across sources in a way that hides where each fact came from.

Skeleton rows marked `issue_fact_inventory[].fact_status=needs_knowledge_llm` need an explicit Knowledge decision before validation. If the source is weak, conflicting, missing, or not comparable, keep that limitation visible instead of smoothing it into a stronger claim.

## What Knowledge Does Not Decide

Knowledge may mark source facts as usable, conflicting, limited, missing, or candidate based on archived records. It should not decide whether a page can use the fact as a headline, whether the deck is client-ready, or how the transaction story should be framed. Those decisions belong to Reasoning, Generation, and QC.

## What To Pass On

Hand Reasoning a concise evidence view:

- usable evidence themes;
- chart-ready metric candidates;
- conflicts and caveats;
- gaps that may require public research;
- source limitations that should constrain page claims.

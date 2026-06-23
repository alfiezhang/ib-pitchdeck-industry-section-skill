# research-external-evidence production scripts

Research, source logging, archiving, and evidence-collection tools. Research validators are owned by QC.

Use these only when the research-external-evidence role or a QC repair brief names the exact tool. Do not browse this folder as a workflow menu.

Scripts:
- `ib_research_graph.py` - state-first research execution compiler. Use `prepare` to create `formal_search_plan.json`, `coverage_map.json`, `executable_search_batch.json`, and `research_graph_state.json` together; fill the state with graph/manual/open_deep_research worker outputs; use `compile` to emit search log, source archive, formal execution report, and coverage accounting. It does not author `research_evidence_db.json`; Knowledge builds the DB skeleton after research validation and LLM-authors source usability, EV/MET rows, and limits. Put key numbers and chart datapoints in audited `metrics`; keep ordinary ODR-style background notes in `research_context`. `FS`/`S`/`SRC` IDs are internal traceability, not the main operator workflow.

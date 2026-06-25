# Reasoning

## Role

Reasoning is now a judgment-support role inside the `banker_page_pack.json` workflow. It sharpens industry judgment, caveat treatment, selective project relevance, and bounded research requests after Knowledge validates the evidence DB.

## When To Use

- A potential page argument rests on thin or conflicting evidence.
- A hypothesis might become an overstated headline.
- A transaction angle or project relevance note needs a sharper logic chain.
- The draft is drifting into target/company promotion instead of industry analysis.
- Public evidence is insufficient and should become a research request.
- The run needs an evidence-limited outline rather than a client-ready deck.

## Default Output

Reasoning writes directly into the relevant `banker_page_pack.slides[]` fields. When a claim needs more evidence before promotion, Reasoning LLM may author `artifacts/research_request_queue.json` from `configs/artifact_templates/research_request_queue.template.json`.

Do not run a builder script for the queue. Do not mechanically convert every `open_questions` item into a research request. A request exists only when Reasoning decides that resolving it would change claim permission, page inclusion, or exhibit readiness.

## How To Work

1. Start from `artifacts/research_evidence_db.json`, not from desired page titles.
2. Separate supported judgments, directional views, caveats, and evidence boundaries.
3. If a hypothesis is unresolved, write a caveated judgment or author a bounded research request instead of promoting it.
4. Decide whether the evidence supports a dense client-facing page, a caveated page, or no page.
5. Feed the result into the relevant `banker_page_pack.slides[]` fields: `page_primary_subject`, `banker_judgment`, `page_argument`, `claim_strength`, `body_blocks`, `project_relevance_note`, `caveats`, and `open_questions`.
6. Preserve the subject hierarchy: industry judgment is the default page subject; target/project context is a short relevance bridge or a labeled limitation unless the page is explicitly `target_context`.
7. If creating `research_request_queue.json`, set `authoring_mode` to `llm_authored`, cite the origin artifact/ref, state the exact source type needed, and set unresolved downstream use conservatively.

## Judgment Boundary

You own the logic of the judgment. You do not search, archive sources, invent metric audit details, fit template slots, or render PPT files.

## Good Repair Target

If the deck feels empty, generic, or data-light, repair `banker_page_pack.json` first:

- add evidence-backed interpretation;
- bind claims to EV/MET IDs;
- add chart/table/card-ready exhibit content;
- downgrade unsupported claims;
- add a short project relevance note that explains why the industry point matters before a mandate, without turning the page into target promotion.

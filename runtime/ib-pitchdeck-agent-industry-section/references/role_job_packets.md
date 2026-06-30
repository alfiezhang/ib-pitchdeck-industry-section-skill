# Role Job Packets

Use a role job packet when one bounded task is easier to isolate than to keep in the main thread. The parent agent remains the engagement lead: it chooses the task, gives the worker only the context needed, inspects the result, and integrates usable work into the owning file.

Good packet tasks include one source review, one boundary ambiguity, one small search batch, one page repair, one template-fit problem, or one QC repair brief.

Avoid packets for broad requests such as "make the whole deck", "fix everything", or "decide whether the project is complete" without full context.

## Parent Guidance

A good packet is self-contained. Include the task, engagement context, relevant input files, source limits, output location or result format, and the shortcuts the worker should avoid. After the worker returns, inspect the result before integrating it. Preserve material constraints instead of silently weakening quality.

The worker should not rely on conversation context that is not in the packet.

For research packets, give the inherited policy cap or any narrower structured request budget, plus the stop or close rule. Include cycle number and max cycles when the parent is continuing a prior loop or changing the default cap. The default cap is no more than 3 actual searches, 4 opened/reviewed sources, and 2 promoted sources per request unless the parent explicitly narrows or raises it. The worker should return a cycle outcome when that budget is spent; it should not recommend another broad pass or rerun the same request unless the parent supplies a narrower decision anchor.

Do not ask a worker to make the final delivery call for the whole engagement. A worker can say what this bounded request found, what it could not find, and whether the specific page decision changed. The parent agent decides whether to run the next narrow cycle, narrow the page scope, or ask QC/user after the cap.

## Packet Contents

Write the packet in whatever concise shape is easiest for the worker to follow. Useful ingredients:

- a short job ID or label if useful;
- the role and one-sentence objective;
- engagement context and disclosure/source limits;
- relevant input files;
- the narrow task and expected outputs;
- boundaries the worker should respect;
- how to report constraints that need parent-agent judgment.

For example, a research packet may ask the worker to verify a China base-makeup market-size definition, read the available boundary, evidence, or page context needed for that request, use the active narrow gap if one exists, run source-specific searches, open/archive useful sources, and return locators, facts, metric candidates, and source limits. It should explicitly avoid citing snippets, backfilling missing early workbenches for appearance, editing helper render files, or making the final delivery call before the parent loop has a concrete gap or exhausted-loop decision.

## Worker Result

The result should be equally compact:

- a one-line outcome in natural language;
- output files or source records created;
- decisions or notes the parent should inspect;
- evidence limits and unresolved gaps;
- next recommended owner if further integration is needed.

Do not force the result into fixed status values. Say what happened, what is usable, and what the parent still needs to decide.

## Integration

Job results are not automatically accepted. The parent or owning role integrates source/archive results into the evidence DB, page draft fields into `banker_page_pack.json`, template notes into the fit plan, and QC notes into a repair brief. Workers should not hand-author helper render files or the final PPT.

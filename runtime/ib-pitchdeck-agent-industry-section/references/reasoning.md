# Reasoning

## Role

Reasoning is the judgment desk behind `banker_page_pack.json`. Use it when a page thesis feels under-supported, a caveat may be overstated, a project relevance note is drifting into target promotion, or an evidence gap may change whether a claim belongs in the deck.

The goal is not to create another intermediate memo. The goal is to make the page pack sharper, more honest, and more useful for a pre-mandate banker conversation.

## How To Judge

Start from `artifacts/research_evidence_db.json`, not from desired slide titles. Separate what is supported, what is directional, what is caveated, and what should stay out of the client-facing deck.

For each potential page point, decide:

- Is the judgment supported strongly enough for the selected page role?
- Should it become a headline, body copy, supporting context, caveat, or no claim?
- Does the exhibit have enough source-backed content to look credible?
- Is the target/project context selective and source-labeled?
- Would one more public source materially change the page permission or exhibit design?

Write the result directly into the relevant `banker_page_pack.slides[]` fields: page subject, banker judgment, page argument, claim strength, explicit deck usage, body blocks, project relevance note, caveats, and evidence-boundary notes. Evidence-boundary notes are use limits for the team; they should not appear as visible task language in a client page.

If more evidence is needed before claim promotion, author `artifacts/research_request_queue.json` from the queue template. Keep requests bounded: name the source type needed, the originating page or evidence point, the success criteria, and the conservative downstream use while unresolved. Do not mechanically convert every caveat into a research request.

## Good Repair Target

If the deck feels empty, generic, or data-light, repair `banker_page_pack.json` first:

- add evidence-backed interpretation;
- bind claims to EV/MET IDs;
- strengthen chart/table/card-ready exhibit content;
- downgrade unsupported claims;
- add a short project relevance bridge only where it clarifies the industry view.

Do not search, archive sources, invent metric audit details, fit template slots, or render PPT files from this role.

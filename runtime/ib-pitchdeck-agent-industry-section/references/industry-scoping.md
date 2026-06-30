# Industry Scoping

## Purpose

Industry Scoping decides what market the team is actually researching. It should feel like a boundary card prepared at the start of a pitch, not like an industry memo.

The card answers:

- What is the working market?
- What parent and broader markets provide context?
- Which categories are core, broad, adjacent, or excluded?
- Which data definitions will need reconciliation later?
- Does any boundary need a small clarifying search before formal research?

Keep the output short, normally one or two screens. Scoping does not write market size, growth, share, rankings, valuation, competitive conclusions, transaction conclusions, or page-ready claims.

## Boundary Card Contents

Author a compact `industry_scope_pack.json` boundary card with these ideas:

- meta: only useful run context such as target, transaction type, geography, language, and date.
- scope summary: working market, parent market, and broader market.
- scope classification: core, broad, adjacent, and excluded categories.
- reconciliation issues: only data definitions that could change market size, share, comparability, or page claims.
- boundary check: only questions where a small search could materially change the market boundary.
- research handoff: the formal research scope, labels to apply when data is broad/channel/user-provided, and scopes Research should not treat as the market.

Use the shape hint only as a brief shape reminder. Do not copy empty template fields, and do not add an ambiguity just because the shape has a place for one.

## Writing Style

Use short phrases, not paragraphs. `working_market`, `parent_market`, and `broader_market` should each be one line. Keep `core`, `broad`, and `adjacent` to the few categories that actually matter; `excluded` should name only scopes likely to cause drift. Use `must_reconcile` for definition or scope issues that would change market size, share, metric comparability, or page claims.

`boundary_checks_if_needed` may be empty. Add an item only when a small search would materially affect the research boundary.

Treat the field names as internal artifact labels. Downstream page writers should translate the boundary into client-facing market framing and source labels; do not reuse scoping slot labels as slide wording.

If an optional `industry_boundary_qc.json` is authored, the natural-language `decision` is the review. Add `business_action` only when a helper needs a short action label; otherwise leave the review as prose. Nonstandard or missing `business_action` stays advisory, and Python does not infer routing from prose.

## What To Pass On

Research needs the final working market, the categories that require labels, the exclusions, and the reconciliation rules. If the brief is too ambiguous to define the market, say so and ask for a small boundary check rather than filling the card with speculative categories.

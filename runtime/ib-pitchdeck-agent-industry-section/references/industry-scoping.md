# Industry Scoping

## Purpose

Industry Scoping decides what market the team is actually researching. It should feel like a boundary card prepared at the start of a pitch, not like an industry memo.

The card answers:

- What is the working market?
- What parent and broader markets provide context?
- Which categories are core, broad, adjacent, or excluded?
- Which data definitions will need reconciliation later?
- Does any boundary need a small validation search before formal research?

Keep the output short, normally one or two screens. Scoping does not write market size, growth, share, rankings, valuation, competitive conclusions, transaction conclusions, or page-ready claims.

## Boundary Card Shape

```json
{
  "schema_version": "industry_scope_pack_boundary_card",
  "meta": {
    "target_company": "",
    "transaction_type": "",
    "geography": "",
    "language": "",
    "prepared_date": ""
  },
  "scope_summary": {
    "working_market": "",
    "parent_market": "",
    "broader_market": ""
  },
  "scope_classification": {
    "core": [],
    "broad": [],
    "adjacent": [],
    "excluded": []
  },
  "must_reconcile": [
    {
      "topic": "",
      "why_it_matters": "",
      "research_instruction": ""
    }
  ],
  "boundary_validation_needed": [
    {
      "question": "",
      "why_needed": "",
      "suggested_validation_source": ""
    }
  ],
  "handoff_to_research": {
    "research_scope": "",
    "do_not_use_as_market_scope": [],
    "must_label_when_used": []
  },
  "do_not_use_as_claims": true
}
```

## Writing Style

Use short phrases, not paragraphs. `working_market`, `parent_market`, and `broader_market` should each be one line. Keep `core`, `broad`, and `adjacent` to the few categories that actually matter; `excluded` should name only scopes likely to cause drift. Use `must_reconcile` for definition or scope issues that would change market size, share, metric comparability, or page claims.

`boundary_validation_needed` may be empty. Add an item only when a small search would materially affect the research boundary.

## What To Pass On

Research needs the final working market, the categories that require labels, the exclusions, and the reconciliation rules. If the brief is too ambiguous to define the market, say so and ask for boundary validation rather than filling the card with speculative categories.

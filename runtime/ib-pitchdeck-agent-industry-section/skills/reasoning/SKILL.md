---
name: ib-industry-reasoning
description: Produce banker judgment for the IB industry section from validated evidence, including supported judgments, hypotheses, research requests, hypothesis resolution, deliverable depth, and page arguments.
---

# Reasoning

## Role

You are the banker reasoning kernel. Your job is to turn evidence into pitch-relevant judgment without overstating what is known.

## Core Questions

- What industry judgments are supported by evidence?
- Which ideas are hypotheses, directional views, or unresolved questions?
- What public evidence is still needed?
- Is the current evidence deep enough for a client-ready pitch section, an evidence-limited outline, or research-first mode?
- What page arguments should Generation develop?

## Outputs

- `artifacts/hypothesis_store.json`
- `artifacts/research_request_queue.json`
- `artifacts/page_argument_pack.json`
- `industry_issue_analysis.json`
- deliverable-depth decision and evidence-readiness rationale

## How To Work

1. Start from Knowledge evidence, not from desired pages.
2. Separate supported judgments, hypotheses, caveats, and research requests.
3. Resolve each hypothesis: support, downgrade, keep as caveat, or request research.
4. Decide whether the current material supports a full pitch section or only a limited outline.
5. Convert supported judgments into page/section arguments.

## Judgment Boundary

You own banker judgment and page argument direction. You do not collect new evidence, write final slide copy, fit template slots, or render PPT files.

## Handoff

Hand off to Generation with:

- supported page arguments;
- allowed and disallowed evidence uses;
- hypotheses that may only appear as caveats or diligence questions;
- research gaps that should not become page conclusions.

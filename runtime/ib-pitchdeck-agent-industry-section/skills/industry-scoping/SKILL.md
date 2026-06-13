---
name: ib-industry-scoping
description: Define and validate the target industry boundary before formal research. Use for broad/core/adjacent/excluded scope, data hierarchy, and boundary validation; do not use for market conclusions.
---

# Industry Scoping

## Your Job

Define the industry that should be researched. This role prevents the workflow
from studying the parent industry, downstream application, channel, product
feature, or adjacent theme instead of the target industry.

Scoping is not a mini research memo and not a pitch thesis. It creates the map
that later research must follow.

## Inputs

- `input_card.json`
- `artifacts/material_extracts.json`
- `artifacts/source_classification.json`
- repository retrievals or user-curated industry materials, if available

## Outputs

- `artifacts/industry_scope_pack.json`
- `artifacts/industry_scope_pack_validation.json`
- `artifacts/industry_boundary_qc.json`
- `artifacts/boundary_research_requests.json`

## How To Think

- Draft:
  - broad industry;
  - core target industry;
  - adjacent themes;
  - excluded scope.
- Explain why the core industry is the right pitch lens for this target.
- Identify boundaries that could be confused:
  - category vs parent market;
  - component vs system;
  - product vs channel;
  - manufacturing vs brand;
  - software layer vs end market;
  - service vs equipment;
  - application industry vs supplier industry.
- Define narrow and broad category treatment only when useful for later data
  reconciliation.
- Build a data hierarchy so later metrics are not compared across incompatible
  levels.
- Use small boundary-validation searches only to verify classification and
  terminology, not to prove growth or valuation.

## What Scripts Handle

Python validates structure, flags prohibited claims, and converts QC's boundary
validation requests into a research-request artifact. It cannot decide the
industry boundary and it does not judge whether QC's reasoning is "complete".

## What You May Edit

LLM may edit:

- `artifacts/industry_scope_pack.json`, including definitions, exclusions,
  ambiguous boundaries, data hierarchy, and unvalidated leads.

LLM must not:

- put confirmed market size, growth, share, ranking, valuation, or page claims
  into scoping;
- use broad discovery as evidence for deck claims;
- allow numeric finds except as `unvalidated_leads`.

## Good Output Looks Like

A good scope pack makes it obvious:

- what industry formal research should study;
- what should be excluded;
- which adjacent themes are context only;
- which data definitions are likely to conflict;
- what needs later formal research validation.

## Avoid These Failure Modes

- Defining the parent industry as the core target industry.
- Treating a sales channel as an industry.
- Treating a downstream customer market as the target industry.
- Writing market growth conclusions during scoping.
- Using model knowledge as if it were sourced evidence.

## Hand Off

Hand off `industry_scope_pack.json` to QC first, not directly to Research. QC
reviews boundary quality and may use boundary-validation search/sources. If QC
returns `needs_scope_repair`, repair the scope pack. If QC returns
`needs_boundary_validation`, let Research handle the requested public evidence
checks. If QC returns `pass`, run the deterministic format/red-line validator
and then hand off to Research. Do not hand off market conclusions.

## Useful Commands

```bash
# First write artifacts/industry_scope_pack.json. Then QC LLM reviews boundary
# quality and writes artifacts/industry_boundary_qc.json with:
# decision: pass | needs_boundary_validation | needs_scope_repair
# decision_rationale
# quality feedback
# boundary_validation_requests when needed

"$PYTHON_CMD" scripts/build_boundary_research_requests.py \
  --boundary-qc "$RUN_DIR/artifacts/industry_boundary_qc.json" \
  --output "$RUN_DIR/artifacts/boundary_research_requests.json"

"$PYTHON_CMD" scripts/validate_industry_scope_pack.py \
  --scope-pack "$RUN_DIR/artifacts/industry_scope_pack.json" \
  --output "$RUN_DIR/artifacts/industry_scope_pack_validation.json"
```

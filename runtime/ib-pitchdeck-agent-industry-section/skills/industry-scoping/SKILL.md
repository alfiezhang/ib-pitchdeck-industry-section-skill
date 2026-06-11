---
name: ib-industry-scoping
description: Define and validate the target industry boundary before formal research. Use for broad/core/adjacent/excluded scope, data hierarchy, and boundary validation; do not use for market conclusions.
---

# Industry Scoping

Defines what industry is being researched. This is a constraint layer before
Reasoning, not a pitch thesis layer.

## Outputs

- `artifacts/industry_scope_pack.json`
- `artifacts/industry_scope_pack_validation.json`

## Responsibilities

- Draft broad industry, core target industry, adjacent themes, excluded scope.
- Identify ambiguous category boundaries and data hierarchy.
- Run thin boundary validation searches only when needed.
- Record numeric discoveries only as `unvalidated_leads`.

## Does Not Do

- Does not confirm market size, growth, share, rankings, M&A, or valuation.
- Does not write page-ready claims.
- Does not use channel, application, or parent industry as core industry unless
  evidence supports that boundary.

## Loop 1: Boundary Calibration

```text
Knowledge Layer
  -> Target Industry Definition
  -> Boundary Validation Search
  -> Knowledge Update
  -> Industry Definition Update
  -> QC pass or return to scoping
```

## Validation

```bash
"$PYTHON_CMD" scripts/validate_industry_scope_pack.py \
  --scope-pack "$RUN_DIR/artifacts/industry_scope_pack.json" \
  --output "$RUN_DIR/artifacts/industry_scope_pack_validation.json"

"$PYTHON_CMD" scripts/build_industry_boundary_qc.py \
  --scope-pack "$RUN_DIR/artifacts/industry_scope_pack.json" \
  --output "$RUN_DIR/artifacts/industry_boundary_qc.json"

"$PYTHON_CMD" scripts/build_boundary_research_requests.py \
  --boundary-qc "$RUN_DIR/artifacts/industry_boundary_qc.json" \
  --output "$RUN_DIR/artifacts/boundary_research_requests.json"
```

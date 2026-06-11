---
name: ib-industry-qc
description: Run and interpret QC, validation, and gate scripts for the IB industry section workflow. Route failures back to the correct role with repair targets; do not author content.
---

# QC

Owns horizontal quality control. QC runs validators, stage gates, and final
delivery checks, then identifies the correct repair layer.

## Responsibilities

- Run validation and gate scripts.
- Interpret failures as repair targets.
- Route issues to Material, Knowledge, Scoping, Research, Reasoning, Generation,
  Template Fit, or Output.
- Prevent downstream work when current gate is missing, failed, stale, or blocked.

## Does Not Do

- Does not write evidence rows.
- Does not write issue analysis or deck copy.
- Does not modify PPTs.
- Does not patch validators during a client run.

## Repair Target Shape

When possible, reports should identify:

- `issue_type`
- `severity`
- `repair_target_role`
- `repair_target_artifact`
- `recommended_action`
- `forbidden_action`
- `blocking`

## Key Commands

```bash
"$PYTHON_CMD" scripts/workflow.py next --run-dir "$RUN_DIR"

"$PYTHON_CMD" scripts/qc_router.py \
  --run-dir "$RUN_DIR" \
  --output "$RUN_DIR/artifacts/qc_router_report.json"

"$PYTHON_CMD" scripts/validate_stage_gate.py \
  --stage pre_research_pack \
  --run-dir "$RUN_DIR" \
  --output "$RUN_DIR/artifacts/stage_gate_pre_research_pack_validation.json"

"$PYTHON_CMD" scripts/pipeline.py validate-pre-ppt --run-dir "$RUN_DIR"

"$PYTHON_CMD" scripts/validate_final_delivery.py \
  --run-dir "$RUN_DIR" \
  --require-client-ready \
  --output "$RUN_DIR/artifacts/final_delivery_validation.json"
```

---
name: ib-industry-qc
description: Run and interpret QC, validation, and gate scripts for the IB industry section workflow. Route failures back to the correct role with repair targets; do not author content.
---

# QC

## Your Job

Run quality control and route repairs. QC is not a content author. Its job is to
explain what failed, why it matters, which layer owns the fix, and what command
or artifact should be handled next.

The core question is: **what is the smallest correct upstream repair, and who
owns it?**

## Inputs

- validation artifacts under `artifacts/`
- `workflow.py next` payload
- `qc_router_report.json`
- `final_delivery_validation.json`
- optional failure memory from prior runs

## Outputs

- normalized repair reports;
- `artifacts/qc_router_report.json`;
- `artifacts/qc_repair_brief.json`;
- `artifacts/qc_repair_brief.md`;
- `artifacts/qc_warning_disposition.json`;
- blocked/not-client-ready status with next owner role.

## How To Think

- Distinguish symptom from root cause:
  - bad query quality;
  - evidence too thin;
  - unsupported page claim;
  - template capacity conflict;
  - derived artifact hand-edit;
  - stale validation;
  - output/render failure.
- Group many errors into a small number of repair targets.
- Treat warnings as workflow signals, not decoration. Classify each warning as:
  - `advisory_only`: may proceed, but record why it is harmless;
  - `repair_before_downstream`: owner role must repair before the next layer;
  - `qc_accept_with_limits`: may proceed only with explicit rationale and
    downstream-use limits.
- Any warning without a disposition remains unresolved. If unresolved warnings
  are present, route to the owner role or write the QC acceptance limits before
  final delivery.
- When scripts report source-quality warnings, decide whether the source can be
  used, downgraded, or rejected based on locator, methodology access, source
  authority, recency, and claim scope. Do not treat marker matching as the
  decision.
- Confirm or reject Reasoning's `evidence_readiness` decision before final
  delivery when evidence depth is close or warnings are material.
- Route each target to the correct role:
  - Material;
  - Knowledge;
  - Scoping;
  - Research;
  - Reasoning;
  - Generation;
  - Template;
  - Output.
- State forbidden shortcuts for the current failure.
- If accepting a warning, state what the downstream may and may not do with it
  (for example: context-only, body-only, caveat-only, not headline support).
- `qc_warning_disposition.json` is the machine-readable record of that decision.
  Do not let the main agent infer warning acceptance from a passing validator.
- Preserve common failure memory when a pattern should be avoided next time.

## What Scripts Handle

Python may:

- run validators and gates;
- normalize reports into a common schema;
- generate stage state;
- detect stale artifacts;
- compile final delivery status.

Python must not:

- decide banker judgment;
- decide source quality or client-readiness from counts alone;
- write source evidence;
- repair deck copy;
- patch validators during a production run.

## What You May Edit

LLM may write:

- normalized repair reports;
- QC summaries;
- repair briefs that identify owner, target, action, and rerun command.

LLM must not directly edit:

- evidence DB content;
- issue-analysis conclusions;
- deck copy;
- renderer/replacement artifacts;
- PPT files;
- validator code during a production run.

## Repair Target Shape

QC reports should follow `templates/qc_repair_schema.json` and identify:

- `issue_id`
- `severity`
- `layer`
- `artifact`
- `field_path`
- `message`
- `why_it_matters`
- `repair_owner`
- `repair_action`
- `rerun_command`
- `downstream_blocked`

## Good Output Looks Like

A good QC output tells the next agent:

- what actually failed;
- which warnings are accepted, repaired, or routed;
- whether `qc_warning_disposition.json` has unresolved warnings;
- why it matters for a pre-mandate pitch;
- which artifact to repair;
- what not to patch;
- which command to rerun;
- whether final delivery can be claimed.

## Avoid These Failure Modes

- Reporting 80 validator messages without root-cause grouping.
- Treating format repair as content quality repair.
- Sending template capacity problems to Output.
- Allowing a final PPT path to be reported when `client_ready=false`.
- Forgetting to record repeated failure patterns.

## Hand Off

Handoff is a repair brief, not content. The next role should receive the layer,
artifact, field path, repair action, and rerun command.

## Useful Commands

```bash
"$PYTHON_CMD" scripts/workflow.py next --run-dir "$RUN_DIR"

"$PYTHON_CMD" scripts/qc_router.py \
  --run-dir "$RUN_DIR" \
  --output "$RUN_DIR/artifacts/qc_router_report.json"

# Writes qc_router_report.json, qc_repair_brief.json/md, and
# qc_warning_disposition.json.

"$PYTHON_CMD" scripts/qc_normalize_report.py \
  --report "$RUN_DIR/artifacts/some_validation.json" \
  --layer qc \
  --artifact artifacts/some_validation.json \
  --rerun-command '"$PYTHON_CMD" scripts/workflow.py next --run-dir "$RUN_DIR"' \
  --output "$RUN_DIR/artifacts/some_validation_repair.json"

"$PYTHON_CMD" scripts/pipeline.py validate-pre-ppt --run-dir "$RUN_DIR"

"$PYTHON_CMD" scripts/validate_final_delivery.py \
  --run-dir "$RUN_DIR" \
  --require-client-ready \
  --output "$RUN_DIR/artifacts/final_delivery_validation.json"
```

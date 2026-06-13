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

## Universal QC Protocol

Use the same pattern at every checkpoint:

1. The owner role writes the substantive artifact.
2. QC judges quality only where judgment is required:
   - boundary relevance;
   - source quality and use limits;
   - evidence readiness;
   - unsupported or over-extended claims;
   - page thinness;
   - template fit tradeoffs;
   - final client-readiness.
3. Python checks deterministic facts only:
   - schema and required fields;
   - IDs and references;
   - provenance and stale artifacts;
   - token/render/template mechanics;
   - final package integrity.
4. If QC says `pass`, the next role may run the deterministic Python check.
5. If QC says repair, validation search, evidence refresh, or downstream limits
   are needed, route to the owner role first. Do not proceed to downstream
   validators.
6. If QC has passed but the Python check fails, route to the owner role for
   format/red-line repair and rerun the same Python check. Re-run QC only if the
   repair changes the underlying judgment, evidence status, page argument,
   boundary, or template fit decision.
7. Do not create a second validator whose purpose is merely to judge whether QC
   wrote enough prose. QC output is a judgment artifact; the workflow only reads
   its decision fields for routing.

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
- Start from `qc_repair_brief.json.root_cause_groups` / the Root Cause Groups
  section in `qc_repair_brief.md`; only drill into individual issues after the
  owner and root cause are clear.
- Treat warnings as workflow signals, not decoration. Classify each warning as:
  - `advisory_only`: may proceed, but record why it is harmless;
  - `repair_before_downstream`: owner role must repair before the next layer;
  - `qc_accept_with_limits`: may proceed only with explicit rationale and
    downstream-use limits.
- A warning without an owner/QC decision is not silently accepted. The main
  agent should ask the relevant owner or QC to decide whether it is advisory,
  repair-required, or accepted with limits. This is a routing problem, not a
  reason to invent a second validator that grades QC prose completeness.
- When scripts report source-quality warnings, decide whether the source can be
  used, downgraded, or rejected based on locator, methodology access, source
  authority, recency, and claim scope. Do not treat marker matching as the
  decision.
- Confirm or reject Reasoning's `evidence_readiness` decision before final
  delivery when evidence depth is close or warnings are material.
- Review industry boundary quality immediately after Scoping writes
  `industry_scope_pack.json`:
  - decide whether the boundary is too broad, too narrow, or transaction-irrelevant;
  - check that channels, parent markets, suppliers, and adjacent themes are not
    mistaken for the core industry;
  - use boundary-validation search/sources when needed;
  - write `artifacts/industry_boundary_qc.json` with `decision` equal to
    `pass`, `needs_boundary_validation`, or `needs_scope_repair`.
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
- `qc_warning_disposition.json`, when used, is a machine-readable routing record
  of the QC decision. Machines may read explicit decision fields such as
  `repair_before_downstream`, `unresolved`, or `downstream_blocked`; machines
  should not judge whether QC wrote enough explanatory prose.
- Preserve common failure memory when a pattern should be avoided next time.

## Checkpoint Routing

Use this routing model unless `workflow.py next` gives a more specific policy:

| Checkpoint | QC decides | Python checks | If not OK |
|---|---|---|---|
| Material / input | Whether ambiguity needs Material/Knowledge review | manifest/input-card structure | Material repairs capture/transcription |
| Industry boundary | `pass`, `needs_scope_repair`, or `needs_boundary_validation` | scope schema and prohibited claims after QC pass | Scoping repairs or Research validates boundary, then QC reviews again |
| Source reviews | source usability, downgrade/reject/use limits | actual S/SRC links, locator/excerpt fields | Research repairs searches/reviews; QC records limits |
| Evidence DB | whether facts/metrics are usable, limited, conflicting, or thin | IDs, provenance, metric fields | Knowledge repairs extraction or Research adds evidence |
| Reasoning | evidence readiness, hypothesis treatment, allowed deck usage | required issue-analysis fields | Reasoning repairs or sends requests to Research |
| Generation | whether pages are substantive, supported, and pitch-relevant | deck fields, evidence contract, renderer spec | Generation repairs; Reasoning/Research repair if evidence is root cause |
| Template | whether content should be compressed, split, or re-fit without changing judgment | profile/fit/render mechanics | Template or Generation repairs |
| Final delivery | whether remaining issues block client-ready delivery | package integrity, debug flags, final validation | route to smallest upstream owner; do not call PPT complete |

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

For industry boundary QC, your handoff is `artifacts/industry_boundary_qc.json`.
If `decision=pass`, Scoping can run the Python format/red-line check. If
`decision=needs_scope_repair`, Scoping must revise the scope pack. If
`decision=needs_boundary_validation`, Research must satisfy the boundary
validation requests before formal research planning.

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

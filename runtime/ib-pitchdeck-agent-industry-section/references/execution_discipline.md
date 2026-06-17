# Execution Discipline

This reference keeps the skill aligned with the role-based workflow. It is not a script checklist.

## Core Rule

The main agent is the engagement lead. `state_report.py`, `qc/gate_report.py`, validators, and pipeline commands are tools. They do not decide the banker story, evidence readiness, or page quality.

## Role-First Execution

Work in role handoffs:

1. Material Intake captures user materials and source types.
2. Knowledge Repository stores facts, metrics, sources, conflicts, and unknowns.
3. Industry Scoping defines broad/core/adjacent/excluded scope.
4. Research collects public or user-supplied evidence.
5. Knowledge updates the evidence database.
6. Reasoning forms supported judgments, hypotheses, research requests, deliverable depth, and page arguments.
7. Generation edits page arguments into slide drafts and deck blueprint.
8. Template fits content to the PPT template without changing judgment.
9. QC runs format validators and LLM quality review, then routes repairs.
10. Output renders and finalizes the package.

## What To Load

At task start, read only:

- the main `SKILL.md`;
- the current role document under `references/`;
- `references/operating_model.md` when architecture context is needed;
- the exact template or schema only when creating or repairing that artifact.

Do not bulk-read every schema, test, or script as a workflow menu.

## QC Discipline

QC has two tracks:

- Python format QC: deterministic validators under `scripts/qc/validators/<layer>/`.
- LLM quality QC: source quality, evidence sufficiency, boundary relevance, reasoning quality, page density, template fit tradeoff, final client-readiness.

A validator failure tells QC where a deterministic red-line exists. QC still decides the repair owner and whether the issue is format-only or substantive.

## Warning Handling

Warnings are not silent permission to proceed. Every material warning needs one of:

- `advisory_only` with rationale;
- `accepted_with_limits` with downstream-use limits;
- `repair_before_downstream` with owner and repair action.

Use `qc/gate_report.py` or `qc_router.py` when failures are numerous or root cause is unclear.

## Repair Discipline

Repair upstream owners, not downstream artifacts:

- Material problems go to Material Intake.
- Fact/source/extract problems go to Knowledge or Research.
- Industry boundary problems go to Scoping.
- Evidence-readiness or hypothesis problems go to Reasoning.
- Thin or unsupported pages go to Generation.
- Layout fit problems go to Template.
- Render mechanics go to Output.

Do not hand-edit derived renderer/replacement/PPT artifacts to hide upstream weakness.

## Evidence Discipline

- Planned searches are not evidence.
- Actual `S-xxx` searches become evidence only after source review and Knowledge extraction.
- Coverage accounting belongs outside the evidence binder.
- User-provided target facts should remain labeled as user/company-provided unless independently verified.
- Conflicting market definitions must keep scope, period, unit, geography, and source basis.

## Page Discipline

Generation should produce pages that answer investor/client questions, not pages that merely fill placeholders.

Good pages have:

- a supported headline;
- evidence-rich body copy;
- clear visual intent;
- source/caveat discipline;
- transaction relevance appropriate for pre-mandate client pitch.

Template fit may compress or split content. It must not change the core judgment.

## Output Discipline

Output can only claim final delivery when final QC and deterministic package checks support it. If delivery is not client-ready, state the repair owner and next action instead of presenting the PPT as complete.

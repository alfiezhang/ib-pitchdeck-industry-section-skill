# IB Pitchdeck Agent Industry Section Operating Model

This plugin builds the industry section of a **pre-mandate client pitchbook**. It is not a CIM, DD workplan, buyer memo, or generic market report. The output should help a potential client believe that the bank understands the industry, the target's position, the transaction window, and how buyers will evaluate the story.

## Design Principles

1. Engagement policy comes first: use only user-provided materials and public evidence unless the user explicitly supplies more.
2. Calibrate the target industry boundary before doing broad research.
3. Knowledge stores facts, metrics, sources, conflicts, and unknowns; it does not search or judge.
4. Research collects public evidence and user-supplied reports; it does not turn hypotheses into conclusions.
5. Reasoning is where banker judgment happens: supported judgments, hypotheses, research requests, deliverable-depth decisions, and page arguments.
6. Generation is page editing: it turns page arguments into slide drafts, chart specs, and deck blueprint content.
7. Template work comes after page logic: the template can compress, split, and fit content, but it cannot change the core judgment.
8. QC owns validation. Python handles deterministic format, ID, provenance, and rendering checks. LLM QC handles quality, evidence sufficiency, source use, page thinness, and pitch relevance.
9. Output is deterministic rendering only.
10. Workflow scripts are dashboards and tool runners, not the engagement lead.

## Target Architecture

```text
User materials / links / instructions
  -> Engagement Context / Policy
  -> Material Intake
  -> Knowledge Repository
  -> Target Industry Scoping
  -> Boundary Validation Loop
  -> Reasoning Kernel
      -> Supported Judgments
      -> Hypothesis Store / Resolution
      -> Research Request Queue
  -> Public Evidence Loop
  -> Page / Section Arguments
  -> Generation
  -> Template Fit
  -> QC Engine
  -> Output
```

## Role Ownership

- Orchestrator agent: phase, owner, handoff, and repair routing.
- Material Intake: source intake and project-fact extraction.
- Knowledge Repository: evidence database and reusable source repository.
- Industry Scoping: broad/core/adjacent/excluded boundary and boundary loop.
- Research / External Evidence: public evidence collection, source archive, and execution accounting.
- Reasoning: banker judgment, hypothesis handling, research requests, deliverable depth, and page arguments.
- Generation: slide drafts, deck blueprint, chart/table intent, and content density.
- Template: template analysis and fit.
- QC: all validators plus LLM quality review and repair briefs.
- Output: replacement dictionary, PPT render, postprocess, and final package.

## Validator Ownership

All `validate_*.py` scripts live under `skills/qc/scripts/validators/<layer>/`.

- Validators are deterministic checks and format red-lines.
- QC decides how to interpret validator output.
- The repair owner remains the role that owns the artifact.
- Validators do not decide source quality, evidence readiness, page quality, or client-readiness by themselves.

## Handoff Contract

Every role handoff should identify:

- current engagement context;
- input artifacts used;
- output artifacts written;
- judgment decisions made;
- evidence limits and unresolved hypotheses;
- repair owner if blocked;
- next role if ready.

## Refactor Execution Plan

1. Rewrite role instructions so each skill reads like a role brief, not a script manual.
2. Move all validators into QC-owned validator folders.
3. Keep production scripts inside the role that creates the artifact.
4. Keep root scripts limited to public orchestration, packaging, shared utilities, and dashboards.
5. Update workflow/pipeline/script maps to call the new entrypoints.
6. Make QC output a repair brief with owner, action, and rerun target.
7. Run compile, JSON, manifest, registry, and full pytest checks after structural changes.

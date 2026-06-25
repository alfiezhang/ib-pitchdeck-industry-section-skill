# IB Pitchdeck Agent Industry Section Operating Model

This skill builds the industry section of a **pre-mandate client pitchbook**. It is not a CIM, signed-engagement workplan, buyer memo, target profile, or generic market report. The output should help a potential client believe that the bank understands the industry first, the transaction implications second, and only the selective project context needed to make the industry view relevant.

## Design Principles

1. Engagement policy comes first: use only user-provided materials and public evidence unless the user explicitly supplies more.
2. Calibrate the target industry boundary before doing broad research.
3. Knowledge stores facts, metrics, sources, conflicts, and unknowns; it does not search or judge.
4. Research collects public evidence and user-supplied reports; it does not turn hypotheses into conclusions.
5. Banker judgment and page design converge in `banker_page_pack.json`: industry-first supported views, caveats, exhibit logic, dense copy, data bindings, and selective project relevance.
6. Reasoning is a diagnostic support role when a judgment needs hypothesis resolution or an LLM-authored research request before it can enter the page pack.
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
  -> Public Evidence Loop
  -> Banker Page Pack
      -> Judgment / Exhibit / Copy / EV-MET Bindings
      -> Optional Reasoning / Research Request Loop
  -> Deterministic Compile
  -> Template Fit
  -> QC Engine
  -> Output
```

## Role Ownership

- Orchestrator agent: phase, owner, handoff, and repair routing.
- Material Intake: source intake and project-fact extraction.
- Knowledge Repository: evidence database, source provenance, conflicts, and limitations.
- Industry Scoping: broad/core/adjacent/excluded boundary and boundary loop.
- Research / External Evidence: public evidence collection, source archive, and execution accounting.
- Reasoning: optional hypothesis handling, LLM-authored research requests, and judgment diagnostics.
- Generation: banker page pack authoring, exhibit design, content density, and compile to renderer artifacts.
- Template: template analysis and fit.
- QC: all validators plus LLM quality review and repair briefs.
- Output: replacement dictionary, PPT render, postprocess, and final package.

## Validator Ownership

Deterministic checks run through `scripts/pipeline.py validate`.

- The unified validator is limited to deterministic checks and format red-lines.
- QC decides how to interpret validator output.
- The repair owner remains the role that owns the artifact.
- Python does not decide source quality, evidence readiness, page quality, or client-readiness by itself.

## Handoff Contract

Every role handoff should identify:

- current engagement context;
- input artifacts used;
- output artifacts written;
- judgment decisions made;
- evidence limits and unresolved hypotheses;
- repair owner if blocked;
- next role if ready.

## Role Job Packet Contract

Use `references/role_job_packets.md` when a task is narrow enough to delegate or isolate. This is the preferred pattern for focused source extraction, QC review, page drafting, template fit review, or other bounded role work.

The parent agent owns:

- creating a self-contained job packet;
- giving the worker all task-local context;
- limiting the worker's write scope;
- inspecting the returned result;
- integrating usable output into the canonical artifact.

The worker owns:

- one role task only;
- returning result, limits, and blocker status;
- avoiding unrelated global edits.

Job packets are not a second workflow engine. They are a cleaner handoff format for role work.

## Refactor Execution Plan

1. Rewrite role instructions so each skill reads like a role brief, not a script manual.
2. Move all validators into QC-owned validator folders.
3. Keep production scripts inside the role that creates the artifact.
4. Keep root scripts limited to public orchestration, packaging, shared utilities, and dashboards.
5. Update workflow/pipeline/script maps to call the new entrypoints.
6. Make QC output a repair brief with owner, action, and rerun target.
7. Run compile, JSON, manifest, registry, and full pytest checks after structural changes.

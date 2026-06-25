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
8. QC owns validation. Python handles deterministic format, ID, provenance, and rendering checks. LLM QC handles quality, evidence sufficiency, source use, page thinness, and transaction relevance.
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

## Focused Delegation

Use `references/role_job_packets.md` only when a task is narrow enough to delegate or isolate. Job packets are not a second workflow engine: the parent agent still owns context, integration, and final judgment.

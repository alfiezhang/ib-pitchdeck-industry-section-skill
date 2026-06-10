# Repository Agent Guide

This repository develops `ib-industry-section-skill`. Do not treat this file as
runtime skill context for customer delivery. It is for coding agents maintaining
the project.

## Project Background

The default product is a **pre-mandate client pitchbook industry section**.

The system should help an investment bank show a potential client that it
understands the industry, the target's sector position, transaction relevance,
buyer concerns, and how to tell the story in a client-ready pitchbook.

It is not primarily a CIM builder, teaser builder, due diligence checklist,
retained-client workplan, generic research-report generator, or buyer-side
investment memo tool.

## Non-Negotiable Design Principles

1. **Policy first**: pre-mandate context constrains every layer, not just final
   copy editing.
2. **Boundary before research**: industry definition and excluded scope must be
   settled before formal research conclusions.
3. **Knowledge does not search**: the knowledge layer stores facts, metrics,
   sources, conflicts, unknowns, and access level; it does not initiate search.
4. **Research collects public evidence**: the research layer executes public
   searches or ingests user-provided sources; it does not make final banker
   judgments.
5. **Reasoning owns judgment**: investment banking judgments belong in the
   reasoning / issue analysis layer.
6. **Hypothesis is not conclusion**: unresolved hypotheses must be caveated,
   sent to research, or rewritten; they must not enter deck headlines as facts.
7. **Generation starts from page argument**: deck pages should be built from
   supported page arguments, not by compressing a research memo.
8. **Template fits content**: PPT templates influence layout and density, not
   claim strength or page thesis.
9. **Python owns mechanics**: scripts should handle IDs, synchronization,
   derived artifacts, validation, exports, rendering, and stale checks.
10. **LLM owns judgment and expression**: do not push banker judgment into
    validators or deterministic builders.

## Repository Layout Policy

- Keep project-level plans in repo-level `docs/`.
- Keep runtime skill content under `runtime/ib-industry-section-skill/`.
- Do not put roadmap, architecture-debate, or implementation-plan documents
  inside the runtime skill package.
- Runtime `SKILL.md` should stay concise and agent-facing.
- Reference files under runtime `references/` should describe execution rules,
  not development history.

## Main Architecture Target

The refactor target is:

```text
Engagement Policy
→ Material Layer
→ Source Classification
→ Knowledge Layer
→ Target Industry Definition
→ Boundary Validation Search
→ Reasoning Kernel
→ Supported Judgments / Hypotheses / Research Requests
→ Page Argument
→ Generation
→ Template Fit
→ Deterministic PPT Delivery
→ QC / Final Delivery
```

Two loops matter:

- Industry boundary loop: knowledge → definition → boundary validation → updated
  knowledge → updated definition.
- Public evidence loop: reasoning → research request → public research →
  knowledge update → reasoning.

## Implementation Bias

When changing the project, prefer:

- one source of truth over duplicated artifacts;
- script-generated skeletons over LLM-maintained mechanical fields;
- repair-target errors over large unstructured validator dumps;
- narrow changes that strengthen the main path over new optional artifacts.


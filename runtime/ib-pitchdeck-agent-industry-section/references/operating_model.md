# Operating Model

This skill builds the industry section of a **pre-mandate client pitchbook**. The work should feel like a banker team moving from raw materials to industry judgment to editable slides, not like a generic report generator.

The basic logic is simple:

1. Capture what the user provided.
2. Define the right industry boundary.
3. Collect public or user-curated evidence.
4. Store facts and metrics with source limits.
5. Turn evidence into banker page judgment.
6. Fit the judgment to the chosen template.
7. Review quality and render only when the package is honest.

## Principles

- The deck is industry-led. Target facts are context, not the default storyline.
- Public evidence and user-provided facts stay visibly separate.
- Search results are leads until sources are opened or otherwise verified.
- The evidence DB stores source-faithful facts; the page pack carries banker judgment.
- Python handles deterministic mechanics. LLMs own research judgment, evidence use, page density, source quality, and client-readiness review.
- Derived renderer artifacts carry judgment forward; they should not become places to invent or repair the story.

## Flow

```text
User materials
  -> Material Intake
  -> Knowledge
  -> Industry Scoping
  -> Public Evidence Research
  -> Knowledge Evidence DB
  -> Banker Page Pack
  -> Compile / Template Fit
  -> QC
  -> Output
```

Reasoning is used when a page judgment needs sharpening, caveating, or a bounded research request. Focused job packets are used only for narrow work that benefits from isolation; the parent agent still integrates the result and remains responsible for the final answer.

## Passing Work Forward

A good handoff tells the next step:

- what was read;
- what was written;
- which judgment was made;
- what evidence limits remain;
- what should be repaired before moving downstream.

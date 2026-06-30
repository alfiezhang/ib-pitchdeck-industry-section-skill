# Operating Model

This skill builds the industry section of a **pre-mandate client pitchbook**. The work should feel like a banker team moving from raw materials to industry judgment to editable slides, not like a generic report generator.

The basic logic is simple:

1. Frame the market and transaction question.
2. Find or review enough evidence to support that framing.
3. Turn evidence into banker page judgment and exhibit choices.
4. Build an editable deck from the selected template style.
5. Review whether the result is source-faithful, dense, and sendable.

Files record these decisions; they are not the decisions themselves.

## Principles

- The deck is industry-led. Target facts are context, not the default storyline.
- Public evidence and user-provided facts stay visibly separate.
- Search results are leads until sources are opened or otherwise verified.
- The evidence DB stores source-faithful facts; the page pack carries banker judgment.
- Python handles deterministic mechanics. LLMs own research judgment, evidence use, page density, source quality, final delivery judgment, and whether a direct editable PPT composition is better than structured rendering for the chosen template.
- Helper render files carry judgment forward; they should not become places to invent or repair the story.
- Do not create or repair a file merely to satisfy a historical artifact path. Create a record when it preserves evidence, clarifies the next action, or helps produce the PPT.

## Freedom Model

Use high LLM freedom where multiple good answers can exist:

- industry framing and what to include or omit;
- search/query wording and source triage;
- evidence usefulness and claim use;
- page count, page order, exhibit choice, and page composition;
- client-facing wording, caveats, and density decisions;
- whether to continue targeted research or, after the loop cap/source limits, stop short of final client delivery.

Use Python only where repeatability matters:

- file creation, paths, JSON shape, and IDs;
- source/metric cross-references and missing-file checks;
- simple calculations, unit consistency checks, and PPT package integrity;
- editable PPT rendering or direct PPT composition from the LLM-authored page pack;
- advisory template fit signals that help the LLM compress, split, or redraw a page.

Structure/helper checks should not choose the story, page shape, evidence strength, or template interpretation. If a check finds a content problem, repair the LLM-authored judgment or the PPT composition rather than adding a new rule or patching a derived helper file. If direct PPT composition can produce a clearer editable deck from the same page pack and template style, use it instead of forcing the structured renderer path.

## Output Path Selection

Choose the output path as an LLM/template judgment. Use direct editable PPT composition when the template is mainly a style reference or the page needs a custom exhibit; use structured rendering when repeatable tooling will preserve the page pack cleanly. The selected path should serve the slide argument, not the other way around.

## Flow

```text
User materials
  -> market framing and source review
  -> evidence record
  -> banker page pack
  -> editable PPT composition
  -> Visual / Source QC

Use helper artifacts when they support one of those moves. Skip optional derived files when the page pack and final PPT can stay traceable without them.
```

Reasoning is used when a page judgment needs sharpening, caveating, or a bounded research request. Focused job packets are used only for narrow work that benefits from isolation; the parent agent still integrates the result and remains responsible for the final answer.

## Passing Work Forward

A good handoff tells the next step:

- what was read;
- what was written;
- which judgment was made;
- what evidence limits remain;
- what should be repaired before moving downstream.

# QC

## Role

Think like the review partner before a deck goes to a potential client. Decide whether the work is structurally sound, evidence-faithful, persuasive enough, and routed to the right owner when it is not.

QC does not write the pitch. It protects the quality of the pitch by separating mechanical failures from judgment failures and by sending repairs back to the artifact where the problem actually lives.

## What To Look For

Ask these questions before accepting a run:

- Does the industry boundary match the project and avoid parent-market drift?
- Are user-provided facts, public evidence, assumptions, and caveats visibly separate?
- Does each claim stay within the limits of its sources?
- Are source quality and metric audit level strong enough for the claim scope?
- Are pages dense enough for a pre-mandate pitch, with exhibits that carry real content?
- Is the deck industry-led rather than target-led?
- Does the template fit preserve the judgment rather than flatten it into generic bullets?
- Can the final output honestly be called client-ready?

## Two Kinds Of Review

Python checks the mechanics: JSON shape, missing files, IDs, stale artifacts, source references, renderer inputs, template tokens, PPT package integrity, and similar deterministic conditions.

LLM QC reviews the professional judgment: source quality, evidence sufficiency, boundary relevance, page density, exhibit usefulness, project-context drift, chart/table professionalism, mixed units or weak visuals, transaction relevance, and whether warnings can be accepted with limits.

For banker-page quality, read `references/content-quality.md`. Treat it as editorial review guidance, not as a script for hard gates.

## How To Route Repairs

Start from the current status report, but do not stop at symptoms. Group failures into root causes and repair the earliest artifact that owns the problem.

Common routing:

- weak or missing source support -> Research or Knowledge;
- wrong market boundary -> Industry Scoping;
- unsupported or thin page judgment -> Reasoning / Generation through `banker_page_pack.json`;
- sparse exhibit, weak body blocks, or data-light page -> `banker_page_pack.json`;
- layout fit problem with sound content -> Template;
- render/package mechanics -> Output.

Avoid patching compiled artifacts to hide upstream issues. If the page is sparse, repair the page pack. If the evidence is weak, repair the evidence DB or research state. If the template cannot carry the content, adjust the template fit without changing the judgment.

## Commands

Use these for mechanical signals:

```bash
"$PYTHON_CMD" scripts/pipeline.py next --run-dir "$RUN_DIR"
"$PYTHON_CMD" scripts/pipeline.py gate --run-dir "$RUN_DIR" --output "$RUN_DIR/artifacts/status_report.json" --markdown-output "$RUN_DIR/artifacts/status_report.md"
"$PYTHON_CMD" scripts/pipeline.py validate --artifact banker_page_pack --run-dir "$RUN_DIR"
```

`pipeline.py validate` is not a substitute for editorial review. It can tell you that files, IDs, and render inputs line up; it cannot tell you that a page is persuasive, dense, source-faithful, or ready for a client.

## Repair Brief

A useful QC note is short and actionable:

- what failed;
- why it matters for a pre-mandate pitch;
- which artifact or page owns the repair;
- whether downstream output is blocked;
- what should be fixed next;
- what should not be patched.

Return pass, repair-needed, or blocker. When a deterministic check should be rerun, name the command.

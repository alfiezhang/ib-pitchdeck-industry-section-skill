# Output

## Purpose

Output is deterministic delivery. Render from the current upstream artifacts, postprocess the PPT, validate the package, and report final status honestly. The output step should never become a place to rewrite evidence, page judgment, or deck copy.

## Rendering Discipline

Render only after upstream evidence, page pack, template fit, and QC surfaces are ready. If rendering fails because of malformed exhibit data, sparse visual payload, single-point chart misuse, or unreadable content fit, route the problem to Generation or Template. If upstream artifacts are missing, stale, or rejected, report the repair owner instead of creating a shortcut deck.

`scripts/pipeline.py render` records `artifacts/runtime_dependencies.json`. Missing search/PDF capability is a readiness warning by default; use `--strict-runtime-readiness` only when the operator wants runtime diagnostics to block rendering.

Use the selected template from `artifacts/template_selection.json`; if it is absent, the pipeline selects a user-registered template or the bundled template. The default render mode is style-guided: Python uses the template for page size, fonts, colors, title style, and source-note treatment, while dynamic placement follows the LLM-authored page composition. Strict placeholder layout is reserved for explicit operator requests. Avoid ad-hoc run-local render scripts such as `render_deck.py`.

## Rendered Files

- `replacement_dict.json`
- `industry_section_filled.pptx`
- `industry_section_filled_clean.pptx`
- final delivery validation artifacts

## What To Pass On

Hand off only when final delivery is client-ready, or clearly state the upstream role and artifact that must be repaired first.

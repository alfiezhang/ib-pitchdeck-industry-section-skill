# Template

## Purpose

Template work adapts the page pack to the chosen PPT style without changing the banker judgment. Read the template as a design system first: color, typography, source-note area, chart treatment, page size, title hierarchy, and expected density.

By default the workflow is `style_guided`. A template page with three boxes, a three-column table, or registered page roles is an example of style and density, not a promise that every generated deck must use exactly those boxes, columns, or page count. The LLM owns page composition; Python can support reliable, editable structured rendering when that path is useful.

A structured-render helper or direct composer should use the selected PPTX as the starting package: keep its theme, master, slide size, typography, colors, and source-note conventions, then remove example pages and draw the LLM-authored composition on copied low-content template pages or blank layouts from that same file. It should not create an unrelated new PowerPoint document and merely approximate the style.

Direct PPT composition is also acceptable when it will better preserve a simple user template or avoid forcing the page into helper-shaped containers. Copy the selected PPTX, duplicate a low-content or blank template page, and build editable text boxes, tables, charts, cards, and shapes that fit the page argument. Keep the evidence and page-pack record; skip only the unnecessary derived render intermediates, not the thinking.

If the user provides a simple template, assume they mainly want house style unless they explicitly ask for exact placeholder reuse. A sample page is a visual reference, not a content contract. It is acceptable to duplicate a low-content or blank page from the template and build the right number of text boxes, tables, charts, or cards for the actual page argument.

A sample placeholder tells you what kind of content may belong there, not how the final page must be structured. Instruction boxes, sample tables, and example charts should be translated into production-quality text, real PowerPoint tables/charts, or a better LLM-authored layout. Do not preserve placeholder formatting, sample column counts, or example page counts when they weaken the client-facing argument.

In the default style-guided path, body copy field names are not a slot contract. Treat `main_body`, side-panel names, and table-row field names as authoring hints that can be normalized into sequential visible points. Preserve exact placeholder keys only in explicit `strict_layout` mode.

## How To Think

The right layout should make the page clearer. If a slide needs a chart, table, matrix, card grid, flow, or value-chain exhibit, describe that composition in the page pack. Do not compress the argument merely to match example placeholders. Do not add a page merely to match a template role. If the page is sparse, send it back to Generation for better exhibit/body-block content or ask whether the page should be merged. If the content is sound but crowded, recommend compression or a split-page treatment.

Use `strict_layout` only when the operator explicitly wants placeholder-level conformity to a formal template. In that mode, the template's placeholder structure is a contract. Otherwise, do not let template analysis turn into a slot-filling exercise.

In style-guided mode, slide numbers, registered roles, and template variants are ordering and lineage hints. Choose the actual sequence, role, and composition from the LLM-authored page argument and use the registry only when it helps preserve output compatibility.

Follow the template selection hierarchy: explicit user template first, then registered `ppt_template` material, then the bundled template.

## Template Signals

Pass on style guidance, not a slot map. The useful signals are: selected template source, house colors and fonts, title hierarchy, source-note treatment, expected density, pages that may need compression or splitting, whether direct PPT composition is more suitable than structured rendering, and any explicit user request for strict placeholder reuse. Do not list render helper files as the work product for the LLM.

## What To Pass On

Hand Output the selected style/profile guidance, fit plan, and any content-fit warnings QC has accepted or routed. Do not rewrite the page argument, weaken caveats, decide source sufficiency, or repair evidence claims to fit a layout.

# Template

## Purpose

Template work adapts the page pack to the chosen PPT style without changing the banker judgment. Read the template like a design system: color, typography, source-note area, chart treatment, layout density, and which slide structures can carry which exhibits.

## How To Think

The right layout should make the page clearer. If a slide needs a chart, table, matrix, card grid, flow, or value-chain exhibit, choose a page type with deterministic render support for that exhibit. If the page is sparse, send it back to Generation for better exhibit/body-block content rather than hiding it in a simpler layout. If the content is sound but too large, recommend compression or a split-page treatment.

Follow the template selection hierarchy: explicit user template first, then registered `ppt_template` material, then the bundled template.

## Template Files

- `template_registry.json`
- `artifacts/template_selection.json`
- `artifacts/template_profile.json`
- `artifacts/template_fit_validation.json`
- `artifacts/template_fit_plan.json`

## What To Pass On

Hand Output the selected layouts, style/profile guidance, fit plan, and any content-fit warnings QC has accepted or routed. Do not rewrite the page argument, weaken caveats, decide source sufficiency, or repair evidence claims to fit a layout.

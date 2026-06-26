# Template

## Purpose

Template work adapts the page pack to the chosen PPT style without changing the banker judgment. Read the template as a design system first: color, typography, source-note area, chart treatment, page size, title hierarchy, and expected density.

By default the workflow is `style_guided`. A template page with three boxes, a three-column table, or eight registered page roles is an example of style and density, not a promise that every generated deck must use exactly those boxes, columns, or page count. The LLM owns page composition; Python owns reliable, editable rendering.

## How To Think

The right layout should make the page clearer. If a slide needs a chart, table, matrix, card grid, flow, or value-chain exhibit, describe that composition in the page pack. Do not compress the argument merely to match example placeholders. Do not add a page merely to match a template role. If the page is sparse, send it back to Generation for better exhibit/body-block content or ask whether the page should be merged. If the content is sound but crowded, recommend compression or a split-page treatment.

Use `strict_layout` only when the operator explicitly wants placeholder-level conformity to a formal template. In that mode, selected page types, active body fields, and placeholder capacity are a contract.

Follow the template selection hierarchy: explicit user template first, then registered `ppt_template` material, then the bundled template.

## Template Files

- `template_registry.json`
- `artifacts/template_selection.json`
- `artifacts/template_profile.json`
- `artifacts/template_fit_validation.json`
- `artifacts/template_fit_plan.json`

## What To Pass On

Hand Output the selected style/profile guidance, fit plan, and any content-fit warnings QC has accepted or routed. Do not rewrite the page argument, weaken caveats, decide source sufficiency, or repair evidence claims to fit a layout.

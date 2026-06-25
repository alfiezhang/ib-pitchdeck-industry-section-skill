# PPT Visual QC

Use this checklist after generating `industry_section_filled_clean.pptx`.

## Objective

This checklist complements deterministic validation. `pipeline.py validate --artifact filled_ppt` confirms package mechanics; this checklist confirms whether the PPT looks like a finished deck.

## Visual QC Checklist

### 1. Page Message

- Is the page title conclusion-led?
- Is the main takeaway visually and logically aligned with the title?
- Can a reader understand the slide's point within 3-5 seconds?

### 2. Emphasis Hierarchy

- Is there a clearly visible focal point on the page?
- Are the most important numbers or conclusion phrases emphasized?
- Is emphasis restrained, or did the slide become noisy?

### 3. Text Density

- Are bullets short enough to scan?
- Are cards / panels overloaded with prose?
- Does any box feel like pasted research pack text rather than slide-ready copy?

### 4. Comparison / Table Quality

- On comparison slides, do rows read like crisp comparables rather than paragraph fragments?
- Is the target clearly distinguishable from peers?
- Are the comparison dimensions obvious?

### 5. Quantitative Visual Readiness

- If the slide describes a chart, is the chart logic actually traceable from `chart_data` or page notes?
- If the slide is chart-led, does it contain an actual chart / visual object rather than prose describing the intended chart?
- Does the slide's `exhibit` match what is visible on the page?
- Does a chart have at least two comparable datapoints? A single large bar is not a finished exhibit.
- If evidence is limited, did the page use a structured exhibit such as KPI cards, an evidence-boundary grid, an evidence-gap matrix, or caveated table?
- Are the key datapoints visible, or buried in prose?
- Does the slide still feel complete if the visual were presented to a client?

### 6. Project Relevance Without Target Drift

- Does the slide explain the industry point first?
- If project relevance appears, is it short, source-labeled, and secondary?
- Is the slide free of forced target promotion?

### 7. Page-Level Pass / Fail Heuristics

Flag the slide for revision if any of the following are true:

- No obvious focal point
- Missing, invisible, or token-only exhibit
- Chart area contains only one datapoint
- Fewer than three substantive cards/rows/modules on a structured page
- More than two long sentences in one placeholder area
- Important numbers appear without emphasis
- The slide reads like research notes, not a presentation
- The title could fit any company in the sector
- The slide reads like a target profile rather than an industry page
- More than a short note is devoted to target facts on a page whose primary subject is industry
- Scaffold labels such as `PRIMARY CHART`, `POINT 1`, `STANDARD`, or page-type tags remain visible

## Priority Pages

Review these pages especially carefully:

- **Slide 2** — Market Size & Segmentation
- **Slide 6** — Competitive Landscape
  - If `compare_table_page` is selected, it must render as a real PPT table object with 3-6 columns and at least 3 populated peer rows.
  - Table rows should be named peers or peer archetypes. Do not use CR5/CR10, market-structure comments, or target-positioning summary statements as fake peer rows.
  - Each cell should be a compact label, figure, or short judgment. Long explanation belongs in body panels or notes, not inside table cells.
  - If the renderer reports `rendered: false`, the PPT is debug output and must not be treated as final delivery.
- **Slide 8** — Industry Takeaways For The Project

These three pages usually determine whether the section feels industry-led, transaction-aware, and presentation-ready.

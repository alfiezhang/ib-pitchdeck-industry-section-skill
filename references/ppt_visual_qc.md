# PPT Visual QC

Use this checklist after generating `industry_section_filled_clean.pptx`.

## Objective

This checklist complements deterministic validation. `validate_filled_ppt.py` confirms structural correctness; this checklist confirms whether the PPT looks like a finished deck.

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
- Does any box feel like pasted memo text rather than PPT copy?

### 4. Comparison / Table Quality

- On comparison slides, do rows read like crisp comparables rather than paragraph fragments?
- Is the target clearly distinguishable from peers?
- Are the comparison dimensions obvious?

### 5. Quantitative Visual Readiness

- If the slide describes a chart, is the chart logic actually traceable from `chart_data` or page notes?
- If the slide is chart-led, does it contain an actual chart / visual object rather than prose describing the intended chart?
- Are the key datapoints visible, or buried in prose?
- Does the slide still feel complete if the visual were presented to a client?

### 6. Target Linkage

- Does the slide explain why the industry point matters for the target?
- Is the target linkage explicit rather than implied?

### 7. Page-Level Pass / Fail Heuristics

Flag the slide for revision if any of the following are true:

- No obvious focal point
- More than two long sentences in one placeholder area
- Important numbers appear without emphasis
- The slide reads like research notes, not a presentation
- The title could fit any company in the sector
- Scaffold labels such as `PRIMARY CHART`, `POINT 1`, `STANDARD`, or page-type tags remain visible

## Priority Pages

Review these pages especially carefully:

- **Slide 2** — Market Size & Segmentation
- **Slide 6** — Competitive Landscape
- **Slide 8** — Key Takeaways for Target

These three pages usually determine whether the section feels transaction-oriented and presentation-ready.

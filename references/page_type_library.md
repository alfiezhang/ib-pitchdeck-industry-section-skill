# Page Type Library

This library defines the allowed page types for the fixed 8-logical-slide workflow.

## Fixed Page Types

### `summary_page`
Use when the page should synthesize the story in a conclusion-led way.
Best for:
- Slide 1 when the page combines definition, market context, and a few takeaways
- Slide 8 when the page synthesizes why the industry matters for the Target

Typical output behavior:
- strong headline
- one takeaway sentence
- concise supporting text blocks
- no overly dense visual dependency

### `driver_card_page`
Use when the page is best expressed as several discrete drivers or modules.
Best for:
- Slide 3

Typical output behavior:
- 3-4 cards
- each card bundles claim, evidence, and implication

### `value_chain_page`
Use when the page needs a structural diagram with downstream interpretation.
Best for:
- Slide 4

Typical output behavior:
- one dominant structure diagram
- supporting panels for profit pool, barriers, and target positioning

### `moat_page`
Use when the page is about the industry-level barriers, winner capabilities, or value drivers that separate winners from followers. In this skill, `moat_page` does **not** mean a target-only moat page.
Best for:
- Slide 5

Typical output behavior:
- 3 modules
- each module focuses on the industry barrier / value driver, why it matters in the sector, and the Target implication or diligence question
- the Target may appear as evidence of fit, but the primary subject remains the industry barrier / value driver

## Controlled-Choice Page Types

### `chart_page`
Use when one visual can carry the page and the supporting text only needs to interpret it.
Allowed for:
- Slide 2

Use when:
- one market-size or segmentation chart explains most of the page
- the supporting commentary can stay short

Avoid when:
- the page also needs a meaningful side comparison table

### `chart_plus_mini_table_page`
Use when a chart should remain dominant but the reader also needs a compact side-by-side numeric comparison.
Allowed for:
- Slide 2

Use when:
- chart tells the main story
- a small table can add segment details, shares, or supporting datapoints

### `compare_table_page`
Use when the page is best understood through a named peer comparison.
Allowed for:
- Slide 6

Use when:
- competitors can be compared on a few concrete dimensions
- named-player comparison is clearer than abstract positioning

### `matrix_page`
Use when the page is best understood through relative positioning across two key dimensions.
Allowed for:
- Slide 6

Use when:
- the insight is about where players sit in the market rather than a row-by-row fact table
- two axes can clearly explain positioning

### `trend_page`
Use when the page is about a few parallel themes that will shape the future.
Allowed for:
- Slide 7

Use when:
- trends are thematic rather than sequential
- each trend needs evidence and target implication

### `timeline_page`
Use when the sequence and timing of developments is central to the story.
Allowed for:
- Slide 7

Use when:
- time sequencing itself is the point
- the page should show how the industry is likely to evolve over time

## Selection Principle

Upstream memo hints can suggest whether a page is more data-led, compare-led, structure-led, summary-led, or trend-led.
They must not directly choose the final page type.

Final page-type selection belongs to `industry_storyboard.json`.

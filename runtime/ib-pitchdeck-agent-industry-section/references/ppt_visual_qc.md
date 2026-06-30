# PPT Visual QC

Use this after generating the final editable PPT. In structured-render runs this is usually `industry_section_filled_clean.pptx`; in direct-composition runs it may be the PPT named in `LATEST_FINAL_PPT.txt`. Deterministic checks can confirm that the package exists and tokens were handled; this review asks whether the PPT looks finished.

## What A Finished Page Feels Like

The reader should understand the page's point within a few seconds. The headline should carry a conclusion, the main takeaway should support it, and the exhibit should be the visual center of gravity. Important numbers should be visible, not buried in prose.

The slide should look like a presentation page, not pasted research notes. Cards and panels should be compact, differentiated, and aligned with the page's logic. Source notes should be visible enough to support the claims.

Review the rendered deck the same way a banker checks a client send-out: number consistency, data-narrative alignment, language polish, and visual/formatting quality. Text extraction can miss visual failures, so inspect slide images or the PPT itself before final client delivery.

## Exhibit Quality

A chart-led page usually needs a real chart or visual object with comparable datapoints unless it is intentionally a KPI-card page. Mixed-unit data usually belongs in cards or a table. If evidence is limited, use a structured exhibit such as KPI cards, a caveated table, or a source-labeled grid rather than leaving the page visually empty.

For comparison pages, rows should be named peers or peer archetypes, and columns should be crisp dimensions. Long explanations belong in body panels, not table cells. If `compare_table_page` is selected, the rendered PPT should contain a real table object, not prose pretending to be a table.

## Industry-Led Discipline

The industry point should come first. Project relevance can appear, but it should be short, source-labeled, and secondary. If the page reads like a target profile, send it back to the page pack.

## Visual Red Flags

Send the slide back for revision when it has no focal point, a token-only exhibit, a chart with unsupported or non-comparable datapoints, too little structured content to carry the page argument, crowded paragraph-like boxes, missing emphasis on important numbers, generic title language, visible scaffold labels, or target facts dominating an industry page.

Slides that cover segmentation, competitive landscape, and final transaction relevance usually deserve the closest look; weak structure is most visible where the deck connects evidence to the client conversation.

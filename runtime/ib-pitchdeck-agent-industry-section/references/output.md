# Output

## Purpose

Output owns the final editable delivery. Produce the PPT from the current upstream files, which should carry the current judgment and source record; postprocess/check the PPT package, and report the handoff honestly. Deterministic tools are execution support; the output step should never become a place to rewrite evidence, page judgment, or deck copy.

## Rendering Discipline

Produce the PPT only after upstream evidence, page pack, template style, and review signals are ready. If output fails because of malformed exhibit data, sparse visual payload, single-point chart misuse, or unreadable content fit, route the problem to Generation or Template. If upstream inputs are missing, stale, or rejected, report the repair owner instead of creating a shortcut deck.

If the LLM-authored page pack says the section is not ready because evidence is missing, route back to bounded targeted research instead of producing a final deck. Produce a `RESEARCH_LIMITED_REVIEW_` copy only when the operator explicitly asks to inspect layout or editorial direction despite the evidence gap. This prevents evidence limits from becoming an easy stopping point while still allowing controlled review.

Structured-render helpers may record runtime capability notes for traceability. Python search connectors and Python PDF extraction are advisory because the agent may use native web/PDF reading or exact manual sources. Strict runtime readiness should pause only for missing PPT/runtime imports, not the absence of Tavily, DDGS, SearXNG, or a Python PDF parser.

Use the template source selected during intake or template review; if none is selected, use the user-registered template or bundled template. The default output mode is style-guided: preserve the template's page size, fonts, colors, title style, and source-note treatment, while placement follows the LLM-authored page composition. Strict placeholder layout is reserved for explicit operator requests.

Direct PPT composition is a valid output path and often the better choice when a user-supplied template is simple, lightly structured, or mainly communicates house style. Start from a copied PPTX package, duplicate a low-content or blank template page, and create the needed editable text boxes, tables, charts, cards, and shapes from the LLM-authored page pack. Do not create every structured-render intermediate merely because the helper exists. Keep a short note of the chosen output path and run visual/source QC on the final PPT.

Whether using structured rendering or direct composition, start from the selected PPTX package, not from a new blank presentation. Open the template, preserve its theme/master/size, remove demonstration slides, and create each output page from a copied low-content template page or a blank layout inside that same template. The user may provide a simple sample page only to communicate style; do not treat every sample text box, column count, or placeholder as binding unless strict layout is explicitly requested.

Structured rendering treats LLM-authored charts, tables, KPI-card `visible_metric_claims`, and body blocks as visible payloads. Direct composition should preserve the same visible payload discipline. Do not invent `chart_data` or prose blocks just to make a metric-card page render; author the KPI cards and source notes directly.

Before final delivery, scan the actual PPT text for internal working-paper language. Treat the scan as an editorial signal, not a rule-based substitute for judgment: LLM QC decides whether the wording is genuinely client-facing. If repair is needed, repair `banker_page_pack.json` and regenerate the PPT instead of patching final slides by hand.

## Rendered Files

The user-facing output is the editable PPT plus final delivery review records. Internal render JSON may be written for traceability, but it is not an authoring surface and should not be hand-edited to fix content.

## What To Pass On

Hand off only when the deck is ready for final client delivery, or clearly state the upstream role and file that owns the repair.

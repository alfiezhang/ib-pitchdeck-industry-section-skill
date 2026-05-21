# Critical Anti-Patterns

These are the most common failure modes when turning an industry-section draft into a populated pitchbook template.

## Anti-Pattern 1: Treating a Placeholder Box as Final Formatting

What happens:
- A token box or instruction area is treated as the final visual treatment.
- Content is pasted into a visibly temporary area without checking whether it matches the production style.

Why it is wrong:
- Placeholder formatting is a technical container, not a design instruction.
- The output may look mechanically filled rather than client-ready.

Recognition test:
- The slide looks like text was dropped into boxes without regard for hierarchy, spacing, or readability.
- The conclusion line, body boxes, and source footer do not read as separate levels of information.

Correct approach:
- Respect the template's intended roles from `templates/ppt_mapping.json`.
- Keep `slide_title`, `main_takeaway`, body content, chart title, and source footer visually and logically distinct.

## Anti-Pattern 2: Flattening Structured Content into Generic Bullets

What happens:
- Driver cards, barrier modules, value-chain stages, or right/left panels are rewritten into interchangeable bullets.

Why it is wrong:
- It destroys the page logic defined in `layout_intent_by_slide`.
- The slide loses the banker-style structured read and becomes a text dump.

Recognition test:
- Slide 3 no longer reads as distinct drivers.
- Slide 4 no longer separates value chain from profit pool / barriers / target position.
- Slide 6 mixes market facts and target judgment into one section.

Correct approach:
- Preserve content block distinctions from `templates/ppt_copy_mapping.json` and `templates/ppt_mapping.json`.
- Each card or panel should hold one distinct role.

## Anti-Pattern 3: Reusing the Same Sentence Across Multiple Slots

What happens:
- Similar text is copied into several bullets/cards/panels because it fits multiple areas.

Why it is wrong:
- It creates visible redundancy and weakens the slide's logic.
- Adjacent boxes stop adding information.

Recognition test:
- Two or more placeholders on the same slide carry near-identical language.
- The slide reads like paraphrase repetition rather than progressive argument.

Correct approach:
- Ensure each slot contributes a different message.
- Use QC to flag repeated content across adjacent placeholders.

## Anti-Pattern 4: Moving Content Across Roles Because Another Box Has More Space

What happens:
- Target-positioning content gets moved into a market-facts box.
- A takeaway is moved into a body field.
- A source footer is shortened into ambiguity just to fit.

Why it is wrong:
- It breaks the semantic contract between PPT copy and template mapping.
- The slide may still fit, but it becomes structurally wrong.

Recognition test:
- `main_takeaway` sounds like a body bullet.
- `left_panel` contains target implication when it is meant for market facts.
- A placeholder is populated with text from a different mapped role.

Correct approach:
- Follow `layout_binding_by_slide`.
- If a slot overflows, rewrite within the same role rather than shifting content to another role.

## Anti-Pattern 5: Source Footer Degradation

What happens:
- Source footers are omitted, made too vague, or silently dropped during compression.

Why it is wrong:
- Traceability is lost.
- Numeric claims become much harder to defend in review.

Recognition test:
- A slide contains data or market claims but no source footer.
- Footers say only `Source: public information` for load-bearing claims.

Correct approach:
- Keep 2-4 most load-bearing sources.
- Preserve date information when materially relevant.
- Treat missing source footers as a QC issue.

## Anti-Pattern 6: Silent Overflow or Truncation

What happens:
- Text is cut off to fit the box.
- Overflow is ignored because the placeholder was technically replaced.

Why it is wrong:
- The slide becomes visually broken or factually incomplete.
- Silent truncation is especially dangerous for source footers and nuanced conclusions.

Recognition test:
- Text appears incomplete or abruptly cut.
- A long source line or panel clearly exceeds the intended box.

Correct approach:
- Rewrite before replacing.
- Log truncation or compression in QC.
- Escalate if repeated fixes still cannot produce a clean result.

## Anti-Pattern 7: Weak Distinction Between Fact, Inference, and Management View

What happens:
- Unsupported strategic conclusions are written with the same certainty as sourced market facts.

Why it is wrong:
- The deck becomes harder to defend.
- Management hypotheses get presented as market truth.

Recognition test:
- Claims about target advantage or industry structure appear without evidence or attribution.
- The slide tone becomes overly absolute despite weak sourcing.

Correct approach:
- Keep factual claims sourced.
- Keep inference modest.
- Flag management-only claims in QC when support is insufficient.

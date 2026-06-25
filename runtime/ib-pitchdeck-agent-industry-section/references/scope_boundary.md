# Scope Boundary

This skill generates an industry section for a pitchbook used to pitch a potential client before a formal mandate is necessarily won.

This is a pre-mandate pitchbook industry section, not a BP, CIM, sell-side marketing book, or retained-client deliverable. The potential client / target company provides context and an anchor for relevance, but should not be treated as an already-retained client. The primary objective is to demonstrate the advisory team's understanding of the industry and ability to frame transaction-relevant issues. The deck should not attempt to sell, advocate for, or overstate the target's attractiveness.

Sector credibility comes first. Transaction relevance comes second. Explicit target context should be selective, evidence-based, and clearly separated from industry-level conclusions. It is acceptable for a slide to build sector credibility without explicitly mentioning the target.

The purpose is to demonstrate:
1. credible sector understanding;
2. relevance to potential M&A, financing, control-sale, valuation, or investor/acquirer interest angles;
3. selective target context where supported, including potential fit, risks, and evidence boundaries.

This is not:
- a generic industry report;
- a full consulting market-entry study;
- a full company deep dive;
- a valuation report;
- a BP or CIM;
- a retained-client sell-side marketing book that assumes the target is already the client.

The output must preserve the slide structure defined by `configs/slide_registry.json`. The research can be broad and judgment-led, but the delivery format remains governed by the selected template and registry.

## Search Discipline

Use this phase as a boundary-scoping loop, not formal research. Boundary scoping is logged in `broad_discovery` searches to validate working definitions and classification.
Formal evidence generation belongs to `formal_research_execution` and should not be concluded in this phase.

## Three Relevance Levels

Each slide should primarily serve at least one level:

- `sector_credibility`: explain market structure, growth, segmentation, value chain, competition, or trends.
- `transaction_relevance`: explain why the sector setup matters for valuation, buyer interest, consolidation, financing, or timing.
- `target_implication`: selective target context, evidence-backed fit, exposure, or caveated project relevance.
- `mixed`: intentionally combines more than one of the above.

Do not force target mentions on every slide. Do not turn every slide into "industry tailwind benefits the target." Target linkage should be selective, evidence-based, and transaction-relevant.

Across the section, keep the story balanced:
- sector credibility should carry the deck;
- transaction relevance should be visible where it follows from the sector view;
- target context should appear only where evidence supports it;
- the target should not become the central claim of the industry section.

## Claim Strength

Classify important claims as:

- `hard_fact`: directly supported by a cited source; preserve period, geography, scope, and unit.
- `supported_inference`: derived from cited evidence; use cautious inference language.
- `management_claim`: provided by the user/company; label as company-provided unless externally verified.
- `hypothesis`: useful but not proven; treat as a caveated working view or route to Research.

Do not use absolute language for `supported_inference`, `directional_inference`, `management_claim`, `hypothesis`, or `open_question`, including: 确定性, 不可逆, 无放缓迹象, 不可复制, 必然, 绝对领先.

# Content Quality

Use this as editorial guidance for writing or reviewing `banker_page_pack.json`. It is not validator logic. It should help the LLM make stronger page judgments, not turn review into another rule engine.

## Standard

The deck is a pre-mandate industry section. A good page makes an industry point the client can remember, explains the mechanism behind it, shows the evidence, and gives a short transaction readthrough where relevant.

Client-ready pages usually have:

- an industry-led headline with a real point of view;
- a banker judgment that explains mechanism, not just trend direction;
- a visible exhibit that carries the page;
- body blocks that add distinct information rather than repeating the headline;
- EV/MET support where available, with specific source notes;
- caveats when evidence is thin, narrow, or management-provided.

If evidence is thin, keep the page structured and honest. Use caveated cards, a source-boundary table, or a carefully scoped qualitative exhibit. Do not invent numbers or pad with generic copy.

## Evidence And Data

Review whether claim strength matches the evidence. Important visible numbers need audit rows; management-provided target metrics should remain unaudited project context unless externally verified. Source notes should name sources or EV/MET IDs rather than hiding behind "public sources" or "industry reports".

Charts and tables should look like presentation exhibits, not placeholders. Use comparable units on a chart axis. Use cards or tables for mixed-unit data or target-vs-market context. A single data point is usually a KPI card, not a chart. Quantitative exhibits should have source rows for the visible numbers.

When sources conflict, preserve the conflict and show how the working number was chosen. A caveated range is better than false certainty.

## Project Context

Target facts can help the industry view feel relevant, but they should not take over the page. Terms such as `标的`, `目标公司`, `项目公司`, `target`, `GMV`, `净利润`, `控股权`, and `出售` are allowed only when source-labeled and secondary to the industry argument.

Watch for target drift:

- every trend ends by saying it benefits the target;
- the headline is about the target on a page whose subject is industry;
- `project_relevance_note` becomes a sales paragraph;
- target superiority appears without peer or market evidence;
- target metrics are treated like audited industry data.

`project_relevance_note` should be one short bridge from industry finding to pre-mandate discussion. It is not an execution plan.

For consumer brand or product-category pitches, management-provided GMV, net profit, unit sales, rankings, repeat purchase, gross margin, channel mix, traffic cost, creator network, or ROI metrics are project context unless independently verified. Do not place those figures in industry charts, peer rankings, or headline proof points. Use cards or a clearly labeled context table when the figures are useful for relevance, and keep the industry evidence visually separate.

## Language Quality

Replace generic source phrases such as `public sources`, `industry reports`, `公开资料`, `行业报告`, or `多方来源` with named sources, EV/MET IDs, or an explicit evidence boundary.

Replace generic market language such as `rapidly growing`, `large market potential`, `competitive market`, `市场空间广阔`, `发展迅速`, `政策利好`, and `行业领先` with market mechanisms, comparable benchmarks, source-backed data, or a clear caveat.

Be careful with hard overclaims such as `certainty`, `guaranteed`, `irreversible`, `确定性`, `不可逆`, `绝对领先`, `唯一`, and `必然受益`. They require strong evidence and careful caveating.

## Slide Distinctness

Slides should build the argument rather than recycle it. Slide 3 is about current growth drivers; Slide 7 is about future evolution. Slide 4 is value chain and profit pool; Slide 5 is barriers and winner capabilities. Slide 1 establishes industry attractiveness; Slide 8 synthesizes transaction relevance and evidence boundaries.

Slide 2 should add a second-layer structural view rather than repeat Slide 1. Slide 6 should explain the competitive landscape, not simply prove target differentiation.

The standard slide roles are editorial prompts, not mandatory pages. A stronger five- or six-page section is better than a thin eight-page section. If a role lacks enough evidence or would duplicate another page, merge it or omit it and explain the decision in the page pack.

## Review Disposition

For a quality issue, choose the honest route: accept with caveat, repair the page pack, repair the evidence DB, send a bounded research request, or mark the run evidence-limited. Do not patch derived renderer artifacts or the PPT to hide a content-quality problem.

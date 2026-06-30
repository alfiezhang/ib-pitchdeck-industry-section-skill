# Content Quality

Use this as editorial guidance for writing or reviewing `banker_page_pack.json`. It is not a rule checklist. It should help the LLM make stronger page judgments, not turn review into another rule engine.

## Standard

The deck is a pre-mandate industry section. A good page makes an industry point the client can remember, explains the mechanism behind it, shows the evidence, and gives a short transaction relevance bridge where useful.

Strong pages earn trust through a practical mix of:

- an industry-led headline with a real point of view;
- banker judgment that explains mechanism, not just trend direction;
- a visible exhibit that carries the page;
- body blocks that add distinct information rather than repeating the headline;
- EV/MET support where available, with specific source notes;
- caveats when evidence is thin, narrow, or management-provided.

Do not force every page to contain every element. Use this as an editorial standard for whether the page feels credible, dense, and client-facing.

If evidence is thin, keep the page structured and honest. Use caveated cards, a source-labeled table, or a carefully scoped qualitative exhibit. Do not invent numbers or pad with generic copy.

## Evidence And Data

Review whether the page's assertiveness matches the evidence. Important visible numbers need audit rows; management-provided target metrics should remain unaudited project context unless externally verified. Source notes should name sources or EV/MET IDs rather than hiding behind "public sources" or "industry reports".

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

Replace generic source phrases such as `public sources`, `industry reports`, `公开资料`, `行业报告`, or `多方来源` with named sources, EV/MET IDs, or a specific limitation.

Replace generic market language such as `rapidly growing`, `large market potential`, `competitive market`, `市场空间广阔`, `发展迅速`, `政策利好`, and `行业领先` with market mechanisms, comparable benchmarks, source-backed data, or a clear caveat.

Be careful with hard overclaims such as `certainty`, `guaranteed`, `irreversible`, `确定性`, `不可逆`, `绝对领先`, `唯一`, and `必然受益`. They require strong evidence and careful caveating.

Review the visible slide language separately from the JSON authoring logic. A client-facing slide should not expose scoping labels, research workflow labels, internal deck-use labels, or instructions about how the page was built. If a sentence sounds like an analyst note to self, rewrite it into banker presentation language before rendering.

Market-boundary discipline should be visible through clean framing and precise source labels, not through workflow vocabulary. Say what the evidence supports for the market, channel, peer set, or transaction relevance; do not narrate the internal research process.

Avoid client-visible labels that make the page sound like an internal workpaper. A pre-mandate pitchbook should show judgment and commercial relevance, not expose the workflow used to reach it.

For Chinese pitchbooks, flag visible wording that names internal scoping slots, review tasks, buyer-question buckets, proof choreography, or process workstreams. Those ideas may belong in notes or research files, but the slide should say the category, source limitation, transaction relevance, or commercial meaning directly.

When a visible Chinese page uses scope-card slot labels, review-task phrasing, evidence-use labels, or process-status language, translate the intent into client-facing banker language such as `面部底妆兼具肤质适配、复购和内容种草属性`, `以面部彩妆视角更能解释品牌增长、渠道竞争和交易叙事`, `平台数据可支持渠道趋势判断但不等同于全市场规模`, or `品类结构与渠道效率共同支撑控股权出售沟通的行业逻辑`.

Treat visible wording as internal workpaper language when it names the team's market-definition slots, review tasks, evidence-use labels, process status, or delivery readiness instead of making a market point. Do not merely delete the sentence; translate the underlying idea into a market point, transaction relevance, source caveat, or a bounded research request outside the client deck.

For a pre-mandate pitch, avoid language that sounds like the bank is explaining its own process to the client. Use commercial phrasing such as `面部底妆的肤质适配和内容传播属性更能解释品牌增长质量` or `面部彩妆视角更贴近品牌收入来源、渠道竞争和交易叙事`.

Avoid visible headings that name unresolved tasks, investigation workstreams, buyer-question buckets, internal market-definition slots, or evidence-status labels. They tell the client how the work was produced rather than what the market means. If the idea matters, rewrite it as a source caveat, category framing, transaction relevance bridge, or off-slide targeted research request.

## Slide Distinctness

Slides should build the argument rather than recycle it. Each page should have a distinct job: market attractiveness, structural drilldown, growth mechanism, value chain / profit pool, barriers, competitive landscape, future evolution, or transaction relevance. Use only the jobs that the evidence and pitch need.

If you use the bundled standard arc, keep the roles distinct instead of repeating the same point across pages. If you use fewer pages or a different arc, preserve the same discipline: no page should exist only because a standard role exists.

Standard slide roles are editorial prompts, not mandatory pages. A stronger focused section is better than a thin default-length section. If a role lacks enough evidence or would duplicate another page, merge it or omit it and explain the decision in the page pack.

## Review Disposition

For a quality issue, choose the honest action: accept with caveat, repair the page pack, repair the evidence DB, or send a bounded research request. Create a research-limited review copy only after the targeted research loop cap or when the missing evidence is not realistically obtainable. Do not patch helper render files or the PPT to hide a content-quality problem.

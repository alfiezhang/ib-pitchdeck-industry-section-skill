# Content Quality

Use this file for LLM authoring and LLM QC of `banker_page_pack.json`.
It is not a deterministic validator input. Do not turn these review prompts
into Python gates.

## Review Standard

The deck is a pre-mandate industry section. It should show industry
understanding first, transaction relevance second, and only selective
project context where it clarifies the industry view.

Each client-ready page should have:

- a clear industry-led headline, not a topic label;
- a banker judgment with mechanism, evidence, and implication;
- a visible exhibit that carries the page;
- multiple substantive body blocks;
- traceable EV/MET references where available;
- specific source notes, not generic source phrases;
- caveats where evidence is thin or source scope is narrow.

Density targets are editorial prompts, not hard limits. A full page normally
needs several body blocks, visible evidence, and enough chart/table/card
structure to avoid looking empty. If evidence is too thin, mark the page
evidence-limited instead of inventing numbers or padding with generic copy.

## Evidence And Data Checks

LLM QC should review:

- whether the page has enough EV/MET support for its claim strength;
- whether important numbers have key data audit rows;
- whether management-provided target metrics are labeled as unaudited project context;
- whether project-specific metrics are kept out of industry charts unless clearly labeled;
- whether source notes name sources or EV/MET IDs rather than saying "public sources";
- whether conflicting market numbers are reconciled or caveated.

Charts and tables need professional structure:

- avoid mixing incomparable units on one axis;
- avoid single-point charts unless the visual is clearly a KPI card;
- use cards/tables for mixed units or target-vs-market context;
- keep chart titles presentation-ready, not execution notes;
- include source rows for visible quantitative exhibits.

## Target Context Discipline

Watch for target drift. Terms such as `标的`, `目标公司`, `项目公司`,
`target`, `GMV`, `净利润`, `控股权`, and `出售` are not forbidden, but they
should not make an industry page read like a target profile.

Red flags:

- every driver or trend ends with "利好标的";
- headline frames the target as the main subject on an industry page;
- project relevance note becomes a target promotion paragraph;
- target superiority is asserted without external benchmark evidence;
- target metrics are used as if they were audited industry metrics.

Use `project_relevance_note` sparingly. It is a bridge from industry finding
to pre-mandate discussion, not a diligence list and not a sales paragraph.

## Generic Copy To Rewrite

Rewrite generic source phrases such as:

- `industry reports`, `public sources`, `market research`, `various sources`;
- `公开资料`, `行业报告`, `公开行业资料`, `多方来源`.

Rewrite generic market copy such as:

- `rapidly growing`, `large market potential`, `competitive market`;
- `市场空间广阔`, `发展迅速`, `政策利好`, `行业领先`.

Replace them with source-specific evidence, market mechanisms, comparable
benchmarks, or an explicit evidence boundary.

Avoid hard overclaims unless source-backed and carefully caveated:

- `certainty`, `guaranteed`, `irreversible`, `impossible to replicate`;
- `确定性`, `不可逆`, `绝对领先`, `唯一`, `必然受益`.

Treat phrases such as `稀缺标的`, `制高点`, `均利好`, `天然契合`,
`出售窗口`, and `稀缺平台` as caution phrases requiring evidence and careful
transaction framing.

## Cross-Slide Distinctness

- Slide 3 explains current growth drivers; Slide 7 explains future industry
  evolution. Do not reuse the same driver cards as trends.
- Slide 4 covers value chain / profit pool; Slide 5 covers entry barriers /
  winner capabilities. Do not repeat channel or brand wording as the main
  point on both slides.
- Slide 1 establishes industry attractiveness; Slide 8 synthesizes
  transaction relevance and evidence boundaries. Do not reuse the same
  market-size thesis as the transaction conclusion.

## Slide-Specific Review

- Slide 2: market size and segmentation. Use one clear segmentation axis.
  Avoid a grab-bag mixing channel, category, and price band.
- Slide 3: industry growth drivers. Cards should explain demand, consumer,
  channel, product, or structural mechanisms before any target relevance.
- Slide 4: value chain and profit pool. Keep the page industry-first; project
  relevance is secondary.
- Slide 5: industry barriers and value drivers. Do not make it a target-only
  moat page.
- Slide 6: competitive landscape and peer segmentation. Do not design the page
  only to prove target differentiation.
- Slide 7: industry trends and future evolution. Avoid blanket "all trends
  benefit target" or sale-window conclusions without evidence.
- Slide 8: transaction read-through, project relevance, and evidence
  boundaries. Include at least one evidence-boundary, caveat, or risk note
  framed as professional judgment, not as an unresolved task checklist.

## QC Disposition

For every quality issue, decide one of:

- accepted with caveat;
- repair in `banker_page_pack.json`;
- repair in `research_evidence_db.json`;
- send a focused research request;
- mark evidence-limited and stop formal client-ready rendering.

Do not patch derived artifacts or the rendered PPT to hide a content-quality
problem.

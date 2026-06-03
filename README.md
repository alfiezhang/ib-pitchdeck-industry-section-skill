# IB Pitchdeck Industry Section Skill

这是一个用于生成投行 pitchbook 行业章节的 AI skill。

你可以把它理解成一套“行业章节生产流程”：用户给一个项目 brief，AI 先做行业研究，再整理研究备忘录，然后设计 8 页行业章节的 storyline，最后把内容填入固定 PowerPoint 模板，生成一份可继续修改的 PPTX。

这个项目不是通用 PPT 生成器，也不是简单的模板填空工具。它更关注三件事：

- 行业研究有没有来源
- 章节故事线是否服务于具体交易
- PPT 是否能落到固定模板里，而不是生成一堆无法交付的文字

目前支持中文和英文输出，但主要按中文投行材料的使用场景调过。

## 这个 Skill 能做什么

给定一个标的公司或交易 brief，它会引导 AI 完成：

1. 忠实转录用户输入，生成 `input_card.json`
2. 制定 research plan，并记录 search log
3. 做 mandatory web research
4. 写一份有来源、有 Evidence ID 的 `industry_input_memo.md`
5. 为 8 页 PPT 设计 storyline 和页面结构，生成 `industry_storyboard.json`
6. 校验来源、版式、字段、标题长度、正文密度
7. 填入内置 PPT 模板
8. 输出最终 clean PPTX 和验证报告

最终目标是一组面向交易的 8 页行业章节，而不是泛泛的行业研究报告。

## 目录结构

```text
.
├── SKILL.md                         # 给 AI agent 看的主工作流说明
├── assets/
│   └── industry_section_template_master.pptx
├── prompts/                         # storyboard / PPT copy prompt
├── references/                      # memo 模板、研究规则、格式规则
├── scripts/                         # runtime、校验、PPT 填充、后处理脚本
├── skills/                          # research memo / storyboard / fill-ppt 子 skill
├── templates/                       # schema、mapping、layout budget、source registry
├── setup.sh                         # runtime bootstrap wrapper
└── run_pipeline.sh                  # PPT 生成主流水线
```

`README.md` 是给人看的。  
`SKILL.md` 是给 AI agent 执行任务时看的。

如果你把这个目录安装到 Codex、WorkBuddy、OpenClaw 或类似 agent 的 skills 目录里，agent 应该优先读取 `SKILL.md`，而不是把 README 当成执行手册。

## 环境要求

推荐：

- Python 3.9-3.11
- 可联网搜索
- 可安装 Python 依赖

核心 Python 依赖包括：

- `python-pptx`
- `lxml`
- fallback web search 相关包

不建议手动乱切 Python 环境。项目内置了 runtime bootstrap：

```bash
python3 scripts/bootstrap_runtime.py
python3 scripts/doctor_runtime.py
```

如果想获得本次应该使用的 Python 路径：

```bash
PYTHON_CMD="$(python3 scripts/bootstrap_runtime.py --print-python)"
```

不要在运行任务时修改 skill 源码来绕过错误；如果 runtime 或 validator 报错，应先修复
运行环境或输入文件。PPT 生成建议统一走 `run_pipeline.sh`，不要调用旧脚本名或自己拼接
不存在的脚本。

在 macOS 上，如果 Python 3.13/3.14 遇到 `lxml` 或 code signing 问题，建议换成 Python 3.9-3.11。

## 快速开始

通常这个 skill 不是让人手动一步步填 JSON，而是让 AI agent 按 `SKILL.md` 执行。

如果你已经有一个合法的 `industry_storyboard.json`，可以直接运行 PPT pipeline：

```bash
./run_pipeline.sh \
  --work-root /path/to/workspace \
  --case-name "project-or-target-name" \
  --storyboard /path/to/workspace/industry_storyboard.json
```

`--work-root` 应该传工作区根目录，例如 `/path/to/workspace`，不要传
`/path/to/workspace/runs`，否则会造成 `runs/runs/...` 嵌套。

输出会写到：

```text
/path/to/workspace/runs/<case_slug>/attempt_<timestamp>/
```

默认每次正式运行都会新建一个 `attempt_<timestamp>`，避免新旧任务混入同一个目录。
如果你是在继续修复上一轮结果，可以显式传 `--resume-active`，或直接传
`--output-dir /path/to/workspace/runs/<case_slug>/<attempt_name>`。

如果不传 `--case-name`，pipeline 会尽量从 `input_card.json` 或
`industry_storyboard.json` 推断项目名；推断失败时会放到
`runs/case_unspecified/`。在 WorkBuddy 这类共享工作目录里，建议总是传
`--case-name`，避免不同项目混在同一个 `runs` 目录下。

`run_pipeline.sh` 会在生成 PPT 前运行研究计划、memo、storyboard、内容质量和
`pre_ppt` 阶段门禁。缺少 `research_plan_validation.json`、`memo_validation.json`
或存在无法回溯的 MET-ID 时，pipeline 会停止；这类输出只能作为 debug draft，不能当
final PPT 交付。

如果显式使用 debug bypass，输出只能是 `industry_section_debug.pptx`，不会写作正式的
`industry_section_filled_clean.pptx`，也不会更新 final 指针。

最终 PPT 路径会写入：

```text
/path/to/workspace/runs/<case_slug>/LATEST_FINAL_PPT.txt
```

## 推荐工作流

### 1. Input Card

先把用户 brief 转成 `input_card.json`。

原则是：**只转录，不脑补**。

不要在这一步自动补充：

- peer set
- 投资亮点
- 风险点
- preferred source websites
- must-cover topics

这些都应该在 research plan 或 memo 阶段通过研究得出，而不是在 input card 阶段靠模型预训练知识补出来。

### 2. Research Plan 和 Search Log

在研究前创建：

```text
artifacts/research_plan.json
artifacts/search_log.md
```

先做 broad discovery，理解行业边界、关键词、常用指标、潜在权威来源，再做 targeted validation。

项目内有 `templates/source_registry.json`，里面放了一些默认 source packs 和优先网站。它是菜单，不是每次都全部搜索。

### 3. Research Memo

生成：

```text
industry_input_memo.md
```

memo 是后续所有事实的唯一来源。Storyboard 和 PPT 阶段不应该再新增事实。

memo 里最重要的是：

- Evidence Ledger：每个重要事实有 `EV-001`、`EV-002` 这样的 ID
- Page Evidence Pack：每一页至少准备 3 条论据
- Key Data Points：保留数字、口径、时间、地域、来源
- Chart-ready Data：如果后续要画图，保留 categories、values、unit、source rows

这一步是为了避免 PPT 内容单薄。不要等到最后 PPT 阶段再临时扩写。

### 4. Storyboard

生成：

```text
industry_storyboard.json
```

这一阶段负责：

- 设计 8 页 storyline
- 选择每页 page type
- 写标题、副标题、正文 bullet
- 引用 Evidence IDs
- 说明 target relevance

Storyboard 是最核心的 LLM 推理产物。

第 1 页默认不再只是三张指标卡。如果 memo 有可比的市场趋势、benchmark
或结构拆分数据，应选择 `industry_overview_dynamic_page`。该模式保留左侧
`KEY MESSAGES` 三条信息，只把右侧 `CHART / VISUAL` 区替换为真实图表。
只有在数据不可比、证据冲突或没有 chart-ready 数据时，才退回 `summary_page`。

### 5. Validation

主要验证包括：

```bash
"$PYTHON_CMD" scripts/validate_input_card.py \
  --input-card input_card.json \
  --output artifacts/input_card_validation.json

"$PYTHON_CMD" scripts/validate_research_plan.py \
  --plan artifacts/research_plan.json \
  --source-registry templates/source_registry.json \
  --stage formal \
  --output artifacts/research_plan_validation.json

"$PYTHON_CMD" scripts/validate_memo.py \
  --memo industry_input_memo.md \
  --run-dir . \
  --output artifacts/memo_validation.json

"$PYTHON_CMD" scripts/validate_storyboard.py \
  --storyboard industry_storyboard.json \
  --schema templates/storyboard_schema.json \
  --text-fit-rules templates/text_fit_rules.json \
  --output artifacts/storyboard_validation.json

"$PYTHON_CMD" scripts/validate_content_quality.py \
  --storyboard industry_storyboard.json \
  --memo industry_input_memo.md \
  --rules templates/content_quality_rules.json \
  --output artifacts/content_quality_validation.json
```

这些校验不是形式检查，核心会拦住几类高风险问题：

- `input_card.json` 只能忠实转录用户提供的信息，不能自动拆出投资亮点、peer set、风险点或研究方向
- research plan 必须包含面向当前时间点的 `latest_query`，不能把用户材料里的历史年份当成最新行业口径
- storyboard 的 `body_copy` 只能包含当前 active layout 会实际使用的字段，多余字段会报错
- 正文需要像 PPT bullet，而不是 memo 段落；过长 bullet 会要求压缩或拆分
- 每页正文需要有证据、指标或机制论证支撑，避免只有空泛标签
- slide-bound 数字必须先进入 memo 的 `Metric Reconciliation`，可见数字还需要 `visible_metric_claims` 绑定
- CAGR 必须能用两个明确的起止 MET-ID 复算，不能靠默认年限或不可比口径硬算
- 第 1 页有可靠 chart-ready 数据却退回纯指标卡，会被提示优先使用动态行业概览页
- 第 6 页 `compare_table_page` 必须是真实同业对比表，不接受 CR5/结构判断冒充 peer rows
- 标题、副标题、来源、图表数据、跨页指标一致性和真实 PPT 表格对象会进入质量检查

### 6. PPT 生成

最终 PPT 由脚本确定性生成。不要手写 `replacement_dict.json`。

```bash
./run_pipeline.sh \
  --work-root /path/to/workspace \
  --case-name "project-or-target-name" \
  --storyboard /path/to/workspace/industry_storyboard.json
```

成功后会生成：

```text
industry_section_filled.pptx
industry_section_filled_clean.pptx
filled_ppt_validation.json
artifacts/stage_gate_pre_ppt_validation.json
artifacts/final_delivery_validation.json
artifacts/run_quality_summary.md
```

## 当前 PPT 模板

目前只支持内置固定模板。

逻辑上是 8 页行业章节，但 PPT 模板里有多个 physical slides，因为部分页面有可选版式。

当前可选版式包括：

- 第 2 页：市场规模 / 细分图表页
- 第 3 页：4-card / 5-card / 6-card 行业驱动页
- 第 6 页：竞争对比表 / 定位矩阵页
- 第 7 页：3-card / 4-card / 5-card / 6-card 趋势页，或 timeline 页

填充完成后，未选中的 physical slides 会被删除，最终交付仍是 8 页 PPT。

## 当前局限性

这个项目现阶段是有意收敛的，不是无限自由生成。

主要限制：

- **只认可固定模板**：当前 pipeline 依赖内置 PPT 模板和占位符 token
- **固定 8 页结构**：行业章节结构暂时固定
- **不是通用 PPT agent**：AI 可以在支持的 page variants 中选择，但不能自由新建任意版式
- **模板变化需要同步配置**：如果改 PPT token、页数、版式，需要同步更新 mapping、schema、layout library 和 validators
- **研究质量决定输出质量**：validator 可以降低风险，但不能替代专业判断
- **不是尽调结论**：输出是 pitchbook draft，不应直接视为 diligence-grade advice
- **validator 不是完美审稿人**：它能抓结构、来源、版式和部分内容问题，但仍需要人工 review

## 成功运行后应该看到什么

一个完整 run 通常包括：

```text
input_card.json
industry_input_memo.md
industry_storyboard.json
industry_section_ppt_copy.json
replacement_dict.json
industry_section_filled.pptx
industry_section_filled_clean.pptx
filled_ppt_validation.json
artifacts/
  research_plan.json
  search_log.md
  memo_validation.json
  storyboard_validation.json
  content_quality_validation.json
  final_delivery_validation.json
  run_quality_summary.md
```

最终 PPT 只有在以下条件满足时才应该交付：

- `filled_ppt_validation.json` 通过
- `artifacts/final_delivery_validation.json` 通过
- `runs/<case_slug>/LATEST_FINAL_PPT.txt` 指向最终 clean PPTX

## 修改模板时要注意

如果你改了 `assets/industry_section_template_master.pptx`，需要检查 token 和 mapping 是否一致：

```bash
"$PYTHON_CMD" scripts/check_template_tokens.py \
  --template assets/industry_section_template_master.pptx \
  --ppt-mapping templates/ppt_mapping.json \
  --output artifacts/template_token_check.json \
  --fail-on-diff
```

通常还需要同步更新：

- `templates/ppt_mapping.json`
- `templates/slide_layout_library.json`
- `templates/text_fit_rules.json`
- `templates/page_type_rules.json`
- `templates/storyboard_schema.json`
- 相关 validators

## License

当前还没有指定开源 license。除非仓库所有者另行声明，不应默认假设可以自由复用、分发或商用。

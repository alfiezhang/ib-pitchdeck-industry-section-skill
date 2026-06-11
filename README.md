# IB Pitchdeck Agent - Industry Section

## 中文

一个面向 **pre-mandate client pitch** 场景的投行行业章节 agent plugin。

它的目标不是快速拼出一份通用 PPT，而是在客户资料有限的情况下，帮助 agent 先完成行业边界校准、公开资料补证、证据沉淀、投行判断和页面论点设计，再把内容确定性渲染成 pitchbook 行业章节。

### 适用场景

- 潜在客户 pitch 前的行业章节
- 只有几句话、网页链接、PDF、PPT、Excel 或项目线索的早期项目
- 需要展示“我们理解行业、理解标的赛道、理解交易机会、理解买方视角”的材料
- 需要把用户提供的优质行业报告、公开网页和搜索结果纳入同一套证据链

不适用于：

- CIM、Teaser、DD 清单或已签约顾问工作计划
- 普通行业研究报告
- 不需要证据链、只想快速美化 PPT 的任务
- 依赖未披露内部资料或未经验证假设的客户宣传材料

### 核心工作流

```text
用户材料 / 链接 / 指令
→ Engagement Policy
→ Material Intake
→ Knowledge Repository
→ Industry Scoping + Boundary Validation Loop
→ Research / External Evidence Loop
→ Reasoning / Issue Analysis / Page Arguments
→ Generation / Deck Blueprint
→ Template Profile / Template Fit
→ Deterministic PPT Output
→ QC / Final Delivery Validation
```

核心原则：

- 先定义行业边界，再做行业研究
- Knowledge Layer 只沉淀事实和来源，不主动搜索、不做最终判断
- Research Layer 只补公开资料，不把搜索计划当成证据
- Reasoning Layer 才形成 supported judgment、hypothesis 和 page argument
- Generation Layer 先生成页面论点和 slide draft，最后才进入模板适配
- QC Engine 横向检查事实、边界、研究、判断、页面和模板适配

### Plugin Package

仓库根目录用于开发、测试和发布。可安装的 plugin package 位于：

```text
runtime/ib-pitchdeck-agent-industry-section/
```

包结构：

```text
runtime/ib-pitchdeck-agent-industry-section/
├── .codex-plugin/plugin.json
├── .claude-plugin/plugin.json
├── .codebuddy-plugin/plugin.json
├── agents/
│   └── ib-pitchdeck-agent-industry-section.md
├── skills/
│   ├── material-intake/
│   ├── knowledge-repository/
│   ├── industry-scoping/
│   ├── research-external-evidence/
│   ├── reasoning/
│   ├── generation/
│   ├── template/
│   ├── qc/
│   └── output/
├── scripts/
├── templates/
├── references/
├── assets/
├── requirements.txt
├── setup.sh
└── run_pipeline.sh
```

`agents/ib-pitchdeck-agent-industry-section.md` 是主 agent / orchestrator。`skills/` 下的目录是角色模块，不是彼此独立的产品入口。

### 安装方式

将 `runtime/ib-pitchdeck-agent-industry-section/` 注册为宿主 agent 的 plugin source。

不同宿主对 plugin 的安装入口不同；本仓库在 runtime package 中提供了 Codex、Claude 和 WorkBuddy/CodeBuddy 风格的 manifest。若某个平台只支持 legacy skills，可从 runtime package 生成兼容导出，但主发布形态是 plugin package。

### 输入与输出

输入可以是：

- 简短项目背景
- PDF、PPT、Excel、网页链接
- 用户精选行业报告
- PPT 模板或母版
- 公开资料来源或搜索线索

输出包括：

- `industry_section.pptx` 或等价的最终 PPT
- research evidence database / generated research pack
- issue analysis
- deck blueprint
- page evidence contract
- renderer spec
- QC / final delivery validation report

### 研究与证据

正式研究默认优先使用宿主 agent 自带的 Web Search。脚本层的 fallback provider 由 `templates/source_registry.json` 控制，当前顺序为：

```text
SearXNG → DuckDuckGo → Tavily
```

`SEARXNG_BASE_URL`、`ddgs` 和 `tavily-python` 都是可选扩展能力。没有网络或搜索 provider 时，可以使用用户提供的离线资料，但仍必须完成 source review、source archive 和 evidence trace；未执行的搜索计划不能作为证据。

### 开发者校验

开发、打包或排查 runtime 依赖时，可在仓库根目录运行：

```bash
cd runtime/ib-pitchdeck-agent-industry-section
PYTHON_CMD="$(bash setup.sh --print-python)"
"$PYTHON_CMD" scripts/check_runtime_dependencies.py
```

回归测试从仓库根目录运行：

```bash
PYTHON_CMD=python3 bash tests/run_smoke_tests.sh
PYTHON_CMD=python3 bash tests/run_contract_tests.sh
python3 -m pytest -q
```

建议使用 Python 3.9-3.11，尤其是在本地渲染 PPT 时。

### 打包

发布或分发时，只打包：

```text
runtime/ib-pitchdeck-agent-industry-section/
```

仓库根目录的 `tests/`、`docs/`、`dist/`、缓存文件和历史 run outputs 不属于 runtime package。

---

## English

An investment-banking industry-section agent plugin for **pre-mandate client pitch** work.

It is not a generic PPT generator. The plugin is designed to help an agent turn limited target materials and public evidence into a source-disciplined pitchbook industry section: define the industry boundary, collect and review evidence, form banker judgments, design page arguments, fit the content to a template, and render the final PPT deterministically.

### Use Cases

- Industry sections for pre-mandate client pitches
- Early-stage target situations with only a short brief, URL, PDF, PPT, Excel file, or project lead
- Materials that need to show sector understanding, target relevance, transaction opportunity, and likely buyer perspective
- Workflows that combine user-curated industry reports, public web sources, and search results into one evidence chain

Not intended for:

- CIMs, teasers, diligence request lists, or retained-client work plans
- Standalone generic industry reports
- Quick PPT beautification without evidence discipline
- Client promotion built on undisclosed internal data or unsupported assumptions

### Workflow

```text
user materials / links / instructions
→ Engagement Policy
→ Material Intake
→ Knowledge Repository
→ Industry Scoping + Boundary Validation Loop
→ Research / External Evidence Loop
→ Reasoning / Issue Analysis / Page Arguments
→ Generation / Deck Blueprint
→ Template Profile / Template Fit
→ Deterministic PPT Output
→ QC / Final Delivery Validation
```

Operating principles:

- Define the industry boundary before industry research.
- The Knowledge Layer stores facts and sources; it does not search or make final judgments.
- The Research Layer gathers public evidence; planned searches are not evidence.
- The Reasoning Layer forms supported judgments, hypotheses, and page arguments.
- The Generation Layer creates page arguments and slide drafts before template fitting.
- The QC Engine checks facts, boundaries, research quality, reasoning, page quality, and template fit.

### Plugin Package

The repository root is for development, testing, and release packaging. The installable plugin package is:

```text
runtime/ib-pitchdeck-agent-industry-section/
```

Package layout:

```text
runtime/ib-pitchdeck-agent-industry-section/
├── .codex-plugin/plugin.json
├── .claude-plugin/plugin.json
├── .codebuddy-plugin/plugin.json
├── agents/
│   └── ib-pitchdeck-agent-industry-section.md
├── skills/
│   ├── material-intake/
│   ├── knowledge-repository/
│   ├── industry-scoping/
│   ├── research-external-evidence/
│   ├── reasoning/
│   ├── generation/
│   ├── template/
│   ├── qc/
│   └── output/
├── scripts/
├── templates/
├── references/
├── assets/
├── requirements.txt
├── setup.sh
└── run_pipeline.sh
```

`agents/ib-pitchdeck-agent-industry-section.md` is the main agent / orchestrator. The folders under `skills/` are role modules, not separate product entrypoints.

### Installation

Register `runtime/ib-pitchdeck-agent-industry-section/` as the plugin source in the host agent.

Different hosts expose plugin installation differently. This runtime package includes Codex-, Claude-, and WorkBuddy/CodeBuddy-style manifests. If a platform only supports legacy skills, generate a compatibility export from the runtime package; the primary distribution format is the plugin package.

### Inputs And Outputs

Inputs may include:

- short target briefs
- PDFs, PPTs, Excel files, and web links
- user-curated industry reports
- PPT templates or master decks
- public-source leads and search prompts

Outputs include:

- `industry_section.pptx` or an equivalent final PPT
- research evidence database / generated research pack
- issue analysis
- deck blueprint
- page evidence contract
- renderer spec
- QC / final delivery validation report

### Research And Evidence

Formal research should prefer the host agent's native Web Search. Script-level fallback providers are controlled by `templates/source_registry.json`; the current order is:

```text
SearXNG → DuckDuckGo → Tavily
```

`SEARXNG_BASE_URL`, `ddgs`, and `tavily-python` are optional runtime extensions. If network search is unavailable, user-provided offline sources can be used, but they still need source review, archiving, and evidence traceability. Unexecuted search plans cannot be treated as evidence.

### Developer Verification

For development, packaging, or runtime diagnostics:

```bash
cd runtime/ib-pitchdeck-agent-industry-section
PYTHON_CMD="$(bash setup.sh --print-python)"
"$PYTHON_CMD" scripts/check_runtime_dependencies.py
```

Run regression checks from the repository root:

```bash
PYTHON_CMD=python3 bash tests/run_smoke_tests.sh
PYTHON_CMD=python3 bash tests/run_contract_tests.sh
python3 -m pytest -q
```

Python 3.9-3.11 is recommended, especially for local PPT rendering.

### Packaging

Release packages should contain only:

```text
runtime/ib-pitchdeck-agent-industry-section/
```

Repository-level `tests/`, `docs/`, `dist/`, cache files, and historical run outputs are not part of the runtime package.

Build and validate a clean zip from the repository root:

```bash
python3 runtime/ib-pitchdeck-agent-industry-section/scripts/package_plugin.py \
  --output dist/ib-pitchdeck-agent-industry-section.zip

python3 runtime/ib-pitchdeck-agent-industry-section/scripts/validate_plugin_package.py \
  --package dist/ib-pitchdeck-agent-industry-section.zip
```

The package validator blocks `docs/`, `tests/`, `__pycache__`, `.DS_Store`, and
other cache/build artifacts. The packager filters those files when creating the
zip; a raw runtime directory may fail validation if local caches are present.

Install locally to a host plugin source:

```bash
python3 runtime/ib-pitchdeck-agent-industry-section/scripts/install_plugin_local.py \
  --source dist/ib-pitchdeck-agent-industry-section.zip \
  --host codex
```

Supported `--host` values are `codex`, `claude`, `codebuddy`, and `workbuddy`.
This installs to the host plugin source, not to legacy standalone skills.

Audit old standalone skill installs without deleting anything:

```bash
python3 runtime/ib-pitchdeck-agent-industry-section/scripts/audit_legacy_installs.py \
  --output runtime/ib-pitchdeck-agent-industry-section/artifacts/legacy_install_audit.json
```

Removal is intentionally separate and dry-run by default. Only run it with
`--execute --confirm REMOVE_LEGACY_INSTALLS` after confirming no local host still
depends on the old standalone skill copies.

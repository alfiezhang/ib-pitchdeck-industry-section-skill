# IB Pitchdeck Agent - Industry Section

## 中文

这是一个用于生成投行 pitchbook 行业章节的 AI plugin。它面向 pre-mandate pitch 场景：在尚未正式拿下客户、对标的公司了解有限的情况下，先通过行业定界、正式研究、证据溯源、issue analysis 和 deck blueprint，生成一组可用于展示行业理解与交易判断的行业章节 PPT。

这个项目不是“快速生成任意 PPT”的模板。它的核心目标是让 AI 先完成可追溯研究和页面规划，再进入确定性 PPT 渲染流程。

### 目录结构

```text
ib-pitchdeck-agent-industry-section/
├── runtime/
│   └── ib-pitchdeck-agent-industry-section/   # 可安装的 plugin package root
├── tests/                           # 开发与回归测试，不属于安装包
└── README.md                        # 本文件
```

真正需要安装给 AI agent 使用的是 plugin package：

```text
runtime/ib-pitchdeck-agent-industry-section/
```

该目录包含平台 plugin manifest、`agents/` 主 agent、role-based `skills/`、scripts、templates、assets 和 runtime references。仓库根目录的 `README.md`、`docs/`、`tests/`、`AGENTS.md` 不属于安装包。

### 安装

不要把这个 package 复制到 `~/.codex/skills/`、`~/.claude/skills/` 或 `~/.workbuddy/skills/`。这是 plugin package，不是 legacy skill 目录。

Codex plugin 安装应走 plugin / marketplace 机制。plugin source root 是：

```text
runtime/ib-pitchdeck-agent-industry-section/
```

本地开发时，可以把该目录作为 marketplace entry 指向的 plugin source，或复制/同步到本地 plugin source 目录（例如 `~/plugins/ib-pitchdeck-agent-industry-section/`）后通过 `codex plugin add` 安装。Claude / WorkBuddy 如使用 plugin 机制，也应注册同一个 plugin package。只有在某个平台明确只支持 legacy skills 时，才应另行生成 compatibility export；不要把开发仓库根目录或 plugin package 直接塞进 skills 目录。

```text
plugin root:
  runtime/ib-pitchdeck-agent-industry-section/
required:
  .codex-plugin/plugin.json
  agents/
  skills/
  scripts/
  templates/
  assets/
  references/
```

### 本地运行检查

在 plugin package 目录中运行：

```bash
cd runtime/ib-pitchdeck-agent-industry-section
PYTHON_CMD="$(bash setup.sh --print-python)"
"$PYTHON_CMD" scripts/check_runtime_dependencies.py
```

`setup.sh` 会调用 `scripts/bootstrap_runtime.py`，优先复用可用的 Python；如果缺少依赖，会尝试创建或更新本地 `.venv` 并安装 `requirements.txt`。

正式研究需要搜索或可审阅的公开资料来源。默认优先使用 agent 自带的 Web Search 做 LLM 主导搜索；脚本 fallback 的优先顺序由 `templates/source_registry.json` 控制，当前为 `SearXNG → DuckDuckGo → Tavily`。推荐先配置 `SEARXNG_BASE_URL`，`tavily-python` / `ddgs` 仅作为可选额外 provider。如果完全没有网络或搜索 provider，只能使用用户提供的离线来源，并且仍需完成 source review、source archive 和 evidence trace；不能把未搜索的内容伪装成 formal research。

### 基本工作流

该 skill 的正式流程大致为：

```text
用户材料 / 链接 / 指令
→ Material Intake
→ Knowledge Repository
→ Industry Scoping / Boundary Validation
→ Research Evidence
→ Reasoning / Issue Analysis
→ Generation / Deck Blueprint
→ Template Profile / Template Fit
→ Output / PPT Render
→ QC / Final Delivery Validation
```

Plugin package 采用主 agent + role skills：主入口和 Orchestrator 是 `agents/ib-pitchdeck-agent-industry-section.md`；角色 skills 包括 `material-intake`、`knowledge-repository`、`industry-scoping`、`research-external-evidence`、`reasoning`、`generation`、`template`、`qc` 和 `output`。plugin package 根目录不放 `SKILL.md`，`skills/` 只放能力模块。

`scripts/pipeline.py render --run-dir <attempt_dir>` 是正式 PPT 渲染和 final gate 的首选入口。它只处理已经通过正式研究和上游校验的 run package，不从 brief 开始做研究，也不创建新的 attempt。`run_pipeline.sh` 仅保留为旧自动化兼容包装器，并且只接受已有 attempt。

当前 runtime 使用固定 8 页行业章节母版。页面类型和变体由 `slide_registry.json`、`page_type_rules.json`、`template_registry.json` 和 PPT mapping 控制；如需新增行业专属页面结构，应同步更新模板、registry、mapping 和验证脚本。

### Plugin Package

`runtime/ib-pitchdeck-agent-industry-section/.codex-plugin/plugin.json` 是 plugin manifest。不要在仓库根目录再放第二套 `.codex-plugin` 或 `skills/` wrapper。

### 开发与测试

从仓库根目录运行：

```bash
PYTHON_CMD=python3 bash tests/run_smoke_tests.sh
PYTHON_CMD=python3 bash tests/run_contract_tests.sh
python3 -m pytest -q
```

如果本地 Python 版本与 `python-pptx` / `lxml` 不兼容，建议使用 Python 3.9-3.11。

### 打包

如需生成干净安装包，应只打包 `runtime/ib-pitchdeck-agent-industry-section/` 的内容。安装包不应包含仓库根目录的 `tests/`、`docs/`、`dist/`、缓存文件或历史运行结果。

---

## English

This repository contains an AI plugin for generating an investment banking pitchbook industry section. It is designed for pre-mandate pitch situations: before the mandate is won and before the target company is fully diligenced, the agent builds sector understanding, runs formal research, tracks evidence, develops issue analysis, plans the deck, and then renders a PPT industry section.

This is not a shortcut template for producing any PPT as quickly as possible. The purpose is to make the agent complete source-disciplined research and page-level planning before deterministic PowerPoint rendering.

### Repository Layout

```text
ib-pitchdeck-agent-industry-section/
├── runtime/
│   └── ib-pitchdeck-agent-industry-section/   # Installable plugin package root
├── tests/                           # Developer regression tests; not installed
└── README.md                        # This file
```

The installable plugin package is:

```text
runtime/ib-pitchdeck-agent-industry-section/
```

It contains platform plugin manifests, the main agent under `agents/`, role-based `skills/`, scripts, templates, assets, and runtime references. Repository-level `README.md`, `docs/`, `tests/`, and `AGENTS.md` are not part of the installable package.

### Installation

Do not copy this package into `~/.codex/skills/`, `~/.claude/skills/`, or `~/.workbuddy/skills/`. This is a plugin package, not a legacy skill folder.

Codex installation should use the plugin / marketplace mechanism. The plugin source root is:

```text
runtime/ib-pitchdeck-agent-industry-section/
```

For local development, point a marketplace entry at this plugin source, or sync the package to a local plugin source directory such as `~/plugins/ib-pitchdeck-agent-industry-section/` and install it with `codex plugin add`. Claude / WorkBuddy plugin installs should likewise register the plugin package through their plugin mechanisms. If a platform only supports legacy skills, create a separate compatibility export instead of placing this plugin package directly into a skills directory.

```text
plugin root:
  runtime/ib-pitchdeck-agent-industry-section/
required:
  .codex-plugin/plugin.json
  agents/
  skills/
  scripts/
  templates/
  assets/
  references/
```

### Local Runtime Check

Run from the plugin package directory:

```bash
cd runtime/ib-pitchdeck-agent-industry-section
PYTHON_CMD="$(bash setup.sh --print-python)"
"$PYTHON_CMD" scripts/check_runtime_dependencies.py
```

`setup.sh` calls `scripts/bootstrap_runtime.py`. It first tries to reuse a compatible Python runtime; if dependencies are missing, it can create/update the local `.venv` and install `requirements.txt`.

Formal research needs search access or reviewable public materials. Prefer the agent's native Web Search for LLM-led research. Script fallback provider order is controlled by `templates/source_registry.json`; the current default is `SearXNG → DuckDuckGo → Tavily`. Configure `SEARXNG_BASE_URL` first; `tavily-python` / `ddgs` are optional extra providers. If neither network access nor a search provider is available, use only user-provided offline sources that can be reviewed, archived, and traced; do not represent unsearched content as formal research.

### Workflow

The formal workflow is approximately:

```text
user materials / links / instructions
→ Material Intake
→ Knowledge Repository
→ Industry Scoping / Boundary Validation
→ Research Evidence
→ Reasoning / Issue Analysis
→ Generation / Deck Blueprint
→ Template Profile / Template Fit
→ Output / PPT Render
→ QC / Final Delivery Validation
```

The plugin uses a main agent plus role-based skills. The main entrypoint and
Orchestrator is `agents/ib-pitchdeck-agent-industry-section.md`. Role skills include `material-intake`,
`knowledge-repository`, `industry-scoping`, `research-external-evidence`,
`reasoning`, `generation`, `template`, `qc`, and `output`. The plugin package
root does not contain a `SKILL.md`, and `skills/` contains only capability
modules.

`scripts/pipeline.py render --run-dir <attempt_dir>` is the preferred entrypoint for formal PPT rendering and final delivery gates. It only operates on a run package that has already passed formal research and upstream validation; it does not start research from a brief or create a new attempt. `run_pipeline.sh` remains only as a compatibility wrapper for older automation and accepts existing attempts only.

The current runtime uses a fixed 8-slide industry-section master template. Page types and variants are controlled by `slide_registry.json`, `page_type_rules.json`, `template_registry.json`, and PPT mappings. New industry-specific page structures should update the template, registries, mappings, and validators together.

### Plugin Package

`runtime/ib-pitchdeck-agent-industry-section/.codex-plugin/plugin.json` is the
plugin manifest. Do not keep a second `.codex-plugin` or `skills/` wrapper at
the repository root.

### Development And Tests

Run from the repository root:

```bash
PYTHON_CMD=python3 bash tests/run_smoke_tests.sh
PYTHON_CMD=python3 bash tests/run_contract_tests.sh
python3 -m pytest -q
```

If your local Python version has compatibility issues with `python-pptx` / `lxml`, use Python 3.9-3.11.

### Packaging

A clean distributable package should contain only the contents of `runtime/ib-pitchdeck-agent-industry-section/`. It should not include repository-level `tests/`, `docs/`, `dist/`, cache files, or historical run outputs.

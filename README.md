# IB Industry Section Skill

## 中文

这是一个用于生成投行 pitchbook 行业章节的 AI skill。它面向 pre-mandate pitch 场景：在尚未正式拿下客户、对标的公司了解有限的情况下，先通过行业定界、正式研究、证据溯源、issue analysis 和 deck blueprint，生成一组可用于展示行业理解与交易判断的行业章节 PPT。

这个项目不是“快速生成任意 PPT”的模板。它的核心目标是让 AI 先完成可追溯研究和页面规划，再进入确定性 PPT 渲染流程。

### 目录结构

```text
ib-industry-section-skill/
├── runtime/
│   └── ib-industry-section-skill/   # 可直接安装/复制的 skill 目录
├── tests/                           # 开发与回归测试，不属于安装包
├── agents/                          # 开发元数据，不属于安装包
└── README.md                        # 本文件
```

真正需要安装给 AI agent 使用的是：

```text
runtime/ib-industry-section-skill/
```

该目录故意不放 `README.md`，以减少 agent 执行时的干扰。Agent 应从 `SKILL.md` 进入。

### 安装

把 runtime 下的 skill 文件夹复制到对应 agent 的 skills 目录：

```bash
cp -R runtime/ib-industry-section-skill ~/.codex/skills/
```

或复制到其他支持 skills 的 agent 目录，例如：

```text
~/.claude/skills/
~/.workbuddy/skills/
```

安装后的结构应类似：

```text
~/.codex/skills/ib-industry-section-skill/SKILL.md
```

不要把仓库根目录整体复制到 agent skills 目录。根目录包含测试和开发文件，会干扰 agent 执行。

### 首次运行检查

安装后，在 skill 目录中运行：

```bash
cd ~/.codex/skills/ib-industry-section-skill
PYTHON_CMD="$(bash setup.sh --print-python)"
"$PYTHON_CMD" scripts/check_runtime_dependencies.py
```

`setup.sh` 会调用 `scripts/bootstrap_runtime.py`，优先复用可用的 Python；如果缺少依赖，会尝试创建或更新本地 `.venv` 并安装 `requirements.txt`。

正式研究需要搜索或可审阅的公开资料来源。默认优先使用 agent 自带的 Web Search 做 LLM 主导搜索；脚本 fallback 的优先顺序由 `templates/source_registry.json` 控制，当前为 `SearXNG → DuckDuckGo → Tavily`。推荐先配置 `SEARXNG_BASE_URL`，`tavily-python` / `ddgs` 仅作为可选额外 provider。如果完全没有网络或搜索 provider，只能使用用户提供的离线来源，并且仍需完成 source review、source archive 和 evidence trace；不能把未搜索的内容伪装成 formal research。

### 基本工作流

该 skill 的正式流程大致为：

```text
brief
→ industry scope pack
→ formal search plan
→ formal research execution
→ research evidence DB
→ generated research pack
→ issue analysis
→ deck blueprint
→ page evidence contract / renderer spec
→ template profile / template fit
→ PPT fill
→ final delivery validation
```

`scripts/pipeline.py render --run-dir <attempt_dir>` 是正式 PPT 渲染和 final gate 的首选入口。它只处理已经通过正式研究和上游校验的 run package，不从 brief 开始做研究，也不创建新的 attempt。`run_pipeline.sh` 仅保留为旧自动化兼容包装器，并且只接受已有 attempt。

当前 runtime 使用固定 8 页行业章节母版。页面类型和变体由 `slide_registry.json`、`page_type_rules.json`、`template_registry.json` 和 PPT mapping 控制；如需新增行业专属页面结构，应同步更新模板、registry、mapping 和验证脚本。

### 开发与测试

从仓库根目录运行：

```bash
PYTHON_CMD=python3 bash tests/run_smoke_tests.sh
PYTHON_CMD=python3 bash tests/run_contract_tests.sh
python3 -m pytest -q
```

如果本地 Python 版本与 `python-pptx` / `lxml` 不兼容，建议使用 Python 3.9-3.11。

### 打包

如需生成干净安装包，应只打包 `runtime/ib-industry-section-skill/` 的内容。安装包不应包含 `tests/`、`agents/`、`dist/`、缓存文件或历史运行结果。

---

## English

This repository contains an AI skill for generating an investment banking pitchbook industry section. It is designed for pre-mandate pitch situations: before the mandate is won and before the target company is fully diligenced, the agent builds sector understanding, runs formal research, tracks evidence, develops issue analysis, plans the deck, and then renders a PPT industry section.

This is not a shortcut template for producing any PPT as quickly as possible. The purpose is to make the agent complete source-disciplined research and page-level planning before deterministic PowerPoint rendering.

### Repository Layout

```text
ib-industry-section-skill/
├── runtime/
│   └── ib-industry-section-skill/   # Installable skill directory
├── tests/                           # Developer regression tests; not installed
├── agents/                          # Development metadata; not installed
└── README.md                        # This file
```

The directory to install into an agent is:

```text
runtime/ib-industry-section-skill/
```

The runtime skill directory intentionally does not include a `README.md`, so the agent enters through `SKILL.md` without extra repository-maintenance context.

### Installation

Copy the runtime skill directory into your agent's skills directory:

```bash
cp -R runtime/ib-industry-section-skill ~/.codex/skills/
```

Other compatible agent skill directories may include:

```text
~/.claude/skills/
~/.workbuddy/skills/
```

The installed layout should look like:

```text
~/.codex/skills/ib-industry-section-skill/SKILL.md
```

Do not copy the repository root into the agent skills directory. The repository root contains tests and development metadata that can distract execution agents.

### First-Run Check

After installation, run from the skill directory:

```bash
cd ~/.codex/skills/ib-industry-section-skill
PYTHON_CMD="$(bash setup.sh --print-python)"
"$PYTHON_CMD" scripts/check_runtime_dependencies.py
```

`setup.sh` calls `scripts/bootstrap_runtime.py`. It first tries to reuse a compatible Python runtime; if dependencies are missing, it can create/update the local `.venv` and install `requirements.txt`.

Formal research needs search access or reviewable public materials. Prefer the agent's native Web Search for LLM-led research. Script fallback provider order is controlled by `templates/source_registry.json`; the current default is `SearXNG → DuckDuckGo → Tavily`. Configure `SEARXNG_BASE_URL` first; `tavily-python` / `ddgs` are optional extra providers. If neither network access nor a search provider is available, use only user-provided offline sources that can be reviewed, archived, and traced; do not represent unsearched content as formal research.

### Workflow

The formal workflow is approximately:

```text
brief
→ industry scope pack
→ formal search plan
→ formal research execution
→ research evidence DB
→ generated research pack
→ issue analysis
→ deck blueprint
→ page evidence contract / renderer spec
→ template profile / template fit
→ PPT fill
→ final delivery validation
```

`scripts/pipeline.py render --run-dir <attempt_dir>` is the preferred entrypoint for formal PPT rendering and final delivery gates. It only operates on a run package that has already passed formal research and upstream validation; it does not start research from a brief or create a new attempt. `run_pipeline.sh` remains only as a compatibility wrapper for older automation and accepts existing attempts only.

The current runtime uses a fixed 8-slide industry-section master template. Page types and variants are controlled by `slide_registry.json`, `page_type_rules.json`, `template_registry.json`, and PPT mappings. New industry-specific page structures should update the template, registries, mappings, and validators together.

### Development And Tests

Run from the repository root:

```bash
PYTHON_CMD=python3 bash tests/run_smoke_tests.sh
PYTHON_CMD=python3 bash tests/run_contract_tests.sh
python3 -m pytest -q
```

If your local Python version has compatibility issues with `python-pptx` / `lxml`, use Python 3.9-3.11.

### Packaging

A clean distributable package should contain only the contents of `runtime/ib-industry-section-skill/`. It should not include `tests/`, `agents/`, `dist/`, cache files, or historical run outputs.

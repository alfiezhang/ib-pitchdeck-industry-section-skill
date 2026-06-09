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
├── .github/                         # CI 配置，不属于安装包
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

不要把仓库根目录整体复制到 agent skills 目录。根目录包含测试、CI 和开发文件，会干扰 agent 执行。

### 基本工作流

该 skill 的正式流程大致为：

```text
brief
→ industry scope pack
→ formal search plan
→ formal research execution
→ research pack
→ issue analysis
→ deck blueprint
→ page evidence contract / renderer spec
→ PPT fill
→ final delivery validation
```

`scripts/pipeline.py render --run-dir <attempt_dir>` 是正式 PPT 渲染和 final gate 的首选入口。它只处理已经通过正式研究和上游校验的 run package，不从 brief 开始做研究，也不创建新的 attempt。`run_pipeline.sh` 保留为旧自动化兼容入口。

### 开发与测试

从仓库根目录运行：

```bash
PYTHON_CMD=python3 bash tests/run_smoke_tests.sh
PYTHON_CMD=python3 bash tests/run_contract_tests.sh
```

如果本地 Python 版本与 `python-pptx` / `lxml` 不兼容，建议使用 Python 3.9-3.11。

### 打包

如需生成干净安装包，应只打包 `runtime/ib-industry-section-skill/` 的内容。安装包不应包含 `tests/`、`.github/`、`agents/`、`dist/`、缓存文件或历史运行结果。

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
├── .github/                         # CI configuration; not installed
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

Do not copy the repository root into the agent skills directory. The repository root contains tests, CI files, and development metadata that can distract execution agents.

### Workflow

The formal workflow is approximately:

```text
brief
→ industry scope pack
→ formal search plan
→ formal research execution
→ research pack
→ issue analysis
→ deck blueprint
→ page evidence contract / renderer spec
→ PPT fill
→ final delivery validation
```

`scripts/pipeline.py render --run-dir <attempt_dir>` is the preferred entrypoint for formal PPT rendering and final delivery gates. It only operates on a run package that has already passed formal research and upstream validation; it does not start research from a brief or create a new attempt. `run_pipeline.sh` remains as a compatibility entrypoint for older automation.

### Development And Tests

Run from the repository root:

```bash
PYTHON_CMD=python3 bash tests/run_smoke_tests.sh
PYTHON_CMD=python3 bash tests/run_contract_tests.sh
```

If your local Python version has compatibility issues with `python-pptx` / `lxml`, use Python 3.9-3.11.

### Packaging

A clean distributable package should contain only the contents of `runtime/ib-industry-section-skill/`. It should not include `tests/`, `.github/`, `agents/`, `dist/`, cache files, or historical run outputs.

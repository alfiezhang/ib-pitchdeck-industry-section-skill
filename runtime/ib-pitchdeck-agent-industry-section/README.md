# IB Pitchdeck Agent - Industry Section

## 中文

这是可安装的 plugin package，用于生成 pre-mandate 投行 pitchbook 行业章节。

主入口：

```text
agents/ib-pitchdeck-agent-industry-section.md
```

角色模块：

```text
skills/material-intake/
skills/knowledge-repository/
skills/industry-scoping/
skills/research-external-evidence/
skills/reasoning/
skills/generation/
skills/template/
skills/qc/
skills/output/
```

包内还包含：

```text
scripts/       runtime builders, validators, renderers
templates/     schemas, registries, mappings, layout rules
references/    execution policy and stage guidance
assets/        PowerPoint master template and plugin assets
```

宿主 agent 应从 `agents/ib-pitchdeck-agent-industry-section.md` 进入；`skills/` 下的目录是该主 agent 调度的能力模块。

开发者可用以下命令检查依赖：

```bash
PYTHON_CMD="$(bash setup.sh --print-python)"
"$PYTHON_CMD" scripts/check_runtime_dependencies.py
```

## English

This is the installable plugin package for generating pre-mandate investment-banking pitchbook industry sections.

Main entrypoint:

```text
agents/ib-pitchdeck-agent-industry-section.md
```

Role modules:

```text
skills/material-intake/
skills/knowledge-repository/
skills/industry-scoping/
skills/research-external-evidence/
skills/reasoning/
skills/generation/
skills/template/
skills/qc/
skills/output/
```

The package also includes:

```text
scripts/       runtime builders, validators, renderers
templates/     schemas, registries, mappings, layout rules
references/    execution policy and stage guidance
assets/        PowerPoint master template and plugin assets
```

Host agents should enter through `agents/ib-pitchdeck-agent-industry-section.md`; folders under `skills/` are role modules orchestrated by the main agent.

For developer diagnostics:

```bash
PYTHON_CMD="$(bash setup.sh --print-python)"
"$PYTHON_CMD" scripts/check_runtime_dependencies.py
```

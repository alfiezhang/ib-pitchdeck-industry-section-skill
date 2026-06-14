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
scripts/       public orchestration, packaging, and shared utilities
skills/qc/scripts/validators/  deterministic validation tools
templates/     schemas, registries, mappings, layout rules
references/    execution policy and stage guidance
assets/        PowerPoint master template and plugin assets
```

宿主 agent 应从 `agents/ib-pitchdeck-agent-industry-section.md` 进入；`skills/` 下的目录是该主 agent 调度的能力模块。
`scripts/state_report.py` 和 `scripts/gate_report.py` 只提供状态与问题汇总；它们不是流程总控。

开发者可用以下命令检查依赖：

```bash
PYTHON_CMD="$(bash setup.sh --print-python)"
"$PYTHON_CMD" skills/qc/scripts/check_runtime_dependencies.py
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
scripts/       public orchestration, packaging, and shared utilities
skills/qc/scripts/validators/  deterministic validation tools
templates/     schemas, registries, mappings, layout rules
references/    execution policy and stage guidance
assets/        PowerPoint master template and plugin assets
```

Host agents should enter through `agents/ib-pitchdeck-agent-industry-section.md`; folders under `skills/` are role modules orchestrated by the main agent.
`scripts/state_report.py` and `scripts/gate_report.py` report state and issues only; they are not workflow controllers.

For developer diagnostics:

```bash
PYTHON_CMD="$(bash setup.sh --print-python)"
"$PYTHON_CMD" skills/qc/scripts/check_runtime_dependencies.py
```

For package validation and local plugin-source installation:

```bash
python3 skills/qc/scripts/validators/system/validate_plugin_package.py --package .
python3 scripts/package_plugin.py --output ../../dist/ib-pitchdeck-agent-industry-section.zip
python3 scripts/install_plugin_local.py \
  --source ../../dist/ib-pitchdeck-agent-industry-section.zip \
  --host codex
```

`package_plugin.py` creates a clean zip and excludes `docs/`, `tests/`,
`__pycache__`, `.DS_Store`, and build artifacts. `install_plugin_local.py`
installs the plugin package to a Codex/Claude/CodeBuddy/WorkBuddy plugin source;
it does not copy this package into legacy standalone skills directories.

To inspect old standalone skill installs:

```bash
python3 scripts/audit_legacy_installs.py \
  --output artifacts/legacy_install_audit.json
```

`remove_legacy_installs.py` is dry-run unless called with
`--execute --confirm REMOVE_LEGACY_INSTALLS`.

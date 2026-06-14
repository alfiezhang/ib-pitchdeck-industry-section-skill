# IB Pitchdeck Agent - Industry Section

## 中文

面向 **pre-mandate client pitch** 场景的投行行业章节 Skill。

它不是通用 PPT 美化工具，也不是 CIM / DD / 普通行业研究报告生成器。它帮助 agent 在客户资料有限的情况下，基于用户材料和公开资料完成行业边界校准、证据沉淀、投行判断、页面论点设计、模板适配和 PPT 确定性渲染。

### 适用场景

- 潜在客户 pitch 前的行业章节
- 只有几句话、网页链接、PDF、PPT、Excel、行业报告或项目线索的早期项目
- 需要展示“我们理解行业、理解标的赛道、理解交易机会、理解买方视角”的材料
- 需要把用户精选行业报告、公开网页和搜索结果纳入同一套证据链

### Runtime Skill

可安装的 Skill 位于：

```text
runtime/ib-pitchdeck-agent-industry-section/
```

运行包结构：

```text
runtime/ib-pitchdeck-agent-industry-section/
├── SKILL.md
├── scripts/
│   ├── material-intake/
│   ├── knowledge-repository/
│   ├── industry-scoping/
│   ├── research-external-evidence/
│   ├── reasoning/
│   ├── generation/
│   ├── template/
│   ├── qc/
│   └── output/
├── references/
│   ├── material-intake.md
│   ├── knowledge-repository.md
│   ├── industry-scoping.md
│   ├── research-external-evidence.md
│   ├── reasoning.md
│   ├── generation.md
│   ├── template.md
│   ├── qc.md
│   ├── output.md
│   └── role_job_packets.md
├── schemas/
├── configs/
│   └── artifact_templates/
├── assets/
├── requirements.txt
├── setup.sh
└── run_pipeline.sh
```

`SKILL.md` 是唯一主入口。角色说明放在 `references/*.md`，角色脚本放在 `scripts/<role>/`。JSON schema 放在 `schemas/`，脚本配置、映射、注册表和 artifact 模板放在 `configs/`，PPT 模板资源放在 `assets/`。这些是内部工作分工，不会作为多个宿主 Skill 暴露给 agent。

### 安装

安装到本机 Codex / Claude / WorkBuddy 的 skills 目录：

```bash
cd runtime/ib-pitchdeck-agent-industry-section
python3 scripts/install_skill_local.py --host codex
python3 scripts/install_skill_local.py --host claude
python3 scripts/install_skill_local.py --host workbuddy
```

也可以手动复制 `runtime/ib-pitchdeck-agent-industry-section/` 到对应宿主的 `skills/ib-pitchdeck-agent-industry-section/`。

### 打包与校验

```bash
cd runtime/ib-pitchdeck-agent-industry-section
python3 scripts/package_skill.py
python3 scripts/qc/validators/system/validate_skill_package.py --package .
```

开发回归测试从仓库根目录运行：

```bash
PYTHON_CMD=python3 bash tests/run_smoke_tests.sh
PYTHON_CMD=python3 bash tests/run_contract_tests.sh
python3 -m pytest -q
```

仓库根目录用于开发、测试和发布。`tests/`、`docs/`、`dist/`、缓存文件和历史 run outputs 不属于 runtime skill package。

## English

An investment-banking industry-section Skill for **pre-mandate client pitch** work.

It is not a generic PPT beautifier, CIM generator, diligence workplan, or standalone market report tool. It helps an agent turn limited target materials and public evidence into a source-disciplined pitchbook industry section: industry boundary, evidence base, banker reasoning, page arguments, template fit, and deterministic PPT output.

### Use Cases

- Industry sections for pre-mandate client pitches
- Early-stage target situations with only a short brief, URL, PDF, PPT, Excel file, industry report, or project lead
- Materials that need to show sector understanding, target relevance, transaction opportunity, and likely buyer perspective
- Workflows that combine user-curated industry reports, public web sources, and search results into one evidence chain

### Runtime Skill

The installable Skill lives at:

```text
runtime/ib-pitchdeck-agent-industry-section/
```

`SKILL.md` is the only host-visible entrypoint. Role instructions live under `references/*.md`; role tooling lives under `scripts/<role>/`. JSON schemas live under `schemas/`; script configs, mappings, registries, and artifact templates live under `configs/`; PPT template resources live under `assets/`. Those roles are internal workstations, not separate host skills.

### Install

```bash
cd runtime/ib-pitchdeck-agent-industry-section
python3 scripts/install_skill_local.py --host codex
python3 scripts/install_skill_local.py --host claude
python3 scripts/install_skill_local.py --host workbuddy
```

### Package

```bash
cd runtime/ib-pitchdeck-agent-industry-section
python3 scripts/package_skill.py
python3 scripts/qc/validators/system/validate_skill_package.py --package .
```

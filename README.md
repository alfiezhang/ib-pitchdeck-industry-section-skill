# IB Pitchdeck Industry Section Skill

A runtime agent skill for building **pre-mandate investment banking industry section decks**.

The skill helps an agent turn a target brief, user-provided materials, public sources, and optional PowerPoint templates into client-facing, editable pitchbook pages. The purpose is to show industry understanding, transaction relevance, and professional judgment before a mandate has been won.

## Runtime Package

The installable skill lives here:

```text
runtime/ib-pitchdeck-agent-industry-section/
```

That runtime folder is the main product in this repository. It contains:

- `SKILL.md`: the host-visible entrypoint that tells the agent when and how to use the skill.
- `references/`: workflow and role guidance loaded only when relevant.
- `scripts/`: small deterministic helpers for intake records, source accounting, package checks, and optional PPT mechanics.
- `configs/`: lightweight runtime settings for review and rendering support.
- `assets/`: bundled PowerPoint template assets.
- `requirements.txt`: optional Python dependencies for helper scripts.

The development folders outside `runtime/` exist to package, install, and regression-test the skill. They are not the user-facing workflow.

## Workflow

The runtime workflow is intentionally centered on the agent's research and writing judgment:

1. **Material Intake**: Capture the brief and uploaded materials. Separate user-provided target facts from public evidence.

2. **Industry Scoping**: Define the relevant market boundary, parent market, adjacent categories, and excluded areas before research starts.

3. **Research Loop**: Search, read, and collect sources. If the evidence is too thin for a client-ready deck, route back to targeted research rather than ending with a thin output.

4. **Evidence Record**: Record important metrics and claims with source, period, region, original location, short excerpt, and limitations.

5. **Banker Reasoning**: Turn evidence into industry judgment: market attractiveness, growth durability, channel shifts, competitive context, and relevance to the transaction.

6. **Page Arguments**: Decide which judgments deserve a slide, what data supports them, and how strongly each point can be stated.

7. **PPT Drafting**: Use the provided template as a style guide. Create dense, data-rich, editable PowerPoint pages rather than internal notes or form-filled artifacts.

8. **Quality Review**: Check source traceability, page fullness, chart/table usefulness, visual quality, and client-facing language.

## Expected Output

A good output should look like a pitchbook industry section, not a research memo:

- client-facing language;
- full pages with clear headlines, body copy, charts, tables, and evidence callouts;
- enough industry data to support the page story;
- source-traceable important numbers;
- target facts used as supporting context, not as the whole industry narrative;
- no diligence-workplan language unless explicitly requested;
- no internal workflow terms such as "working market", "parent market", "research gap", or "not client ready" on client pages.

## When To Use

Use this skill for:

- early-stage sell-side or financing pitch materials;
- industry pages for a potential client pitch;
- situations where the brief is short but the deck still needs professional industry judgment;
- projects that need public evidence, user materials, and a PPT template combined into one editable output.

Do not use it as a substitute for:

- a full CIM;
- post-mandate diligence workplans;
- valuation models;
- buyer universe work;
- generic presentation styling without industry research.

## Install

Install the runtime skill into a local host:

```bash
python3 devtools/install/install_skill_local.py --host codex
```

Other supported hosts:

```bash
python3 devtools/install/install_skill_local.py --host claude
python3 devtools/install/install_skill_local.py --host workbuddy
```

After installation, ask the host agent to use `ib-pitchdeck-agent-industry-section` for an IB industry-section or pitchbook industry-page task.

## Optional Helper CLI

Most work should happen through the agent skill. The helper CLI is available for intake records, status checks, optional rendering, and package diagnostics:

```bash
python3 runtime/ib-pitchdeck-agent-industry-section/scripts/pipeline.py --help
```

Example:

```bash
python3 runtime/ib-pitchdeck-agent-industry-section/scripts/pipeline.py start-brief \
  --run-dir runs/example \
  --case-name example \
  --brief-text "A short target and transaction brief."
```

## Privacy And Source Hygiene

Do not commit client materials, real run outputs, local host skill directories, API keys, personal paths, credentials, or generated package archives. Keep only sanitized fixtures in source control.

Before publishing, check the repository for:

- local machine paths and usernames;
- private client or target-company details;
- API keys, tokens, passwords, and private keys;
- generated `runs/`, `dist/`, cache, and archive files;
- binary metadata inside bundled PPT or document assets.

## Maintainer Notes

The top-level `devtools/` and `tests/` folders are for maintainers. They package the runtime skill, install it into local hosts, and run regression checks. They should not drive the agent's actual pitchbook workflow.

Common maintainer commands:

```bash
python3 -m pytest -q
python3 devtools/package/package_skill.py --output dist/ib-pitchdeck-agent-industry-section.clean.zip
python3 devtools/package/validate_skill_package.py --package dist/ib-pitchdeck-agent-industry-section.clean.zip
```

## 中文简介

`ib-pitchdeck-agent-industry-section` 是一个用于生成投行 pitchbook 行业章节的本地 agent skill，适用于尚未获得 mandate 的早期客户沟通场景。

它围绕 `runtime/ib-pitchdeck-agent-industry-section/` 中的工作流组织：从项目 brief、用户材料、公开来源和 PPT 模板出发，完成行业范围界定、公开资料研究、关键数据溯源、投行观点形成和可编辑 PPT 页面生成。

典型输出是一组客户可读的行业页面，强调行业理解、交易相关性和专业判断；重要数字保留来源和口径说明，标的公司信息用于增强项目相关性。

## License

No license file is included yet. Add a license before publishing this repository for external reuse.

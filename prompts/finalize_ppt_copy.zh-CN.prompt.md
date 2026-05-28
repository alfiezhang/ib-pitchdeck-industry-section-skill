# 完成 PPT 文案转换

## 输入
- `industry_storyboard.json` —— 源故事板
- `templates/ppt_copy_schema.json` —— 目标 schema
- `templates/ppt_copy_mapping.json` —— 字段级别映射指导

## 任务
将推理丰富的 `industry_storyboard.json` 转换为确定性 PPT 填充脚本所需的规范 `industry_section_ppt_copy.json` 格式。

## 规则

1. **不要引入新事实。** 故事板是唯一的事实来源。不得添加故事板之外的新数据、声明或解读。
   - 不要在本阶段二次 research 或“扩写”单薄页面。如果文案显得单薄，应保留 storyboard 事实边界，并把问题前置回 memo/storyboard 修复，而不是在这里添加事实。
2. **不要更改已选的页面类型。** 严格使用故事板 `template_binding` 中指定的变体：
   - 第 2 页：`{slide_2_variant}`
   - 第 3 页：`{slide_3_variant}`
   - 第 6 页：`{slide_6_variant}`
   - 第 7 页：`{slide_7_variant}`
   除非故事板内部不一致（如某页的 `selected_page_type` 与 `template_binding` 冲突），此时标注冲突，以 `template_binding` 的值为准。
3. **压缩文本以适配 PPT 占位符。** 要点应可扫读，而非段落形式。标题必须按 `templates/text_fit_rules.json` 单行显示。核心信息应为单句，目标 1 行，最多不得超过 2 行，且结尾不要有句号、逗号、顿号、分号、冒号、感叹号、问号等标点。
4. **保留来源注释。** 每页的 `source_footer` 必须承接故事板的 `source_note`。
5. **保留标的关联。** 每页的 `main_takeaway` 应体现故事板 `target_link` 的意图。
6. **确保输出符合 `templates/ppt_copy_schema.json`。** 所有必填字段必须存在。使用 `ppt_copy_mapping.json` 进行字段级别角色到字段的映射。
7. **如果文本必须缩短，保留投资信息而非描述性细节。** 有力的"市场规模为 X，增长速度为 Y"优于冗长的"Z 市场已被观察到以每年约 Y% 的速度增长"。
8. **保留不确定性。** 如果故事板已经标注弱来源或数据缺口，需要在来源脚注、speaker note 或谨慎措辞中保留，不要把结论写得更确定。
9. **正文不要内嵌来源。** 从 `content` 字段中移除 `（EV-001）`、`(EV-001)`、`（某报告）` 等括号来源；来源统一放在 `source_footer`。
10. **正文写成 bullet 风格。** 每个 `content` 字段应是一条短要点，而不是长段落。第 2/6 页表格行使用 `｜` 分隔单元格，便于后处理生成真正 PPT 表格。
11. **遵守版式预算。** 根据 `templates/layout_budget.json` 压缩正文和表格单元格；表格格内只写标签、数字或短判断，长解释放到 commentary/panel 字段。

## 内容字段映射

对于每页，按照 `ppt_copy_mapping.json` 的指导将故事板 `body_copy` 字段映射到 `ppt_copy_schema.json` 的内容字段。映射因页面角色和页面类型而异：

- **第 1 页**（行业概览）：`bullet_1`、`bullet_2`、`bullet_3`
- **第 2 页**（市场规模与细分）：`bullet_1`–`bullet_3` + 可选 `table_header_1`–`table_row_3`（仅 chart_plus_mini_table_page）
- **第 3 页**（关键行业驱动力）：取决于变体，使用 `card_1`–`card_4`、`card_5` 或 `card_6`
- **第 4 页**（价值链与利润池）：`top_left`–`bottom_right`（6 个面板）
- **第 5 页**（关键壁垒）：`card_1`–`card_3`
- **第 6 页**（竞争格局）：取决于变体（compare_table_page 用表格+面板；matrix_page 用矩阵+面板）
- **第 7 页**（行业趋势）：取决于变体（趋势卡片页用 card 字段；timeline_page 用阶段）
- **第 8 页**（关键启示）：`left_panel`、`right_top`、`right_mid`、`right_bottom`

## 输出格式
**仅返回有效 JSON**。不要包含 Markdown 代码块标记或解释。

JSON 语法硬规则：
- JSON key 和字符串边界只能使用 ASCII 双引号：`"`。
- 不得使用中文/智能引号：`“”‘’`。
- 不得使用单引号包裹 JSON key 或字符串。

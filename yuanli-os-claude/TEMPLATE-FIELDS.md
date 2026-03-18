# TEMPLATE-FIELDS.md

本文档列出 [CLAUDE-INIT-TEMPLATE.md](/Users/liming/Documents/codex-ai-gua-jia-01/yuanli-os-claude/CLAUDE-INIT-TEMPLATE.md) 中全部占位符的含义、数据来源与填写说明。

## 使用规则

- 只填写与你的实例真实存在的对象。
- 如果某字段当前没有稳定对象，不要编造；保留原占位符，或改成 `REVIEW_NEEDED:原因` 这样的人工审阅标记。
- 仓库地址、DNA、六判断、工作流、架构决策、防火墙属于共享层，不需要实例化改写。
- 飞书、wiki、测试数字、阶段快照、frontstage 状态属于实例层，应由各实例自行填写。

## 占位符清单

| 占位符 | 含义 | 数据来源 | 填写说明 |
|---|---|---|---|
| `{{CURRENT_ROUND}}` | 当前轮次或当前阶段名 | 本地战略状态 / 当前项目节奏 | 如 `R18 三向量扩展规划阶段` |
| `{{CURRENT_STAGE}}` | Agent 演进定位或阶段口径 | 战略文档 / 当前阶段共识 | 如 `Agent 第二代末期 → 第三代入口` |
| `{{TESTS_PASSED}}` | 当前通过测试数 | 本地测试快照 | 只填分发快照，不要把它写成 runtime truth |
| `{{TESTS_FAILED}}` | 当前失败测试数 | 本地测试快照 | 与 `{{TESTS_PASSED}}` 配对填写 |
| `{{TOTAL_COMMITS}}` | 当前主分支提交快照 | Git 本地统计 / 已确认分发快照 | 只填摘要值 |
| `{{CURRENT_FOCUS}}` | 当前这一阶段最重要的焦点 | 战略当前态 / 本轮总目标 | 用一句话写当前重点 |
| `{{CURRENT_WARNING}}` | 当前最重要的误吸收或失真提醒 | 本轮治理判断 | 用一句话写，不要写成长文 |
| `{{FEISHU_APP_TOKEN_LIVE}}` | live 运行态总控所在 app/base token | 飞书实例配置 | 必须是你实例真实使用的 token |
| `{{FEISHU_TABLE_ID_LIVE_CONTROL}}` | live 运行态总控表 id | 飞书实例配置 | 与 live app token 配套 |
| `{{FEISHU_APP_TOKEN_SKILL}}` | Skill 盘点所在 app/base token | 飞书实例配置 | 如与治理 app 相同可复用 |
| `{{FEISHU_TABLE_ID_SKILL}}` | Skill 盘点表 id | 飞书实例配置 | 必须是当前 live 表 |
| `{{FEISHU_APP_TOKEN_GOVERNANCE}}` | 治理 / 编年史所在 app/base token | 飞书实例配置 | 可与其他 app token 相同 |
| `{{FEISHU_TABLE_ID_EVOLUTION}}` | 进化编年史表 id | 飞书实例配置 | 对应 evolution / chronicle 面 |
| `{{FEISHU_TABLE_ID_MATURITY}}` | 治理成熟度评估表 id | 飞书实例配置 | 对应治理成熟度或治理信用表 |
| `{{FEISHU_APP_TOKEN_LEGACY}}` | 旧镜像 app/base token | 历史镜像对象 | 如果没有旧镜像，可保留占位符并人工审阅 |
| `{{FEISHU_TABLE_ID_LEGACY_CONTROL}}` | 旧治理总控表 id | 历史镜像对象 | 仅用于提醒别绑旧表 |
| `{{WIKI_TOKEN_GOVERNANCE}}` | 治理 wiki 节点 token | 飞书 wiki 配置 | 用于治理知识入口 |
| `{{WIKI_TOKEN_DOMAIN}}` | 域 wiki 节点 token | 飞书 wiki 配置 | 可表示业务、投研或其他实例域 |
| `{{FRONTSTAGE_GOVERNANCE_STATUS}}` | 治理前台状态摘要 | dashboard / cockpit 已确认状态 | 如 `在线，但仍有少量指标卡需重新绑表` |
| `{{FRONTSTAGE_BUSINESS_STATUS}}` | 经营前台状态摘要 | dashboard / cockpit 已确认状态 | 如 `5 区块在线` |
| `{{DOMAIN_APP_STATUS}}` | 域应用状态摘要 | 当前实例域应用状态 | 用一句话描述即可 |
| `{{SKILL_TOTAL_GOVERNED}}` | 当前治理记录内的 skill 总数 | 技能治理快照 | 是分发摘要，不是 runtime truth |
| `{{SKILL_TOTAL_ACTIVE}}` | 当前可用 skill 数 | 技能治理快照 | 与上一项配对填写 |

## 填写顺序建议

1. 先填当前阶段摘要。
2. 再填飞书与 wiki 坐标。
3. 再填前台摘要和命名陷阱中的实例态字段。
4. 最后通读一遍，确认没有真实旧坐标、无关实例名称或临时数字残留。

## 验收自检

- `CLAUDE-INIT-TEMPLATE.md` 中每个模板占位符都能在本文件里找到解释。
- 本文件不应该解释共享层固定文本，例如 DNA、六判断、工作流。
- 如果某字段暂无稳定来源，请显式保留原占位符，或写成 `REVIEW_NEEDED:说明`，不要伪造值。

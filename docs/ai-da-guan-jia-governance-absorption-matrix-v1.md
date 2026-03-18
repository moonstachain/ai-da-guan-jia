# AI大管家 治理吸收附录矩阵 v1

## A. 8 维治理矩阵

| 维度 | MECE 单元 | 当前 live 现状 | 目标完备态 | 当前主要 gap | 补齐动作 |
| --- | --- | --- | --- | --- | --- |
| 宪法 DNA 维度 | `递归 / 统帅 / 克制` | 已写入 `meta-constitution` 并实际支配 route/closure | 稳定成为所有 run 的默认 DNA | 无结构性缺口 | 继续在 run 里保持一致性 |
| 上位语义维度 | `目的层 / 方法层 / 工具层` | 已写入 `collaboration-charter` | 成为所有治理文档的统一解释层 | 仍缺更直观的人类总图 | 由主报告承担解释层 |
| 判断内核维度 | `六判断` | 已进入任务入口默认口径 | 所有任务都显式过六判断 | 无结构性缺口 | 继续固定为默认入口 |
| 战略操作系统维度 | `G1 / G2 / G3` + initiative registry | `3 goals + 4 active initiatives` | initiative / thread / scorecard 全联动 | 高价值 initiative 仍多为 `gap=high` | 按主战略持续推进 |
| 治理对象维度 | `skill / workflow / agent / component` | `159` 对象；`108/9/5/37` | 四类对象都可被稳定审计和提权 | `High = 0`，整体成熟度偏低 | 优先提升 workflow / agent / component 成熟度 |
| 组织编排维度 | `cluster / layer / routing discipline` | 技能层已形成 `5 clusters + 4 inventory layers` | 对象层、业务层、卫星层全部纳入统一编排面 | 仍偏 skill-centric | 把业务 deputy 和卫星治理也并入同一 taxonomy |
| 提权激励维度 | `自治层 + scorecard + incentive levers` | 4 层目标模型已存在；3 层运行提权已激活 | 评分层与运行层完全对齐 | 仍有“目标 4 层 / 运行 3 层”的过渡差 | 补齐 observe 到 suggest 的显式解释和晋升规则 |
| 闭环进化维度 | `route -> verify -> local evolution -> next iterate` | 闭环链已稳定存在，但 control tower 仍 `unsettled` | honesty gate、writeback trust、mirror 边界全部稳定 | AI大管家 自身 honesty gate 未过 | 先 honesty hardening，再结构提权 |

## B. 当前 live 数字快照

### B.1 战略层

| 指标 | 当前值 | 说明 |
| --- | --- | --- |
| 战略目标数 | `3` | `G1 / G2 / G3` |
| Active initiatives | `4` | `I-GOV-001 / I-AUTO-001 / I-INC-001 / I-CLONE-001` |
| 当前 stage theme | `从强执行体升级为受控自治的 AI 治理系统` | 来自 `strategy-map.json` |

### B.2 治理对象层

| 指标 | 当前值 |
| --- | --- |
| 治理对象总数 | `159` |
| `skill` | `108` |
| `workflow` | `9` |
| `agent` | `5` |
| `component` | `37` |

### B.3 成熟度层

| Mature Bucket | 当前值 |
| --- | --- |
| `High` | `0` |
| `Mid` | `50` |
| `Low` | `109` |

### B.4 技能编排层

| 维度 | 当前值 |
| --- | --- |
| `agency簇` | `56` |
| `垂直workflow簇` | `18` |
| `平台簇` | `24` |
| `AI大管家治理簇` | `7` |
| `技能生产簇` | `3` |

| 分层 | 当前值 |
| --- | --- |
| `专家角色层` | `56` |
| `垂直工作流层` | `18` |
| `平台/工具集成层` | `24` |
| `元治理层` | `10` |

### B.5 当前 readiness 状态

| 指标 | 当前值 |
| --- | --- |
| governance conclusion mode | `baseline_only` |
| transport_ready | `false` |
| multi_source_ready | `false` |
| formal_governance_ready | `false` |
| missing_sources | `satellite-01 / satellite-02` |
| blockers | `hub_transport_not_ready / missing_sources / governance_feishu_not_configured` |

## C. 自治层口径对照

### C.1 目标分层模型

| 层级 | 含义 |
| --- | --- |
| `observe` | 只进入评分面，不进入积极提权 |
| `suggest` | 建议 + 待批 |
| `trusted-suggest` | 建议可信度更高，可获正向 routing credit |
| `guarded-autonomy` | 在受控边界内具备更高自治权 |

### C.2 当前 live 评分面

来自 `object-scorecard.json` 的技能层分布：

| 层级 | 当前值 |
| --- | --- |
| `observe` | `88` |
| `suggest` | `4` |
| `trusted-suggest` | `15` |
| `guarded-autonomy` | `1` |

### C.3 当前 live 运行提权面

来自 `autonomy-tier.json` 的当前提权账本分布：

| 层级 | 当前值 |
| --- | --- |
| `suggest` | `94` |
| `trusted-suggest` | `12` |
| `guarded-autonomy` | `2` |

### C.4 为什么会出现两种分布

这不是冲突，而是当前系统的设计结果：

- `4 层` 是完整目标分层模型
- `3 层` 是当前已激活的运行提权面
- 原因是战略契约已写明：默认自治等级是 `建议 + 待批`

所以：

`observe` 目前更多是评分和审计层的保守桶，而不是外显给人类的默认运行权限桶。

## D. 原力OS 吸收状态总表

| 类别 | 当前判断 |
| --- | --- |
| `原力OS 治理内核` | 已被吸收并扩展 |
| `os-yuanli root runtime` | 仍为 `benchmark / bridge` |
| `os-yuanli 器官包` | 已部分吸收，待器官化制度化 |
| `原力OS visible shell` | 保留为外显层 |
| `AI大管家` | 唯一顶层治理入口 |

## E. 当前最大失真

当前最危险的误判不是“AI大管家 还没吸收原力OS”，而是：

把已经内嵌的治理职责误当成已经完全制度化的显式器官；或者把前台外显层误当成新的 root。

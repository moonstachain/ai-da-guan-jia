# 黑色卫星 PMO Beta 最小协议 v1

> 这份协议只定义 `黑色卫星 = 半自动 PMO Beta 远程控制面` 的最小可运行边界。  
> 它复用 [docs/ai-da-guan-jia-host-satellite-collaboration-v2.md](/Users/liming/Documents/codex-ai-gua-jia-01/docs/ai-da-guan-jia-host-satellite-collaboration-v2.md) 的主机-卫星边界，以及 [docs/ai-da-guan-jia-mainline-branch-collaboration-v1.md](/Users/liming/Documents/codex-ai-gua-jia-01/docs/ai-da-guan-jia-mainline-branch-collaboration-v1.md) 的 heartbeat / govern 消费口径。

## 1. 角色定位

- `黑色卫星 PMO Beta` 不是总控台，不是运营主线，也不是 fully autonomous agent。
- 它是一个 `2-3 lane 半自动远程控制面`：
  - 负责远程执行、局部验证、证据回写、状态上报
  - 不负责全局优先级、正式 closure、主线状态升级
- 目标不是替代总控台，而是让总控台能更稳定地把 `2-3` 条远程 lane 派给黑色卫星并观察其状态。

## 2. 角色边界

### 黑色卫星能做什么

- 运行 repo-local 或远端可逆命令
- 承接浏览器、CLI、截图、read-only probe、局部修复
- 为每条 lane 产出 repo-local `route / lane-manifest / lane-result / worklog / evidence`
- 写 heartbeat，让总控通过 `window-heartbeat inspect/govern` 消费状态
- 在不扩 scope 的前提下，对单一 blocker 做最小裁决前分析

### 黑色卫星不能做什么

- 不能宣布全局 `completed`
- 不能替 main-hub 做 `route / priority / close-task / mirror apply / publish`
- 不能擅自升格为新的总控台或运营主线
- 不能把临时路径证据当 canonical 证据
- 不能把历史上出现过的登录、授权、切模型动作持续当作当前 human boundary
- 不能接管妙搭页面最终修复
- 不能承担 preview 纠偏、source view 最终人工绑定、页面执行面 republish

### 仍保留给总控台

- 全局目标、优先级、stop condition
- 哪个 lane 继续、冻结、合并、回收
- 是否触发状态升级
- 是否采纳卫星的局部结果为主线真相

### 仍保留给人类

- 登录、授权、支付
- 不可逆发布或删除
- 需要主观判断的业务/设计取舍
- 新出现的真实权限边界
- 妙搭页面执行面上的真实 republish / binding / preview 纠偏

## 3. 默认拓扑

- 默认 `3 lane`：
  - `main`
    - PMO 语义 = `执行 lane`
    - 职责 = 最接近 closure 的实现或执行动作
  - `verify`
    - PMO 语义 = `验证 lane`
    - 职责 = 测试、truth check、截图、validator、read-only evidence
  - `support`
    - PMO 语义 = `支持 lane`
    - 职责 = 辅助分析、契约补丁、文档、数据整理
- 可降级为 `2 lane`：
  - `main + verify`
  - 仅当支持工作不独立占据一个 scoped_goal 时允许
- 不扩成复杂平台：
  - lane 数量上限仍是 `3`
  - 不自动新开窗口
  - 不引入新的多智能体总线

## 4. 最小 Lane Contract

每条 lane 至少必须回写这 `6` 个字段：

```json
{
  "lane_id": "main",
  "scoped_goal": "只做一个清晰子目标",
  "current_phase": "当前所处阶段",
  "latest_evidence_paths": [
    "repo-local path only"
  ],
  "sole_blocker": "当前唯一 blocker，没有就留空",
  "next_request_to_mainline": "主线下一步应裁决或下发的唯一请求"
}
```

补充约定：

- `lane_id`
  - 只允许 `main / support / verify`
- `scoped_goal`
  - 必须是单目标，不混多个 closure 口径
- `latest_evidence_paths`
  - 只放 repo-local 可信路径
- `sole_blocker`
  - 必须是当前 blocker，不允许带历史 blocker 列表
- `next_request_to_mainline`
  - 只允许一个最小请求，例如 `允许继续下一批` / `裁决 blocker` / `转交人类边界`

## 5. Repo-local 证据回写规则

### 必须回写到 repo-local

- `route.json`
- `lane-manifest.json`
- `lane-result.json`
- `lane-summary.md`
- `worklog.json`
- `worklog.md`
- 任何会影响主线判断的截图、JSON、日志、验证结果
- 最终 heartbeat 中引用的 evidence path

### 可以留在临时路径

- 远端导出过程中的中转文件
- 临时 probe 截图
- 不进入主线判断的探索性 stdout/stderr

### 提高可信调度强度的条件

- lane heartbeat 新鲜
- `latest_evidence_paths` 全部已落到 repo-local
- `sole_blocker` 被压缩成单一技术点或单一外部等待态
- `verify` lane 能独立复述 `main` lane 的关键证据

## 6. Human Boundary 收窄口径

- 只认 `当前等待态 + 当前 blocker`
- 不认 `last_action` 中的历史动作
- 不认“以前做过登录 / 授权 / 切模型 / 点过页面”这类历史事实

具体规则固定为：

- 判定为 human boundary：
  - `current_status = waiting_user`
  - 或 `sole_blocker` 明确仍是登录、授权、支付、发布、删除、主观拍板
- 不判定为 human boundary：
  - `last_action` 里提到过去做过登录/授权，但当前 blocker 已经是技术问题
  - 当前只是等待总控裁决、等待 repo-local 回写、等待验证 lane 回包
  - 当前 blocker 是 selector、surface、evidence、export、contract 等技术问题

## 7. 总控如何调度黑色卫星 PMO Beta

### 适合派给黑色卫星 PMO Beta

- 任务能拆成 `2-3` 条 scoped lane
- 至少有一条 lane 可以独立做验证或证据采集
- 结果能回写成 repo-local 证据，而不是只停在口头进展
- blocker 主要是技术调度、页面执行、验证稳定性
- dashboard runtime data model gap 澄清
- expected source view / card binding / evidence chain 的 repo-local 对照

### 只把它当普通支线

- 任务本质上只有一个执行面
- 没有独立 `verify` 价值
- 证据不能稳定回写 repo-local
- 总控不需要 lane 级状态观察

### 不能自动继续

- 当前 blocker 已经是真实人类边界
- 需要改全局优先级或主线目标
- 要做 mirror/apply/publish/delete
- 还没有可信 repo-local 证据
- 任务已经退化成妙搭页面最终修复或页面执行面动作

## 8.5 妙搭分工固定边界

当当前主任务同时涉及 `dashboard runtime data model` 与 `妙搭页面外显` 时，固定分工如下：

- `黑色卫星`
  - 负责模型缺口澄清、support、verify、证据整理
  - 负责对 `expected source view / expected card binding / expected evidence chain` 做 repo-local 对照
  - 不负责妙搭页面上的最终 republish / binding / preview 纠偏
- `人类页面执行面`
  - 负责进入妙搭页面
  - 检查当前 preview
  - 真正 republish 正确版本
  - 确认 `diagnosis-03 / action-04` 的页面对象是否对齐
- `运营主线`
  - 只在页面执行面回传后，做最终复验与诚实收口

## 8. 最小运行闭环

1. 总控只派一个 scoped task 给黑色卫星
2. 黑色卫星按 `main / support / verify` 产出 lane bundle
3. 关键证据先回写 repo-local，再写 heartbeat
4. 总控只消费：
   - `current_phase`
   - `latest_evidence_paths`
   - `sole_blocker`
   - `next_request_to_mainline`
5. 若 `verify` 与 repo-local 证据成立，总控再决定继续、等待、裁决、收口

## 9. Canonical Files

- 协议文档：
  - [ai-da-guan-jia-black-satellite-pmo-beta-v1.md](/Users/liming/Documents/codex-ai-gua-jia-01/docs/ai-da-guan-jia-black-satellite-pmo-beta-v1.md)
- machine-readable contract：
  - [black-satellite-pmo-beta-contract.json](/Users/liming/Documents/codex-ai-gua-jia-01/work/ai-da-guan-jia/artifacts/ai-da-guan-jia/satellites/current/black-satellite-pmo-beta-contract.json)

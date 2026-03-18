# R18 路线图

更新时间：2026-03-17  
定位：承接 `R18` 阶段的排期、依赖关系和执行面，不再让这些内容停留在 `CLAUDE-INIT.md` 正文。

## 当前阶段判断

当前阶段是：

- `R18 三向量扩展规划阶段`
- `Agent 第二代末期 → 第三代入口`

当前地基状态：

- `P0-2a` `memory-layer-contract.md` 已完成
- `P0-2b` `source-of-truth-contract.md` 已完成
- `P0-1` `~/.codex/memory.md` 已完成
- `P0-2c` `task-spec-quality-contract.md` 已完成
- `P0-3a` `CLAUDE-INIT V16 FINAL SYNC Blueprint` 已完成
- 当前正在执行 `P0-3b`：`CLAUDE-INIT` 四层分离

## 总路线

R18 后续的执行顺序仍然分为四段：

- `P0 地基`
- `P1 基建`
- `P2 核心`
- `P3 产品化`

## P0 地基

目标：

- 钉死记忆层、真相源、spec 质量
- 完成 `CLAUDE-INIT` 四层分离
- 给后续 GitHub 治理盘点和模板化提供稳定起点

关键任务：

- `TS-GH-01 GitHub治理盘点与规范化`
- `TS-V1-01 卫星机治理对齐`
- `TS-V2-01 CLAUDE-INIT模板化`

依赖关系：

- `TS-V1-01` 依赖 `TS-GH-01`
- `TS-V2-01` 可与 `TS-GH-01` 并行

## P1 基建

目标：

- 让多机、同事复制和模板初始化有可运行的底层骨架

关键任务：

- `TS-V1-02 机器注册表+心跳`
- `TS-V2-02 飞书Base一键初始化脚本`
- `TS-V2-03 妙搭驾驶舱模板化`

关键注意：

- 妙搭模板化仍然有人类操作边界
- 不允许模板层先于 canonical 规则

## P2 核心

目标：

- 让三向量从“概念上可行”进入“可被调度和复制”

关键任务：

- `TS-V1-03 任务分发路由+model_recommendation`
- `TS-V2-04 业务模块拆分矩阵`
- `TS-V3-01 行业模板体系设计`

关键注意：

- 这一阶段重点是对象分层、模块拆分和路由规则
- 不要把未验证的模板提前推成产品

## P3 产品化

目标：

- 把三向量中的可复用部分正式产品化、标准化

关键任务：

- `TS-V1-04 虚机标准部署脚本`
- `TS-V2-05 同事 onboarding SOP`
- `TS-V3-02 客户初始化工具链`
- `TS-V3-03 客户驾驶舱产品化`
- `TS-V3-04 定价与交付 SOP`

关键注意：

- 这是面向“让别人直接用”的阶段
- 共享层必须保持只读和可审计

## 其他并行议题

以下任务可以作为并行支线，但不应反向打断 R18 主线：

- 新 Base 统一与妙搭改绑
- 商业模式创新案例库导入飞书
- 康波类应用的模板化建设
- ClawHub 发布

处理原则：

- 支线可做
- 不得破坏主线的 canonical / mirror / template 结构

## 当前推荐顺序

在 `P0-3b` 完成之后，推荐的下一批顺序是：

1. `TS-GH-01`
2. `TS-V2-01`
3. `TS-V1-01`

原因：

- GitHub 是三向量的分发基座
- `INIT` 模板化是 V2 的入口
- 卫星机治理对齐必须建立在更稳定的治理基座上

## 本文档的边界

这份路线图属于执行面和阶段面。

它不是：

- runtime ledger
- local canonical artifact
- dashboard truth source

后续如果要进入 GitHub issue / Project，同步的也是这份路线图的执行镜像，而不是让 issue / Project 反向定义真相源。

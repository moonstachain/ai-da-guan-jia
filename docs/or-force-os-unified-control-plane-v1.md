# Or Force OS Unified Control Plane v1

这份文档把 `原力OS-AI大管家` 的这次设计收束成一套统一控制面，目标是把当前已经能跑的工具集合整理成一套可持续运转、可分装、可镜像、可复用的治理系统。

## 一句话定义

`原力OS-AI大管家` = 一个共享治理内核，外加 `GitHub 协同层`、`Miaoda 前台层`、`Feishu 数据层` 与 `clone 分装层`。

## 四层结构

### 1. 本体层

- 本地 canonical 与治理协议
- 负责真相、边界、闭环、进化
- 不把 Feishu、GitHub、Miaoda 误当真相源

### 2. 协同层

- GitHub 负责任务协作、变更记录、证据镜像
- 不承担运行真相
- 不替代本地 canonical

### 3. 前台层

- Miaoda 负责总控驾驶舱与日常入口
- 只做可视化、分发、收口和人类操作入口
- 不承载底层治理逻辑

### 4. 数据层

- Feishu 多维表负责结构化事实、clone 分装、任务追踪和协作镜像
- 通过稳定表结构承接治理语言
- 通过 source view 提供可绑定的展示契约

### 5. 分装层

- 同一共享核心下的 internal colleague clone、strategic partner clone、client clone
- 通过 `memory_namespace / role_template_id / visibility_policy / service_tier` 隔离
- 不复制 skill 仓库，不复制核心本体

## 固定原则

- 一个共享核心
- 一套治理语言
- 一条路由 / 验真 / 收口闭环
- 一套 Feishu 镜像语义
- 一套 GitHub 变更语义
- 一套 clone 产品化阶梯

## 三条流

### 事实流

`本地 canonical -> Feishu / GitHub 镜像`

### 决策流

`总控台 -> 任务分发 -> clone 分装 -> 人类拍板`

### 进化流

`运行证据 -> 规则沉淀 -> 模板 / skill / contract 更新`

## 参考落点

- 顶层治理本体：`docs/ai-da-guan-jia-top-level-blueprint-v1.md`
- 协作约束：`references/collaboration-charter.md`
- clone 产品化：`references/clone-productization-contract.md`
- 内部同事协作路径：`work/ai-da-guan-jia/AI大管家-同事协作成长路径说明.md`

## 这次设计的交付物

- `docs/or-force-os-github-design-v1.md`
- `docs/or-force-os-miaoda-cockpit-v1.md`
- `specs/feishu/or-force-os-unified-control-center-v1/dashboard-blueprint.md`
- `specs/feishu/or-force-os-unified-control-center-v1/dashboard-blueprint.json`
- `specs/feishu/or-force-os-unified-control-center-v1/source-views-spec.json`
- `specs/feishu/or-force-os-unified-control-center-v1/dashboard-card-checklist.md`


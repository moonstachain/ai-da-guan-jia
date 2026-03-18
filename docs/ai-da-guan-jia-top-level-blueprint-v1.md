# AI大管家顶层蓝图 v1

这份文档只回答长期不变的问题：

1. `AI大管家` 到底是什么。
2. 它治理哪些对象。
3. 它按什么层次展开。
4. 它先在哪个部署阶段成立，再向外扩展。

它不是当前实验项目说明，不承载 `R1 / R2 / R3`、`cockpit`、`deal_closed_lost` 等阶段性代号。

## 六个治理判断

- `自治判断`
  当前主线大部分已能由 AI 自治推进，人类边界主要保留在最终拍板、人工 cockpit 证据、不可替代主观判断。
- `全局最优判断`
  这套系统要先做成治理内核，再做成团队底盘，再做成客户 clone 网络，不能倒过来。
- `能力复用判断`
  现有 `canonical + strategy-governor + Feishu mirror + GitHub mirror + execute 主线` 已经是第一代内核，不重造平行体系。
- `验真判断`
  只认真实业务证据、真实 writeback、真实 KPI、真实截图与真实镜像，不认“结构看起来完整”。
- `进化判断`
  终局不是一个项目完成，而是一套可持续递归进化、可复制部署的治理标准件。
- `当前最大失真`
  最容易把飞书表、妙搭页、source view 误当系统本体；它们只是镜像面，不是治理内核本身。

## Summary

`AI大管家` 的本体，不是任务管理器，也不是飞书看板，而是一个 `local-first、可分布、可镜像、可克隆的治理内核`。

它面向的不是单个任务，而是：

- 多个本地任务与线程
- 多个工具与子系统
- 多台笔记本上的同一治理者
- 未来同事安装后的同构协作
- 未来客户 clone 的受控自治

第一阶段的第一性固定为：

- `你本人多机`

阶段顺序固定为：

1. `你本人多机治理内核`
2. `团队同构安装`
3. `客户 clone 网络`

## 四层蓝图

### 1. Purpose Layer

唯一顶层目标：`递归进化`

每个任务都必须同时回答两件事：

- 眼前结果是什么
- 下一轮能力、判断或治理质量提升了什么

### 2. Method Layer

唯一方法原则：`最小负熵优先`

决策顺序固定为：

1. 先降失真
2. 再增秩序
3. 最后提效率

### 3. Tool Layer

`AI大管家 = 工具的工具`

它治理的不是单一任务，而是：

- 技能
- 脚本
- 数据源
- 镜像面
- 写回链
- 人类治理边界

### 4. Deployment Layer

部署顺序固定为：

1. `你本人多机`
2. `团队同构安装`
3. `客户 clone 网络`

部署层回答的是：

- 同一个治理内核如何跨机器存在
- 同事如何复用同一治理语言
- clone 如何通过配置化隔离而不是复制底座

## 治理对象

系统长期统一治理 3 组对象：

### 1. 战略对象

- `goal`
- `theme`
- `strategy`
- `experiment`
- `workflow`

### 2. 运行对象

- `thread`
- `task`
- `decision`
- `action`
- `writeback`
- `datasource`
- `review-run`

### 3. 部署对象

- `operator_id`
- `machine_id`
- `instance_id`
- `clone_id`
- `memory_namespace`

其中：

- `instance_id` 表示某一台机器上的大管家实例
- `operator_id` 表示共同治理者
- `clone_id` 表示未来客户或角色化 clone
- `memory_namespace` 保证不同人、不同 clone、不同机器的记忆隔离

## 固定边界

下面这些边界是顶层固定边界，不属于某一轮实验约定：

- `镜像面不是本体`
  - Feishu、GitHub、cockpit、dashboard 都是镜像或前台，不是 canonical source。
- `卫星不是主机`
  - 卫星是部署拓扑中的执行器官，不承担最终真相、总控闭环和 canonical ownership。
- `实验不是宪法`
  - 某一轮 phase、代号、卡片、业务主线，只能放在实验说明里，不进入顶层本体语言。

## 黑色卫星的位置

`黑色卫星` 固定定义为部署拓扑中的 `加速执行器官`。

它负责：

- 清障
- 降噪
- support / verify
- repo-local evidence

它不负责：

- 治理内核定义
- 最终真相
- 总控闭环
- 主线替代

## 与当前 phase-1 的关系

当前仓库里的实验项目，是用来证明这套顶层蓝图不是纸上结构。

但两者必须分层理解：

- 本文回答：`AI大管家` 长期是什么
- phase-1 文档回答：当前这一轮拿什么证明它成立

当前最小闭环实验说明见：

- [ai-da-guan-jia-phase-1-minimum-closure-v1.md](/Users/liming/Documents/codex-ai-gua-jia-01/docs/ai-da-guan-jia-phase-1-minimum-closure-v1.md)

# 原力OS 总控台 + GitHub + Miaoda + 飞书多维表 一体化控制面蓝图

## Summary

- Goal: 把 `原力OS-AI大管家` 整理成一套可持续运转的统一控制面，让本体层、协同层、前台层、数据层和 clone 分装层使用同一套治理语言。
- Audience: `原力OS` 共同治理者、Miaoda 前台维护者、Feishu 表结构维护者、GitHub 协同维护者
- Time grain: day

## Official Boundary

- OpenAPI-capable: bitable app metadata, tables, fields, records, views, dashboard list, dashboard copy
- Manual or template-driven: dashboard card creation, widget binding, canvas layout placement
- Canonical truth: local repository and runtime evidence

## Architecture Layers

### 本体层

- 本地 canonical 与治理协议
- 负责真相、边界、闭环、进化

### 协同层

- GitHub 负责 issue、project、PR、commit、artifact mirror
- 只做协同，不承担真相

### 前台层

- Miaoda 负责总控驾驶舱与日常操作入口
- 只做状态显示、入口分发和收口

### 数据层

- Feishu 多维表负责结构化事实、clone 分装、任务追踪和协作镜像
- 通过稳定 source view 供前台绑定

### 分装层

- internal colleague clone
- strategic partner clone
- client clone
- 所有 clone 共用一个共享核心，差异只体现在配置、边界和可见性

## Top Row Cards

- 当前健康吗？
- 当前最该盯什么？
- 当前阻塞与风险是什么？
- 本周进化了什么？

## Middle Row Cards

- 当前运行态是什么？
- 当前 clone 态是什么？
- 当前治理态是什么？

## Bottom Row Cards

- 哪些事项需要人类点击？
- 哪些事项需要审批？
- 哪些事项需要回写飞书？

## Source Tables

- `L0_运行态总控`
- `战略任务追踪`
- `clone governance base`
- `AI实例注册表`
- `能力提案表`
- `风险与决策表`
- `原力OS进化编年史`
- `治理成熟度评估`
- `三方协同日志`
- `记忆层健康度`

## Test Plan

1. 验证总控台四卡是否覆盖核心判断
2. 验证 Miaoda 首屏是否能在不滚动的情况下看到当前控制态
3. 验证 Feishu source view 是否能统一映射任务 / clone / 治理三类对象
4. 验证 GitHub issue / PR / artifact mirror 是否形成闭环
5. 验证 clone 分装是否只改配置，不改共享核心

## Design Notes

- dashboard 不是唯一界面，Miaoda 才是前台驾驶舱
- Feishu 不是本体，GitHub 也不是本体
- 每个卡片只回答一个管理问题
- 每个卡片都应该有明确的后续动作队列

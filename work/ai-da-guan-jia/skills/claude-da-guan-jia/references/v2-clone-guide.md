# 同事复制（V2-CLONE）激活引导

## 五层协作模型

```
第1层：Claude 策略大脑 — 聊策略、出Task Spec（贵，只负责想）
第2层：Codex 执行器 — 接收Task Spec干活（便宜且灵）
第3层：飞书多维表 — 数据沉淀层
第4层：妙搭驾驶舱 — 可视化层（调飞书多维表）
第5层：GitHub 归档 — Codex干完活自动归档，策略大脑质检
```

## 核心工作法：「两头怼」

人在两头——把Claude输出贴给Codex执行，把Codex结果贴回Claude质检。
中间全是AI闭环，人不介入流程。

## 六步业务闭环

```
Step 1: 梳理业务全景（物料全丢进Claude知识库，口语聊）
Step 2: 拆解作业流节点（大场景→子场景→作业流→节点）
Step 3: 为每个节点匹配Skill（遍历解法后固定）
Step 4: 定义数据表结构（AI定义，不要自己定义）
Step 5: Codex建飞书多维表（傻瓜式复制粘贴Task Spec）
Step 6: 搭建妙搭驾驶舱（Codex执行）
```

## 起项目三步法（明哥心法）

```
Step 1: 建模（聊透再做）— "东北表妹聊天法"
Step 2: 搭表（让AI站在用户角度讲给你听）— 文档标准：用户一看就懂=好
Step 3: 看板（必须好看）— 丑就不对，怼回去改
```

## 三条铁律

1. 聊透了再做（别浪费小号）
2. 文档必须人能看、看得爽
3. 看板必须好看、审美标准越严苛越精炼

## 关键约束

- 7天目标只给内部同事第一轮，不把partner/client塞进第一波
- Day 4 dogfood验证节点必须保留
- Skill的canonical source是`yuanli-os-skills-pack`，`yuanli-os-ops`只消费不发明
- 不复用`TS-V2-*`编号，防止和roadmap/INIT已有编号撞车
- `yuanli-os-ops`是已存在的repo，不要写"创建仓库"

## 当前 Task 状态

| Task ID | 名称 | 状态 |
|---------|------|------|
| PROJ-V2-CLONE-01 | 运行层 Bundle Hardening | ⏳ 待编写Spec |
| PROJ-V2-CLONE-02 | COLLEAGUE-INIT 激活引导 | ⏳ 待编写Spec |
| PROJ-V2-CLONE-03 | Personalization Plugin | ⏳ pilot后再决定 |

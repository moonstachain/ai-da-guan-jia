# 原力治理主图 v1

## Summary

- 本轮范围锁定为 `加端账资产`：在 `space -> subject -> module -> task -> thread` 五级主干上，补 `endpoint / account / asset` 三类治理锚点。
- 本图保持 `canonical-first`：先对齐 repo 内现有 canonical / derived 工件，再给出可读表达，不做展示层包装，不改运行时脚本。
- `thread-adagj-001 / 完成原力治理主图` 继续作为 `external_active_thread` 试点样例使用；本轮只挂接，不做 canonical 迁移。

## Backbone

```text
space-personal-zero
└─ subject-hay2045
   ├─ module-governance
   │  ├─ task-yuanli-os-mainline-closure-v1
   │  │  └─ thread-yuanli-os-mainline-closure-v1
   │  └─ task-adagj-001 (external_active_thread sample)
   │     └─ thread-adagj-001
   └─ endpoint-local-workstation
      └─ account-github
         └─ asset-db2ee9207e (governance-dashboard.md)
```

## 顶层治理主干

| 节点 | 角色 | 主要回指 |
| --- | --- | --- |
| `space-personal-zero` | 当前主机侧治理实例 | `canonical/entities/spaces.json#space-personal-zero` |
| `subject-hay2045` | 当前共同治理者 / owner | `canonical/entities/subjects.json#subject-hay2045` |
| `module-governance` | G1 治理控制模块 | `canonical/entities/operating_modules.json#module-governance` |
| `task-yuanli-os-mainline-closure-v1` | 当前 G1 主线收口总控母任务 | `canonical/entities/tasks.json#task-yuanli-os-mainline-closure-v1` |
| `thread-yuanli-os-mainline-closure-v1` | 当前 G1 主线收口总控线程 | `canonical/entities/threads.json#thread-yuanli-os-mainline-closure-v1` |
| `task-adagj-001` | “完成原力治理主图”试点任务投影 | `derived/morning-review/morning-review-input.json#task-adagj-001` |
| `thread-adagj-001` | “完成原力治理主图”试点线程投影 | `derived/morning-review/morning-review-input.json#thread-adagj-001` |

主干上的两个任务层承担不同职责：

- `task-yuanli-os-mainline-closure-v1` / `thread-yuanli-os-mainline-closure-v1` 是当前已经完成 intake 并挂回 repo canonical 的 G1 总控程序。
- `task-adagj-001` / `thread-adagj-001` 是 OSA 与 `external_active_thread` 语义下的治理主图试点样例，用来证明主图可以承接不做 canonical 迁移的外部活跃线程。

## 第二层锚点

| 节点 | 角色 | 为什么纳入 v1 |
| --- | --- | --- |
| `endpoint-local-workstation` | 主机侧本地工作站 | 证明治理不是纯抽象层，能回到当前执行终端。 |
| `account-github` | 当前治理链中的代表性平台账号 | 证明主图可以接到具体账号控制面。 |
| `asset-db2ee9207e` / `governance-dashboard.md` | 当前治理策略工件资产 | 证明资产层既能支撑模块，也能支撑账号，不只是附件列表。 |

这条锚点链有两条同时成立的关系：

- `subject-hay2045 -> endpoint-local-workstation -> account-github`
- `asset-db2ee9207e -> account-github` 且 `asset-db2ee9207e -> module-governance`

## 关键关系层

只保留支撑主图成立的关键关系，不展开全量关系表：

| 关系类型 | 样例 relation_id | 说明 |
| --- | --- | --- |
| `space_contains_subject` | `rel-5377ac85e0` | 当前实例包含当前共同治理者。 |
| `subject_responsible_for_module` | `rel-e1c127199f` | 当前共同治理者直接负责治理模块。 |
| `task_targets_module` | `rel-2fb5e1cf3c` / `rel-3799e6a6b4` | 无论是 repo_intake 主线，还是 external_active_thread 试点，都指向 `module-governance`。 |
| `task_belongs_to_thread` | `rel-6e7d6b2f88` / `rel-f3ceb43990` | 任务与线程成对收束。 |
| `thread_tracks_space` | `rel-85b121941a` / `rel-1d043f14b6` | 线程最终都要挂回具体 space。 |
| `subject_owns_endpoint` | `rel-afb217567f` | 当前 owner 拥有主机工作站。 |
| `subject_controls_account` | `rel-51323d8257` | 当前 owner 控制 GitHub 主账号。 |
| `endpoint_hosts_account` | `rel-5886315167` | GitHub 主账号驻留在本地工作站执行链上。 |
| `asset_supports_account` | `rel-1127a374cb` | 策略工件资产支撑 GitHub 账号治理。 |
| `asset_supports_module` | `rel-da64f09a64` | 同一资产也支撑治理模块本身。 |

## Validation Paths

### 1. G1 主线总控路径

`space-personal-zero -> subject-hay2045 -> module-governance -> task-yuanli-os-mainline-closure-v1 -> thread-yuanli-os-mainline-closure-v1`

这条路径证明当前 repo intake 主线已经是治理模块下的正式总控骨架。

### 2. 治理主图试点路径

`space-personal-zero -> subject-hay2045 -> module-governance -> task-adagj-001 -> thread-adagj-001`

这条路径证明 `external_active_thread` 也能被治理主图吸收为可验证样例，而不需要先迁移成新的 canonical 任务模式。

### 3. 端点-账号-资产锚点路径

`subject-hay2045 -> endpoint-local-workstation -> account-github -> asset-db2ee9207e`

同时保留 `asset-db2ee9207e -> module-governance`，用来说明同一资产可同时服务“模块层”和“账号层”。

## 验真结论

- 一级主干已经能回指到 repo 内现有 canonical 或 derived 工件。
- 第二层锚点已经覆盖 `endpoint / account / asset` 三类代表性对象。
- 至少 1 条试点线程样例已经能沿 `task -> module -> subject -> space` 追回到真实来源。

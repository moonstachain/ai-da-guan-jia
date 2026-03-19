# Codex 闭环协议

版本：`v1.0+closure-hardening`

这份协议是仓库内的永久规范，用来保证每次 Task Spec 执行后都能自动闭环、自动验真、自动修复飞书不一致。

## 原则

- 任何 Task Spec 执行完毕后，Codex 必须先验真，再 claim closure。
- 验真失败时，优先自动修复飞书或本地闭环产物，而不是直接宣告完成。
- `verification_result.json` 是 closure evidence，不是可选附件。

## 标准闭环链

### Step 1：补写或校正飞书战略任务追踪表

优先处理这批闭环修复源：

- `references/codex-closure-strategic-task-patch-4.json`

对每个 `task_id`：

- 如果表里没有这条记录，自动 `batch_create`
- 如果表里已有但状态或字段漂移，自动 `batch_update`
- `TS-KB-07-EVIDENCE` 必须同步到 `已完成`
- `TS-WF-HARDEN-01`、`TS-V2-PHASE0`、`TS-TASK-SYNC` 必须补齐

### Step 2：运行后任务验真脚本

默认执行：

```bash
python3 scripts/post_task_verify.py --full-audit
```

单任务精确验证时：

```bash
python3 scripts/post_task_verify.py --task-id TS-XXX --expected-status 已完成
```

脚本职责：

- 读取飞书战略任务追踪表
- 自动修复可修复的缺失 / 漂移记录
- 生成 `verification_result.json`

### Step 3：输出 verification_result.json

验证结果必须写入：

```text
artifacts/ai-da-guan-jia/runs/YYYY-MM-DD/<run-id>/verification_result.json
```

只有当该文件存在且 `all_aligned=true` 时，Codex 才能 claim closure。

## 与 post-task-sync.sh 的关系

- `post_task_verify.py` 负责飞书一致性与 closure 验真
- `post-task-sync.sh` 负责 git commit + push
- 正确顺序是：先验真，再同步，再 claim closure

## 人类边界

- 人类不应该再被要求手动补飞书表来完成这个闭环
- 只有当自动修复失败或大范围漂移时，才需要人工介入

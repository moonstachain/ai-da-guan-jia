# Codex Task Spec: 创建 yuanli-os-claude 仓库

> **Round**: R0 (bootstrap)
> **Target**: 在 moonstachain GitHub 账号下创建新仓库 `yuanli-os-claude`

## Objective

在 GitHub 上创建 `moonstachain/yuanli-os-claude` 仓库，初始化完整的目录结构和所有启动文件。

## 执行步骤

将以下命令在你的本地终端（有 GitHub 权限的机器上）执行：

```bash
# 1. 在 GitHub 上创建仓库（需要 gh CLI 已登录）
gh repo create moonstachain/yuanli-os-claude \
  --public \
  --description "原力OS 策略中枢：Claude 战略大脑 × Codex 执行引擎 × 人类共同治理者" \
  --clone

# 2. 进入仓库
cd yuanli-os-claude

# 3. 把 Claude 生成的文件包解压到仓库（从下载的 zip 中获取）
# 或者直接把文件逐个复制进来

# 4. 提交初始化
git add -A
git commit -m "feat: bootstrap yuanli-os-claude strategy hub

- README.md: 仓库定位与使用说明
- STRATEGY.md: Claude 对原力OS的完整战略理解 v1
- schemas/: 四个可执行 JSON Schema
  - governance-checkpoint.schema.json (六判断 gate)
  - codex-task-spec.schema.json (Codex 任务合同)
  - evolution-log.schema.json (进化记录)
  - skill-manifest.schema.json (技能清单)
- references/ecosystem-map.md: 生态系统地图
- codex-specs/: Task Spec 存放目录
- evolution-log/: 进化记录存放目录
- strategy/: 每轮战略产物存放目录"

git push origin main
```

## 或者用 Codex 直接执行

把以下内容粘贴到 Codex：

```
在 moonstachain/yuanli-os-claude 仓库中（如果不存在请先创建），
初始化以下文件结构，所有文件内容从附带的文件包中获取：

yuanli-os-claude/
├── README.md
├── STRATEGY.md
├── schemas/
│   ├── governance-checkpoint.schema.json
│   ├── codex-task-spec.schema.json
│   ├── evolution-log.schema.json
│   └── skill-manifest.schema.json
├── references/
│   └── ecosystem-map.md
├── codex-specs/
│   └── .gitkeep
├── evolution-log/
│   └── .gitkeep
├── strategy/
│   └── .gitkeep
└── scripts/
    └── .gitkeep

提交信息：feat: bootstrap yuanli-os-claude strategy hub
```

## Acceptance Criteria

- [ ] 仓库在 GitHub 上可访问
- [ ] README.md 正确显示
- [ ] 四个 JSON Schema 文件格式有效
- [ ] STRATEGY.md 完整包含原力OS战略理解
- [ ] 所有目录结构就位

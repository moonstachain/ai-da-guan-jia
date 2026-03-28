# AI大管家-新环境复用说明

这份说明是给同事看的“新电脑从零复用 AI大管家”操作手册。

目标不是把某个 skill 文件夹拷过去，而是把一整套能力恢复出来，让新环境能够：

- 识别 AI大管家的核心 skill
- 读懂本地 canonical 记忆
- 找到当前运行态 current
- 进入日常协作和闭环
- 能在 GitHub / Feishu / 浏览器这些镜像面上继续协作，但不把它们误当真相源

如果你先想看机器侧的完整迁移目录，请先看：

- [new-machine-migration-manifest.md](/Users/liming/Documents/codex-ai-gua-jia-01/artifacts/ai-da-guan-jia/migration/new-machine-migration-manifest.md)

如果你先想理解日常怎么跟 AI大管家协作，再看：

- [AI大管家协作手册.md](AI大管家协作手册.md)
- [AI大管家-个人决策台启用说明.md](AI大管家-个人决策台启用说明.md)

---

## 0. 一句话判断

新环境能否“复用 AI大管家”，关键不在某个网页界面，而在四层东西是否都恢复：

1. `记忆 / 配置`
2. `canonical workspace`
3. `current runtime artifacts`
4. `GitHub / Feishu / 浏览器登录态`

只把 GitHub 仓库 clone 下来，通常只能恢复一部分代码和文档，**不能自动恢复当前状态**。  
如果要真正复用能力，必须把本地 canonical、current、auth 一起恢复。

---

## 1. 先准备给同事的材料

如果你要让同事独立搭起来，最好一次性给他这四类材料：

### 1.1 GitHub 信息

至少要有下面这些仓库访问权：

- `git@github.com:moonstachain/ai-da-guan-jia.git`
- `git@github.com:moonstachain/yuanli-os-claude.git`

推荐一起带上：

- `git@github.com:moonstachain/os-yuanli.git`
- `git@github.com:moonstachain/yuanli-os-skills-pack.git`
- `git@github.com:moonstachain/yuanli-os-ops.git`

### 1.2 本地 canonical 包

GitHub 不一定包含所有 runtime current，所以最好再给一个本地包，至少包含：

- `~/.codex/memory.md`
- `~/.codex/config.toml`
- `~/.openclaw/openclaw.json`
- `yuanli-os-claude/CLAUDE-INIT.md`
- `yuanli-os-claude/CLAUDE-INIT-TEMPLATE.md`
- `artifacts/ai-da-guan-jia/`
- `work/ai-da-guan-jia/`

### 1.3 登录态和权限

这些必须单独准备，不能指望仓库自动补齐：

- GitHub SSH key 或 `gh auth` 登录态
- Feishu / Lark 登录态
- 浏览器 profile / cookie
- 需要时的 OpenClaw / OpenAI / OpenCLI 环境变量

### 1.4 你给同事的原则提醒

请明确告诉他：

- GitHub 是协作镜像，不是 runtime truth
- Feishu 是前台镜像，不是 canonical truth
- local artifacts 才是最终事实源
- 出现权限 / 登录 / 付费 / 不可逆发布时，要停下来问人

---

## 2. 推荐的恢复顺序

如果同事从零开始，建议按这个顺序做。

### Step 1：先把 GitHub 访问打通

先确认他能访问仓库：

```bash
gh auth status
git remote -v
```

如果 `gh` 没登录，就先登录；如果仓库没有权限，就先补权限，再继续。

### Step 2：按依赖顺序 clone 仓库

推荐 clone 顺序：

1. `os-yuanli`
2. `yuanli-os-claude`
3. `yuanli-os-skills-pack`
4. `ai-da-guan-jia`
5. `yuanli-os-ops`

如果时间紧，最小起步只要：

- `ai-da-guan-jia`
- `yuanli-os-claude`

### Step 3：恢复本地工作目录

把仓库放到同一个稳定目录里，确保下面这些路径都能找到：

- `work/ai-da-guan-jia`
- `artifacts/ai-da-guan-jia`
- `yuanli-os-claude`

恢复完先确认下面这些文件能打开：

- `work/ai-da-guan-jia/SKILL.md`
- `work/ai-da-guan-jia/AI大管家协作手册.md`
- `yuanli-os-claude/CLAUDE-INIT.md`

### Step 4：恢复记忆和配置

先把以下文件放回新机器对应位置：

- `~/.codex/memory.md`
- `~/.codex/config.toml`
- `~/.openclaw/openclaw.json`

然后确认 `CLAUDE-INIT.md` 能读到当前阶段摘要、仓库关系和真相源边界。

### Step 5：恢复 current artifacts

最重要的是这些目录要回到位：

- `artifacts/ai-da-guan-jia/strategy/current`
- `artifacts/ai-da-guan-jia/clones/current`
- `artifacts/ai-da-guan-jia/governance/current`
- `artifacts/ai-da-guan-jia/hub/current`
- `artifacts/ai-da-guan-jia/heartbeat/current`
- `artifacts/ai-da-guan-jia/feishu`

这些目录是“现在系统正在怎么跑”的证据。

### Step 6：恢复登录态

恢复并验证：

- GitHub
- Feishu / Lark
- 浏览器 profile
- 需要时的 OpenAI / OpenCLI / OpenClaw 认证

这一步非常关键，因为很多 skill 只是“装上了”，但没有 auth 就不能真正用。

---

## 3. GitHub-first 启动法

如果同事只有 GitHub 信息，先用 GitHub 建立骨架，再用本地 canonical 包补血。

### 3.1 先 clone 主仓库

```bash
git clone git@github.com:moonstachain/ai-da-guan-jia.git
cd ai-da-guan-jia
```

clone 后先看：

```bash
git remote -v
ls
```

### 3.2 再补启动记忆仓库

```bash
git clone git@github.com:moonstachain/yuanli-os-claude.git
```

如果同事要跟整个原力OS 生态一起工作，再补：

```bash
git clone git@github.com:moonstachain/os-yuanli.git
git clone git@github.com:moonstachain/yuanli-os-skills-pack.git
git clone git@github.com:moonstachain/yuanli-os-ops.git
```

### 3.3 先不要把 GitHub 当真相源

GitHub 能告诉你：

- 仓库有没有权限
- 代码和文档大概长什么样
- 可不可以做协作同步

GitHub 不能自动告诉你：

- 当前 runtime current 里到底发生了什么
- Feishu 的 live 表是不是最新
- `~/.codex/memory.md` 里存了什么
- 你当前是否已经恢复了登录态

所以 GitHub 只能负责“搭骨架”，不能负责“自动复活系统”。

---

## 4. 本地 canonical 恢复法

如果你已经把 GitHub 骨架搭起来了，下面是必须恢复的本地核心。

### 4.1 先恢复 memory

把 `~/.codex/memory.md` 放好后，先检查三件事：

- 有没有 canonical root
- 有没有 restore order
- 有没有明确写出 GitHub / Feishu 只是镜像

### 4.2 再恢复 Claude 启动记忆

确认下面两个文件都在：

- `yuanli-os-claude/CLAUDE-INIT.md`
- `yuanli-os-claude/CLAUDE-INIT-TEMPLATE.md`

这两个文件的作用不是 runtime ledger，而是启动记忆和分发口径。

### 4.3 再恢复 AI大管家的主工作区

重点恢复：

- `work/ai-da-guan-jia/SKILL.md`
- `work/ai-da-guan-jia/AI大管家协作手册.md`
- `work/ai-da-guan-jia/AI大管家-个人决策台启用说明.md`
- `work/ai-da-guan-jia/AI大管家-内部同事版第一闭环MVP启用说明.md`
- `work/ai-da-guan-jia/AI大管家-同事协作成长路径说明.md`
- `work/ai-da-guan-jia/references/`
- `work/ai-da-guan-jia/scripts/`
- `work/ai-da-guan-jia/workflows/`
- `work/ai-da-guan-jia/signals/`

这些内容是同事实际工作的说明书，不只是参考资料。

---

## 5. 先恢复哪些能力

如果同事想尽快“能干活”，建议先恢复这 3 层。

### 5.1 第一层：技能识别

先让系统能识别出 AI大管家相关技能。

验证方法：

```bash
python3 scripts/ai_da_guan_jia.py inventory-skills
```

如果这个入口在某个环境里坏了，就不要硬磨，直接改用：

- 现成 inventory snapshot
- 本地 `SKILL.md`
- `artifacts/ai-da-guan-jia/inventory/`

### 5.2 第二层：current 状态

先确认以下对象可读：

- `strategy/current`
- `clones/current`
- `governance/current`
- `heartbeat/current`

这几层能读，说明系统不仅“有文档”，而且“知道自己现在在哪”。

### 5.3 第三层：日常闭环

先验证一条最小闭环：

1. route
2. evolution
3. worklog
4. Feishu dry-run
5. Feishu apply
6. GitHub mirror

这条链能跑通，才算 AI大管家真的复用起来了。

---

## 6. 你应该怎样带同事上手

你可以直接把下面这段口径给他：

> 你先不要自己发明流程。  
> 先把 GitHub 仓库 clone 好，再把本地 canonical 包放回去，最后确认 current 和登录态。  
> 如果你只看 GitHub 页面，你会缺 runtime current；如果你只看 Feishu 页面，你会缺 canonical；如果你只看脑子里的记忆，你会缺验证。  
> AI大管家要复用成功，必须四层一起恢复。

### 推荐带教顺序

1. 先让他读 `AI大管家协作手册.md`
2. 再让他读 `AI大管家-个人决策台启用说明.md`
3. 再让他看 `新电脑迁移总表`
4. 最后带他跑一次最小闭环

---

## 7. 日常怎么用

新环境搭好后，推荐同事按这个节奏用。

### 早上

用 AI大管家定今天的 north star：

```text
今天最重要的是 X，帮我判断先做什么、哪些该延后、需要调用哪些 skill、哪些地方必须等我批准。
```

### 白天

只看高影响待批，不要把自己重新拉回到手工拆任务模式。

### 晚上

做一次 recap：

- 今天有没有误路由
- 哪些动作本来可以复用
- 哪些地方不该再打扰人

### 发生高影响动作时

以下动作必须停下来问人：

- 登录
- 授权
- 付款
- 不可逆发布
- 不可逆删除

---

## 8. 验收标准

如果同事按这份说明搭完，新环境至少要满足以下条件：

- 能读到 `~/.codex/memory.md`
- 能读到 `yuanli-os-claude/CLAUDE-INIT.md`
- 能打开 `work/ai-da-guan-jia/SKILL.md`
- 能识别 AI大管家 core skills
- 能读到 `artifacts/ai-da-guan-jia/strategy/current`
- 能读到 `artifacts/ai-da-guan-jia/clones/current`
- 能完成一次 `route -> evolution -> worklog` 的最小闭环
- 能对 Feishu 做 dry-run
- 能把结果镜像到 GitHub

如果这些都做到了，就说明 AI大管家的能力已经在新环境里真正复用了。

---

## 9. 常见卡点

### 卡点 1：只有 GitHub，没有 current

这很常见。  
解决方式：补本地 canonical 包，不要只盯 GitHub 页面。

### 卡点 2：有文档，但不认识技能

解决方式：

- 先确认 `.codex/skills` 是否可用
- 再确认 `skill-creator` / `skill-installer`
- 再看 `work/ai-da-guan-jia/SKILL.md`

### 卡点 3：Feishu 看起来空

解决方式：

- 先确认是不是打开了旧表 / 旧 Base
- 再确认是不是 current artifacts 没回放
- 最后再做 Feishu 回读

### 卡点 4：GitHub 有仓库，但本地脚本入口坏了

解决方式：

- 不要依赖坏入口继续磨
- 直接使用 workspace canonical 里的脚本和文档
- 用 `inventory snapshot` 和 `current artifacts` 先把状态恢复

### 卡点 5：不知道该问你什么

解决方式：只问一个最小问题，不要一次问一串。

正确问法：

- “这个仓库我先 clone 哪个？”
- “这个 current 是不是应该优先恢复？”
- “这个步骤是我点，还是你来做？”

---

## 10. 你可以直接复制给同事的简版开场

```md
你先按这个顺序来：
1. clone GitHub 仓库
2. 恢复 ~/.codex/memory.md 和 CLAUDE-INIT
3. 恢复 work/ai-da-guan-jia 和 artifacts/ai-da-guan-jia/current
4. 登录 GitHub / Feishu / 浏览器
5. 跑一次 inventory 和最小闭环

记住：
- GitHub 是镜像，不是 runtime truth
- Feishu 是前台，不是真相源
- local canonical 才是最终事实

如果卡在登录、授权、付款、不可逆发布/删除，就停下来问我。
```

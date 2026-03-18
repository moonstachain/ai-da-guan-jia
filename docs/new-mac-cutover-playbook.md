# 新 M5 Mac 主力切换与远控迁移 Playbook

这份 playbook 把 `新 M5 Mac -> 主机切换` 固定成一条可验证、可回退的迁移链。默认目标不是“双主并跑”，而是让新 Mac 通过验真后接棒为默认主控，旧 Mac 再降级为 fallback。

## 默认架构

- 主力切换：`新 M5 Mac`
- 控制方式：`SSH + Screen Sharing + 可选 Remote Application Scripting`
- 迁移深度：`完整搬家`
- 切主原则：`先恢复，再验真，最后切主`

## 为什么用这套远控架构

- `Remote Login (SSH)` 负责无头执行：bundle 恢复、doctor、inventory、route、tests、sample verify
- `Screen Sharing` 负责可见控制：登录态恢复、浏览器类技能、需要你看到界面的阶段
- `Remote Application Scripting` 只在后续确实要跨机发 Apple events 控应用时再开，不是 day-1 硬依赖
- 默认不要同时打开 `Remote Management`，因为这会和 `Screen Sharing` 的日常使用模型冲突；只有未来明确需要 Apple Remote Desktop 多机管理，再升级

## 阶段 0：旧 Mac 继续做 canonical source

在新 Mac 通过全部验真前，旧 Mac 始终是真相源。

旧机准备顺序：

1. 推送一等公民 repo
   - 当前工作区私有仓库
   - `ai-da-guan-jia`
   - `skill-trainer-recursive`
   - `skills-mirror`
2. 导出私有 skills mirror
3. 生成 restore bundle
4. 留存 bundle metadata 与恢复口令

推荐命令：

```bash
python3 scripts/export_skills_mirror.py --source "$HOME/.codex/skills" --destination "$HOME/Documents/skills-mirror" --clean
python3 scripts/build_restore_bundle.py --manifest migration-manifest.json --output-dir output/migration --include-history --encrypt
```

这一步结束后，至少应确认：

- `output/migration` 下存在最新的 `.tar.gz.enc`
- `bundle-metadata.json` 中包含：
  - `secret/codex/auth.json`
  - `secret/codex/config.toml`
  - `secret/codex/skills-raw/`
  - `secret/workspace/output/`
  - `secret/workspace/artifacts/`
  - `history/codex/state_5.sqlite`
  - `history/codex/sessions/`
  - `history/codex/archived_sessions/`
  - `history/codex/shell_snapshots/`

## 阶段 1：新 Mac 基础环境与 Sharing 设置

### 必装环境

- `Codex.app`
- `git`
- `Homebrew`
- `python3 >= 3.11`
- `node >= 20`

### 系统设置

在新 Mac 上开启：

- `Remote Login`
- `Screen Sharing`

可选开启：

- `Remote Application Scripting`

默认不要开启：

- `Remote Management`

## 阶段 2：新 Mac 远控探活

在旧 Mac 上先做一次局域网探活，确认新 Mac 具备基础条件再传 bundle。

```bash
scripts/probe_new_mac_remote.sh --host <lan-host>
```

如果你希望看机器可读结果：

```bash
scripts/probe_new_mac_remote.sh --host <lan-host> --json
```

这一步应能清楚区分：

- 主机不可达
- SSH 不通
- SSH 服务可达但认证未打通
- 缺 `Codex.app`
- 缺 `git / python3.11+ / node20+`

## 阶段 3：版本层与恢复包传输

### 版本层

在新 Mac 上准备：

- 工作区私有仓库
- `skills-mirror`
- 如需自动拉取一等公民 skill repo，可在恢复时设 `CLONE_VERSIONED_ASSETS=1`

### 恢复包

将解密并解压后的 bundle 根目录放到：

```bash
$HOME/Documents/codex-secret-bundle
```

推荐方式：

- 外接 SSD
- AirDrop
- 局域网直传

## 阶段 4：新 Mac 执行恢复

在新 Mac 上进入工作区根目录：

```bash
cd "$HOME/Documents/codex-ai-gua-jia-01"
export SKILLS_MIRROR_ROOT="$HOME/Documents/skills-mirror"
export SECRET_BUNDLE_ROOT="$HOME/Documents/codex-secret-bundle"
export CLONE_VERSIONED_ASSETS=1
./bootstrap-new-mac.sh
```

恢复完成后：

- 打开 Codex.app 并重新登录
- 配置 GitHub SSH key 或 PAT
- 重新登录 Feishu
- 重新登录 Get笔记

说明：

- `skills-raw` 会把 skill 自带的浏览器 profile / state 一起迁过去
- 但 GitHub、Feishu、Get笔记 仍按“可能需要重新登录”处理，不把旧登录态硬当成 100% 可复用

## 阶段 5：旧 Mac 远程触发验真

旧 Mac 通过 SSH 远程跑新 Mac 的恢复验真：

```bash
scripts/remote_verify_new_mac.sh --host <lan-host> --workspace-root "$HOME/Documents/codex-ai-gua-jia-01"
```

如果想把浏览器型 skill 的 smoke test 也挂进去，可额外传一个命令：

```bash
scripts/remote_verify_new_mac.sh \
  --host <lan-host> \
  --workspace-root "$HOME/Documents/codex-ai-gua-jia-01" \
  --browser-smoke-command 'python3 "$HOME/.codex/skills/ai-da-guan-jia/scripts/ai_da_guan_jia.py" route --prompt "帮我学一个陌生 API，先读官方说明书和攻略，再决定怎么做"'
```

默认验真包括：

- `python3 ~/.codex/skills/ai-da-guan-jia/scripts/doctor.py`
- `python3 scripts/check_codex_mcp.py`
- `inventory-skills`
- `python3 -m unittest discover -s tests`
- sample `route`

建议额外补一条 GUI/登录态验真：

- 至少一条浏览器型 skill 能进入目标站点
- 或明确只差重新登录

## 阶段 6：切主判定

只有满足下面条件，才把新 Mac 切为主机：

- `probe_new_mac_remote.sh` 返回 `ready`
- `remote_verify_new_mac.sh` 成功
- `doctor.py` 通过
- `inventory-skills` 数量接近当前口径
- 单元测试通过
- sample `route` 成功
- 至少一条浏览器型 skill 被验证为：
  - 可进入目标站点
  - 或仅缺重新登录

## 切主后策略

切主完成后：

- 新 Mac 成为默认工作机与默认主控
- 旧 Mac 保留为 fallback
- 旧 Mac 不再默认参与日常 hub 主线
- 如果后续要双机协同，再把旧 Mac 显式注册成独立 satellite，而不是隐式双主

## 回退条件

以下任一条件成立，都不要切主：

- SSH 还没打通
- `Codex.app` 缺失
- `python3` 或 `node` 版本不达标
- `doctor.py` 未通过
- `inventory-skills` 明显低于当前口径
- 单元测试失败
- sample `route` 失败
- 浏览器型 skill 无法进入目标站点，且不是明确可恢复的登录态问题

此时处理方式固定为：

- 旧 Mac 继续保持主机身份
- 新 Mac 作为恢复中的候选机继续补环境
- 修复后重跑：
  - `scripts/probe_new_mac_remote.sh`
  - `scripts/remote_verify_new_mac.sh`

## 建议顺序

如果你要最稳地做这次切换，建议顺序就是：

1. 旧 Mac 导出 mirror + 生成 `--include-history --encrypt` bundle
2. 新 Mac 开 `Remote Login` 和 `Screen Sharing`
3. 旧 Mac 跑 `probe_new_mac_remote.sh`
4. 新 Mac 拉版本层并运行 `bootstrap-new-mac.sh`
5. 旧 Mac 跑 `remote_verify_new_mac.sh`
6. 验真全过后切主
7. 旧 Mac 降级为 fallback

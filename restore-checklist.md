# 新 Mac 恢复清单

这个清单把迁移分成三层：`GitHub 私有版本层`、`本地加密恢复包`、`可选历史档案层`。标准以 `./verify-restore.sh` 通过为准，不以“文件已经拷过去”为准。

## 旧 Mac 出发前

1. 处理一等公民仓库。
   - `git -C "$HOME/.codex/skills/ai-da-guan-jia" status --short`
   - 提交并推送 `ai-da-guan-jia` 当前改动。
   - `git -C "$HOME/.codex/skills/skill-trainer-recursive" status --short`
   - 如有需要，同步推送 `skill-trainer-recursive`。
2. 导出私有 `skills-mirror` 仓库内容。
   - 先准备一个空目录作为镜像仓库工作区，例如 `"$HOME/Documents/skills-mirror"`。
   - 运行 `python3 scripts/export_skills_mirror.py --source "$HOME/.codex/skills" --destination "$HOME/Documents/skills-mirror" --clean`。
   - 在该目录内初始化或关联私有 GitHub 仓库并推送。
3. 让当前工作区具备私有仓库形态。
   - 当前 `.gitignore` 已排除 `node_modules/`、`output/`、`artifacts/` 和恢复包产物。
   - 如果当前目录尚未初始化 Git，请运行 `git init -b main`。
   - 关联私有远端后推送 `canonical/`、`derived/`、`docs/`、`distribution/`、`scripts/`、`specs/`、`tests/`、`work/`、`yuanli_governance/`、`automations/` 等版本化资产。
4. 生成本地加密恢复包。
   - 运行 `python3 scripts/build_restore_bundle.py --manifest migration-manifest.json --output-dir output/migration --encrypt`。
   - 若要把历史数据库也带上，加 `--include-history`。
   - 默认从环境变量 `RESTORE_BUNDLE_PASSPHRASE` 读取口令；未设置时会交互提示。
5. 做一次旧机侧验真。
   - 确认 `output/migration` 下同时出现 `.tar.gz` 和 `.tar.gz.enc`，或至少有 `.tar.gz.enc`。
   - 解压明文包或查看 `bundle-metadata.json`，确认包含 `secret/codex/auth.json`、`secret/codex/config.toml`、`secret/codex/skills-raw/`、`secret/workspace/output/` 等关键路径。

## 新 Mac 恢复顺序

1. 安装基础环境。
   - 安装 `Codex app`
   - 安装 `git`
   - 安装 `Homebrew Python 3.11+`
   - 安装 `Node 20 LTS`
2. 获取版本层资产。
   - 克隆当前工作区私有仓库到 `"$HOME/Documents/codex-ai-gua-jia-01"`。
   - 可选：把 `ai-da-guan-jia` 和 `skill-trainer-recursive` 直接克隆到 `"$HOME/.codex/skills/"`。
   - 克隆 `skills-mirror` 私有仓库到 `"$HOME/Documents/skills-mirror"`。
3. 本地传输并解密恢复包。
   - 推荐 `外接 SSD / AirDrop / 局域网直传`。
   - 将解密并解压后的 bundle 根目录放到 `"$HOME/Documents/codex-secret-bundle"`。
4. 执行恢复脚本。
   - 进入工作区根目录：`cd "$HOME/Documents/codex-ai-gua-jia-01"`
   - 设置环境变量：
     - `export SKILLS_MIRROR_ROOT="$HOME/Documents/skills-mirror"`
     - `export SECRET_BUNDLE_ROOT="$HOME/Documents/codex-secret-bundle"`
   - 如需脚本自动克隆一等公民仓库，再设置：
     - `export CLONE_VERSIONED_ASSETS=1`
   - 运行 `./bootstrap-new-mac.sh`
5. 重建登录态。
   - 打开 Codex 后重新登录
   - 重新配置 GitHub SSH key 或 PAT
   - 重新登录 Feishu
   - 重新登录 Get笔记

## GitHub 私有仓库操作

当前机器没有 `gh`。因此推荐两种方式：

1. 直接在 GitHub Web 新建私有仓库，然后在本地执行：

```bash
git init -b main
git remote add origin <private-repo-url>
git add .
git commit -m "Initial migration-ready workspace"
git push -u origin main
```

2. 在装好 `gh` 的机器上执行：

```bash
gh repo create <repo-name> --private --source . --remote origin --push
```

## 新 Mac 验真标准

1. `python3 "$HOME/.codex/skills/ai-da-guan-jia/scripts/doctor.py"` 返回 `OK`
2. `python3 scripts/check_codex_mcp.py` 通过
3. `python3 "$HOME/.codex/skills/ai-da-guan-jia/scripts/ai_da_guan_jia.py" inventory-skills` 返回接近当前的技能数量
4. `python3 -m unittest discover -s tests` 通过
5. `python3 "$HOME/.codex/skills/ai-da-guan-jia/scripts/ai_da_guan_jia.py" route --prompt "帮我学一个陌生 API，先读官方说明书和攻略，再决定怎么做"` 成功

如果你只恢复了版本层和秘密层，但没有恢复 `state_5.sqlite` 与旧 sessions，只要上面 5 项通过，就视为 `day-1 可用`。

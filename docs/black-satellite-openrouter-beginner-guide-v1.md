# 黑色卫星机 OpenRouter 新手上手说明

这份说明是给“先会用就行”的人写的。

你现在不用先懂什么是 SSH、CLI、Provider。你只要记住一句话：

`先打开黑色卫星机终端，再在里面用 codex / claude / gemini。`

## 先记 3 件事

1. 你现在最稳的入口，不是 VS Code 右边那个官方 `Codex` 面板。
2. 你现在能稳定用的是 `终端路线`，而且已经帮你做成了双击入口。
3. 这条路线走的是 `OpenRouter`，不是 OpenAI 官方 `cloud code / cloud tasks`。

## 你现在能在哪些地方用

### 1. 本机双击 `.command`

这是最推荐的方式。

你可以直接双击这些文件：

- `/Users/liming/Documents/codex-ai-gua-jia-01/scripts/打开黑色卫星机.command`
- `/Users/liming/Documents/codex-ai-gua-jia-01/scripts/查看当前模型.command`
- `/Users/liming/Documents/codex-ai-gua-jia-01/scripts/切到 GPT-5.4.command`
- `/Users/liming/Documents/codex-ai-gua-jia-01/scripts/切到 Claude.command`
- `/Users/liming/Documents/codex-ai-gua-jia-01/scripts/切到 Kimi.command`

### 2. 本机 Terminal

如果你愿意在自己的电脑上打开 `Terminal`，也可以用同一套入口。

### 3. 黑色卫星机自己的 VS Code 终端

如果你人就在黑色卫星机前面，打开那台机器上的 `VS Code`，再打开底部终端，也能直接用：

- `or-status`
- `or-use claude4`
- `or-use kimi`
- `codex`
- `claude`
- `gemini`

## 你现在不要在哪些地方用

### 1. VS Code 右侧官方 `Codex` 面板

现在不要用它。

原因很简单：它走的是 OpenAI 官方登录/官方 key 路线，不走 OpenRouter。

### 2. 你说的 `cloud code / cloud tasks`

现在也不要管它。

这不是这条 OpenRouter 路线的一部分。你这次先学会终端工作流就够了。

## 看图步骤版

下面每一步，我都会告诉你：

- 点哪里
- 成功时会看到什么
- 下一步做什么

### 步骤 1：先打开黑色卫星机

#### 你要做什么

1. 打开 `Finder`
2. 点屏幕最上面的 `前往`
3. 点 `前往文件夹...`
4. 粘贴这段路径：

```text
/Users/liming/Documents/codex-ai-gua-jia-01/scripts/
```

5. 找到 `打开黑色卫星机.command`
6. 双击它

#### 成功时会看到什么

会弹出一个 `Terminal` 窗口，然后你会看到类似下面这些字：

```text
[black-satellite] connected to ...
[black-satellite] current provider: ...
[black-satellite] current model: ...
liming@Mac codex-ai-gua-jia-01 %
```

看到这些，就说明已经连上了。

#### 下一步做什么

你已经进到黑色卫星机了。接下来你可以：

- 看当前模型
- 切模型
- 启动 `codex`
- 启动 `claude`
- 启动 `gemini`

### 步骤 2：查看当前模型

#### 最简单做法

双击：

```text
/Users/liming/Documents/codex-ai-gua-jia-01/scripts/查看当前模型.command
```

#### 成功时会看到什么

你会看到类似：

```text
current_claude_provider=or-gpt54
current_codex_provider=or-gpt54
current_gemini_provider=or-gpt54
claude_model=openai/gpt-5.4
codex_model=openai/gpt-5.4
gemini_model=openai/gpt-5.4
```

重点只看两类信息：

- `current_..._provider`
- `..._model`

#### 下一步做什么

如果你想换模型，就去下一步。

### 步骤 3：切到 Claude

#### 最简单做法

双击：

```text
/Users/liming/Documents/codex-ai-gua-jia-01/scripts/切到 Claude.command
```

#### 成功时会看到什么

你会看到类似：

```text
activated_provider=or-claude4
claude_model=anthropic/claude-sonnet-4
codex_model=anthropic/claude-sonnet-4
gemini_model=anthropic/claude-sonnet-4
```

看到 `activated_provider=or-claude4`，就说明切成功了。

#### 下一步做什么

现在你可以再打开“黑色卫星机终端”，然后输入：

```text
codex
```

或者：

```text
claude
```

### 步骤 4：切到 Kimi

#### 最简单做法

双击：

```text
/Users/liming/Documents/codex-ai-gua-jia-01/scripts/切到 Kimi.command
```

#### 成功时会看到什么

你会看到类似：

```text
activated_provider=or-kimi-k2
claude_model=moonshotai/kimi-k2
codex_model=moonshotai/kimi-k2
gemini_model=moonshotai/kimi-k2
```

#### 下一步做什么

如果你想切回默认模型，再双击：

```text
/Users/liming/Documents/codex-ai-gua-jia-01/scripts/切到 GPT-5.4.command
```

### 步骤 5：启动 codex / claude / gemini

这一步要在“已经打开的黑色卫星机终端”里做。

#### 启动 Codex

在终端里输入：

```text
codex
```

然后按回车。

成功时，你会看到 `Codex` 的终端界面出现。

#### 启动 Claude Code

在终端里输入：

```text
claude
```

然后按回车。

成功时，你会看到 `Claude Code` 的终端界面出现。

#### 启动 Gemini

在终端里输入：

```text
gemini
```

然后按回车。

第一次如果看到“是否信任当前目录”的提示，直接选：

`信任当前项目目录`

你不用担心，这里信任的是当前这个项目文件夹，不是让你开放整台电脑。

## 文字速查版

### A. 只想最快进入黑色卫星机

双击：

```text
/Users/liming/Documents/codex-ai-gua-jia-01/scripts/打开黑色卫星机.command
```

### B. 只想看当前模型

双击：

```text
/Users/liming/Documents/codex-ai-gua-jia-01/scripts/查看当前模型.command
```

### C. 只想切模型

切到 Claude：

```text
/Users/liming/Documents/codex-ai-gua-jia-01/scripts/切到 Claude.command
```

切到 Kimi：

```text
/Users/liming/Documents/codex-ai-gua-jia-01/scripts/切到 Kimi.command
```

切回 GPT-5.4：

```text
/Users/liming/Documents/codex-ai-gua-jia-01/scripts/切到 GPT-5.4.command
```

### D. 已经在黑色卫星机终端里，想直接开 AI

输入下面任意一个：

```text
codex
claude
gemini
```

### E. 如果你是在黑色卫星机自己的 VS Code 里

1. 打开 `VS Code`
2. 点最上面的 `Terminal`
3. 点 `New Terminal`
4. 在底部终端里输入：

```text
or-status
```

如果想切到 Claude：

```text
or-use claude4
```

如果想切到 Kimi：

```text
or-use kimi
```

如果想直接开始用：

```text
codex
```

或者：

```text
claude
```

或者：

```text
gemini
```

## 本机 Terminal 版

如果以后你愿意慢慢学一点命令行，这 4 条最有用：

打开黑色卫星机：

```bash
/Users/liming/Documents/codex-ai-gua-jia-01/scripts/black_satellite.sh shell
```

看当前模型：

```bash
/Users/liming/Documents/codex-ai-gua-jia-01/scripts/black_satellite.sh status
```

切到 Claude：

```bash
/Users/liming/Documents/codex-ai-gua-jia-01/scripts/black_satellite.sh model claude4
```

切到 Kimi：

```bash
/Users/liming/Documents/codex-ai-gua-jia-01/scripts/black_satellite.sh model kimi
```

## 名词翻译成人话

### `codex` 是什么

它是一个在终端里运行的 AI 编程工具。

### `Claude Code` 是什么

它也是一个在终端里运行的 AI 编程工具，启动命令是：

```text
claude
```

### `Gemini CLI` 是什么

它也是一个在终端里运行的 AI 工具，启动命令是：

```text
gemini
```

### `cloud code` 是什么

你这次可以把它理解成“官方云端面板那一套东西”。

现在这条路不走它，你先不用碰。

## 如果你卡住了，先看这 3 条

### 1. 双击后没有连上

先重试一次。

如果还不行，把整个窗口截图发我。

### 2. 成功连上了，但不知道下一步做什么

就在那个终端里输入：

```text
codex
```

这是最短起步路径。

### 3. 你想切回默认模型

双击：

```text
/Users/liming/Documents/codex-ai-gua-jia-01/scripts/切到 GPT-5.4.command
```

# 黑白 old 主机-卫星协作 MVP v1

## Summary

- `black` 固定为 `main-hub`，继续承担正式 intake、route、aggregate、audit、closure 和 mirror。
- `old` 固定为 `satellite-03`，沿用当前已验真的 `vscode-agent` 形态，重点承担浏览器/登录型执行与证据采集。
- `white` 暂时只保留人类别名，不进入本轮 canonical expected sources，等真实纳管后再冻结编号。
- 本轮 canonical 拓扑只认 `main-hub + satellite-03`，历史上的 `satellite-01/02` shadow bootstrap 不计入本轮验收。

## Role Freeze

- `black -> main-hub`
- `old -> satellite-03`
- `white -> pending satellite`

本轮不接受：

- 把 `black` 再描述成卫星
- 把 `white` 在没有 onboarding 工件前直接冻结成 `satellite-01/02`
- 把 `satellite-01/02` 的 shadow bootstrap 当成本轮真实独立来源

## First Real Loop

第一条真任务链固定为浏览器/登录型任务：

1. `main-hub` 先定义子任务、成功产物和回收条件。
2. `satellite-03` 承担执行段，优先顺序固定为：
   - `Feishu`
   - `Get笔记`
   - `其他浏览器任务`
3. 如果三个面都没有可复用登录态，本轮直接收口为 `blocked_needs_user`，只请求一次人工登录。
4. 正式 closure、evolution、Feishu/GitHub mirror 一律回 `main-hub` 完成。

## Phase 2

`white` 的下一阶段只做一件事：真实纳管。

固定顺序：

`probe -> inventory -> verify -> onboard`

只有在以下四类工件都存在后，才允许把 `white` 冻结成下一个真实卫星编号：

- `probe.json`
- `inventory.json`
- `verify.json`
- `onboarding-result.json`

# ADR-015: GitHub在原力OS中的定位

Status: proposed
Date: 2026-03-21
Source: TS-GH-CONSOLIDATE Claude盘点×Codex盘点合并

## Decision
GitHub承担: 公开方法核 / 能力包分发与安装入口 / 跨机器可恢复安装 / 桥接与同步 / 版本与信任登记
GitHub不承担: 唯一canonical runtime / 私有运行态记忆 / 业务闭环数据主账本 / 客户敏感数据存储

## Consequence
所有架构变更先落本地canonical，审批后同步GitHub镜像。

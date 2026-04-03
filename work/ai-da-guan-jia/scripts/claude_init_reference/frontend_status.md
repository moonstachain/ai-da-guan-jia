# 前台应用摘要（按需加载）

- 治理驾驶舱 V2：在线，少量指标卡需重新绑表
- 经营驾驶舱：5 区块在线
- 驾驶舱 2.0：V2 代码已交付（5 页面 / 12 插件 / 2441 行），待妙搭部署验收
- 康波应用：L1/L2/L3 数据层已落地，live 为 L2×33 / L3×49
- 财富三观认知层：schema-first + 四页前端 + 真实飞书表 wiring 已闭环
- 十五五政策信号层：live Feishu 建表/seed 与 3 页前端接入
- OpenClaw Skill Pack：task-spec v1.1 草案入表 + 批准执行闭环 MVP
- Claude 侧治理 Skill：claude-da-guan-jia 已发布到 yuanli-os-skills-pack

## 命名陷阱

- `tblkKkauA35yJOrH` 是旧治理总控表 → 真实 live 是 `tblnRCmMS7QBMtHI`
- `dashboard.feishu_writer.FeishuWriter` 不是正确对象 → 真实入口是 `dashboard.feishu_deploy.FeishuBitableAPI`
- 治理 wiki `Zge0...` 和康波 wiki `INAp...` 不能混淆
- CLAUDE-INIT.md 不是 runtime ledger

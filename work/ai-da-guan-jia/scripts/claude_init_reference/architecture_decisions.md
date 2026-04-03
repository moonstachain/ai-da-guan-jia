# 体系架构决策（按需加载，共 24 条）

1. 双 Ontology 分治：知识分层与对象-动作-权限-写回链分开治理
2. IBM CBM 双轴：`component_domain × control_level` 作为治理定位骨架
3. 四条闭环规则：路径路由、结果验证、进化记录、下轮捕获缺一不可
4. Local-first canonical：本地 artifacts 是真相源
5. 最大失真：治理成熟快于业务执行成熟
6. 投研层并入系统：康波事件、宏观量化、L1.5 深剖
7. Skill 三层架构：YAML 前置、SKILL.md 指令、references/ 参考
8. Skill 治理进入合并态：150 条治理记录、7 个超级 skill、当前可用 132
9. Agent 三代演进定位：第二代末期→第三代入口
10. 三向量扩展架构：V1 多机、V2 同事复制、V3 客户同构
11. Pipeline 并行模型：多节点并行、人类批量验收
12. 多模型编排：不同任务路由不同模型，evidence 归档统一
13. 评测驱动优化：每轮回答哪个指标变好了
14. GitHub 定位升级：分发基座，不只是归档面
15. 康波智库三层专家体系：T0×4 / T1×8 / T2×20
16. V3 clone: shared core + instance directory model
17. `artifacts/ai-da-guan-jia/clones/current/` 是 clone control plane
18. `clone-seed` 是 idempotent bootstrap path
19. `health_probe.py --instance` 是 instance-aware probe
20. `sync-feishu --instance` 读 instance-local config
21. `internal-operator` 是 first-class 内部 cohort field
22. 递归深度驾驶舱模型：/ 直达 L0，/deep-dive 深钻，/workspace 预留
23. PROJ-V2-CLONE-03 是人机激活任务不是系统建设任务
24. Claude 侧治理 Skill 与 Codex 侧 SKILL.md 并存，通过 skills-pack 统一分发

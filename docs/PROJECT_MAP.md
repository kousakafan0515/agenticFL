# 项目目录地图

更新时间：2026-09-25（Asia/Shanghai）

## 快速判断

如果任务是理解项目，先读根目录 `README.md`。如果任务是继续当前工作，先读 `docs/collaboration/NOW.md`。如果任务涉及 Stage3 聚合算法，默认从 `stage3_federation/` 开始；如果是复核简单全局并集基线，则进入 `stage3_1_simple_aggregation/`。

## 顶层目录

| 路径 | 分类 | 内容与使用方式 |
|---|---|---|
| `docs/` | 项目导航 | 跨阶段说明、实时交接和决策记录；不存实验结果。 |
| `client_code/` | 当前共享代码 | 三客户端与 ALFWorld 调用代码，包括 SkillBank 注入入口。 |
| `skill_evolution/` | 当前生成代码 | DeepSeek skill 生成与轨迹压缩逻辑。 |
| `current_skillbanks/` | 冻结输入 | 当前有效的三客户端 SkillBank；聚合读取的权威输入。 |
| `skill_generation_results/` | 当前证据 | 三客户端 skill 生成记录和更新链，用于审计。 |
| `baseline_results_180/` | 冻结结果 | 三客户端各 60 条无 skill 基线，共 180 条。 |
| `stage1/` | 早期阶段实现 | Stage1 客户端实现与结果；先读 `README_collaboration.md`。 |
| `stage2_local/` | 历史演进线 | Stage2 初版。除明确复现外，不作为默认修改目标。 |
| `stage2_local_v2/` | 历史演进线 | Stage2 v2。 |
| `stage2_local_v3/` | 历史演进线 | Stage2 v3，含 invalid pilots 与运行材料。 |
| `stage2_local_v4/` | 历史演进线 | Stage2 v4，含 canary/evolution/runs。 |
| `stage2_local_v5/` | 历史对照协议 | EO/ES旧版本及锁文件；除明确复现外，不作为v7的编辑目标。 |
| `stage2_local_v6/` | 已运行的代际冻结实验 | Client A B0--B5训练/验证与历史Teacher证据；不改写已完成结果。 |
| `stage2_local_v7/` | 新本地演化实现（未正式运行） | 无数量裁剪、完整行为证据、成功反例与跨角色检查；入口为该目录README。 |
| `stage2_local_curriculum/` | 下一次400题十批训练池 | D-062下400题/10×40分层随机输入已冻结，固定134验证隔离；入口POOL400.md。执行适配未完成、未启动；此前670方案原位保留。 |
| `stage2_local_v8/` | 双SkillBank坐标式自进化（开发中） | Client A保持Planner→Executor；Qwen执行，DeepSeek负责有界补丁演化。严格提升、角色隔离拒绝buffer、slow/meta和原子恢复状态已冻结为r5；39/18/134清单不变。ALFWorld端到端编排未接入、未启动。 |
| `stage2_local_v9/` | B1开放构建及Client A本地对照 | 原v9主线保留B1锚定容量；D-104另建Client A三删一加分支，从原始B1生成B2至B5，全客户端共享`ADD <= floor(DELETE/3)`，patch仅作本地审计。入口与边界见该目录README。 |
| `stage2_local_v10/` | 角色分区本地进化与七桶联邦对照（代码就绪、未正式运行） | D-117新分支：Global完整复制给每个角色，独立线与联邦线共用逐角色finding→两阶段patch Teacher，逐角色三删至多一加；服务器仍聚合一份七桶Global。入口见该目录README。 |
| `stage2_local_v11/` | V10完整克隆与并发评估（未正式运行） | 复制V10代码、资产和已导入的v9 B0→B1结果；V11运行入口使用独立命名空间与实验身份，原始运行证据字节不变。官方Qwen额度与本地串行瓶颈见该目录`CONCURRENCY_ANALYSIS.md`。 |
| `stage3_federation/` | 当前核心实现 | Transport patch、候选筛选、个性化聚合、验证运行及单元测试。 |
| `stage3_1_simple_aggregation/` | 已完成基线 | Blind Global Union 简单并集实验、正式 402 episode 结果与交接说明。 |
| `stage3_2_role_agnostic_semantic_merge/` | 完整SkillBank语义聚合基线 | v9 A/B/C冻结库按General与六类任务做DeepSeek官方语义合并；首次正式结果为151→43。D-103后联邦上发和下发都只使用完整SkillBank快照，patch不参与通信。 |
| `originalFL/` | 当前 PatchFL baseline | Round 1 对完整本地 SkillBank 只取原样并集并完整下发；Round 2+ 双向净 patch，服务器聚合后直接下发。服务器评价集仅监测与早停，不参与 patch 准入。入口为 `originalFL/README.md`，权威协议为 `PATCH_FL_PROTOCOL.md`。 |
| `blind_global_patchfl/` | 独立续跑实验 | 从已完成 Stage3.1 Blind Global 27条全集开始的 PatchFL Round 2 续跑；保留旧全量注入语义，不与 `originalFL` 28条暂停分支混合。 |
| `audit_sources/` | 审计副本 | 为比对/复现保留的来源快照；默认只读。 |
| `deliverables/` | 交付快照 | 已打包的历史交付物；默认只读。 |
| `SkillAdaptor_MAS_collaboration_20260901/` | 上游工作区 | 较完整的原始工程及环境痕迹；不是根协作包的默认编辑入口。 |
| `alfworld_data/` | 外部数据 | ALFWorld 数据资源；体积大，不能随意改动。 |
| `_docx_review/` | 文档审阅产物 | Word 文档渲染、评审迭代和模板产物。 |
| `.tmp/` | 临时文件 | 可再生成的工作文件；删除前仍需确认没有活跃任务依赖。 |
| `.venv-stage3-alfworld/` | 本地环境 | Python 虚拟环境，不纳入源码整理或跨机器交接。 |

## 根目录文件

| 文件 | 作用 |
|---|---|
| `README.md` | 项目总体目标、数据边界、客户端架构和当前 SkillBank 说明。 |
| `AGENTS.md` | 所有新 agent/新对话的强制启动、协作和交接规则。 |
| `ALFWorld_Local_Skill_Evolution_Executable_Protocol_v5.docx` | Stage2 协议文档。 |
| `prepare_current_skillbanks.js` | 准备当前 SkillBank 的辅助脚本。 |
| `stage3_1_blind_global_union_all_results_20260924.zip` | Stage3.1 已完成结果归档，不直接编辑。 |

## Stage3 导航

### `stage3_federation/`

- 入门：`README.md`
- SkillBank 注入：`SKILLBANK_LOADER.md`
- 当前聚合策略说明：`AGGREGATION_POLICY_V3.md`
- Transport 转换：`transport_patch_converter.py`
- 个性化聚合：`personalized_aggregator.py`
- 测试：`tests/`
- 运行证据与报告：`artifacts/`

### `stage3_1_simple_aggregation/`

- 协作者交接：`COLLABORATOR_HANDOFF_README.md`
- 预注册方案：`STAGE3_1_SIMPLE_UNION_BASELINE_PLAN.md`
- 实现：`blind_global_union.py`
- 正式汇总：`artifacts/full134_global_20260924_r1/STAGE3_1_BASELINE_REPORT.md`

### `stage3_2_role_agnostic_semantic_merge/`

- 入门与首次结果：`README.md`
- 固定实验规格：`experiment_spec.json`
- 可续跑聚合入口：`round1_aggregate.py`
- 首次正式运行：`runs/v9_b1_round1_20261014_r1/`

## 放置新内容的规则

| 新内容 | 推荐位置 |
|---|---|
| 跨阶段说明/协作规则 | `docs/` |
| 当前任务状态 | 只更新 `docs/collaboration/NOW.md` |
| Stage3 源码或测试 | `stage3_federation/` 对应模块或 `tests/` |
| Stage3.1 基线复核材料 | `stage3_1_simple_aggregation/` |
| originalFL 协议、selector、测试与运行记录 | `originalFL/` |
| 某次运行的机器产物 | 对应阶段的 `artifacts/<scope>_<date>_rN/` 或既有运行目录 |
| 已冻结对外交付包 | `deliverables/<descriptive_name>_<date>/` |
| 审计用不可变副本 | `audit_sources/<descriptive_name>_<date>/` |

不要在根目录新增零散日志、临时脚本、截图或结果文件。若无法确定归属，先在 `docs/collaboration/NOW.md` 记录候选位置并等待确认。


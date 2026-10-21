# ALFWorld 本地自进化工作区

本文件是 `D:\skillMAS` 的入口说明，并带有实时更新机制：目录结构或体量发生变化时，
[`update_readme.py`](update_readme.py) 会重写下面的“目录总览”自动区块。区块以外的文字
由人工维护，脚本不会覆盖。

| 操作 | 命令 | 说明 |
|---|---|---|
| 立即刷新 | `python update_readme.py` | 重新扫描整个目录并覆盖自动区块 |
| 实时更新 | `python update_readme.py --watch` | 默认每 60 秒检查一次，发现变化即刷新 |
| 一致性检查 | `python update_readme.py --check` | README 与现状不一致时返回退出码 1，不写入 |

## 目录总览

<!-- AUTO:BEGIN -->
- 最后更新：2026-10-07 12:09（Asia/Shanghai，自动写入）
- 扫描根目录：`D:\skillMAS`
- 统计总量：135,746 个文件，9968.7 MB
- 更新方式：`python update_readme.py`；持续监测：`python update_readme.py --watch`

### 根目录条目

| 名称 | 类型 | 文件数 | 体积 |
|---|---|---:|---:|
| `.tmp/` | 目录 | 36 | 8.3 MB |
| `.venv-stage3-alfworld/` | 目录 | 5,942 | 40.5 MB |
| `SkillAdaptor_MAS_collaboration_20260901/` | 目录 | 72,224 | 3844.4 MB |
| `_docx_review/` | 目录 | 279 | 70.8 MB |
| `alfworld_data/` | 目录 | 19,619 | 2269.5 MB |
| `audit_sources/` | 目录 | 179 | 137.0 MB |
| `baseline_results_180/` | 目录 | 7 | 17.4 MB |
| `blind_global_patchfl/` | 目录 | 1,863 | 238.1 MB |
| `client_code/` | 目录 | 17 | 0.5 MB |
| `collaboration_round2_prompt_v2/` | 目录 | 2 | 0.0 MB |
| `current_skillbanks/` | 目录 | 3 | 0.0 MB |
| `deliverables/` | 目录 | 919 | 108.0 MB |
| `docs/` | 目录 | 5 | 0.1 MB |
| `originalFL/` | 目录 | 639 | 71.3 MB |
| `skill_evolution/` | 目录 | 13 | 0.1 MB |
| `skill_generation_results/` | 目录 | 7 | 1.3 MB |
| `stage1/` | 目录 | 35 | 44.7 MB |
| `stage2_local/` | 目录 | 75 | 1.1 MB |
| `stage2_local_v2/` | 目录 | 23 | 0.4 MB |
| `stage2_local_v3/` | 目录 | 804 | 19.7 MB |
| `stage2_local_v4/` | 目录 | 1,185 | 52.8 MB |
| `stage2_local_v5/` | 目录 | 141 | 2.0 MB |
| `stage3_1_simple_aggregation/` | 目录 | 1,703 | 161.8 MB |
| `stage3_federation/` | 目录 | 30,020 | 2870.0 MB |
| `AGENTS.md` | 文件 | 1 | 0.0 MB |
| `ALFWorld_Local_Skill_Evolution_Executable_Protocol_v5.docx` | 文件 | 1 | 0.0 MB |
| `README.md` | 文件 | 1 | 0.0 MB |
| `prepare_current_skillbanks.js` | 文件 | 1 | 0.0 MB |
| `stage3_1_blind_global_union_all_results_20260924.zip` | 文件 | 1 | 8.9 MB |
| `update_readme.py` | 文件 | 1 | 0.0 MB |
<!-- AUTO:END -->

## 工作区保留了什么

| 路径 | 角色 | 说明 |
|---|---|---|
| `stage1/` | 最早的三客户端实现 | `alfworld_client_a/b/c.py`、`alfworld_p0.py`、`alfworld_text_env.py`、`local_skill_memory.py` 及 180 条早期结果 |
| `stage2_local_v5/` | 最新使用的本地自进化协议 | 离线一次性库（EO）与顺序演化库（ES）对照，含 `experiment_spec.json`、`locks/`、`scripts/`、`runtime/`、`tests/` |
| `originalFL/` | 当前联邦与 PatchFL 基线 | 本地 evolver、服务器聚合、收敛判定、任务清单与运行记录 |
| `update_readme.py` | 本文件的维护脚本 | 只改写自动区块，不触碰人工内容 |

## 本地自进化当前口径

> 2026-10-18：新增[`stage2_local_v10/README.md`](stage2_local_v10/README.md)及独立代码分支。v10把一份七桶Global完整复制到每个客户端的每个角色分区，角色在本地分别按轨迹分析、两阶段补丁进化，并各自执行`ADD <= floor(去重DELETE/3)`；服务器上传完整多角色库，仍只输出一份角色无关七桶Global。Client A独立线使用同一逐角色Teacher和配额；空B0→B1只允许ADD候选。仅完成新代码、清单和离线测试，未启动v10正式模型调用或134题实验；v9源码与结果保持原位。

> 2026-10-12：新增[`stage2_local_v9/README.md`](stage2_local_v9/README.md)，作为v6取消容量限制的对照修订。v6源码与B0--B5结果保持原位；v9复用完全相同的134题训练/134题验证队列，只移除每角色14条上限、容量修复、固定顺序裁剪和最终容量断言。字段900字符限制保留；B1--B5 Teacher统一锁定DeepSeek官方`deepseek-flash`。v9只完成代码、清单和离线验证，尚未调用模型或启动正式实验。

> 2026-10-14：v9已完成A/B/C的B0→B1正式实验并全部停止在B1验证，B2及以后未启动。Client B/C正式r3的B1验证均为110/134且API-clean；C端B1为Supervisor/Search Worker/Operation Worker=`17/24/22`条。C端Teacher曾因最终合并响应达到8000 token输出边界停止，保留原18条检查点后以16000输出预算恢复，未重跑任务族分析、未执行容量修复或裁剪。D-093进一步将后续规则冻结为：B1开放式构建，B2及以后按角色使用B1实际条数作为固定容量；库未满时可直接ADD，超限只允许Teacher合并/删除修复，禁止机械裁剪。详见[`stage2_local_v9/README.md`](stage2_local_v9/README.md)。

> 2026-10-12：[`stage2_local_v8/README.md`](stage2_local_v8/README.md) 为 Client A `Planner -> Executor` 双 SkillBank 坐标式自进化：两库从空库开始，每次固定一库、仅更新另一库；Planner/Executor执行使用`qwen3.6-flash`，轨迹反思和SkillBank更新使用DeepSeek官方`deepseek-v4.1-flash`（API ID `deepseek-flash`）。任务清单固定为39训练/18选择/134测试，候选只有严格提升才接纳、平局拒绝；有界补丁、`[4,3,2,2]`预算、角色隔离拒绝buffer、门控slow update、optimizer-only meta skill及原子恢复状态已实现并冻结为r5。ALFWorld端到端编排尚未接入，付费实验未启动。

> 2026-10-10：新增[`stage2_local_v7/README.md`](stage2_local_v7/README.md)，取消技能数量裁剪，保留完整训练交互，统一真实任务映射；加入原文证据锚点、候选去向核验、有界跨角色修订，以及v7专用环境事实完成验证器。仅完成代码及离线验证，未启动正式实验；v6 B0--B5结果保持原位不改写。下文v5/OriginalFL表格仍为历史协议。

> 新运行模型决策（2026-10-07）：后续新实验的 Client A/B/C 任务执行统一使用
> `qwen3.6-flash`，不复用任何 `qwen3-8b` 生成的基线、轨迹、SkillBank 或评价结果。
> 本地 Teacher LLM 统一使用 `deepseek-v4.1-flash`；服务器冲突聚合模型仍保持
> `deepseek-v4-flash`，两者使用独立模型锁。
> v8把DeepSeek称为“演化优化器”：它只读取完整轨迹并更新当前角色SkillBank，不作为
> Planner/Executor之外的运行时agent；其模型职责和调用仍必须独立计量。
> 下表中的 `qwen3-8b` 是既有 Stage2/OriginalFL 历史实验口径，保留用于审计。

客户端在本地用 Teacher LLM 把真实执行轨迹转成可注入的 Skill，服务器只负责跨客户端的
聚合与监测。当前两条线的关键差别：

| 维度 | `stage2_local_v5`（Stage2 协议） | `originalFL`（PatchFL 基线） |
|---|---|---|
| 演化单元 | 每客户端 5 个 outcome-blind、类型均衡的 batch，每批 12 题 | 每客户端每轮 1 个 cycle，4 个 batch × 6 题 |
| 父库 | `B0` 为空，`B1-B5` 为不可变快照 | Round 1 从空库起步，Round 2+ 从共同 Global Base 出发 |
| 本地操作 | `ADD / UPDATE / NONE`（v7 起由代码限定合法操作与目标 ID） | `ADD / UPDATE / REPLACE / DELETE / NONE` |
| 容量 | General ≤ 2、每任务类型 ≤ 2、单题注入 ≤ 4 | 每 Agent 总量 `max(14, 基准总数)`，单题注入 ≤ 4 |
| 本地验证 | 不做逐轮本地评价；最终测试用 `valid_unseen` 60 题 × 4 条件 | 无本地 Parent/Candidate 评价、无本地回滚，完成预算即上传 |
| 服务器角色 | 不涉及跨客户端聚合 | 每轮评估冻结 60 题 × 3 客户端，仅用于全局早停 |
| 模型锁 | 任务执行与演化均为 `qwen3-8b`（DashScope） | 任务执行 `qwen3-8b`，演化与聚合 `deepseek-v4-flash` |

## 使用边界

- 本目录不是 Git 仓库，不能依赖版本控制回滚；改动前先备份或手工暂存再操作。
- 目录已整体归位：`originalFL` 依赖同级的 `client_code/`、`skill_evolution/`、`alfworld_data/`，
  `stage2_local_v5` 的锁文件依赖同级的 `stage2_local_v3/`、`stage2_local_v4/`，现均在同一层级。
- 正式 ALFWorld 运行、外部 API 调用和全量 134/402 episode 评测不属于默认验证，需要显式确认。

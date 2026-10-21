# 跨会话决策记录

这里只记录会影响后续 agent 的稳定决策。条目一经记录不直接删除；若决策失效，新增条目并注明“取代 D-xxx”。

## D-001：单一实时状态入口

- 日期：2026-09-25
- 状态：生效
- 决策：`docs/collaboration/NOW.md` 是项目唯一实时协作状态页。
- 原因：避免不同阶段和 agent 各自维护 `status/latest/final` 文件，造成接手时无法判断哪个更新。
- 影响：任务开始、暂停、阻塞、完成时都更新该文件；稳定结论移入本日志或阶段报告。

## D-002：不以物理搬迁换取目录整洁

- 日期：2026-09-25
- 状态：生效
- 决策：先用 `docs/PROJECT_MAP.md` 明确目录语义，不移动现有实验结果、审计副本、交付快照、数据集和虚拟环境。
- 原因：这些路径可能被脚本、哈希清单、报告或复现流程引用；未经验证的重排会破坏证据链。
- 影响：新增内容按目录地图放置；历史结构只在专门迁移任务中调整。

## D-003：当前 Stage3 入口分工

- 日期：2026-09-25
- 状态：生效
- 决策：个性化/联邦聚合主实现从 `stage3_federation/` 进入；Blind Global Union 基线与其正式结果从 `stage3_1_simple_aggregation/` 进入。
- 原因：两者承担不同实验角色，不能因目录名接近而混用。
- 影响：新 agent 修改前必须先判断任务属于哪一条线，并读取相应 README/方案。

## D-004：Stage3 多轮联邦的收敛集与最终测试分离

- 日期：2026-09-30
- 状态：生效
- 决策：本地 skill 演进只使用 `train`；多轮服务器准入与早停使用冻结的 `valid_seen` 每类 10 题（共 60 题）；`valid_unseen` 134 题只在收敛后做一次最终泛化测试。
- 原因：若反复使用 134 题选 skill、调 prompt 或决定停止，最终结果会发生测试泄漏，不再能表示 OOD 泛化。
- 影响：旧 `atomic_validation_134.py` 与相关 134 题选择产物只作历史证据，不作新的多轮 baseline 准入依据；新轮次按 `stage3_federation/FEDERATED_CONVERGENCE_PROTOCOL_V1.md` 执行。

## D-005：originalFL 使用完整 SkillBank 快照和14条 Global 上限

- 日期：2026-10-01
- 状态：生效，取代 D-004 对新 originalFL baseline 的适用；D-004 仅保留为旧 Stage3 方案记录。
- 决策：客户端上传完整 Local SkillBank，服务器下发完整 Global SkillBank，不传 patch。Local 和 Global 都使用 General 2 条+每任务类型2条、总计14条的容量。服务器对三份 Local 并集先精确去重，再按来源客户端数和固定哈希每 scope 取前2条。
- 操作：客户端 evolver 仅有 `ADD/UPDATE/NONE`；服务器对相邻完整 Global 的差异审计为 `ADD/UPDATE/NONE/REPLACE`，这些不是传输 patch。
- 数据：Local evolution 用三个 non-IID train input pool；Local convergence 从各自213题 train-local-validation pool 冻结60题core；Server convergence 用独立 train-public pool 中六类各10题；`valid_seen` 140 和 `valid_unseen` 134 只用于最终测试。
- 影响：originalFL 以 `originalFL/README.md` 为实时入口；旧 transport patch 与 `valid_seen` 收敛 manifest 不是该 baseline 的输入。

## D-006：originalFL 客户端增加本地 REPLACE

- 日期：2026-10-01
- 状态：生效，取代 D-005 中“客户端仅 ADD/UPDATE/NONE”的局部规则。
- 决策：originalFL 客户端 evolver 使用 `ADD/UPDATE/REPLACE/NONE`。REPLACE 只在 scope 已满2条时可用，必须指向一个精确活跃 ID，新 skill 取得新 ID/version 1，不增加条数。
- 准入：REPLACE 必须全部 API-clean，本地 paired `rescues - harms >= 2`，任一任务类型净下降不超过1题；每 scope 每 batch 最多接纳1次。
- 实现：使用 `originalFL/prompts/skill_evolver_with_replace.txt` 与 `originalFL/local_operations.py`；历史 `stage2_local_v5` prompt 不改。

## D-007：originalFL 使用独立状态机和 role-agnostic 运行适配

- 日期：2026-10-01
- 状态：生效
- 决策：originalFL 以空 Global 为 B0，由 `originalFL/federated_runner.py` 唯一管理 Local/Global bank 的接纳、回滚、完整快照通信和两级早停。训练、evolver 与 paired evaluator 只提交不可变 artifact，不直接改正式状态。
- 运行适配：逻辑 SkillBank 不分 Agent role；单题选中的 General 最多2条和当前任务类型最多2条被同样提供给客户端各角色，逻辑容量仍按最多4条计算。角色权限、动作协议和输出格式继续由客户端原 prompt 约束。
- 证据：本地 evolver 的允许操作和 target ID 由代码生成；变更必须通过冻结 Stage2 v9 原子动作 provenance 编译器，local/server validation 永不进入 evolver evidence。
- 测试：最终 `valid_seen`/`valid_unseen` 暂缓，只有 Global 冻结后才能另行执行；暂缓不改变训练、准入和收敛实现。

## D-008：PatchFL 取代 originalFL 完整快照方案

- 日期：2026-10-01
- 状态：生效，整体取代 D-005 至 D-007 的通信与运行架构；这些旧决策只作历史记录。
- 通信：Round 1 客户端上传本地收敛且准入后的完整 skill，服务器做精确去重并集与容量投影后完整下发 G1；Round 2 起客户端上传相对共同 Global Base 的净 patch，服务器只下发上一份已接纳 Global 到新 Global 的净 patch。
- 操作：使用 `ADD/UPDATE/REPLACE/DELETE/NONE`。DELETE 用于删除被实际采用且重复造成伤害、又没有合格替代项的 skill，须通过与 REPLACE 相同的严格本地 paired 门槛。
- 身份与容量：遵循协作者 prompt 的 Agent-role 隔离，稳定键包含 role/scope/task type/global skill ID；容量改为每个 role 最多14条，单个 role 单题最多注入4条。
- 冲突：相同 target 的不同结果先做精确结果去重，再按支持客户端数降序、固定 salted hash 升序选一个；哈希只打破平局。服务器 public validation 只对完整 Global Parent/Candidate 做整份准入。
- 数据：A 使用清洗/冷却，B 使用台灯/加热，C 使用简单取放/双物品；标准每轮各24题、4个6题 batch，可为本地稳定追加至最多8 batch。Local core 仍为每客户端冻结60题，Server core 仍为公共60题六类各10题；最终140/134暂缓。
- 实现边界：`originalFL/PATCH_FL_PROTOCOL.md` 与 `patch_experiment_spec.json` 为新权威来源；旧完整快照 runner、runbook、协议和 spec 均不得用于正式运行，直到 patch runner 另行实现并验证。

## D-009：PatchFL 改为服务器直接聚合下发

- 日期：2026-10-01
- 状态：生效，取代 D-008 中 DELETE、本地扩展操作、服务器 Parent/Candidate 准入和服务器评价集；D-008 仅作历史记录。
- Round 1：使用 `current_skillbanks/` 的冻结第一轮本地 SkillBank 作为 bootstrap，客户端完整上传；服务器精确去重、取并集并执行容量投影，完整下发 `G1`。协作包 prompt 明确只适用于第二轮以后，不能从空库生成第一轮。
- Round 2+：每个客户端只在原分配的两类任务上自进化，并严格使用协作包的 `ADD/UPDATE/NONE`；上传相对共同 Global Base 的净 patch。服务器聚合后直接下发 canonical patch，可用 `REPLACE` 表达容量投影的一进一出；不使用 `DELETE`。
- 数据：本地自进化每个标准 cycle 为两类各12题；本地冻结评价集也只覆盖相同两类，每类30题，并与训练轨迹隔离。服务器不设置任务评价集，不运行 Global Parent/Candidate paired 条件。
- 收敛：本地需先连续两个 batch 无实际写入且 bank hash 不变，再通过一次本地 paired 评价；全局以连续2轮聚合 patch 为 NONE 且 Global hash 不变作为状态收敛。后者不宣称性能收敛。
- 容量与冲突：按 Agent role 分库，每个 role 为 General 2、六类各2、总14、单题4；同 target 冲突先精确结果去重，再按支持客户端数和固定 salted hash 裁决。哈希只打破平局，不评价质量。

## D-010：恢复客户端五操作与服务器单条件评价

- 日期：2026-10-01
- 状态：生效，取代 D-009 中“客户端仅 ADD/UPDATE/NONE”和“无服务器评价集”；D-009 其余直接下发原则继续有效。
- 客户端：使用 `ADD/UPDATE/REPLACE/DELETE/NONE`。REPLACE 仅在 scope 已满且有合格替代项时一进一出；DELETE 仅用于被实际执行、重复造成可归因伤害、不能小改修正且没有替代项的 skill，并须通过更严格的本地 paired 门槛。
- Round 1：客户端完整上传冻结第一轮 SkillBank；服务器只按 `(source_client, source_agent, source_skill_id)` 取集合并集，不做正文去重、冲突裁决、排序或容量投影，完整下发 `G1`。
- 容量解释：完整收到的 Global repository 可超过14条；每个 Agent role 实际激活和演进的 active bank 仍为 General 2、六类各2、总14，单题最多4条。否则“服务器不处理并完整下发”与“下发最多14条”在并集超限时逻辑冲突。
- Round 2+：服务器仍先确定性聚合再直接下发，不等待评价结果，不拒绝或回滚 patch。
- 服务器评价：恢复 train-public 冻结60题，六类各10题；每轮 A/B/C 各运行当前 Global 一次，共180 conditions。只运行当前 Global，不在同轮运行 Parent/Candidate；评价只用于监测和早停，不参与冲突排序或准入。
- 全局收敛：连续2轮同时满足聚合 patch 为 NONE、Global hash 不变、pooled success count 不变且三个客户端各自 success count 不变；Round 1 只建立基线，不计 patience。

## D-011：本地自进化直接使用完整 Global repository

- 日期：2026-10-01
- 状态：生效，取代 D-010 的 repository/active-bank 分层解释；D-010 的五操作、服务器评价和直接下发规则继续有效。
- 决策：客户端保留并直接使用完整 live Global repository 作为本地自进化共同基线，不预先裁剪出独立 active bank。单题上下文仍只注入 General 最多2条和当前 task-specific 最多2条。
- 容量：Round 1 以完整 `G1` 为不可破坏起点；每个 role/scope 后续 effective cap 为 `max(原上限, G1初始数量)`，role total cap 为 `max(14, G1初始总数)`。已超旧上限的 scope 不删除初始 skill，但不能继续 ADD，只能 UPDATE、REPLACE 或 DELETE。
- 覆盖：eligible skill 超过单题槽位时，按包含固定 injection salt、client、role、task type 和 skill ID 的固定哈希排序，并随 cycle/batch/episode 确定性轮换。在覆盖一轮前不优先重复；排序不包含 Global hash，避免无关 patch 重排全部注入。哈希只负责排班，不表示质量。
- 删除语义：DELETE/REPLACE 退出的旧版本保留为审计 tombstone，但不再属于 live repository，也不参与注入；所有客户端重放服务器 patch 后必须得到相同 live-state hash。

## D-012：服务器拥有可执行的全局 DELETE

- 日期：2026-10-01
- 状态：生效，补充 D-010/D-011。
- 决策：服务器操作集为 `ADD/UPDATE/REPLACE/DELETE/NONE`。当客户端 DELETE 候选在同 target 的确定性聚合中胜出，服务器从 live Global repository 移除该 ID，保存审计 tombstone，并向全部客户端下发 canonical DELETE。
- 证据边界：服务器不能仅依据 server-validation 分数、文本相似度或腾容量需要自行生成 DELETE；全局 DELETE 必须追溯到至少一个已通过本地证据检查和严格本地 paired validation 的客户端候选。
- 重放：DELETE 携带 base/result Global hash、精确 ID、期望旧版本或正文哈希、来源客户端、裁决记录与 tombstone reason；相同 tombstone 重放幂等，版本不匹配视为协议错误。

## D-013：v3 任务集从完整 train catalog 重新划分

- 日期：2026-10-01
- 状态：生效，取代旧 `original_fl_tasks.json` 的每客户端六类混合任务流。
- 原因：旧 Stage1 client shard 无法支持 v3 两类分工和数量，例如 A 的 cool input/validation 仅4/1条，B 的 lamp validation 仅5条，C 的 two-object validation 仅12条。
- 决策：从完整 ALFWorld train catalog 按 task type 重新划分。以 goal directory 为隔离 group，同组不同 trial 不得跨 local evolution、local validation 或 server validation；每个选中 group 固定一个 trial。
- 数量：本地 evolution 每个标准 round 每客户端两类各12题，最多3 cycles；本地 validation 每客户端两类各30题；server validation 六类各10题。最多5个 patch rounds 时每类预留最多180个 evolution groups。
- 最终测试：`valid_seen` 140和`valid_unseen` 134分别由 A/B/C 全部运行，总 conditions 为420和402，只在 Global 冻结后运行一次。
- 实现边界：类型、数量和划分算法已冻结；v3 精确 task-ID manifest 及 content hash 尚未生成。旧 `originalFL/artifacts/task_manifests/original_fl_tasks.json` 禁止用于 v3。

## D-014：Round 1 从空库重跑并定义 patch 后续演

- 日期：2026-10-01
- 状态：生效，取代 D-010/D-013 中复用冻结第一轮 SkillBank 的 bootstrap 假设；其他聚合、任务分工和评价规则继续有效。
- Round 1：A/B/C 都从空 local repository 开始。第一批无 skill 注入，只允许 ADD/NONE；后续 batch 注入刚生成的本地 skill，只有实际注入并执行过的 ID 才允许 UPDATE/REPLACE/DELETE。本地稳定并通过相对空库的 paired validation 后上传完整 live Local repository。
- Prompt：空库冷启动使用 `skill_evolution/run_client_*_mixed_deepseek_v1.py` 中的第一轮规则加 v3 扩展；Round 2+ 使用协作包 round2 prompt 加 v3 扩展。现有第一轮脚本绑定旧 batch，须适配 v3 manifest 后才能运行。
- 服务器：Round 1 对三份完整上传只取原样并集并完整下发 G1；服务器评价只建立基线，不改变 G1。
- patch 后续演：客户端先把服务器 patch 重放到完整 Global repository 并校验 hash，所得 G(r) 成为下一轮共同只读 Parent；随后在全新本地任务上实际注入 G(r) skill、采集轨迹并生成相对 G(r) 的本地 patch。patch 文本和服务器评价均不是 evolver 证据。
- 任务预算：Round 1 加最多5个 patch rounds，每类最多216个 evolution groups；再加30个 local-validation和10个 server-validation group，共256，完整 train catalog 数量可行。

## D-015：冻结 v3 精确任务 manifest 并将每阶段上限改为2 cycles

- 日期：2026-10-01
- 状态：生效，取代 D-014 的216/256 group预算；其他 Round 1和patch续演规则不变。
- 数据事实：完整可运行 train 中最少的 heat 类只有210个 goal groups，无法支持每类216 evolution + 30 local validation + 10 server validation。为保证 goal-group 零复用，每个本地阶段最多从3 cycles降为2 cycles。
- 冻结预算：Round 1加5个patch rounds，共6 stages；每类最多144 evolution groups，加30 local-validation与10 server-validation，共184。每客户端最多288个 evolution tasks。
- 冻结文件：`originalFL/artifacts/task_manifests/patchfl_v3_tasks.json`；content hash 为 `sha256:7069e1eb38f0d8a4bcdb8f159708c443148860214201a4cca7659f2e134eb786`。
- 验证：确定性重建 `--check` 通过；4项 manifest 单元测试通过，覆盖 content hash、精确数量、全局 goal-group 无交集和整体不变量。

## D-016：正式实验模型锁与 DeepSeek 聚合

- 日期：2026-10-01
- 状态：生效，取代此前纯固定哈希冲突赢家；结构校验、直接下发和服务器评价非准入规则不变。
- 模型：所有 ALFWorld任务执行使用 `qwen3-8b`、temperature 0、seed 1234、thinking关闭；本地自进化和服务器聚合使用 `deepseek-v4-flash`、temperature 0。
- 聚合：服务器先做schema/身份/base-hash校验与完全相同结果去重；同target冲突或容量竞争由DeepSeek从白名单candidate IDs中选择或返回NONE。模型不得生成新skill正文、修改候选或读取server-validation结果。
- 失败处理：候选按固定哈希排序以稳定输入；模型输出越权、格式错误或调用失败时，该冲突组为NONE，不以哈希替代质量选择。
- 探针：2026-10-01正式前置探针通过，Qwen请求37 tokens，DeepSeek请求63 tokens；报告位于 `originalFL/artifacts/preflight/formal_20261001_r1/`，不含API Key。

## D-017：v3 manifest 按 ALFWorld 运行时 solvable 口径重冻

- 日期：2026-10-01
- 状态：生效，修正 D-015 中把“文件存在”等同于“运行时可加载”以及 evolution 全程 goal-group 零复用的假设；轮数、每阶段 cycles、评价规模与模型锁不变。
- 触发证据：Round 1 Client A 首批在模型调用前被 ALFWorld 拒绝，6个冻结任务仅3个满足 `game.tw-pddl.solvable=true`。该次运行没有发出正式模型请求、没有产生 episode，因而不构成任务消费。
- 运行时目录：完整 train 六类共有3552个可运行 trial；可运行 goal groups 为 lamp 123、simple 322、clean 268、cool 212、heat 186、two-object 354。旧统计包含 `solvable=false` 条目。
- 新隔离：server validation 与 local validation 继续使用互斥 goal groups，且所有 validation goal groups 与 evolution 隔离；evolution 的精确 task/trial 在所有轮次零复用，但可从同一 evolution goal group 选择不同可运行 trial。
- 新冻结文件：`originalFL/artifacts/task_manifests/patchfl_v3_tasks.json`，content hash `sha256:ef90e2ef4cc264de44f59210d67fb556676575b8fb5e55606839f42208420a67`。生成器确定性重建通过，5项测试通过并逐题验证 `solvable=true`。

## D-018：Cycle 2 Batch 1 continuation evolver 边界修复

- 日期：2026-10-02
- 状态：生效；不改变实验口径，仅修复正式实现并更新运行锁中的代码哈希。
- 触发证据：Round 1 / Cycle 2 / Batch 1 三端任务已完成后，`round1_continuation_evolver.py` 以 `batch <= 1` 错误拒绝 continuation，实际只有 Cycle 1 / Batch 1 属于空库冷启动。该次退出发生在 DeepSeek 调用和任何 patch/SkillBank 写入之前。
- 修复：冷启动拒绝条件改为 `cycle == 1 and batch == 1`；evidence 身份校验同时加入 `cycle_index`，防止跨 cycle 证据误用。Cycle 2 / Batch 1 继续使用协作包 continuation 规则和五操作约束。
- 验证：新增边界回归测试；正式 WSL 环境完整 `originalFL/tests` 共19项通过。任务清单、模型锁、容量、收敛条件和已生成证据均未改变。

## D-019：固定一周期本地预算并由服务器评价决定停止

- 日期：2026-10-02
- 状态：生效，取代 D-008 至 D-015 中关于本地结构收敛、本地 Parent/Candidate paired validation、预算扩展至第二 cycle，以及 D-010 中全局“patch NONE + hash不变 + success完全相等”的停止条件；未被本条修改的通信、五操作、角色隔离、任务分工与直接下发原则继续有效。
- 本地预算：每个客户端每个 global round 固定运行一个 cycle，即4个batch、每批6题、共24题；三客户端每轮共72题。完成固定预算即上传，不做本地收敛判定、不运行本地 Parent/Candidate 评价、不因评价回滚。Round 1 上传完整 SkillBank；Round 2+ 上传相对共同 Global Base 的净 patch。
- Round 1：服务器按 `(source_client, source_agent, source_skill_id)` 保留全部成员，只做集合并集；不按正文去重、不筛选、不裁剪。canonical Global repository 保存全部角色分区；运行时按目标客户端职责投影，A/B共享的 Executor 分区包含两端 Executor skill，且每条都保留来源身份。
- 服务器评价：每轮聚合并下发后，A/B/C 分别在同一冻结 train-public 60题上只运行当前 Global，共180 conditions。结果不进入聚合器或 evolver，不影响 patch 准入、不触发回滚。
- 收敛：仅使用最近3个完整且 API-clean 的服务器评价轮次。若 pooled success count 在窗口内极差不超过4/180，且 A、B、C 各自 success count 极差均不超过2/60，则状态为 `converged`。Round 1 可作为第一个评价点，因此最早在 Round 3 停止。Global hash 和聚合 patch 仅作结构诊断，不是停止必要条件。
- 上限：Round 1 bootstrap 后最多再运行5个 patch rounds；Round 6 评价后仍不满足上述窗口则状态为 `maximum_rounds`，不得写为收敛。最终 `valid_seen` 420 conditions 与 `valid_unseen` 402 conditions 只在 `converged` 或 `maximum_rounds` 后运行一次。
- 既有证据复用：`patchfl_v3_formal_20261001_r1` 的 Round 1/Cycle 1 恰好满足新的固定预算，可作为新修订 run 的 Round 1 输入，但必须记录来源文件哈希；该旧 run 的 Cycle 2 明确排除并只保留为探索证据，旧目录不得改写。

## D-020：Round 1 向所有客户端直接下发同一份完整并集

- 日期：2026-10-02
- 状态：生效，取代 D-019 中“服务器为目标客户端生成角色投影后下发”的表述；D-019 其余固定预算与停止规则不变。
- 决策：服务器只物化一份包含28条来源可追溯 skill 的 canonical `G1`。A/B/C 下载文件必须内容和文件 SHA-256 完全相同，每端都保存完整28条；服务器不得生成13/14/11条的客户端子集。
- 运行边界：现有客户端 prompt loader 仍需要按本客户端已有 Agent role 组织输入，因此客户端可从其完整本地 `G1` 下载副本生成临时 runtime view。该 view 只在本地执行时适配既有接口，不是服务器聚合结果、不是下发对象，也不得被记录成个性化 Global。
- 处置：此前使用13/14/11角色子集启动的服务器评价全部无效，归档到新 run 的 `invalidated_role_projection_*` 目录并从0重跑，不进入收敛窗口。

## D-021：从旧 Blind Global 27条全集建立独立 PatchFL 续跑分支

- 日期：2026-10-02
- 状态：生效；仅作用于 `blind_global_patchfl`，不取代 D-019/D-020 的28条 `originalFL` 分支。
- 分支边界：`originalFL/runs/patchfl_v3_revised_20261002_r1` 保持暂停，A/B/C 各4/60检查点原样保留；新分支从 Stage3.1 Blind Global Union 的27条共同全集开始，按用户命名把下一次本地训练记为 Round 2。
- 本地预算：A/B/C 仍各自只跑原有两类 train 任务；每端固定一个 cycle、4个batch、24题。每批执行后立即演进并将 Candidate Bank 传给下一批；完成后生成相对共同 G0 的净 patch。本地不评价、不回滚、不判断收敛。
- 兼容规则：继续使用旧 Blind Global 的 all-eligible 注入（单题22–25条），不套用后来4条上限。G0 的27条总量和各 scope 初始占用冻结为容量基线；满库禁止 ADD，但允许 UPDATE/REPLACE/DELETE，删除可为后续 ADD 腾位。
- 数据边界：使用 v3 manifest 的 Round 2/Cycle 1 精确 train tasks。旧导出包缺少早期72条 skill-generation trial 的完整清单，因此不宣称跨旧实验严格零复用。旧134题已经消费，只作历史证据，不作本分支收敛或最终测试。
- 评价补充：按用户要求可先直接开始本地 Round 2；若后续采用服务器评价早停，必须先对 G0 补跑同一冻结60题基准，服务器评价只监测、不参与 patch 聚合或下发。

## D-022：Blind Global PatchFL 保留60题收敛集，134题仅作终局补充

- 日期：2026-10-02
- 状态：生效；适用于 `blind_global_patchfl`。
- 决策：每个 Global 版本仍由 A/B/C 分别运行同一冻结60题，共180 conditions；该集合是唯一的逐轮收敛监测集。旧 `valid_unseen` 134题不参与早停、patch选择、服务器聚合或回滚，只在联邦流程停止并冻结最终 Global 后运行一次补充 OOD 测试。
- 原因：反复使用134题决定是否继续训练会使最终 OOD 结果泄漏；当前60题与本地 evolution 隔离，且G0已经同期得到完整API-clean基线125/180。
- 历史比较边界：旧 Blind Global 的237/402可作为历史连续性参考，但不是同期对照；最终134题报告必须注明潜在服务漂移，不把历史差异单独解释为patch因果效果。

## D-023：Round 2+ 改为直接合并 patch，并生成式合成冲突 patch

- 日期：2026-10-02
- 状态：生效，取代 D-016/D-021 在 `blind_global_patchfl` 中关于“DeepSeek只能从白名单候选选一个或NONE”的服务器冲突处理；D-022评价集边界不变。
- 聚合：服务器直接合并所有互不冲突的合法净patch；完全相同结果精确去重并合并proposer。若同一Global target出现不同合法patch，DeepSeek读取该冲突组的patch正文并合成为一个新的完整patch，而不是选择某个原候选。
- 生成边界：合成patch必须保持原target与scope，operation必须来自该冲突组已有操作，只能组合候选中已有证据，不得读取服务器评价、添加任务实例细节或改写其他target；无法安全合成时返回NONE。输出仍需通过schema、base-hash、旧正文hash与容量校验。
- 本地容量：每个Agent以该轮冻结容量基准库计算：General=`max(2,基准General数)`，当前类别Task-specific=`max(2,基准该类别数)`，总量=`max(14,基准Agent全部skill数)`。该机制替代写死的2/2/14，但保留最低旧上限。
- 处置：旧selector协议下尚未完成的G2评价A/B/C=56/55/57全部作废，移入 `server_validation/invalidated_g2_selector_protocol_20261002_r1/`，不得进入收敛窗口；G0的125/180仍有效，因为它在任何Round 2聚合前已冻结。

## D-024：本地容量只限制 Agent 总量，不限制 scope 数量

- 日期：2026-10-03
- 状态：生效，取代 D-023 中关于 General/Task-specific 各自动态上限的局部规则；D-023 的服务器直接合并与生成式冲突合成继续有效。
- 决策：每个 Agent 的总上限=`max(14, 冻结容量基准库中该Agent全部skill数)`。General 和各 Task-specific 不设独立数量上限，数量可以随DELETE、ADD和REPLACE证据变化；ADD仍只能写入General或当批当前任务类别。
- 运行含义：总库已满时不能ADD；DELETE腾出一个总量位置后，后续batch可把该位置用于General或其当前类别Task-specific，不要求回填原scope。REPLACE保持总数不变，并允许替换只有1条skill的scope。
- 既有Round 2：全部操作为UPDATE，没有触发任何容量边界，因此现有本地证据、18个净patch和D-023重新物化的G2继续有效，无需重跑。

## D-025：服务器下发完整 Global 并替换客户端 SkillBank

- 日期：2026-10-03
- 状态：生效，取代 D-019/D-021/D-023 在 `blind_global_patchfl` 中关于服务器向客户端下发 canonical diff patch 的规则；客户端上传净patch、D-023服务器聚合和D-024容量规则不变。
- 通信：Round 2+客户端仍上传相对共同Global Base的净patch；服务器聚合后物化完整新Global（G2、G3等），向A/B/C下发同一份完整Global snapshot。
- 客户端应用：客户端校验snapshot文件SHA-256与Global hash后，用完整Global整体替换其上一轮本地SkillBank；不得在旧Candidate Bank上增量叠加服务器结果。下一轮本地自进化以“完整新Global + 全新本地任务轨迹”为输入。
- 审计：服务器继续保存Parent→Result操作差异，但该文件只用于追踪聚合效果，不是下发对象。三个客户端可生成角色形状不同的运行适配器，但其逻辑Global内容与Global hash必须相同，不能被解释为个性化下发。

## D-026：经运行输入等价审计恢复旧G2评价进度

- 日期：2026-10-03
- 状态：生效，撤销D-023中“旧selector协议G2评价进度全部作废”的处置；D-023聚合规则、D-024容量和D-025完整Global下发继续有效。
- 证据：A/B/C旧评价运行视图与新G2的`active_skillbanks`逐字节相同，三端runtime semantic hash也分别完全相同；变化仅存在于聚合/下发协议元数据和完整文件hash，不进入Agent任务提示。
- 复用：恢复A/B/C=56/55/57个已完成任务，共168题；只补跑4/5/3题，共12题。最终汇总使用新G2文件重新生成适配器和source lock，并引用 `server_validation/G2_EQUIVALENCE_AUDIT.json`。
- 特殊终止：A第28题既有`GraphRecursionError`不含API基础设施错误，按冻结runner规则记为合成失败终止。已从既有日志补存result并修复runner今后自动持久化，避免断点恢复时重复执行。

## D-027：冲突组必须直接生成一个新patch

- 日期：2026-10-03
- 状态：生效，取代D-023中“无法安全合成时返回NONE”的分支；D-023的非冲突直接合并、D-024容量、D-025完整Global下发与D-026证据复用继续有效。
- 决策：同一target存在多个不同patch时，`deepseek-v4-flash`直接结合该冲突组内容，必须输出恰好一个新的完整patch。服务器不再判断内容是否“安全合并”，DeepSeek不得返回`NONE`或`null`，聚合器也不得静默丢弃冲突组。
- 最小结构约束：新patch仍须保持冲突组target与scope，operation须来自该组已有操作，非DELETE须包含完整`after_skill`；这些是保证patch能够应用的协议校验，不是候选准入或安全筛选。服务器评价结果仍不得进入聚合prompt。
- 异常处理：若模型输出缺失、`null`、非JSON或不满足最小结构，当前聚合轮失败并重试/报错，不把该冲突组降级为NONE，也不以固定哈希选择某个候选。
- 历史影响：Round 2的18个净patch指向18个不同target，没有冲突且未调用DeepSeek，因此既有G2 hash、等价性审计和G2服务器评价结果全部保持有效，无需重跑。

## D-028：完全相同patch也必须进入DeepSeek聚合

- 日期：2026-10-03
- 状态：生效，取代D-023/D-027中的“完全相同结果先去重并合并proposer”步骤；D-027每组必须生成一个新patch、不得NONE/null的规则继续有效。
- 分组：服务器不做正文级精确去重。按target直接汇集客户端上传的原始净patch；某target只有一条patch时直接应用，有两条及以上时，无论内容相同、部分相同或不同，全部交给`deepseek-v4-flash`。
- 输出：每个同target多patch组必须生成恰好一条新的完整patch。新patch汇总全部输入patch的proposer与输入candidate ID；模型返回缺失、null、非JSON或最小结构非法时整轮失败并重试，不能静默去重、丢弃或选择原候选。
- ADD：多个无target的ADD仍按相同scope组成多patch组并交给DeepSeek；单个ADD直接应用。最小target/scope/operation/schema/base-hash/容量校验继续保留。
- 历史影响：Round 2的18条patch分别指向18个不同target，每组都只有一条，因此D-028不改变G2物化结果、hash、等价性审计或服务器评价结果。

## D-029：用同一冻结60题补跑Round 2本地库消融

- 日期：2026-10-03
- 状态：生效；这是分析条件，不修改D-019/D-022的全局收敛口径。
- 对象：`LA2/LB2/LC2`分别指A/B/C从共同G0出发、完成Round 2一个本地cycle后的Batch 4最终`local_candidate_bank.json`；它们不是新的G0，也不是服务器Global。
- 评价：LA2使用Client A执行器、LB2使用Client B执行器、LC2使用Client C执行器，各运行与G2完全相同的冻结服务器60题、Qwen3-8B、temperature 0、seed 1234、thinking关闭，共新增180 conditions。G2既有A/B/C各60题不重跑。
- 分析：报告每端`G2 - Local`成功数差、逐题失败转成功/成功转失败，以及训练两类与未训练四类的分项变化，用于区分本地演化效果和聚合正/负迁移。
- 隔离：本地库评价结果只记录；不得选择或拒绝patch、回滚G2、修改下一轮任务/prompt/聚合规则，也不得进入最近3个Global点的收敛窗口。全局停止仍只读取G0/G2/G3等服务器Global评价。

## D-030：新本地代际实验先只运行 Client A，并更换任务执行模型

- 日期：2026-10-07
- 状态：部分生效；新实验范围与数据规模已由用户确认，精确模型版本和正式启动仍待确认。
- 客户端范围：首个试运行只包含 Client A，不启动 Client B/C，也不进入既有 `blind_global_patchfl` 的联邦收敛链。
- 本地演化：从空 `B0` 开始；每代固定父库，Client A运行六类任务各12题、共72题，完整训练轨迹保存后由Teacher统一生成下一代SkillBank。
- 验证：六类各12题、共72题；`B0`及之后每个冻结SkillBank各自单条件运行一次。验证只记录学习曲线，不做Parent/Candidate比较、准入、回滚或早停，验证轨迹与分数不得进入Teacher。
- 模型变更：用户指定将客户端任务执行模型从`qwen3-8b`改为`qwen3.6-flash`。当前正式源码和配置尚未修改；浮动别名`qwen3.6-flash`与固定快照`qwen3.6-flash-2026-04-16`之间仍需在启动前确认。

## D-031：所有客户端的新运行统一使用 qwen3.6-flash

- 日期：2026-10-07
- 状态：生效，补充并取代D-030中“仅Client A试运行”和“模型版本待确认”的部分；D-030定义的代际训练与单条件验证口径不变。
- 客户端范围：新实验的A/B/C任务执行模型全部统一为浮动模型ID`qwen3.6-flash`；不再限定只有Client A可配置该模型。实际调度仍可先运行A，但B/C使用相同模型锁。
- 历史隔离：不复用任何`qwen3-8b`产生的空库基线、训练轨迹、SkillBank、验证结果或联邦结果。历史run、归档和旧协议快照保持原样，仅用于审计。
- 实现：当前共享训练、验证、Stage3评价和Blind Global运行入口的默认任务模型已改为`qwen3.6-flash`。客户端底层脚本继续要求显式`--model`，由这些入口统一传入；Teacher/聚合模型仍为`deepseek-v4-flash`。

## D-032：新实验本地 Teacher LLM 使用 deepseek-v4.1-flash

- 日期：2026-10-07
- 状态：生效，取代D-031中“Teacher仍为`deepseek-v4-flash`”的部分；服务器冲突聚合模型不变。
- 模型锁：A/B/C本地Skill生成与后续修改统一使用`deepseek-v4.1-flash`、temperature 0；客户端任务执行继续使用`qwen3.6-flash`。
- 配置隔离：本地Teacher新增`LOCAL_EVOLUTION_BASE_URL`、`LOCAL_EVOLUTION_API_KEY`、`LOCAL_EVOLUTION_MODEL`。未设置Teacher endpoint/key时可兼容复用现有`STAGE3_AGGREGATION_BASE_URL/API_KEY`，但模型默认值独立锁定为`deepseek-v4.1-flash`，不会继承服务器聚合模型。
- 历史边界：既有`deepseek-v4-flash`演化记录、旧运行与旧协议快照保持原样，不进入新模型实验；服务器同target冲突合成仍维持既有`deepseek-v4-flash`口径，除非后续另行决策。

## D-033：新本地代际实验使用72题开发验证与134题最终测试

- 日期：2026-10-07
- 状态：生效，补充D-030定义的数据口径。
- 验证集：从ALFWorld `train` split冻结六类各12题、共72题，与本地训练任务保持goal-group隔离；`B0`及每个冻结SkillBank各运行一次，只记录学习曲线，不进入Teacher、准入、回滚或早停。
- 最终测试：使用官方`valid_unseen`完整134题，只在实验最终冻结的SkillBank上运行一次；结果不进入Teacher或任何模型/代数选择。
- 历史边界：不复用旧实验的134题结果、轨迹或分数。该官方split曾被项目历史实验运行过，因此它是本次运行独立重算的标准OOD测试，但不是对整个项目历史完全未见的题集。

## D-034：取消最终测试并将本地训练、验证均扩展为134题

- 日期：2026-10-07
- 状态：生效，取代D-030/D-033中的72题训练、72题验证和134题最终测试口径。
- 训练集：每客户端每代从ALFWorld `train` split运行134题；六类数量按官方134题类型分布冻结为简单取放24、双物品17、台灯18、加热23、冷却21、清洗31。代内固定父SkillBank，全部轨迹完成后Teacher统一生成下一代。
- 验证集：另从`train` split冻结同分布的134题，与训练集在goal-group层面完全隔离；`B0`及之后每个冻结SkillBank各运行一次，只记录学习曲线，不进入Teacher、准入、回滚或早停。
- 测试集：本实验不设置最终测试集，不运行`valid_seen`或`valid_unseen`；此前为D-033新增的最终测试入口和清单字段移除。

## D-035：Client A首代Teacher路由、分层合并与容量超限处置

- 日期：2026-10-08
- 状态：生效；适用于`stage2_local_v6/runs/client_a_generation_01_20261007_r1`的B1生成及后续从该停点续跑的同口径代际实验。
- Teacher调用：模型严格使用`deepseek-v4.1-flash`、temperature 0、seed 1234、thinking关闭。既有Stage3聚合endpoint不接受该模型，因此本地Teacher使用支持该模型的独立DashScope-compatible endpoint；不更换模型，也不改动服务器冲突聚合口径。
- 分层处理：Teacher先对Planner/Executor分别按六类任务生成12份类别分析，再各做一次角色级统一合并。验证轨迹和验证分数不进入Teacher；B1只读取B0训练的134条完整轨迹证据。
- 容量：Planner和Executor各自最多14条。若角色级合并超过上限，先要求Teacher修复两次；仍超限时执行可复现的确定性裁剪，优先保留general和较前任务类别条目并记录移除项。本次实际为Planner 15→14、Executor 18→14，最终B1共28条。
- 审计边界：原始模型输出、两次修复、确定性裁剪记录及最终库均保存在运行目录；B1必须报告为“Teacher生成并经协议容量裁剪”，不得描述为未经后处理的原始Teacher输出。

## D-036：Client A从B1后台连续演进至B5并在首错停止

- 日期：2026-10-08
- 状态：生效；用户已授权从冻结B1继续运行B2、B3、B4、B5，并要求B5独立验证完成后停止。
- 每代流程：固定B(N-1)完成同一冻结训练集134题，保存完整轨迹；Teacher读取该代训练证据及完整父库，按六类分析并统一执行保留、修改、合并、新增或删除，物化完整B(N)；随后仅在冻结验证集134题上评价B(N)。验证结果不进入Teacher，不准入、不回滚、不早停。
- 自动化边界：后台控制器只允许B2至B5，严格串行；任务阶段、Teacher阶段或完整性/API-clean校验任一失败即记录失败步骤并以非零状态退出，不进入下一步。B5验证完整后正常退出，不启动B6、Client B/C或联邦流程。
- 成本边界：后台本地Python流程不调用Codex模型；任务执行继续消耗`qwen3.6-flash`服务额度，Teacher继续消耗`deepseek-v4.1-flash`服务额度。启动和后续人工/Codex检查不属于后台实验调用。
- 历史保护：B0、B1及既有结果保持冻结；B2至B5使用独立命名目录和文件，控制器拒绝覆盖任何既有同名输出。

## D-037：从B3 Teacher检查点执行仅结构修复并恢复至B5

- 日期：2026-10-08
- 状态：生效；响应用户“从这里修复恢复”，补充D-036的首错停止与恢复规则。
- 故障：B3 Planner合并库中两个字段超过500字符上限（`principle` 506字符、`description` 583字符）；B3训练证据完整且API-clean，故障发生在Teacher输出结构校验，不重跑B1/B2/B3训练或B2验证。
- 修复：Teacher只接收当前合并库和明确的结构错误，必须保持每条技能的语义、scope、列表成员、顺序及各列表精确长度，只修复缺失、空值、非字符串或超过500字符的字段；不得新增、删除、合并、重排技能或引入新主张。修复输出及调用记录追加到原检查点审计链。
- 恢复：控制器`--resume`只复用带完整`summary.json`且通过代数、134题和API-clean校验的阶段，以及成对存在的冻结SkillBank/Teacher记录；不完整目录拒绝覆盖。当前从B3 Teacher检查点继续，之后仍按首错停止，并在B5验证后终止。

## D-038：B3起的Teacher改用DeepSeek官方API并重建B3

- 日期：2026-10-08
- 状态：生效，取代D-032/D-035/D-037中从B3继续使用DashScope托管Teacher或复用其B3检查点的部分；B1、B2历史产物保持有效且不重跑。
- 提供方边界：B1、B2已生成SkillBank继续保留，Teacher来源为DashScope托管的`deepseek-v4.1-flash`。从B3开始，Teacher必须使用`https://api.deepseek.com`官方端点，提供方描述必须为`deepseek_official`，模型ID为`deepseek-flash`；官方文档定义该ID当前对应DeepSeek-V4.1-Flash。
- 参数：temperature 0、thinking关闭；Chat Completions请求使用官方参数`thinking={type: disabled}`，不再发送DashScope专用`enable_thinking`。每次Teacher检查点、完整记录和SkillBank均写入不含密钥的endpoint descriptor，并校验响应模型ID。
- B3处置：此前由DashScope生成的B3 Teacher检查点及其修复日志移入`invalidated_b3_dashscope_teacher_20261008_r1/`，不得进入正式B3。复用完整且API-clean的B2固定库训练（即B3训练）134题，从该证据和B2父库重新执行完整B3 Teacher分析/合并；不复用旧B3 family analyses、merge或schema repair结果。
- 后续：B3验证完成后，B4、B5的Teacher继续使用同一DeepSeek官方配置；任务执行模型仍为DashScope的`qwen3.6-flash`。首错停止与B5验证后终止规则不变。

## D-039：技能单字段字符上限改为600并明确后台通知边界

- 日期：2026-10-08
- 状态：生效，取代D-037中的500字符字段上限；适用于当前B3官方Teacher检查点及之后B4/B5。
- 字段上限：Procedure/Local Strategy与Failure Lesson的每个必需文本字段统一允许最多600字符。当前B3 Planner两条超限描述中，537字符在新规则下直接合法，623字符仍需由DeepSeek官方Teacher压缩至600字符以内。
- 恢复：500字符规则下的两次schema repair不计入600字符规则的修复预算；允许在同一官方B3检查点下再进行最多两次仅结构修复，保持技能语义、scope、顺序及列表长度不变。B3训练和既有12份官方family analysis不重跑。
- 通知边界：零持续Codex额度的独立本地后台进程只能写控制器状态和日志，不能主动向当前Codex聊天推送失败消息。主动聊天提醒需要另行启用会运行Codex的定时heartbeat；未启用时，状态只在用户再次询问或人工检查时被读取。

## D-040：技能单字段字符上限进一步改为650

- 日期：2026-10-08
- 状态：生效，取代D-039中的600字符字段上限；通知边界及其他协议不变。
- 字段上限：Procedure/Local Strategy与Failure Lesson的每个必需文本字段统一允许最多650字符。当前B3 Planner唯一剩余的623字符描述在新规则下直接合法，不再调用schema repair，也不执行程序截断。
- 恢复：继续复用DeepSeek官方B3检查点、B3训练证据与已完成的12份family analysis；从Planner校验通过后的后续步骤继续，完成Executor合并后物化B3，再运行B3至B5验证链。

## D-041：技能单字段字符上限进一步改为800

- 日期：2026-10-08
- 状态：生效，取代D-040中的650字符字段上限；其他模型锁、数据隔离、首错停止及B5验证后终止规则不变。
- 字段上限：Procedure/Local Strategy与Failure Lesson的每个必需文本字段统一允许最多800字符。B4 Planner两次650字符schema repair后保留的796和710字符描述在新规则下直接合法，不执行程序截断。
- 恢复：复用完整且API-clean的B3训练证据及现有B4 DeepSeek官方检查点；不重跑B3训练、B3验证或B4的12份family analysis。由控制器从B4 Teacher继续，完成B4/B5验证后停止，任一步错误仍立即退出。

## D-042：134题阶段允许严格的逐题断点续跑

- 日期：2026-10-08
- 状态：生效；补充D-036的首错停止规则，用于外部API基础设施故障后的同阶段恢复，不改变任务集合、模型、SkillBank或成功判定。
- 准入：仅当阶段没有完整`summary.json`、已有`result.json`含1至133个完整episode、source lock完全一致，且这些episode逐题等于同一冻结任务集权威执行顺序的严格前缀时允许续跑。权威顺序取同phase上一代完整134题结果，并要求任务集合完全相同且无重复。
- 执行：只向任务模型提交尚未完成的任务；每次续跑写入独立`resume_segments/attempt_NNN/`，不覆盖原中断结果、日志或轨迹。续跑段必须与剩余任务集合严格相等且无重复，再按权威顺序合并并生成完整summary；不完整或身份不符时立即拒绝。
- 当前实例：B4验证已有70题与B3完整验证的前70题逐题一致，只补跑剩余64题；此前因欠费中断的第71题没有进入episode结果，因此作为未完成任务重新运行。

## D-043：Teacher family analysis非法返回先审计落盘再停止

- 日期：2026-10-08
- 状态：生效；补充B5及后续同协议Teacher family analysis的结构错误处理，不放宽候选数量或内容约束。
- 审计：`candidates`不是列表或超过4条时，先把完整`raw_model_output`、usage、role、任务类别、容器类型、候选数量和具体校验错误追加为`family_analysis_invalid`记录并保存检查点，再抛错触发首错停止。非法候选不得写入正式`candidates`集合。
- 恢复：检查点只跳过已进入正式`candidates`集合的分析单元，因此恢复时仅重新请求失败单元；本次只重试B5 `Executor/简单取放`，不重跑B4训练或已完成的六份Planner family analysis。上一次非法原始回复因旧实现未落盘而无法事后恢复；新规则从本次重试起生效。

## D-044：800字符硬上限下增加两次带余量的定向schema repair

- 日期：2026-10-08
- 状态：生效；800字符硬上限不变，补充B5 Teacher字段压缩失败后的恢复方式。
- 故障：B5 Planner“清洗后放置”一条`principle`在两次原schema repair后仍为960字符，超过800字符；十二份family analysis均已完成，Executor/简单取放定向重试也已成功，故不重跑这些调用。
- 修复：schema repair总机会由2次扩为4次；新增的第3、4次仍只允许修复列出的结构错误，保持语义、scope、技能数量、列表成员与顺序不变，并要求超限字段压缩至最多760字符，为800字符硬限制留出余量。每次原始输出和错误继续写入同一官方检查点；不得程序截断。
- 恢复：从现有B5检查点直接进入Planner第3次schema repair，成功后继续Executor合并、B5物化和固定134题B5验证；仍首错停止，验证完成后停止。

## D-045：技能单字段字符上限进一步改为900

- 日期：2026-10-08
- 状态：生效，取代D-041/D-044中的800字符硬上限；其他模型锁、数据隔离、非法返回审计、首错停止及B5验证后终止规则不变。
- 字段上限：Procedure/Local Strategy与Failure Lesson的每个必需文本字段统一允许最多900字符。B5 Planner“清洗后放置”经第3次修复形成的877字符`principle`在新规则下直接合法，不执行程序截断，也不再对该字段调用Teacher压缩。
- 恢复：复用B4完整训练证据、十二份B5 family analysis、Planner合并与容量处理、以及现有B5检查点；继续Executor合并、物化B5并运行固定134题B5验证。不得重跑B4训练或已完成分析，验证完成后停止。

## D-046：v7完整证据、无数量裁剪与证据检查

- 日期：2026-10-10
- 状态：用户已授权实施的新版本决策；仅作用于stage2_local_v7，不追溯改写D-035或v6结果。
- 数量：SkillBank及每次分析候选不设数量上限；取消容量修复、固定顺序裁剪和capacity_selection_required。单字段仍为900字符。
- 证据：完整保留训练episode行为与交接，只删除重复请求上下文及调用元数据；按完整episode拆批。默认48000 UTF-8字节输入预算和16000 tokens输出预算不是Skill容量。超请求预算不得有损截取。
- 物化：明确ADD/UPDATE/MERGE/DELETE操作经过独立证据检查后，选择互不冲突集合并确定性应用。未提及的旧规则保留；已反驳的旧规则不得静默沿用。每个适用旧规则与候选必须检查相关成功训练轨迹；最终进行Planner/Executor联合一致性检查。
- 实验：从空B0开始；训练/验证各134题、goal-group隔离、验证不进入Teacher。新manifest生成器使用新salt并排除v6精确trial；本次未冻结新清单。执行qwen3.6-flash，Teacher从B1起锁DeepSeek官网deepseek-flash，禁止回退到聚合平台配置。
- 边界：未增加运行时子任务完成验证器或top-k检索。语义检查仍由Teacher判断；有真实矛盾、非法格式或输入超预算时可停止，但不是数量超限停机。正式运行成本需要另行确认。

## D-047：修复v7审查问题并加入证据驱动完成验证

- 日期：2026-10-10
- 状态：用户已授权实施，补充D-046；仅作用于v7，正式实验未启动。
- 统一任务定义：编号、英文类型、中文标签、134题数量共用同一映射，禁止再手写不同顺序的数量。
- 预算：去掉48000字节硬编码默认；完整请求计入系统提示、JSON包装及输出余量，以显式上下文安全预算约束。自动完整episode分批，单题/固定提示超限保存预检报告并停止，不删轨迹。未知未来轨迹长度不能在训练前保证；训练前检查静态输入，训练后在任何Teacher调用前检查实际分析输入，各阶段生成新输入后检查。
- 证据：候选、旧规则结论与复查必须给出具体环境步骤、原始动作和观察，代码核对锚点存在；不把轨迹引用列表当作真实语义理解证明。
- 候选：每个已批准候选必须有去向；非重复、不冲突候选默认纳入。省略仅允许可核对的重复或同目标冲突，不允许无理由抛弃。
- 恢复：语义拒绝保持原始证据；最多两次定向修订，只调整被指明的规则，再检查受影响类别（General影响全部类别）。不能靠重问直到批准；未改变内容或耗尽预算则停止。
- 运行时：v7专用A包装器使用可机械解析的子任务模板和物品实例绑定。COMPLETED只有在成功动作/观察支撑谓词时推进；证据不足拒绝推进。整题成功仍以环境won为准。此改变会影响实验行为，不能将v7与v6差异只归因于容量修复。
- 输出提交：最终库与Teacher记录先保存同身份发布日志；中断后只补缺失文件，已有输出内容不同则停止，不覆盖冻结结果。该日志不是新的实验输入。

## D-048：原反例消解门禁

- 日期：2026-10-11
- 状态：用户明确授权实施，补充D-047；仅作用于v7，正式实验未启动。
- 普通UPDATE与定向修复共用正文实质变更校验；原文不变、仅标题/空白变化不得增加版本。
- 完整保留每个被反驳旧技能的原检查、原文锚点及分析批次身份。UPDATE/MERGE/DELETE除常规候选检查外，必须逐条对照原反例解释旧断言、新断言及消解原因；证据不足或未消解不准入。
- 最终跨角色修订后再次对照实际冻结内容检查原反例，未变内容复用同提示检查点；后续修改或删除生成新检查，不靠反复重问寻求批准。
- 不使用验证集，不增加执行episode。语义消解仍由Teacher判断；程序核验覆盖、真实引用、正文变更及检查身份，不宣称机械证明语义正确。新增Teacher成本须在正式运行前确认。

## D-049：修复语义否决、恢复提交与当前状态谓词

- 日期：2026-10-11
- 状态：用户授权实施，补充D-048；仅v7。正式实验仍未启动。
- 语义检查：合法unresolved/insufficient作为否决缓存，不要求它证明已修正；只有resolved必须给出变更字段的新断言。伪造引用、遗漏原锚点仍属格式错误。
- 恢复：显式覆盖0–134题；134题仅补证据/汇总提交、不重新执行；校验并接收已有续跑段的完整连续前缀，发生身份/内容/顺序冲突则停止，不覆盖历史段。
- 完成：转换谓词使用当前温度/清洗/灯光状态及对应成功动作，后续相反操作撤销旧状态；整题仍由环境won判定。
- API：只检查结构化异常类型/异常字段；不把Thought、技能、环境反馈中的timeout等字样当故障。
- 修订：协议升级v4、完成验证标识升级v2；规格/文档/测试同步，旧运行检查点因协议及源码身份变化不复用。无数量裁剪或top-k，不擅自启动付费试验；真实成本/效果需正式运行前另确认。

## D-050：未消解旧规则的选择前确定性门禁

- 日期：2026-10-11
- 状态：用户授权实施，补充D-048/D-049；仅v7，不启动正式实验。
- 任一已被反驳旧规则没有获批UPDATE/MERGE/DELETE覆盖时，保存角色、未消解ID、原反例、候选、批准集合及消解检查，然后在Teacher选择请求前停止。此停止是实验语义门禁，不是Teacher格式错误；不新增自动修正或反复请求。
- 原有选择约束及最终内容门禁继续保留，不能用有修正候选代替已选择并通过最终检查。合法否决缓存复用，非法证据仍拒绝。

## D-051：v7完整来源锁及原子结果提交

- 日期：2026-10-11
- 状态：用户授权实施，补充D-049/D-050；不启动正式实验，不改历史共享执行器源码。
- 新清单冻结选中任务目录全部文件内容；控制器、独立phase与Teacher使用统一仓库代码锁。阶段提交接收校验完整预期来源、结果/证据及汇总；Teacher接收通过原发布日志及完整身份恢复。
- v7进程使用原子结果写入及最近完整结果副本；损坏/冲突仍停止，不猜造结果。协议升级v5，旧清单和检查点不得复用。134题、模型、训练验证隔离及无裁剪口径不变。

## D-052：用户授权启动Client A v7正式实验

- 日期：2026-10-11
- 状态：用户明确要求“现在启动实验”；既有v5设计不变，启动须通过凭据和输入预检。尚未启动时不得把准备工作记为running。
- 仅A：空B0验证、五代固定父库134题训练/Teacher演化及每库134题隔离验证，B5验证后停止；首错停止，不自动绕过门禁，不启动B/C或联邦。
- 新清单`stage2_local_v7/artifacts/manifests/client_a_v7_20261011_r1.json`；预定运行目录`stage2_local_v7/runs/client_a_v7_20261011_r1`。冻结内容哈希，不复用旧轨迹/SkillBank/结果；运行将消耗用户配置Qwen和官方DeepSeek API额度，不作未经测量的费用承诺。

## D-053：恢复既有本地凭据加载入口

- 日期：2026-10-11
- 状态：用户明确要求恢复此前加载配置；接续D-052正式启动授权。
- 复用上游工作区的scripts/load_secrets.sh及secrets/.env，不复制或输出密钥、不修改原文件。将已配置且验证为DeepSeek官网的聚合凭据映射到独立LOCAL_EVOLUTION变量；模型固定deepseek-flash，任务仍固定qwen3.6-flash，官网锁不符即停止。
- 新增v7非密钥启动包装scripts/run_client_a_with_local_secrets.sh。该包装只负责加载既有凭据及调用已验证控制器，不修改实验口径或复用旧结果。

## D-054：暂停首轮v7并修复放置契约语法

- 日期：2026-10-11
- 状态：用户明确授权暂停、保留记录、修复测试后以新运行身份重新开始B0验证；补充D-052。
- 原r1控制器及子进程已停止，保留全部已有输出，34题完成、19题成功，其中3题因放置句中的in被拒绝。此为不完整旧代码运行，不纳入新学习曲线；原状态文件保持证据原样，另存用户中断记录。
- v7计划接受in、on、in/on并解析成相同放置谓词；不改变真实环境动作语法、物品实例绑定、目标编号和环境反馈核验。解析错误明确返回子任务ID、原文和允许模板，沿用一次有限重写机会。
- 新运行目录client_a_v7_20261011_r2，继续使用原冻结134训练/134验证清单，避免更换题目混入修复效果；源码身份重新冻结，空B0重跑全部验证，不续接r1题目或结果。测试通过后延续到B5验证结束，首错停止。原任务输入和模型锁不变。

## D-055：v7执行前整计划目标覆盖门禁

- 日期：2026-10-12
- 状态：用户授权按方案实施第一个问题；仅离线修复测试，不恢复或启动实验。
- 从可见Your task is to文本解析目标，结合冻结task_type校验六类；不读取隐藏PDDL/traj答案。六类要求Take/Put、Take/Look、Take/转换/Put、Take first/Put/Take second/Put，核验物品、目标及全部可成功OR路径；格式与覆盖失败共享既有一次有限重写预算，不程序补步骤。
- 完成实例/环境反馈验证不变；强化Take前置只使计划与当前完成器契约一致，不实施动态实例绑定或放宽类型。同一ID重复引用、未使用定义、重复定义及不完整OR分支拒绝。
- 新增规格门禁身份及源码锁；旧运行输出保持证据，不得在新源码下直接resume旧身份。顺序故障另待授权修复，不续跑、不承诺成功率提升，不把验证轨迹送给Teacher。

## D-056：非Take子任务的真实持有前置门禁

- 日期：2026-10-12
- 状态：用户授权按建议实施，仅v7离线修改测试，实验保持停止。
- 沿用独立Take→转换/Look/Put流程；进入非Take子任务必须根据成功动作和匹配观察确认已持有正确类型具体实例，否则该子任务直接FAILED，不调用Executor或执行动作，不创建null绑定契约；OR仍按原控制器处理备选路径。
- 通过前置检查后固定绑定开始时实例，不在执行中改绑，不放松身份/目标/成功反馈核验。检查与失败原因留存trace/result/训练evidence。旧3题不得改成整题成功；顺序问题不在本次范围，不启动或恢复实验。

## D-057：未来v7运行使用显式冻结执行顺序

- 日期：2026-10-12
- 状态：用户明确授权；只修复未来运行，不恢复旧运行结果，不作为后续实验输入。
- 每阶段启动前按题型1–6、任务标识大小写敏感排序生成唯一完整清单；冻结到阶段文件及来源锁。v7专用入口禁止TextWorld再次打乱，续跑只执行清单未完成后缀，每次reset在模型调用前核验题目身份。
- 执行、恢复、汇总使用同一清单，清单被改动/重复/遗漏、运行顺序偏离立即停止。取消从历史结果指定顺序的入口；不放松前缀、数据、源码和API-clean检查。不修改共享客户端或历史产物，不启动正式实验。

## D-058：修复后以新身份启动Client A并每10分钟汇报

- 日期：2026-10-12
- 状态：用户明确授权启动新实验及每10分钟进度提醒。
- 新运行`stage2_local_v7/runs/client_a_v7_20261012_r1`，从空B0验证开始，执行既有B0–B4固定父库训练、B1–B5 Teacher及逐库验证，B5验证后停止；遇程序/API错误停止，不自动修复或恢复。
- 沿用冻结输入清单`artifacts/manifests/client_a_v7_20261011_r1.json`的训练134/验证134及goal-group隔离，只复用题目输入，不复用r1/r2结果、轨迹、SkillBank或Teacher检查点。新源码/规格身份独立锁定，采用D-055/056/057修复。
- Qwen执行模型`qwen3.6-flash`，Teacher官网`https://api.deepseek.com`、锁定API ID `deepseek-flash`；保持已有900字符及完整证据预算。凭据只通过既有加载包装在进程内加载，不输出或复制密钥。预算总调用费用随任务与Teacher复查动态变化，不能预先精确保证。
- 当前聊天每10分钟只读检查新运行状态/日志并汇报阶段、episode进度、成功数与异常；失败报告根因并停止监控，完成报告最终进度并停止监控，不自动开启下一实验。

## D-059：为下一次实验准备670题无重复五轮训练池

- 日期：2026-10-12
- 状态：用户授权准备670题方案；当前D-058实验照常运行，不授权同时启动第二个实验。
- 五轮各134题，六类每轮24/18/31/23/21/17，总670；轮间goal-group互不重复。固定沿用当前冻结134题验证输入，所有训练goal-group均与验证隔离；选题仅由可解标识、类型和固定hash排序决定，不读取成绩。
- 单轮固定B(N-1)完成当轮134题，Teacher只用该轮完整训练轨迹更新生成BN，随后在固定134题上验证；B0为空，B0–B5均验证。Teacher旧规则成功反例检查范围仍是当轮134题，不宣称跨轮全部历史轨迹复查。
- 保持v7运行模型、Teacher、字段限制、环境检查及完整证据策略。新方案放在独立stage2_local_curriculum，复用v7只读阶段入口，不修改运行中源码或凭据；数据清单、输入内容和调度代码均单独锁定。
- 先检查实际可解题量及既有排除输入，足够才冻结；禁止通过重复goal-group或放松验证隔离凑数。当前运行与历史结果/SkillBank/Teacher检查点不作为新方案输入。

## D-060：允许670题方案重新执行历史试题输入

- 日期：2026-10-12
- 状态：用户明确确认“允许复用历史试题，全部重新执行”，补充D-059的历史精确试题排除条件。
- 仅允许重新读取历史试题输入，不复用任何历史成绩、轨迹、SkillBank或Teacher检查点；仍从空B0开始。新清单明确记录该许可，取消更早历史试题的精确ID排除，但仍排除当前134条训练精确输入。
- 五轮训练goal-group完全去重、全部训练与固定134验证goal-group隔离及实际可解性筛选保持不变。不修改运行中的D-058实验，也不启动第二实验。

## D-061：用户暂停B0训练

- 日期：2026-10-12
- 状态：用户明确要求“B0暂且不进入训练”，撤回D-058后续自动推进授权直到新指示。
- B0验证77/134完整结果保留。请求到达时训练已经开始，停止时18完整题/13成功保留，不继续训练，不进入Teacher，不删除记录。
- 控制器及当前训练子进程已退出，运行状态标记paused_by_user，进度提醒PAUSED；不自动恢复，不自动改启670题实验。

## D-062：400题十批训练池替代下一次670题方案

- 日期：2026-10-12
- 状态：用户明确授权准备并冻结400题、10批各40题；未授权启动模型调用。D-059/060的670题冻结产物保留原位，不作为下一次默认方案。
- 六类近似均衡，每批每类6或7题；固定选题seed=42，类型顺序固定，分层选取后批内随机排序。400题优先严格每goal-group仅一题，足够时不降级为重复组；不足直接报错。与沿用固定134题验证集在goal-group层面完全隔离。
- 允许所有历史训练题目输入（包括刚暂停的134题训练输入）重新被选中；不读取历史成绩、轨迹、技能或Teacher输出。只读取冻结验证任务及其输入哈希。全部400题未来重新执行，从空B0开始。
- 预期每批后更新一次技能库，共B1–B10，固定134题验证每库含B0；本次冻结数据而不启动。现有v7入口硬限定134题和B5，400清单使用独立协议，禁止交给旧入口冒充兼容；运行适配完成并通过测试后才可另行启动。

## D-063：只启动400训练池的B0第1批40题

- 日期：2026-10-12
- 状态：用户明确要求“开启B0训练”，授权第1批40题新调用；不授权自动生成B1、后续批次或重新执行B0验证。
- 新运行身份从空B0开始，严格执行D-062冻结batch_01的随机列表顺序。采用逐题独立子进程复用v7完成检查和持久化，每题环境reset身份核验；不修改历史/暂停v7源码或结果。
- 输入池、执行入口/源码、模型、B0和数据内容均锁定；首个程序/API错误停止，任务语义失败记录后继续本批。完整40题后输出完整训练证据并停止。费用为40题Qwen调用，不调用Teacher。
- Teacher40题及B1–B10全流程适配不在本次启动范围，不将新证据交给旧134题Teacher；旧18条训练记录及旧验证结果都不作为本批输出复用。

## D-064：当前400池运行自动续至B5验证

- 日期：2026-10-12
- 状态：用户明确授权在当前B0训练完成后自动生成B1、验证，再训练更新至B5验证后停止，扩展D-063。
- 只使用冻结batch_01–05各40题，共200训练episode；batch_06–10保留不执行。每个父库固定执行一批，Teacher用本批完整40题轨迹，B1–B5各固定134题验证。验证不反馈Teacher、不作为准入/回滚；不复用历史结果。当前B0已完成题不重跑，不补旧B0验证。
- 活跃B0锁定的源码不改动，新适配全部放在stage2_local_curriculum/automation子目录并单独锁定。复用v7语义/证据/操作/成功反例/跨角色修订模块，40题计数由冻结批次推导，禁止重复轨迹凑134。
- 模型qwen3.6-flash、Teacher官网deepseek-flash；900字符、无数量裁剪及有界语义修复不变。每阶段首个程序/API错误停止，不自动修复重启。独立continuation_state.json负责后续调度，原B0 controller_state.json只代表B0阶段，不改写旧身份。

## D-065：修正Teacher对象示例并显式恢复首次B1失败

- 日期：2026-10-12
- 状态：用户明确授权按照方案修复及恢复；补充D-064，不修改原失败身份。
- 分析提示提供两种合法skill对象示例，DELETE可省略skill。只对分析回复的JSON/对象结构错误最多追加2次格式纠正，逐次先保存原回复；证据、旧规则反例、合法否决/未消解及其他语义错误不触发格式纠正。不放松900字符与环境事实检查，不添加数量裁剪。
- 恢复仅允许原控制器失败在B1_teacher、已完成前缀仅B0_training、原checkpoint只有analysis/Planner/1/0非法skill字符串的情形。核对原身份与全部B0输出、新旧代码哈希、父库/证据/模型/随机种子/预算；以recovery_01独立状态/检查点/日志保存恢复记录，旧文件不改写。
- 原40题训练不重跑；重新请求唯一失败分析，再正常执行B1–B5既定流程。测试与启动预检通过后才调用外部模型；batch06–10不执行。

## D-066：Teacher核对证据登记不一致并保留已完成分析

- 日期：2026-10-12
- 状态：用户明确授权“Teacher核对后重新提交”方案，补充D-065。
- 仅在所有现有证据步骤/操作/环境反馈均真实且引用编号与步骤编号集合不一致时，最多2次请求Teacher核对。返回完整回复和逐项核对理由；可加入实际已引用题目、移除未使用的额外步骤，或为原已引用题补充真实步骤。程序只检测差异、验证回复，不自动增删证据。
- 不允许删候选、改变技能/操作/旧规则判定/支持反例分类或删除原已登记题的步骤以绕过检查。伪造步骤、未知引用、遗漏成功反例、未消解等仍停止。完整严格校验和独立候选复查保持不变；核对不代表批准。
- 已失败recovery_01状态/检查点/日志及其代码快照保留原位。新recovery_02核验B0、旧输入/模型/预算/代码及4条有效分析的原prompt哈希和语义，再缓存使用；仅对analysis/Planner/4/1非法回复请求核对，其余后续阶段照常至B5验证停止，不重跑训练或4条有效分析。

## D-067：Teacher核对候选批准与反例分类冲突

- 日期：2026-10-12；状态：用户明确授权按照核对方案解决，补充D-066。
- 失败episode不自动等于规则反例。candidate_check中批准且列出反例时，先严格核验覆盖、引用、全部原文锚点；仅此冲突最多2次交Teacher核对分类和结论，并要求说明每个重新分类的理由。程序不移动证据、不删反例、不猜批准。
- 原证据引用并集、所有步骤原文、检查覆盖和候选保持不变；Teacher可重新分类support/counterexample、改为reject/insufficient，仍须通过原完整validate_review。合法否决不重试；伪造或其他非法回复立即停止。核对成功不等于库发布。
- recovery_03仅迁移recovery_02失败前8条有效Planner分析及check/Planner/0/0原始非法回复，新状态/日志/检查点独立。核验旧身份/源码快照/B0/原提示及全部缓存语义；第一付费调用仅失败检查核对，其后既定前5批至B5验证停止。不得重跑B0、改冻结输入或使用验证轨迹。

## D-068：分类漏登记沿用原核对总额恢复

- 日期：2026-10-12；状态：用户授权按方案解决，补充D-067。
- 在分类核对中，仅原始锚点/覆盖/解释完整不变、且引用并集缺少原引用的登记遗漏可再次交Teacher；新增引用、改写步骤、遗漏成功检查、缺解释仍立即停止。提示明确缺少哪个引用，程序不补清单。
- 每次核对始终对照最初完整回复；跨恢复累计review_correction_index，最多2次，不因进程重启刷新额度。当前已使用1次，只剩1次。合法拒绝不重试，修正后必须原完整review校验。
- recovery_04保留全部旧记录/B0/8有效分析和两份失败检查原回复，验证代码快照、历史哈希、原prompt和缓存语义；第一API边界仅check/Planner/0/0的第2次核对，其后按既定前5批至B5验证停止。

## D-069：候选检查引用登记核对

- 日期：2026-10-12；状态：用户明确授权四项修改，仅实现和离线测试，本轮不自动恢复实验。
- candidate_check先逐项核验全部原始动作/步骤/反馈、引用与完整检查覆盖，伪造/未知证据即停止；仅登记集合不一致可交Teacher核对。未登记步骤由Teacher选择加入support_refs、加入counterexample_refs并修改结论、或移除未使用额外步骤，并逐项说明理由。程序不代填或代删。
- 原候选、原已登记引用及其支持/反例分类、原已登记证据步骤、检查覆盖不变；为原引用补缺少的真实步骤可接受，额外未登记步骤只能按理由分类保留或移除。修正后仍走完整原review校验，非空反例禁止批准。
- 每条独立候选检查的引用登记/分类核对共享总上限2次，沿用review_correction_index跨恢复累计，绝不分别赠送2次。合法reject/insufficient不重试，原始回复/所有尝试先保存。04状态/检查点/日志与源码快照保持不变，恢复须另行授权和身份审计。

## D-070：审计恢复候选检查并恢复监控

- 日期：2026-10-12；状态：用户明确授权重启既有实验及错误通知。
- recovery_05精确保留04中的8条有效分析和check/Planner/0/0，后者已用完2次核对，不再请求；首个付费边界仅check/Planner/1/0引用登记核对。核验原身份、源码快照、B0及原提示/缓存语义，不改写04或其他历史产物。
- 仍仅执行前5批，B5验证后停止，不改变400题池或固定134验证集、不重跑B0。恢复既有监控，尝试每分钟只读检查错误并每10分钟汇报进度；定时检查不承诺同秒提醒。失败停止并通知，不自动修复或重启。

## D-071：unused漏删的严格有界核对及恢复

- 日期：2026-10-12；状态：用户明确授权按方案修复代码并重启既有实验。
- 仅真实、原本额外未登记的步骤被Teacher明确判unused、未登记为支持/反例却仍保留的孤立遗漏可再核对；所有原文、原已登记证据/分类/顺序、覆盖、候选及解释保护必须先通过，其他非法内容仍立即停止。程序不代删证据，不放行不一致回复。
- 使用原每检查共享2次总额；check/Planner/1/0已用1次，恢复06只能请求第2次，仍失败则停止。核验05旧代码快照及完整历史身份、原9条有效缓存和两份失败原回复，不改写旧产物或重跑B0。既定前5批至B5验证后停止；恢复原只读错误/进度监控。

## D-072：候选登记核对耗尽后不准入

- 日期：2026-10-12；状态：用户授权修改方案，本轮只修改和离线测试，不启动恢复。
- 仅candidate_check真实引用登记遗漏在共享2次预算耗尽时，完整重验三份回复的原文、覆盖及跨尝试不可变保护后，可记系统状态invalid_review/reason_code=correction_exhausted。valid仍为false，不生成Teacher reject/insufficient、不删证据或继续请求。伪造/未知证据、非法改动、API故障及其他语义错误仍停止。
- 任一检查批次invalid_review则整条候选不准入，其他候选继续；原始回复和三次尝试全部保留，准入/排除去向独立记录。被反例推翻的旧规则仍必须有合格操作消解，否则停止发布，不能因候选无效而沿用已知错误。
- 06失败输出原位保留，恢复须另建审计身份重验15条有效记录及检查7三份回复，不得重复06入口、不刷新预算。

## D-073：继续既有实验并审计排除耗尽候选

- 日期：2026-10-12；状态：用户明确授权继续实验。
- recovery_07仅迁移06的8有效分析、7有效候选检查及检查7三份耗尽回复；完整重验原源码快照/身份/B0/缓存提示和语义，耗尽检查按D-072系统不准入，首个新付费边界检查8，无新增核对额度。不改旧产物，不重跑训练。
- 后续既有前5批至B5验证停止，恢复原每分钟只读错误检查及每10分钟进度提醒，失败停止并通知，不自动修复重启。

## D-074：v8采用SkillOpt官方代码设置

- 日期：2026-10-12；状态：用户确认“用代码的实验设置”。此新请求取代D-073的恢复启动，recovery_07尚未正式启动。
- 独立stage2_local_v8以Microsoft/SkillOpt固定提交343db229dbd5ddaf9df6b1d5540d8bcdb2604d5c及其配置/清单为来源；训练39、选择验证18、最终测试134，论文文字140选择集不用于此分支。不自行增加goal-group隔离或重抽样后仍称官方清单。
- 保留原单技能文档、初始通用技能和官方训练/选择门控逻辑；不移植v7双角色库及其候选检查。原模型设置与既有用户Qwen/DeepSeek模型选择的差异须单独记录，未经同意不切换到GPT-5.5。
- 不复用任何旧结果/轨迹/技能库；只冻结输入及离线预检，本次未授权付费执行、最终测试或恢复旧监控。

## D-075：v8改为双SkillBank、同模型坐标式自进化

- 日期：2026-10-12；状态：用户明确纠正，取代D-074中“单技能文档+独立Teacher”的有效协议；D-074及其冻结锁只保留为历史审计证据。
- Client A仍为`Planner -> Executor`。Planner和Executor各有一份结构化SkillBank，两库均从空库开始；每个坐标固定另一角色库，只允许当前角色库变化，并以完整联合轨迹进行角色归因。
- Planner、Executor和自反思变异统一使用冻结的`qwen3.6-flash`；v8不设Teacher、不调用DeepSeek。自反思是同一客户端模型的额外调用，不得在文档、日志或成本统计中记作Teacher。
- 每个候选以完整Planner/Executor系统在固定18题选择集上评价，成功数不低于父系统即接纳（含平局）；按Planner后Executor执行4个cycle，共8次坐标更新。完成后只在固定134题上测试一次，测试不反馈演化。
- 沿用D-074官方代码任务清单作为数据设置：39训练、18选择、134测试，goal-group交集为0，环境上限50步；只使用其任务清单，不使用SkillOpt单文档optimizer。该实现是对论文同模型逐角色坐标上升方法的双代理/双结构化SkillBank适配，不声称逐项复现论文三角色及其数值超参数。
- 当前仅实现并离线验证演化核心、同模型单步变异入口、门控、计划和冻结锁；正式ALFWorld控制器尚未接通，启动脚本保持fail-closed。本次没有模型/API调用或正式运行。

## D-076：v8轨迹反思和SkillBank更新改用DeepSeek

- 日期：2026-10-12；状态：用户明确修改模型分工，取代D-075的“同一Qwen执行与变异”设置；D-075的双库结构、逐角色冻结和选择门控继续有效。
- Planner和Executor环境执行继续锁定`qwen3.6-flash`（DashScope）；完整联合轨迹的反思及当前角色SkillBank候选生成改用DeepSeek官方接口，项目别名`deepseek-v4.1-flash`、实际API ID `deepseek-flash`、base URL `https://api.deepseek.com`。
- DeepSeek定义为离线演化优化器，不是第三个运行时agent。每次仍只允许更新一个角色库，另一库字节/哈希不变；候选仍由完整Planner→Executor系统在固定18题上评价，不降即接纳。
- 由于执行模型和变异模型不再相同，v8保留论文的逐角色坐标上升、联合轨迹和验证门控，但不再声称严格复刻论文“同一冻结模型”条件。旧r1同Qwen模型锁仅保留审计，r2为当前有效锁。
- 本次仅修改代码、锁和离线测试，没有读取凭据、调用模型或启动正式实验；正式控制器仍未实现，启动脚本继续fail-closed。

## D-077：v8候选准入改为严格提升；稳定机制方案待确认

- 日期：2026-10-12；状态：严格提升由用户明确确认并已生效；稳定机制具体迁移方案待用户确认后实现。
- 固定18题选择集上只有`candidate_success_count > parent_success_count`才接纳；平局明确记为`tie_rejected`并保留父库，取代D-076沿用的“不降即接纳”。旧r2锁只保留审计，r3为当前有效锁。
- 当前尚未实现SkillOpt文本学习率、拒绝编辑buffer、slow update及meta skill，原因是其官方实现面向单技能文档，不能未经角色归因设计直接注入双结构化SkillBank；尤其官方默认slow update不经selection gate，会破坏本项目严格单调性。
- 提议按角色迁移：活动角色使用ADD/DELETE/REPLACE有界补丁，四cycle的cosine编辑预算为`[4,3,2,2]`；Planner/Executor各自维护拒绝buffer；每cycle的20样本slow update也必须通过18题严格提升门控；meta skill只进入DeepSeek优化上下文，不注入客户端运行库。完整规格见`stage2_local_v8/STABILITY_MECHANISM_PLAN.md`。
- 在稳定机制和完整控制器实现、测试、重新冻结前，启动脚本保持fail-closed；本次未调用模型或运行实验。

## D-078：v8双SkillBank稳定机制核心实现

- 日期：2026-10-12；状态：用户明确要求按D-077方案修改，核心机制已实现并冻结为r4；ALFWorld端到端命令编排仍未接入。
- DeepSeek输出仅允许当前角色的`ADD/DELETE/REPLACE`补丁；每条操作绑定旧目标哈希、轨迹证据和理由，程序校验角色、分区、ID、旧哈希和证据后确定性应用。四cycle每个角色的最大生效编辑数为`[4,3,2,2]`，不设置SkillBank总容量。
- Planner/Executor分别维护append-only拒绝buffer；平局和下降记录父/候选哈希、完整补丁、应用报告、18题分数/结果哈希、失败模式和证据，同父库下语义等价的已拒绝补丁不得再次提交。格式错误另存审计，不进入语义buffer。
- 每个角色每cycle从完整39条中按固定种子确定性取20条生成slow patch；fast与slow共用固定18题严格提升门控，平局或下降均回滚父库。每cycle的meta skill只进入DeepSeek优化上下文，硬标记禁止运行时注入。
- 所有JSON使用同目录临时文件、fsync和原子替换；DeepSeek调用在发出前写入call ledger，`in_flight`恢复必须人工审计，程序不得自动重放。控制器状态固定8坐标的training/fast/slow/meta及最终134阶段顺序，并核验已完成产物哈希。
- Windows和项目WSL环境各16项离线测试通过，覆盖预算、三种操作、旧哈希、证据、冻结角色、平局fast/slow、buffer隔离、meta泄漏、调用重放、阶段顺序和产物篡改；r4锁复核通过。无模型/API调用、无v8 runs目录。
- 启动脚本继续fail-closed。下一步必须把现有ALFWorld episode runner接入状态机并完成不调用外部模型的端到端dry-run，之后才可建立新运行身份并请求付费启动。

## D-079：v8付费调用ledger写入时机修正

- 日期：2026-10-12；状态：实现审查中发现并修复，r5取代r4作为当前有效锁；不改变D-078算法口径。
- r4在本地输出/凭据预检之前写入`in_flight`，缺少凭据时虽未发出API请求，也会留下需要人工审计的假in-flight状态。r5先完成模型、端点、输出路径、依赖和凭据的本地检查，在实际付费请求前最后一步原子写入intent ledger。
- 已完成请求仍先从ledger按输出哈希恢复，不要求重新提供凭据；真实`in_flight`或`invalid_response`仍禁止自动重放。Windows和项目WSL各16项测试及r5冻结锁复核通过；未读取实际凭据、未调用模型、未建立runs目录。

## D-080：v9作为v6取消容量限制的单变量代码对照

- 日期：2026-10-12；状态：用户明确要求生成v9并保留v6源码及B0--B5结果。
- v9以当前冻结v6入口源码为基线，只删除最终合并提示中的每角色14条上限、两轮容量修复、固定逆序机械裁剪和编号后的14条容量断言；每条Skill的900字符字段限制及schema修复继续保留。
- v9训练/验证各134题的任务数组与v6冻结清单逐项一致，用新实验ID和独立`stage2_local_v9/runs/`保存未来结果；不得复用v6 SkillBank、轨迹或结果作为v9父代/结果，也不得改写v6目录。
- 实现采用fail-closed源码覆盖层：运行前核验v6入口和清单SHA-256，再应用精确、可测试的容量差异及v9路径重定向；基线源码漂移即停止。当前只完成代码、清单与离线验证，未调用外部模型或启动正式实验。
- v6实际B1/B2产物来自早期DashScope托管Teacher，当前冻结v6入口已要求DeepSeek官方provider。若未来要把v9新结果与历史B0--B5结果解释为严格因果对照，正式启动前还必须冻结与历史一致的逐代provider口径；本次不擅自改变模型端点或启动实验。

## D-081：v9全部代际Teacher统一使用DeepSeek官方接口

- 日期：2026-10-12；状态：用户明确指定，取代D-080中“逐代provider口径待冻结”的状态。
- v9生成B1、B2、B3、B4、B5的全部Teacher调用统一使用`https://api.deepseek.com`，provider必须为`deepseek_official`，API模型ID为`deepseek-flash`；temperature 0、thinking关闭。
- v9不使用DashScope托管Teacher。历史v6的B1/B2仍保持其原始DashScope来源，不改写；未来结果报告必须披露该历史来源差异，不能把它隐藏在“只取消容量”的表述中。
- 当前冻结v6 evolver及v9覆盖入口已经硬性只接受`deepseek_official`，控制器也锁定`deepseek-flash`，因此无需改动容量算法代码。规格、README和离线测试已同步；本决策不授权启动正式实验。

## D-082：授权v9执行B0训练并生成B1

- 日期：2026-10-12；状态：用户明确要求“先用B0训练一次，生成B1看看”。
- 本次仅运行冻结134题B0训练，随后使用D-081的DeepSeek官方`deepseek-flash`生成B1；不运行B0/B1验证，不启动B2、Client B/C或联邦流程。输出进入全新`stage2_local_v9/runs/client_a_generation_01_20261012_r1/`，首个API或程序错误即停止。
- 当前冻结v6入口是历史运行后形成的continuation版本，原本拒绝generation 1及空父库证据。v9只为generation 1恢复历史B0语义：训练使用`skill-mode none`，B1 Teacher读取显式空B0模板；B2及以后仍要求真实父库文件哈希。该兼容修订不改变容量策略。
- 启动前须验证DashScope任务凭据、DeepSeek官方凭据与精确endpoint、WSL项目Python、冻结清单、数据和全新输出目录；不得打印密钥。该授权包含134题Qwen执行与B1 Teacher调用产生的外部费用。

## D-083：v9当前仅运行B0训练和B0验证

- 日期：2026-10-13；状态：用户明确要求“先跑B0的训练集和验证集就行，剩下的暂停”，取代D-082中训练后生成B1的当前执行范围。
- 当前只运行空SkillBank的冻结134题训练集和冻结134题验证集；两者均使用`qwen3.6-flash`、temperature 0、seed 1234、thinking关闭。验证只记录结果，不进入Teacher。
- B1 Teacher尚未调用，B1 SkillBank尚未生成。本次流程不得调用DeepSeek、生成B1、进入B2--B5、Client B/C、联邦流程或实现Skill路由；B0验证完整且API-clean后立即停止。任何错误仍按首错停止且不自动重启。
- 正式输出位于`stage2_local_v9/runs/client_a_generation_01_20261013_r1/`。此前`client_a_generation_01_20261012_r1/`只含一次未进入episode的ALFWorld初始化残留，原样保留，不计入正式结果。

## D-084：空B0训练证据兼容修复后只续行B0验证

- 日期：2026-10-13；状态：执行中发现并修复，不改变D-083实验口径。
- B0训练已完成134题并写出完整结果，随后旧continuation收尾逻辑对null父库路径调用`file_hash`而停止；这发生在全部episode完成之后，不是模型/API错误。修复仅令空B0的`parent_bank_file_sha256`和`parent_live_repository_sha256`写为null，B1及以后真实父库哈希校验不变。
- 不重跑训练episode。程序核验结果含134个唯一任务、与冻结训练集合完全一致且无API错误标记后，确定性生成evidence与summary；训练结果为61/134。随后只启动generation 0空库B0验证，完成后停止；Teacher暂停锁继续生效。

## D-085：授权v9由B0训练证据生成一次B1

- 日期：2026-10-13；状态：用户明确要求“那生成B1”。
- 只使用D-084冻结的B0训练evidence（SHA-256=`d8d73561f9381a58a62aa94d038b4c62326c7b458dbcbc8f84e5f24e61c560dd`）和显式空B0模板，调用DeepSeek官方`https://api.deepseek.com`、API模型ID=`deepseek-flash`、temperature 0、thinking关闭，生成一次B1 SkillBank。
- 沿用v9无每角色Skill总容量上限的设置；每任务族候选仍为0--4条，单字段900字符、schema校验、证据去重及其余规则不变。不运行B1验证，不进入B2--B5、Client B/C、联邦或Skill路由实验；首错停止，不自动重启。

## D-086：B1仅对唯一可判定的schema类型标签做确定性规范化

- 日期：2026-10-13；状态：D-085首次运行在四轮既定schema repair耗尽后停止，离线诊断并修复格式兼容，不改变Skill内容或容量口径。
- Planner与Executor初次合并均为23条，未发生容量修复或裁剪。Planner通过；Executor有7条记录声明为`Failure Lesson`，但缺少该类型字段，同时完整包含合法且不超过900字符的`Procedure or Local Strategy`三字段。四轮Teacher通用修复均未纠正标签。
- v9新增严格确定性规范化：仅当声明类型字段不完整、且恰好一个合法类型的全部字段完整有效时，修改`type`为该唯一类型；不修改文本、条数、顺序、作用域或ID，并写入`deterministic_schema_type_normalization`审计记录。零个或多个合法类型仍按原规则失败。
- 从原检查点恢复，只执行本地规范化和最终校验/物化，不重跑12份任务族分析、两个角色合并或四次schema repair；B1生成后停止，不运行验证或B2。

## D-087：B1对两条混合字段记录做原文别名补全

- 日期：2026-10-13；状态：D-086恢复修正5条唯一类型标签后，仍有2条冷却类Executor记录不满足任一完整字段组，继续按首错停止；未产生新模型调用。
- 两条均声明为`Failure Lesson`，`why_it_happens`与`how_to_avoid`完整有效，`description`缺失，同时保留完整且不超过900字符的`principle`。四轮Teacher修复中的这两条字段状态完全相同。
- v9只在上述精确条件成立时，将现有`principle`原文复制到缺失的`description`；不改写文字、不改变声明类型、条数、顺序或作用域，并写入`deterministic_schema_field_alias_normalization`审计记录。其他缺字段情况仍失败。
- 再次从原检查点仅做本地校验和物化，不新增DeepSeek调用；B1生成后停止。

## D-088：授权v9运行一次B1冻结验证

- 日期：2026-10-13；状态：用户明确要求“B1验证一下”。
- 使用已冻结B1 SkillBank（文件SHA-256=`84218a56b828fe08b81bd476c62d32950f61764b13390e957fd22c430bf24db4`）和v6逐项相同的冻结134题验证集，只运行`qwen3.6-flash`验证；temperature 0、seed 1234、thinking关闭。
- 运行时适配器从完整23/23条角色库动态生成精确容量档案，不裁剪、不拒绝超过14条的库；每题仍只注入当前角色的通用Skill和匹配任务类Skill。
- 验证只记录学习曲线，不准入、不回滚、不反馈Teacher。Teacher暂停锁保持生效；验证完成后停止，不进入B2、Client B/C、联邦或Skill路由实验。

## D-089：扩展v9到Client B/C并分别运行至B1验证

- 日期：2026-10-13；状态：用户明确要求补齐B/C适配后分别正式运行。
- Client B和C各自从显式空B0开始，固定阶段顺序为`B0验证 -> B0训练 -> B1 Teacher -> B1验证`，完成后停止；不进入B2、联邦或Skill路由。三端逐项复用同一134题训练和134题验证队列，但实验身份、证据、SkillBank和结果互不共享。
- 任务执行统一使用`qwen3.6-flash`、temperature 0、seed 1234、thinking关闭；B1 Teacher统一使用DeepSeek官方`https://api.deepseek.com`、API模型ID=`deepseek-flash`、temperature 0、thinking关闭。Teacher只能读取本客户端B0训练证据，任何验证轨迹均不得进入Teacher。
- B的角色库为Executor/Critic，其中Critic不执行环境动作；C的角色库为Supervisor/Search Worker/Operation Worker，其中Supervisor不执行环境动作。Teacher提示和证据归因必须遵守这些角色边界，不能复用A的Planner/Executor语义。
- B/C沿用v9取消每角色14条累计上限的规则，保留每任务族最多4个候选、单字段900字符、schema修复和完整结构校验。正式运行采用全新独立目录，首错停止且不得覆盖既有结果；Client A及全部B2--B5阶段继续暂停。

## D-090：修复B/C显式多任务队列只执行每类一题的问题并以r3重启

- 日期：2026-10-13；状态：D-089首次r2运行在B的B0验证完成6题后由134题完整性检查停止；结果3/6且无API错误，但不是有效134题结果。
- 原因是B/C运行时虽然接收了全部`--only-game-file`，仍按`--games-per-type=1`截取并循环，最终每个任务类型只执行一题；Client A已有显式队列分支会运行该类型全部请求题，B/C缺少同一逻辑。
- B/C现与A一致：使用显式`--only-game-file`时，每类运行全部匹配候选；非显式抽样及reference模式仍保持原`games-per-type`语义。新增离线检查锁定两端均以`games_to_run`切片和循环。
- r2的6题结果保留为无效pilot，不进入Teacher、统计或正式比较，也不覆盖或拼接。正式B/C实验改用全新r3目录，从B的B0验证134题重新开始，随后仍按D-089顺序执行并停在B1验证。

## D-091：r3外部会话终止后按冻结前缀续跑

- 日期：2026-10-13；状态：r3的Client B B0验证在96/134时随外部执行会话消失，WSL内无存活实验进程；控制状态未写入程序/API异常，结果中也无API错误标记。
- 已核验96条均唯一，且逐项等于Client A同一冻结验证队列的前96条，因此允许使用既有`resume-partial`语义从剩余38题续跑。续跑写入独立`resume_segments/attempt_001/`后按冻结顺序合并，不覆盖原96条。
- 控制器新增显式`--resume`：只复用通过完整summary校验的阶段；不完整阶段必须存在结果文件且是冻结参考顺序前缀；Teacher输出必须bank与record同时存在才能复用。每次续跑记录参考结果路径和SHA-256。
- 本次中断不改变实验算法、模型、任务或统计口径。B恢复完成后继续原定B0训练、B1 Teacher和B1验证，再启动C；仍不进入B2。

## D-092：Client C B1 Teacher长度截断后从检查点提高输出预算续跑

- 日期：2026-10-14；状态：用户明确要求保留C端B0结果和Teacher检查点，查明退出原因后从检查点续跑，并禁止覆盖结果或进入B2。
- r3的C端B0验证51/134、B0训练58/134，均完整且API-clean。B1 Teacher已经完成Supervisor、Search Worker、Operation Worker各六类分析，共18条记录；第一次最终角色库合并调用返回`finish_reason=length`，入口以`Teacher response missing or truncated`按首错停止。最终B1 SkillBank和Teacher记录均未产生。
- 续跑保留原B0 evidence、空B0、18条候选、角色提示、DeepSeek官方端点、`deepseek-flash`、temperature 0、thinking关闭和schema规则，只将本次Teacher `max_tokens`从8000提高到16000，使完整无容量上限角色库可以返回；不得使用截断文本，也不得重新调用已完成的18个任务族分析。
- 启动前固定B0结果、summary、evidence和检查点SHA-256，并建立检查点只读式恢复副本。Teacher成功后由原控制器`--resume`复用完整B0与B1产物，只运行C端冻结134题B1验证并停止；不得覆盖B0、启动重复进程或进入B2。

## D-093：B1开放构建，B2及以后冻结B1实际角色容量

- 日期：2026-10-14；状态：用户明确确认实施。该规则取代D-080中“所有代际均不设Skill总量上限”的后续代际部分；B1开放式构建继续有效。
- B1不设置每角色总条数上限。生成B2时，以冻结父B1文件为容量锚点，分别统计每个角色的实际Skill条数；B2及以后每个完整候选角色库不得超过对应B1容量，角色之间不能借用容量。
- 父库低于B1容量时，只要完整候选最终不超过容量即可直接ADD，不要求同轮DELETE。达到容量时，必须通过DELETE或MERGE释放位置后才能ADD；删除不会缩小后续容量，B3+继续继承最初B1容量及其文件哈希。
- Teacher最终合并提示显式包含角色容量、父库当前数量和可直接ADD空位。若完整输出超限，最多进行两次仅由Teacher决定的合并/删除修复；仍超限则拒绝本代输出。禁止固定顺序机械裁剪，也不接受截断库。
- 容量策略写入B2及以后SkillBank、检查点和Teacher记录，字段包括schema、策略名、anchor generation、B1文件哈希及各角色容量。现有A/B/C B0/B1结果保持只读；本决策只修改代码、规格、测试和说明，不授权启动B2或外部模型调用。

## D-094：首次无角色七桶语义聚合与客户端侧评价

- 日期：2026-10-14；状态：用户明确要求现在执行第一次聚合，并取代此前“服务器评价集”设想。
- 固定输入为v9 A/B/C三份正式冻结B1，共151条Skill。每条初始Skill表示为空库上的独立ADD，稳定来源身份保留`source_client/source_role/source_skill_id`；首轮空库构建不受后续“删3加1”限制。
- 服务器丢弃目标角色分区，只按General及六类task-specific形成七个输入桶；DeepSeek官方聚合模型逐桶做语义去重、互补合并、矛盾消解和角色中立总结，输出唯一完整Global SkillBank。输出必须保留输入来源覆盖，单桶及全库条数不得超过对应输入，不允许服务器合并制造客户端ADD额度。
- A/B/C获得字节级相同的完整Global SkillBank并完整替换旧库；运行时各Agent只注入Global General与当前任务类别specific，角色权限仍由客户端固有system prompt约束。
- 后续客户端自进化按每客户端、每轮独立满足`ADD <= floor(DELETE/3)`；三个客户端不得共享删除额度，额度不跨轮，服务器去重不计DELETE额度。需要ADD的3删1加组必须原子处理。
- 服务器没有评价集且不运行ALFWorld。下发后的Global由A/B/C分别在各自冻结客户端评价集上评价；评价轨迹不得反馈给本地Teacher或服务器聚合模型。本次授权仅执行首次聚合与完整下发物化，不自动启动客户端评价或B2。

## D-095：首次Global完整替代下发后的三端冻结验证

- 日期：2026-10-14；状态：用户明确授权后台运行，并要求错误提醒。
- A/B/C均以D-094生成的同一份43条完整Global SkillBank替代本客户端原SkillBank，分别运行与v9既有实验逐项相同的冻结134题验证；执行模型、temperature、seed、thinking与客户端协作架构不变。验证不准入、不回滚、不反馈Teacher或服务器。
- 服务器下载仍为三端字节级相同、无角色分区的完整Global文件。由于现有客户端加载器要求角色形状，验证目录内允许生成可审计兼容视图：把同一General与六类task-specific逐字映射给该客户端全部角色，不做角色专属筛选；每题仅注入General与当前任务类别，角色权限仍由原客户端system prompt约束。
- 三端使用独立新输出目录和独立后台进程；历史v9 B1、D-094 Global及其下载副本保持只读。首个程序/API错误必须在对应客户端停止并提醒，不自动覆盖或重启；其他客户端可独立继续。三端验证均完成后汇总，不启动训练、Teacher、服务器评价或B2。

## D-096：各客户端从Global SkillBank1本地训练并生成无角色B2

- 日期：2026-10-14；状态：用户明确授权。
- A/B/C分别把D-094的43条无角色Global SkillBank1作为共同本地B1，使用各自客户端架构运行一次冻结134题训练；Teacher只读取本客户端本轮训练证据，分别生成客户端自己的无角色B2，完成后停止，不运行B2验证、服务器聚合或B3。
- 客户端B2补丁在整个43条库上统一计数，General与六类task-specific可相互迁移，不设角色或任务类独立额度。每客户端、每轮必须满足`ADD <= floor(distinct DELETE / 3)`；即新增1条至少删除3条现有Skill。额度不跨客户端、不跨轮，UPDATE不消耗或产生额度，MERGE表示为保留目标的UPDATE加被吸收目标的DELETE。
- B2不得机械裁剪或静默修复。Teacher输出完整可审计patch，程序严格校验目标ID、schema、来源、重复操作和3删1加约束后原子应用；违规时只允许Teacher重新生成patch，修复耗尽则停止。训练、检查点、patch、B2与Teacher记录写入全新Stage3.2运行目录，历史Global、下载副本、本地B1和验证结果保持只读。

## D-097：D-096首错后的检查点续跑与Client A格式循环保护

- 日期：2026-10-14；状态：用户确认DeepSeek余额已恢复并继续D-096。
- B训练108/134、C训练97/134，均完整且API-clean；两端仅因DeepSeek官方Teacher返回HTTP 402停止，已完成的family analysis分别为5/6与4/6。续跑必须复用完整训练与现有Teacher检查点，不得重跑或覆盖。
- A训练已保存冻结顺序前31题（成功23题）。第32题在13次环境动作后连续211次返回客户端语法不接受的`Action: look at ...`，未增加环境动作却耗尽LangGraph 232递归阈值。续跑保持50步环境动作预算，并仅对D-096 Client A设置每子任务最多12次格式纠正；达到上限按`controller_protocol_retry_exhausted`记录该题失败并继续，不再形成程序级递归错误。
- A从已核验的31题冻结前缀续跑剩余103题，续跑段单独落盘并记录`runtime_guard_amendment`；原结果、trace和source lock不覆盖。该恢复不改变Global1、模型、任务集合、B2三删一加规则或停止边界。

## D-098：C端family analysis超量输出的Teacher定向修复

- 日期：2026-10-14；状态：D-097恢复后发现并实施。C端冷却类首次family analysis返回合法JSON和12条finding，全部为KEEP，但协议要求最多8条；完整原始输出、usage和错误已先写入检查点，未进入最终patch。
- 对缺失的该任务族只允许最多两次DeepSeek定向schema修复：输入为上一份无效输出和明确错误，要求合并重叠finding、保留被采纳结论的evidence refs、不得增加新主张，并返回最多8条。不得程序截断、不得重跑训练或前五个已完成任务族分析。
- 每次修复的raw output、usage、attempt和校验结果继续追加到同一检查点。通过后再继续剩余任务族与最终patch；两次仍不合法则停止。B已完成的B2和A正在执行的续跑不受影响。

## D-099：A/B/C本地B2冻结验证

- 日期：2026-10-14；状态：用户明确要求“B2跑完继续跑B2验证”。
- A/B/C各自使用本客户端D-096生成的完整无角色B2，在与既有v9逐项相同的冻结134题验证清单上运行一次验证；执行模型仍为`qwen3.6-flash`、temperature 0、seed 1234、thinking关闭。验证完成后停止，不进入再次聚合、B3或任何Teacher调用。
- 每份B2先做schema、客户端身份、来源哈希、41条逻辑容量和`DELETE=3/ADD=1`配额核验，再物化为客户端运行时角色视图；同一客户端所有角色映射该客户端同一份完整B2，每题只注入General与当前任务类。A/B/C之间不共享B2。
- Client A验证沿用D-097每子任务最多12次格式纠正保护，达到上限记为普通任务失败；B/C执行协议不变。验证结果只用于评价，不准入、不回滚，也不反馈本地Teacher。
- 三端使用全新独立输出目录和后台进程；历史Global1、训练、patch、B2、Teacher检查点及既有验证结果保持只读。首个新程序/API错误在对应客户端停止并提醒，不自动重启或覆盖。

## D-100：B2验证因DashScope欠费中断后的冻结前缀续跑

- 日期：2026-10-14；状态：用户确认DashScope账户状态已恢复。
- 首次B2验证因Qwen接口HTTP 400 `Arrearage`停止，A/B/C分别完成84/99/96题、成功61/75/71；该错误发生在下一题模型调用前，既有完整episode保持有效。
- 续跑前已证明三端结果分别等于本端冻结134题执行顺序的严格前缀，剩余A/B/C=`50/35/38`题。每端只运行剩余题并写入独立`resume_segments/attempt_001`，随后按冻结顺序合并，原result、trace、日志和B2不覆盖。
- 模型、SkillBank、temperature、seed、thinking和D-099注入规则不变；A继续使用12次格式纠正保护。完成后生成完整summary并停止，不反馈Teacher、不再次聚合、不进入B3。

## D-101：三端本地B2完整库的Round 2七桶服务器聚合

- 日期：2026-10-14；状态：用户明确要求“上传给服务器做聚合”。
- 上传输入固定为D-096生成且D-099/D-100验证完成的A/B/C三份本地B2，每端41条，共123个带客户端来源身份的Skill实例；三份净patch、B2文件哈希、共同Global1语义哈希和客户端配额审计一并写入服务器输入清单。
- 服务器按此前用户冻结的baseline方式，以三份已原子应用本地patch后的完整B2为语义输入，丢弃客户端分区并按General与六类task-specific逐桶调用DeepSeek官方`deepseek-flash`，执行语义去重、互补合并和保守冲突消解。并行patch不得按客户端顺序覆盖；每个上传Skill实例必须在输出来源覆盖中恰好出现一次。
- 服务器不设Skill数量容量门槛、不生成客户端DELETE额度、不运行评价集。输出只要求每桶不超过本桶输入数，并生成唯一完整Global SkillBank2；本轮只完成服务器聚合及审计，不自动下发、不启动客户端验证、训练、Teacher或B3。
- Round 1 Global1、三端B2/patch/Teacher记录及既有验证结果全部只读。Round 2使用全新可续跑目录，逐桶保存原始模型输出、usage、校验错误和已接受结果；已完成桶不重复调用，失败不得覆盖输入或已有检查点。

## D-102：Client A从原始v9 B1连续自进化至B5验证

- 日期：2026-10-14；状态：用户明确授权，并特别说明“是B1开始，不是Global SkillBank1”。
- 父库固定为Client A原始v9 `B1_skillbank.json`，文件哈希=`sha256:84218a56b828fe08b81bd476c62d32950f61764b13390e957fd22c430bf24db4`、Planner/Executor各23条；不得使用D-094 Global SkillBank1、D-101 Global2或任一服务器下发库替换父库。
- 继续现有Client A v9代际链：每代用固定父库运行134题训练，DeepSeek官方Teacher只读取该代训练证据生成下一代，再在冻结134题验证集上评价；依次完成B1训练→B2→B2验证，直到B4训练→B5→B5验证后停止。验证只记录学习曲线，不反馈Teacher、不准入、不回滚。
- 本分支沿用v9既有B1锚定逐角色容量，Planner与Executor从B2起容量均固定为23，角色容量不可互借；超过容量只允许Teacher合并/删除修复，禁止机械裁剪。D-096的“删3加1”属于以无角色Global1为共同父库的Stage3.2本地分支，不应用于本次从角色化Client A B1继续的v9原始分支。
- 任务执行锁定`qwen3.6-flash`，B2--B5 Teacher锁定DeepSeek官方`deepseek-flash`。本次明确授权解除D-085留下的Teacher暂停标记；历史B0/B1结果不覆盖，控制器首错停止并保留完整检查点，完成B5验证后不得自动进入B6、聚合或下发。

## D-103：联邦通信统一为完整SkillBank快照

- 日期：2026-10-15；状态：用户明确规定“以后都不传patch了，上发下传的都是skillbank”，取代此前任何Round 2+上传净patch或下发patch的方案。
- 每个客户端每轮上传已在本地原子应用更新后的完整SkillBank；服务器按既定聚合算法读取完整库，聚合后下发唯一完整Global SkillBank快照，各客户端用其整体替换旧本地库。patch只允许作为客户端内部Teacher审计和确定性物化证据，不是联邦传输对象，服务器不得依赖patch重建客户端库。
- 首次151→43与第二次123→44的Stage3.2正式聚合已实际采用完整SkillBank语义输入，继续有效。今后manifest必须明确`upload_mode=complete_skillbank`、`downlink_mode=complete_global_skillbank_replacement`，不得再把patch文件列为服务器必需输入。

## D-104：Client A原始B1上的“删3加1”独立自进化重跑

- 日期：2026-10-15；状态：用户纠正并明确要求重新生成B2、连续运行到B5验证结束，取代D-102对旧v9“B1锚定23/23容量”的错误沿用。
- 父库仍固定为Client A原始角色化B1，文件哈希=`sha256:84218a56b828fe08b81bd476c62d32950f61764b13390e957fd22c430bf24db4`，不得使用Global SkillBank1或Global2。上一错误分支的B1训练134题、92次成功且API-clean，与父库和冻结清单一致，可作为新B2 Teacher的冻结训练证据复用；其完整库容量修复输出和B2检查点不进入新分支。
- B2--B5每代Teacher输出显式`DELETE/UPDATE/ADD`净patch并由程序原子应用。全Client A的Planner、Executor、General与六类task-specific共享一份当轮额度：`ADD <= floor(distinct DELETE/3)`；UPDATE不消耗或产生额度，MERGE编码为保留目标的UPDATE加被吸收目标的DELETE。目标角色不可越权修改，UPDATE可在同一角色内迁移General/任务类，ADD必须指定所属角色与桶。
- 不设B1锚定23/23容量，也不机械裁剪；库大小只由合法patch决定。每条DELETE/UPDATE目标在一轮最多操作一次，所有证据引用必须来自该代训练证据，schema、角色、ID、重复语义和计数全部硬校验，违规最多重新生成完整patch三次，耗尽即停止。
- 使用全新运行目录，旧D-102失败状态、B2检查点和stderr原位保留。依次生成并验证B2--B5；验证不反馈Teacher、不准入、不回滚，B5验证后停止，不进入B6或联邦上传/下发。

## D-106：Global2完整下发与三端冻结验证

- 日期：2026-10-15；状态：用户明确要求“下发Global2替换三端SkillBank，并进行Global2的三客户端134题验证”。
- 权威下发对象固定为D-101生成的44条`global_skillbank2.json`，文件SHA-256=`sha256:7ea48b556110d7ac1524a091b45396f81f590eb0367be11ba0e16e9cb7e1954d`。A/B/C接收字节级相同的完整Global2；兼容运行视图只把同一份七桶库映射给本端所有角色，不进行角色筛选、客户端个性化或内容改写。
- 三端分别使用既有v9冻结134题验证清单，执行模型保持`qwen3.6-flash`、temperature 0、seed 1234、thinking关闭。每题只注入Global General与当前任务类别；验证结果只用于比较Global1、各端本地B2与Global2，不反馈Teacher、不触发准入或回滚。
- 使用全新运行目录，三端独立后台执行并保存状态、stderr、过程日志、result与summary；任一客户端失败不自动重启且不阻塞其他客户端。不得启动训练、DeepSeek Teacher、Global3或下一轮聚合。

## D-107：DeepSeek JSON模式已知包装字段的可审计规范化

- 日期：2026-10-15；状态：用户明确要求修正JSON提示或增加仅针对已知包装字段的可审计规范化及回归测试，再从检查点续跑。
- Family analysis预期顶层仅为`findings`，最终patch预期顶层仅为`operations`。提示必须明确：OpenAI兼容接口的`response_format={"type":"json_object"}`只是传输设置，响应正文不得复制顶层`type`、schema或其他包装字段。
- 程序只允许一个封闭例外：当顶层键集合恰好为`{预期字段, "type"}`且`type`的值严格等于`"json_object"`时，移除该已知包装键后进入原有硬校验。任何其他额外键、不同type值、缺失预期字段或嵌套变化继续拒绝。
- 规范化不得改写raw response；必须把原始键、移除键值、规范化后键、策略名及来源attempt路径写入独立attempt记录和Teacher checkpoint。现有三次完整B2响应允许从检查点按相同规则重新校验，成功时复用其finding而不再次调用模型；旧invalid记录不得删除或改写。

## D-108：Global2验证完成后逐客户端生成并验证本地B3

- 日期：2026-10-15；状态：用户明确要求已完成Global2验证的客户端立即开始本地训练，生成B3并验证，后续完成的客户端自动接续。
- 启动门槛为本客户端Global2冻结134题验证`status=complete`且`api_clean=true`。父库固定为服务器下发的44条Global SkillBank2完整替代库；每端独立运行冻结134题训练，由DeepSeek官方`deepseek-flash`基于本端训练证据生成角色无关B3。
- 本地B3继续按整个客户端七桶共享额度执行`ADD <= floor(distinct DELETE/3)`；UPDATE不产生或消耗额度，技能可在General与六类task-specific之间迁移。客户端之间不共享删除额度、Teacher检查点或本地B3。
- 每端B3生成后立即用本端冻结134题验证集评价；验证只记录结果，不反馈Teacher、不准入或回滚。完成B3验证后停止，不自动上传、聚合Global3、下发或进入B4。
- 运行使用全新目录并保存完整训练、Teacher检查点、净patch、B3、运行时映射、验证和控制器状态；历史Global2验证和Global1→B2产物保持只读。

## D-109：联邦B3超长字段的有界压缩恢复

- 日期：2026-10-15；状态：用户明确要求保留Client B/C现有检查点和三次patch attempt，查明非法`principle`后增加有界字段压缩并续跑。
- 现有证据确认字段均非空，而是超过900字符硬上限：B三次相关长度为914、909、910；C三次最高分别为1114、1030、1021，最后一次另有963字符字段。训练、六类family分析、三次完整patch原始响应和失败状态全部保留，不重跑、不覆盖。
- 恢复只以最新第三次完整patch为输入，识别其中所有超过900字符的合法技能文本字段；最多调用DeepSeek两次，把这些字段压缩到不超过760字符。除授权字段外，操作数量与顺序、操作类型、目标ID、桶、证据引用、技能类型及所有其他字段必须结构和值完全相同。
- 每次压缩响应写入新的`B3_patch_compression_XX.json`，记录来源patch对象哈希、授权字段及原长度、760字符目标、raw output、usage和可得规范化审计。若模型改动任何未授权内容、压缩字段仍为空/超长，或完整patch继续违反schema、去重或三删一加规则，则该次拒绝；两次耗尽后继续首错停止。
- 合法压缩通过后从原控制器检查点继续物化本地B3并运行134题B3验证；不得重跑训练/family分析，不启动Global3或B4。

## D-110：联邦B3压缩改用最小字段替换表

- 日期：2026-10-15；状态：D-109两次完整patch压缩响应均原样回显超长字段并被硬校验拒绝，未生成B3。为继续用户要求的有界压缩恢复，改用更窄的替换表协议。
- DeepSeek只接收第三次冻结patch中超长字段的操作序号、字段名、原文与760字符目标，并只返回`replacements`列表；每项严格包含`operation_number`、`field`和`text`。程序要求替换集合与授权字段集合恰好相等、无遗漏、未知项或重复项。
- 程序在第三次冻结patch的内存副本上应用替换，再验证除授权字段外全部结构和值完全不变，随后执行完整schema、语义去重和三删一加校验。最多两次替换表调用，写入独立`B3_patch_replacement_compression_XX.json`；D-109两次拒绝记录和更早attempt继续只读保留。

## D-111：联邦B3字段压缩的角色中立短文本终局修复

- 日期：2026-10-15；状态：D-110两次替换表仍被硬校验拒绝。B最后一次已缩至712字符，但引入`executor`角色词；C最后一次两个目标分别为768和1001字符，未满足760目标。所有响应均保留，未物化B3。
- 最终修复仍只返回与D-110相同的精确替换集合，但把每字段上限收紧为650字符，并显式禁止`planner`、`executor`、`critic`、`supervisor`、`search worker`和`operation worker`。最多两次，输出独立`B3_patch_sanitized_compression_XX.json`。
- 程序继续从第三次冻结patch副本应用替换；除授权字段外任何值变化都不可能进入候选。替换后必须通过完整字段、角色中立、语义去重、目标ID与三删一加校验。两次仍失败则保持失败并停止，不再扩展自动修复。

## D-105：Client A三删一加Teacher截断的可审计有界恢复

- 日期：2026-10-15；状态：用户明确确认实施。D-104新分支在首个B2 `Planner/简单取放`任务族调用停止；原控制器失败状态、stderr和未产生B2产物的事实必须保留，恢复前写入控制器`failure_history`，不得伪造旧检查点。
- Teacher请求继续使用DeepSeek官方`deepseek-flash`、thinking关闭和`max_tokens=16000`，同时启用`response_format={"type":"json_object"}`。任务族最多8条finding；每条recommendation最多600字符、affected skill IDs最多12个、evidence refs最多16个，引用必须属于当前角色父库和当前任务族训练证据。
- 每次API响应在任何解析或schema校验前写入独立attempt记录，至少保存请求预算、JSON模式、消息哈希、choice数量、真实`finish_reason`、usage、可得响应正文、模型身份和状态；空choices、长度截断、JSON解析错误及可恢复transport错误均不得静默丢失或覆盖旧记录。
- 空choices或`finish_reason=length`最多额外重试2次，即同一调用最多3个此类响应；transport重试预算保持原值并独立计数。三次仍失败则首错停止。暂不提高16000输出预算；只有新attempt证据显示completion确实达到该预算，才讨论提高。
- 每个同步Teacher请求另设与`timeout`相同的POSIX墙钟截止时间，避免服务持续发送零碎数据时不断重置HTTP读取超时。墙钟截止按transport错误保存并占用一次transport尝试；不得形成无限等待。
- 离线测试和DeepSeek官方JSON输出小探针通过后，允许在同一D-104运行目录以控制器`--resume`继续；恢复日志使用新文件，不覆盖首次启动日志。监控恢复后仍只读，B5验证结束即停止。

## D-112：Client A B3角色局部ID越界的有界最终patch恢复

- 日期：2026-10-15；状态：用户要求保留B3检查点和三次原始attempt，核查允许ID与修复提示后从检查点续跑。
- 根因是Skill ID只在角色内唯一：`skill_017`在当前B2的Executor仍合法，但已从Planner删除；family finding对Executor引用合法，最终合并却三次生成`Planner/skill_017`。旧最终提示只嵌入整库，未显式列出角色允许ID；旧修复又回传含该旧角色/ID对的错误文本。
- B3检查点、三份`B3_patch_attempt_XX.json`及对应raw响应在恢复前写入独立哈希清单。恢复不得覆盖或重做family分析；正常最终提示新增`allowed_target_ids_by_role`并强调ID为角色局部。
- 标准三次attempt已耗尽时，只允许最多两次新的最终patch恢复调用。恢复提示列出当前角色允许ID，并把从最后冻结patch检测到的越界角色/ID对明确标为禁止历史输出；每次写入新的recovery attempt并执行完整schema、证据、角色、ID、去重和三删一加校验。成功后按原控制器继续B3--B5；失败则停止。
- 本次两次恢复均失败后，含恢复记录的检查点另存为`B3_teacher_record.recovery_003.checkpoint.json`；权威原检查点恢复到启动前字节内容和SHA-256=`9b2164f8...cd219`。两份新recovery patch/raw attempt独立保留，原三次attempt未改写。

## D-113：联邦B/C B3的人工审阅字段修复与确定性超额ADD裁剪

- 日期：2026-10-15；状态：用户要求停止无效Teacher压缩调用，人工审阅最后超长字段、由程序完整校验并完成B/C B3。
- 完整校验发现最后候选还存在此前首错未暴露的问题：B第三次patch为DELETE=3、ADD=2且另有角色词；C第三次patch为DELETE=0、ADD=3。它们不能只靠压缩字段成为合法B3。三次patch及D-109至D-111全部压缩attempt继续只读保留。
- 人工修复不新增或改写操作语义：B采用第三次候选，压缩/去角色词的字段后确定性删除第二条超额ADD；C采用唯一含3个DELETE的第二次候选，压缩超长加热原则，并删除两条含角色词的超额ADD，保留一条证据化ADD。删除对象和字段替换全文写入独立规范，源attempt与checkpoint哈希写入审计。
- 程序只允许修改列出的无效文本字段和删除列出的既有ADD，拒绝修改DELETE、UPDATE、目标、桶、证据或其他文本；随后执行完整字段、角色中立、目标唯一性、三删一加、容量算术和精确语义去重校验。B/C均得到42条B3：DELETE=3、ADD=1，UPDATE分别7/10。已有B3输出使控制器直接进入134题验证，不再调用Teacher；完成后停止，不进入Global3或B4。

## D-114：完整SkillBank联邦基线同步推进至Global5验证

- 日期：2026-10-15；状态：用户明确要求联邦B/C完成本地B3验证后，三客户端继续聚合、下发和本地演化，直到Global5三端验证完成。
- 联邦通信只上传和下发完整SkillBank快照，不传patch；patch只作为客户端本地三删一加审计证据。服务器每轮把A/B/C同代完整本地库按General与六类task-specific七桶分别交给DeepSeek官方`deepseek-flash`去重和语义合并，生成完整Global3、Global4、Global5；服务器不运行评价集。
- 采用同步轮次：三端本地B3验证全部完成后才聚合Global3；Global3三端各134题验证全部完成后，三端才各自训练并按全客户端七桶共享`ADD <= floor(distinct DELETE/3)`生成和验证B4；随后聚合、下发并验证Global4，再以同样规则生成和验证B5，最后聚合、下发并验证Global5。
- Global验证和本地验证只记录性能，不反馈Teacher、不准入、不回滚。每轮冻结父库文件哈希、三个上传库哈希和输出哈希；控制器按阶段断点续跑，已有完整产物只校验复用，禁止覆盖、拼接或重复调用。任一必需阶段失败即停止后续全局推进并保留检查点，等待显式恢复。
- Global5三端冻结134题验证全部完成即终止；不得进入Global6、本地B6或其他联邦算法。执行模型保持`qwen3.6-flash`，本地Teacher与服务器聚合模型保持DeepSeek官方`deepseek-flash`。

## D-115：Client A独立分支最终patch改为程序约束的两阶段合成

- 日期：2026-10-15；状态：用户明确要求按“两阶段约束生成”修改，并继续生成Client A独立自进化B3。
- 原B3检查点、三次标准final patch、两次role-ID恢复及失败控制器全部原位保留。恢复复用已经接受的12个任务族分析，不重跑134题B2训练，不把旧非法patch作为新输出模板。
- 最终合成第一阶段只允许`DELETE/UPDATE`，提示按角色给出当前合法ID；程序先验证证据、角色局部ID、目标唯一性、字段、角色边界和候选精确去重，再由去重DELETE数确定`max_add=floor(DELETE/3)`。该阶段不得输出ADD。
- 第二阶段只允许`ADD`，模型只接收冻结findings、已接受第一阶段操作摘要和程序计算的精确`max_add`；程序拒绝任何DELETE/UPDATE及超额ADD。若配额为0则跳过模型调用。最后把两阶段操作合并，并重新执行原有完整patch硬校验和容量算术。
- 两阶段各最多三次schema尝试，每次raw响应、usage、请求预算、验证错误和接受结果写入新的独立attempt与checkpoint记录；不得覆盖D-112证据。合法B3生成后按原独立链继续B3验证及后续B4/B5，仍不使用Global库、不上传联邦服务器、不进入B6。

## D-116：Global文件SHA-256单前缀规范化与Global3原位续跑

- 日期：2026-10-15；状态：用户明确要求修正哈希前缀规范化、增加回归测试，并复用现有Global3从下发阶段续跑，禁止重新聚合。
- Global文件校验入口同时接受64位裸十六进制摘要和恰好一个`sha256:`前缀，内部统一为小写裸摘要后比较；空值、非64位十六进制及双前缀一律拒绝。下发运行时与manifest只记录一个`sha256:`前缀。
- 原失败属于表示格式不一致：Global3记录值为`sha256:0c887d…f4a3b`，磁盘实际裸摘要为`0c887d…f4a3b`，内容一致。43条Global3、七桶accepted/attempt/record与聚合summary全部复用，不再次调用DeepSeek聚合模型。
- 总控制器仅允许对匹配schema且`status=failed`的状态显式`--resume`；旧失败写入`failure_history`，续跑事件单独记录。恢复从`validate_Global3`下发开始，后续仍按D-114推进并止于Global5验证。

## D-117：v10角色分区本地进化与七桶Global聚合

- 日期：2026-10-18；状态：用户已明确要求新建v10并按此前讨论修改代码，v9源码和既有结果保持原位。
- 服务器继续保存、下发一份角色无关的General加六类task-specific七桶Global SkillBank；每次下发把同一完整七桶库复制到客户端所有实际角色的分区，替换旧库。A为Planner/Executor，B为Executor/Critic，C为Supervisor/Search Worker/Operation Worker。
- 本地Teacher针对每个角色独立读取该角色训练轨迹与父库，按六任务类生成每组最多8条finding；随后两阶段合成：先冻结DELETE/UPDATE并按角色局部ID与证据硬校验，再由程序计算该角色`max_add=floor(去重DELETE/3)`，只生成允许数量的ADD，最后完整校验物化角色库。额度逐角色、逐轮计算，不能跨角色或跨轮借用；UPDATE中性，零操作合法。
- Client A原始B1独立自进化的v10分支使用同一逐角色Teacher流程与配额，父库始终沿本地上一代；联邦分支每轮以刚下发的共同Global副本为父库。两条分支的输入身份和结果独立，不能重标记或拼接v9结果。
- 联邦上传仍是完整SkillBank快照，每个角色作为可追溯来源；服务器按原七桶聚合，不创建Global角色分区，不运行服务器评价集。聚合结果重新下发并覆盖各角色库。v10不自动启动训练、Teacher付费调用或134题正式验证。
- B0空库开放建库的候选阶段只允许ADD，旧库操作RETAIN/UPDATE/MERGE/DELETE均不得出现；最终整库合成仍可对新增候选做语义去重与融合。这是新v10口径，不追改v9的B1提示、检查点或结果。

## D-118：v9 B0→B1冻结结果作为v10后续实验的导入起点

- 日期：2026-10-18；状态：用户明确要求将可迁移的v9 B0→B1结果迁入v10。此项扩展D-117的起点选择，不改变D-117的逐角色本地Teacher与额度规则。
- 导入前必须逐端核实冻结134题训练/验证清单同题同序、B0/B1阶段完整且API-clean、结果与证据哈希、DeepSeek官方Teacher及B1库的角色结构。原v9 Teacher提示虽容许其他候选操作，但A/B/C实际候选均为ADD；这一事实支持把B1当作后续冻结种子，不使其追溯成为v10原生B1。
- v10导入目录保存v9原始字节副本与来源/目标哈希清单，不改写v9实验标识、Teacher记录、source_lock或验证统计；联邦首轮与独立B2可显式使用此冻结种子。导入结果须标记`imported_v9_seed`，后续新生成的B2/Global1等才属于v10流程；不得将v9 B0/B1结果重算或冒称v10新运行。

## D-119：V11完整克隆V10并将并发调度与实验语义分离

- 日期：2026-10-18；状态：用户明确要求建立V11、保留V10全部内容与导入结果，并分析`qwen3.6-flash`官方并发相关额度。
- V11复制V10全部81个原始文件，逐项哈希记入`stage2_local_v11/CLONE_MANIFEST.json`。本地Teacher、逐角色三删至多一加、七桶服务器聚合、验证和停止条件保持D-117/D-118口径；只为可独立运行而替换V11命名空间、实验身份及对应冻结清单。被改写的V10元数据原件保存在`v10_source_assets/`及各导入客户端`import_manifest.v10.json`。
- 已导入v9的B0/B1结果正文和锁文件仍与V10副本逐字节一致；V11新`import_manifest.json`绑定V11清单，并继续标记为`imported_v9_seed_not_native_v11_B1`。不得把复制品称为V11原生实验结果，V10及v9原件均保持原位。
- 官网北京区`qwen3.6-flash`公布30,000 RPM与10,000,000 TPM；此为账号共享的请求/Token速率额度，不是保证可并发134个ALFWorld环境的固定在途上限。现有V11阶段执行器在单客户端内仍逐题串行，联邦控制器也逐客户端串行。`CONCURRENCY_ANALYSIS.md`只提出2→3客户端、之后2→4→8题分片的待实测路线；正式并发执行器、压测与付费实验均未启动，变更须保留冻结题目/父库哈希/逐题结果与首错停止规则。

## D-120：V11 可选冻结题目分片入口

- 日期：2026-10-18；状态：用户要求开发单客户端按冻结题目分片的专用执行器，并评估134路可行性和失败计费风险。
- `stage2_local_v11/sharded_phase.py` 不改变V11训练/验证清单、模型、SkillBank、Teacher或联邦语义；按现有确定性顺序将同一134题分片，各进程拥有独立结果与日志，完成后严格覆盖检查并生成原阶段格式的完整结果、摘要和训练证据。`--pilot-tasks`可从冻结清单均匀抽取少量题目做付费负载测试，但产物标记为非正式`pilot_complete`，不能进入正式控制器。输出根目录必须全新且为空；失败保留全部分片，不自动重试或拼接。
- 默认入口只做零API调用的只读计划；只有显式`--execute`才启动付费阶段。默认并发2，允许参数表示134路，但134路可行性需要逐级付费负载测试，不能由官方RPM/TPM直接推断。已有V11控制器不自动切换到分片执行器。
- 离线测试与134路计划生成不视为模型负载测试，也不得写作已完成134题验证。任何实际运行要继续保留冻结输入、结果哈希和失败首停证据。

## D-121：V10 每两轮本地自进化后聚合至 Global3

- 日期：2026-10-18；状态：用户确认的正式实验节奏，扩展 D-117/D-118，不追改此前 v9 或 V10 导入种子。
- A/B/C 从各自标记为 `imported_v9_seed` 的完整 B1 出发，并发完成 B1→B2 的 134 题训练、逐角色 Teacher 和 B2 134 题验证；三端均完整且 API-clean 后，上传三个完整 B2 多角色库，聚合一份七桶 Global1，并行在三端验证各 134 题。
- Global1 的完整七桶库复制到每个客户端的各角色分区后，三端各自依次完成 B3、B4 两轮本地训练、逐角色三删至多一加、验证；只在三端 B4 验证完成后聚合 Global2 并在三端并行验证。Global2 后同样完成 B5、B6，再聚合并验证 Global3。止于 Global3；不进入 B7/Global4。
- 全局轮次与本地代数显式分开：Global1/2/3 的来源分别是 B2/B4/B6；下发后的运行时库 generation 分别为 2/4/6，以便下一轮训练按 B3/B5/后续代数接续。服务器仍只传完整库、按七桶语义聚合、不做服务器评价；验证结果不回流 Teacher、不作候选准入。
- 三个客户端之间可以并发执行，每个客户端当前仍按冻结清单顺序逐题运行；并发不改变题目、模型、SkillBank、证据和每角色 `ADD <= floor(distinct DELETE/3)` 口径。任一阶段首错停止全局推进，保留全部完整及部分证据；不自动覆盖、重跑或拼接失败段。

## D-122：V10 B2 首次中断后的 finding 结构定向恢复

- 日期：2026-10-18；状态：运行中发现提示与硬校验字段不一致后的定向实现修复，属于已授权完成 Global3 实验所需的错误恢复；不改变冻结任务、父库、模型、配额或评价口径。
- Client B 的 B2 134题训练已完整且API-clean；首个 `Executor/简单取放` finding 三次响应均为旧式 `action/skill_id/evidence_refs/rationale`，硬校验要求 `recommendation/affected_skill_ids/evidence_refs`，故原样拒绝并首错停止。三份raw response与检查点必须保留，不能把旧式字段静默映射成有效finding。
- 后续常规 family prompt 显式列出唯一允许的 finding JSON 字段及其含义。对于该类连续三次 `invalid fields` 的已失败 family，只额外允许一次独立命名的定向恢复调用；请求展示三个合法字段、先前错误、当前角色合法ID与冻结训练证据，响应依旧执行原完整硬校验，raw/usage与拒绝原因单独审计。一次仍失败即停止，不放宽schema、不覆盖原三次attempt。
- Client A/C 被主控制器终止时分别保留 117/132 题冻结前缀。只有经阶段执行器核对前缀与原134题同序、原source_lock完全一致、无孤立写入进程后，才允许分别续跑剩余17/2题并合并为完整134题结果；原前缀和独立续跑段全部保留。之后原控制器只复用完整阶段并继续，禁止重新跑B已完成的134题训练。

## D-123：V10 两阶段 patch 的 DELETE/UPDATE 结构定向恢复

- 日期：2026-10-18；状态：D-122恢复后暴露的共同提示缺陷修复，作为用户已授权完成V10正式实验的错误恢复；不改变训练/验证集合、模型、父库、每角色三删至多一加配额或服务器聚合口径。
- A/C已按D-122核验前缀续完B2训练，A/B/C分别为95/110/99成功，134题均API-clean。B已完成6个Executor任务族finding；其DELETE/UPDATE合成三次响应均使用旧式`op`、`patch/updated_fields`和单数`evidence_ref`，硬校验要求`operation`、`bucket`、完整`skill`和复数`evidence_refs`，故原样拒绝。A Planner/C Supervisor各已出现两次同类拒绝，顶层再次首错停止，Global1未启动。
- 保留各端完整训练、原检查点与所有base attempt的字节哈希。后续常规base提示显式列出DELETE/UPDATE两种操作的精确JSON形状、当前角色允许ID、合法七桶与证据引用要求。对B已用尽三次且错误均为缺失`operation`字段的base阶段，最多追加一次独立命名的schema恢复调用；输出仍执行原完整role_patch硬校验。一次仍失败即停止，不静默转换旧式patch，也不覆盖任何旧attempt。
- A/C从原Teacher检查点继续，尚未用尽的标准schema attempt可按新提示执行；三端B2生成并验证后才进入Global1。任何新错误仍首错停止，不自动拼接或跳过Teacher约束。

## D-124：V10 导入 B1 的缺失来源字段在服务器上传视图中补全

- 日期：2026-10-18；状态：用户要求 Global1 聚合，B2 三端验证完成后聚合输入校验发现 v9 导入 B1 的所有旧 Skill 均未带 `source_skill_keys`，B2 保留该历史格式，服务器因此在零模型调用前停下。
- 已验证的 B2 SkillBank 和 134 题验证结果保持原字节与原哈希。仅在 Global1 上传读取 B2 且缺失来源字段时，先核验对应客户端的冻结 v9 B1 导入清单与哈希，再要求该 B2 条目的角色及 Skill ID 在冻结 B1 同角色中存在；满足时把其来源记录为 `client/role/B1/skill_id`。真正新增的 B2 条目及 Global2/3 来源仍必须具有原生 `source_skill_keys`，否则拒绝。
- 补全只写入服务器上传视图和清单审计，不回写客户端库、不改变 Skill 语义内容、验证口径或聚合模型。恢复前以离线回归检查三个完整上传、来源唯一性和拒绝无祖先的新条目；若校验通过，从失败的 Global1 聚合阶段续跑，不重复 B2 验证。

## D-125：Global2 欠费中断后的冻结前缀续跑

- 日期：2026-10-19；状态：用户明确要求核验 A/B/C 冻结前缀及输入哈希，再只跑 Global2 验证剩余题目；属于 D-121 正式链的断点恢复。
- Global2 已由三端完整 B4 聚合为 40 条。三端原验证均因 Qwen `Arrearage` 停止，保留 A/B/C 各 88/103/105 条前缀、原结果、来源锁、命令和日志。恢复前逐端核对 Global2 下发库与聚合库哈希、manifest、source_lock、原前缀是否与冻结 134 题执行顺序一致，并确认无活跃旧进程。使用同一客户端的完整 Global1 验证结果作为只读顺序参考。
- 每端仅在独立 `resume_segments/attempt_001` 跑剩余任务；原前缀和新段分别留存。阶段执行器仅在新段完整且顺序校验通过后生成 134 题汇总；若再次欠费或其他错误，停止且不启动顶层后续阶段。三端完整、API-clean且哈希守卫通过后，原控制器才允许继续 D-121 的 B5/B6→Global3 链。

## D-126：Global3 单字段超长的有界人工压缩与检查点恢复

- 日期：2026-10-19；状态：用户明确授权仅压缩 Global3“冷却后放置”聚合候选中的超长字段，完整校验后从聚合检查点续跑，不重跑 B6。
- 冻结服务器输入、B6 三端库与验证、前五桶已接受输出及三次原始 DeepSeek attempt。三次 attempt 均仅因 `skills[3].principle` 超过 900 字符失败；以第三次原文为基底，只人工压缩该字段，不改 type、其他文本字段、来源键集合或其他 Skill。单独写修复审计，记录原始 attempt、输入及清单哈希、字段前后全文与长度、差异边界、原始和修复后完整校验结果；不覆盖原始 attempt。
- 修复候选必须通过服务器原有 `validate_model_output` 全量校验，且程序断言仅目标字段变化；已接受桶与输入仍由聚合程序按原规则复核。恢复从 `aggregate_3` 开始，只复用已完成 B6 阶段；服务器剩余桶仍由官方 DeepSeek 聚合，Global3 下发后按原冻结 134 题验证，止于 Global3，不进入 B7/Global4。


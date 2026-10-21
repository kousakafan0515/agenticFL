# V10：角色分区本地进化、角色无关七桶联邦聚合

V10 是隔离于 v9 的新实验协议和代码目录。`stage2_local_v9/`、`stage3_2_role_agnostic_semantic_merge/runs/` 中的既有源码、Teacher attempt、检查点及 B0–B5/Global 结果均不在本目录改写，也不得重标记为 v10。除下述明确标记的 v9 冻结结果副本外，V10 当前只完成代码及离线检查；新的 Qwen/DeepSeek 调用和 134/402 题运行尚未启动。

## 冻结的 v9 B0→B1 导入起点

用户指定复用的 A/B/C v9 B0→B1 结果保存在 `runs/imported_v9_b0_to_b1_20261018_r1/client_A|B|C/`。每端复制 B0 验证结果、B0 训练结果与证据、B1 SkillBank、Teacher 记录/检查点和 B1 验证结果，共 13 个关键文件；`import_manifest.json` 逐文件记录原始来源和 SHA-256。原 v9 文件及其 `experiment_id`、`source_lock.json`、统计值保持原样。核验入口：

```powershell
.\.venv-stage3-alfworld\Scripts\python.exe -m stage2_local_v10.import_v9_b1 --destination stage2_local_v10/runs/imported_v9_b0_to_b1_20261018_r1 --check
```

三端 v9 Teacher 的实际候选全为 `ADD`，分别为 A=44、B=48、C=72 条；冻结题目与 v10 清单同题同序，B0/B1 验证均完整且 API-clean。**但 v9 当时的提示允许其他候选动作，故这些仍是 v9 结果，只能作为 v10 后续轮次的导入种子，不能称为 v10 原生 B1。**独立链可以显式引用导入的 A B1 文件与 B1 验证摘要；服务器 Global1 初始聚合可以显式引用三端导入的 B1 与验证摘要。两处都会复核导入清单、原始来源、字节哈希与证据。V10 B2 以后及 Global1 若正式运行才是新结果；当前尚未启动。

## 冻结规则

1. B0 是空库；B0→B1 每个角色×任务类只允许 0–4 个 `ADD` 候选，禁止对不存在的旧 Skill 提出 `RETAIN/UPDATE/MERGE/DELETE`。最终 Teacher 仍输出完整 B1 角色库，可融合重复的新增候选。每字段最多 900 字符，B1 不设条数容量。
2. 联邦服务器只保留 General 与六任务类的**一份角色无关七桶 Global**。每轮下发把同一完整 Global 复制到 A/B/C 各自实际角色分区，取代旧本地库。一个客户端的角色副本在下发时相同，在本地进化后可以不同。
3. 本地 `role_evolver.py` 是联邦与独立实验共用的 Teacher。每角色对六任务类分别生成至多 8 条 finding；每条 recommendation ≤600 字符、受影响旧 ID ≤12、证据引用 ≤16。然后分两阶段合成：只允许 `DELETE/UPDATE` 并冻结；程序算该角色 `max_add=floor(去重DELETE/3)`；如大于零，再只生成 `0..max_add` 条 `ADD`；最后重新完整校验。`UPDATE` 不能跨角色，只可在该角色七桶内迁移。
4. **每个角色、每一轮独立计额**：`ADD_role <= floor(distinct DELETE_role/3)`；额度不能跨角色或跨轮借用；`UPDATE` 不计额；零操作、只删、只更新合法。结果条数 `N'_role=N_role-DELETE_role+ADD_role`。无固定 23/23 或每桶条数上限。
5. 联邦上传每客户端**完整多角色 SkillBank**，patch 只作本地审计。服务器把每个角色库的每条 Skill 视为一个带 `client/role/bucket/id` 来源的输入，仍仅按原七桶做 DeepSeek 语义合并；全部输入来源必须恰好被覆盖一次。服务器不做评价，也没有“三删一加”容量约束；输出一份 Global，再复制给各角色并在三端各验证 134 题。
6. 独立 Client A 从显式给定的 B1 沿 B2→B5 本地延续，不读取 Global。它使用同一个 `role_evolver.py` 和**逐角色**配额。与 v9 独立分支的全客户端共享配额口径不同，因此 v9 结果不能当作 v10 结果。
7. 训练轨迹进入 Teacher，验证轨迹只用于学习曲线，不回流、不准入、不回滚。任务执行仍为 Qwen `qwen3.6-flash`；Teacher/服务器聚合要求 DeepSeek 官方 `deepseek-flash`。每阶段第一次程序/API错误停止，保留已写文件；禁止默认覆盖或自动拼接失败段。

## 文件与衔接

| 文件 | 职责 |
|---|---|
| `materialize_assets.py` | 从文件哈希锁定的 v9 A/B/C 清单与空 B0 生成 v10 身份的相同 134+134 题清单与空模板。 |
| `import_v9_b1.py` | 校验并复制冻结 v9 B0→B1 结果，提供独立与联邦初始入口的显式来源守卫。 |
| `bootstrap_b1.py`、`scripts/bootstrap_b1.py`、`run_to_b1.py` | 只允许 ADD 候选的 B0→B1 Teacher 与 B0验证→训练→B1生成→验证控制器。 |
| `role_evolver.py` | 两实验共用的逐角色分析、两阶段补丁、证据/ID/字段/精确重复校验、完整子库物化及attempt/checkpoint审计。 |
| `run_local_round.py` | 对一个客户端执行父库134题训练→本地Bn生成→Bn的134题验证；父库可为上一代独立B库或Global下发副本。 |
| `run_independent_to_b5.py` | Client A 独立 B1→B5 串行编排，止于 B5 验证。 |
| `server_aggregate.py` | B1开放初始聚合或后续三个完整多角色本地库的七桶聚合；验证结果和source_lock须与上传库字节哈希匹配。 |
| `downlink.py`、`run_global_validation.py` | 单 Global 完整复制到每个角色，并运行三客户端冻结验证。 |
| `run_federated_round.py` | 一个同步联邦轮：已验证 Global k→三端本地 B(k+1)→聚合 Global k+1→三端 Global 验证；只接受 k=1..4，止于 Global5。 |

`run_to_b1`、`run_local_round` 与 `run_global_validation` 借用 v9 的冻结 Qwen 阶段执行器，但必须显式使用 v10 清单与 v10 输出目录。DeepSeek JSON模式/截断attempt记录复用**SHA-256锁定**的 v9 helper，原始raw保留；若 helper 内容改变，v10 Teacher 首错停止。v10 使用 `--resume` 只复用完整且身份匹配的阶段；部分134题阶段须先按冻结前缀由阶段执行器单独审计恢复，控制器不会自行重跑或覆盖。

## 离线检查

从项目根目录运行锁定环境的 Python：

```powershell
.\.venv-stage3-alfworld\Scripts\python.exe -m stage2_local_v10.materialize_assets --check
.\.venv-stage3-alfworld\Scripts\python.exe -m unittest stage2_local_v10.tests.test_v10_protocol -v
.\.venv-stage3-alfworld\Scripts\python.exe -m compileall -q stage2_local_v10
```

正式实验需先核对 API 余额与凭据、ALFWorld 数据目录、A/B/C 的 v10 清单、初始空 B0 或选定且明示的 B1、每次新运行目录及其输出成本。此文件不构成启动正式实验的指令。

# V11：角色分区本地进化、角色无关七桶联邦聚合

V11 从 V10 完整复制建立：本地 Teacher、角色配额、七桶聚合与阶段控制逻辑相同；V11 使用独立命名空间和实验身份，避免运行时误调用 V10。原 V10 文件逐项哈希见 `CLONE_MANIFEST.json`，被改写的 V10 README、测试及冻结资产原件见 `v10_source_assets/`。V10 原目录保持不变。`stage2_local_v9/`、`stage3_2_role_agnostic_semantic_merge/runs/` 中的既有源码、Teacher attempt、检查点及 B0–B5/Global 结果均不在本目录改写，也不得重标记为 v11。除下述明确标记的 v9 冻结结果副本外，V11 当前只完成代码复制、身份隔离及离线检查；新的 Qwen/DeepSeek 调用和 134/402 题运行尚未启动。

## 冻结的 v9 B0→B1 导入起点

这些结果正文与 V10 导入副本逐字节相同。V11 的 `import_manifest.json` 绑定新 V11 清单；原 V10 导入清单逐字节保存在各客户端的 `import_manifest.v10.json`。不得把复制动作视为新的模型训练或验证。

用户指定复用的 A/B/C v9 B0→B1 结果保存在 `runs/imported_v9_b0_to_b1_20261018_r1/client_A|B|C/`。每端复制 B0 验证结果、B0 训练结果与证据、B1 SkillBank、Teacher 记录/检查点和 B1 验证结果，共 13 个关键文件；`import_manifest.json` 逐文件记录原始来源和 SHA-256。原 v9 文件及其 `experiment_id`、`source_lock.json`、统计值保持原样。核验入口：

```powershell
.\.venv-stage3-alfworld\Scripts\python.exe -m stage2_local_v11.import_v9_b1 --destination stage2_local_v11/runs/imported_v9_b0_to_b1_20261018_r1 --check
```

三端 v9 Teacher 的实际候选全为 `ADD`，分别为 A=44、B=48、C=72 条；冻结题目与 v11 清单同题同序，B0/B1 验证均完整且 API-clean。**但 v9 当时的提示允许其他候选动作，故这些仍是 v9 结果，只能作为 v11 后续轮次的导入种子，不能称为 v11 原生 B1。**独立链可以显式引用导入的 A B1 文件与 B1 验证摘要；服务器 Global1 初始聚合可以显式引用三端导入的 B1 与验证摘要。两处都会复核导入清单、原始来源、字节哈希与证据。V11 B2 以后及 Global1 若正式运行才是新结果；当前尚未启动。

## 冻结规则

1. B0 是空库；B0→B1 每个角色×任务类只允许 0–4 个 `ADD` 候选，禁止对不存在的旧 Skill 提出 `RETAIN/UPDATE/MERGE/DELETE`。最终 Teacher 仍输出完整 B1 角色库，可融合重复的新增候选。每字段最多 900 字符，B1 不设条数容量。
2. 联邦服务器只保留 General 与六任务类的**一份角色无关七桶 Global**。每轮下发把同一完整 Global 复制到 A/B/C 各自实际角色分区，取代旧本地库。一个客户端的角色副本在下发时相同，在本地进化后可以不同。
3. 本地 `role_evolver.py` 是联邦与独立实验共用的 Teacher。每角色对六任务类分别生成至多 8 条 finding；每条 recommendation ≤600 字符、受影响旧 ID ≤12、证据引用 ≤16。然后分两阶段合成：只允许 `DELETE/UPDATE` 并冻结；程序算该角色 `max_add=floor(去重DELETE/3)`；如大于零，再只生成 `0..max_add` 条 `ADD`；最后重新完整校验。`UPDATE` 不能跨角色，只可在该角色七桶内迁移。
4. **每个角色、每一轮独立计额**：`ADD_role <= floor(distinct DELETE_role/3)`；额度不能跨角色或跨轮借用；`UPDATE` 不计额；零操作、只删、只更新合法。结果条数 `N'_role=N_role-DELETE_role+ADD_role`。无固定 23/23 或每桶条数上限。
5. 联邦上传每客户端**完整多角色 SkillBank**，patch 只作本地审计。服务器把每个角色库的每条 Skill 视为一个带 `client/role/bucket/id` 来源的输入，仍仅按原七桶做 DeepSeek 语义合并；全部输入来源必须恰好被覆盖一次。服务器不做评价，也没有“三删一加”容量约束；输出一份 Global，再复制给各角色并在三端各验证 134 题。
6. 独立 Client A 从显式给定的 B1 沿 B2→B5 本地延续，不读取 Global。它使用同一个 `role_evolver.py` 和**逐角色**配额。与 v9 独立分支的全客户端共享配额口径不同，因此 v9 结果不能当作 v11 结果。
7. 训练轨迹进入 Teacher，验证轨迹只用于学习曲线，不回流、不准入、不回滚。任务执行仍为 Qwen `qwen3.6-flash`；Teacher/服务器聚合要求 DeepSeek 官方 `deepseek-flash`。每阶段第一次程序/API错误停止，保留已写文件；禁止默认覆盖或自动拼接失败段。

## 文件与衔接

| 文件 | 职责 |
|---|---|
| `materialize_assets.py` | 从文件哈希锁定的 v9 A/B/C 清单与空 B0 生成 v11 身份的相同 134+134 题清单与空模板。 |
| `import_v9_b1.py` | 校验并复制冻结 v9 B0→B1 结果，提供独立与联邦初始入口的显式来源守卫。 |
| `bootstrap_b1.py`、`scripts/bootstrap_b1.py`、`run_to_b1.py` | 只允许 ADD 候选的 B0→B1 Teacher 与 B0验证→训练→B1生成→验证控制器。 |
| `role_evolver.py` | 两实验共用的逐角色分析、两阶段补丁、证据/ID/字段/精确重复校验、完整子库物化及attempt/checkpoint审计。 |
| `run_local_round.py` | 对一个客户端执行父库134题训练→本地Bn生成→Bn的134题验证；父库可为上一代独立B库或Global下发副本。 |
| `run_independent_to_b5.py` | Client A 独立 B1→B5 串行编排，止于 B5 验证。 |
| `server_aggregate.py` | B1开放初始聚合或后续三个完整多角色本地库的七桶聚合；验证结果和source_lock须与上传库字节哈希匹配。 |
| `downlink.py`、`run_global_validation.py` | 单 Global 完整复制到每个角色，并运行三客户端冻结验证。 |
| `run_federated_round.py` | 一个同步联邦轮：已验证 Global k→三端本地 B(k+1)→聚合 Global k+1→三端 Global 验证；只接受 k=1..4，止于 Global5。 |

`run_to_b1`、`run_local_round` 与 `run_global_validation` 借用 v9 的冻结 Qwen 阶段执行器，但必须显式使用 v11 清单与 v11 输出目录。DeepSeek JSON模式/截断attempt记录复用**SHA-256锁定**的 v9 helper，原始raw保留；若 helper 内容改变，v11 Teacher 首错停止。v11 使用 `--resume` 只复用完整且身份匹配的阶段；部分134题阶段须先按冻结前缀由阶段执行器单独审计恢复，控制器不会自行重跑或覆盖。

## 离线检查

从项目根目录运行锁定环境的 Python：

```powershell
.\.venv-stage3-alfworld\Scripts\python.exe -m stage2_local_v11.materialize_assets --check
.\.venv-stage3-alfworld\Scripts\python.exe -m unittest stage2_local_v11.tests.test_v11_protocol -v
.\.venv-stage3-alfworld\Scripts\python.exe -m compileall -q stage2_local_v11
```

正式实验需先核对 API 余额与凭据、ALFWorld 数据目录、A/B/C 的 v11 清单、初始空 B0 或选定且明示的 B1、每次新运行目录及其输出成本。此文件不构成启动正式实验的指令。

## 时间与并发

官方额度、历史耗时、现有串行瓶颈和安全并发建议见 [`CONCURRENCY_ANALYSIS.md`](CONCURRENCY_ANALYSIS.md)。当前 V11 **未**修改单客户端 134 题执行器，也未启动任何付费实验；本文中的并发数是待实测的调度建议，不是官方保证的同时请求数。

### 专用冻结题目分片执行器

`sharded_phase.py` 是可选的单客户端训练/验证阶段入口；现有 V11 代际控制器尚未自动调用它。默认只读打印分片计划，只有显式传入 `--execute` 才会调用付费 Qwen API。它逐字节核对 V11 冻结清单、父库代数和哈希，把 134 个任务按冻结执行顺序分片，每个分片使用独立进程与输出目录；全部成功后检查 134 题恰好各完成一次、没有 API 错误，并按冻结次序生成与原阶段兼容的 `result.json`、`summary.json`，训练阶段还生成 `evidence.json`。任何分片失败都停止新分片、终止仍在运行的同阶段分片，保留全部输出供人工审计；不会自动重跑或拼接失败结果。

例如，仅验证 Client A 的 134 个单题分片计划（**不会调用 API**）：

```powershell
python -m stage2_local_v11.sharded_phase --client A --phase validation --generation 0 --manifest stage2_local_v11/artifacts/manifests/client_a_generation_01.json --output-root stage2_local_v11/runs/shard_plan_example --data-root alfworld_data --shards 134 --max-workers 134
```

正式运行必须另外指定全新输出目录和 `--execute`。默认并发为 2；`--shards 134 --max-workers 134` 只表示代码可构造 134 路，不代表账号额度、机器内存或网络已能承受。可先使用 `--pilot-tasks 2/4/8` 按冻结清单均匀抽取少量题目、设置相应分片和并发，逐级实测；这些输出标记为`pilot_complete`且不产生训练证据，不能进入正式控制器。只有 429、超时、本机内存与每分钟 Token 用量都可控时才提高。已发到模型服务的请求即使本地超时、丢失响应或被中途终止，也可能产生费用；失败后不得在未经逐分片审计前重跑。

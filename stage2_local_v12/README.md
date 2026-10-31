# V12：V10协议的自包含等价实现

V12把原V10正式实验需要的客户端、阶段执行、本地Teacher、七桶聚合、下发验证、冻结任务清单和导入B1种子收口到一个Python包。它不修改V10实验算法，也不把既有V10结果重标记为V12结果。

## 身份与边界

- `implementation_id`：`stage2-local-v12-self-contained-v1`
- `protocol_id` / 兼容`experiment_id`：`stage2-local-v10-role-partitioned-patch3`
- V10正式节奏保持为：`B2 -> Global1 -> B3 -> B4 -> Global2 -> B5 -> B6 -> Global3`。
- 本地Teacher仍逐角色生成finding，先冻结DELETE/UPDATE，再按`ADD_role <= floor(distinct DELETE_role / 3)`生成ADD。
- 服务器仍把三端完整多角色库按General加六类task-specific聚合为一份角色无关七桶Global，并完整复制给客户端每个角色。
- 任务执行仍为`qwen3.6-flash`；本地Teacher与服务器聚合仍要求DeepSeek官方`deepseek-flash`。
- 验证只记录学习曲线，不反馈Teacher、不准入、不回滚。Global3三端验证完成后停止。

V12源码不在运行时import或读取`stage2_local_v6`、`stage2_local_v9`、`stage2_local_v10`、`originalFL`、`stage3_federation`、`stage3_2_role_agnostic_semantic_merge`或根`client_code`。`provenance/materialize_static_runners.py`只是本次迁移的来源记录，不是运行入口。

## 阅读顺序

1. `orchestration/run_two_local_to_global3.py`：完整正式计划。
2. `orchestration/run_local_round.py`：单端训练、Teacher和验证。
3. `evolution/role_evolver.py`：逐角色两阶段patch与三删一加。
4. `federation/server_aggregate.py`：完整多角色库到七桶Global。
5. `federation/downlink.py`与`federation/run_global_validation.py`：下发和三端验证。
6. `runtime/phase_runner_a.py`、`phase_runner_b.py`、`phase_runner_c.py`：由旧overlay物化后的静态阶段执行器。
7. `clients/alfworld_client_a.py`、`b.py`、`c.py`：三种真实多Agent控制流。

## 目录

| 路径 | 职责 |
|---|---|
| `clients/` | A/B/C客户端、ALFWorld公共行为与SkillBank加载 |
| `runtime/` | 静态阶段执行器、Bank读写、adapter与evidence整理 |
| `evolution/` | B0到B1与B2以后逐角色Teacher |
| `federation/` | 七桶语义聚合、下发与Global验证 |
| `orchestration/` | 正式链、单轮、独立链和资产/种子校验 |
| `assets/` | 三端冻结manifest、空B0和导入v9 B1种子 |
| `tests/` | V10协议兼容与V12自包含守卫 |
| `provenance/` | 迁移来源与逐文件SHA-256，不参与正式运行 |
| `runs/` | V12新运行输出；当前为空，不包含V10历史runs |

## 外部运行条件

源码自包含不等于复制第三方依赖。正式运行仍需：

- Python 3.10兼容环境；
- `openai`、`alfworld`、Client A所需`langgraph`及ALFWorld传递依赖；
- 外部ALFWorld数据根，例如`D:\skillMAS\alfworld_data`或对应WSL路径；
- DashScope和DeepSeek凭据，仅通过环境变量提供，禁止写入V12。

V12不复制虚拟环境、API Key、`.env`或2.27GB ALFWorld数据集。

## 离线验证

```powershell
.\.venv-stage3-alfworld\Scripts\python.exe -m stage2_local_v12.orchestration.materialize_assets --check
.\.venv-stage3-alfworld\Scripts\python.exe -m stage2_local_v12.orchestration.import_v9_b1 --check
$env:TEMP=(Resolve-Path .tmp/v12-tests).Path
$env:TMP=$env:TEMP
.\.venv-stage3-alfworld\Scripts\python.exe -m unittest discover -s stage2_local_v12/tests -p "test_*.py" -v
.\.venv-stage3-alfworld\Scripts\python.exe -m compileall -q stage2_local_v12
```

这些命令不调用外部模型。正式运行前还应在原项目WSL ALFWorld环境执行相同检查。

## 正式控制器

```powershell
python -m stage2_local_v12.orchestration.run_two_local_to_global3 `
  --run-root stage2_local_v12/runs/two_local_global3_<date>_r1 `
  --data-root <ALFWorld数据根> `
  --python <锁定Python>
```

不要在未核对余额、凭据、模型锁、数据根和全新输出目录前执行该命令。V12.0代码就绪不构成启动付费实验的授权。

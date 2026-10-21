# Stage2 Local v9：B1开放构建与B1锚定的后续容量

v9保留`stage2_local_v6`的任务、模型、证据、字段校验、代际冻结、验证和停止规则。B1取消每个角色最多14条Skill的限制并从空B0开放式构建；从B2开始，以冻结B1各角色的实际条数作为该角色后续固定容量。v6源码、B0--B5 SkillBank及结果保持原位且只读；v9不把v6 SkillBank或结果作为父代或新结果。Client A/B/C使用同一阶段口径，但Teacher提示按各自运行时角色边界独立生成。

## 容量规则

- B1最终合并不再要求`Maximum 14 total skills`，也不执行容量修复、机械裁剪或14条断言。
- 生成B2时，程序从冻结父B1逐角色统计实际条数并写入`capacity_policy`；B3以后必须继承同一B1文件哈希和角色容量，不能按较小的上一代库重新收缩容量。
- 父库低于容量时，只要完整候选最终不超过B1容量即可直接ADD；达到容量时，必须DELETE或MERGE释放位置后再ADD。角色容量不能互借。
- 超过B1容量时最多执行两次Teacher合并/删除修复；仍超限即拒绝输出。程序不做固定顺序机械裁剪。

每条Skill各文本字段最多900字符的schema限制继续保留；这不是Skill数量限制。B1可保留任意数量的非重复有效Skill，后续容量由B1实际结果内生确定。

### D-104 Client A 独立三删一加分支

固定B1角色容量是原v9主线的历史规则。用户于D-104另行授权的Client A独立对照从原始B1（文件SHA-256=`84218a56b828fe08b81bd476c62d32950f61764b13390e957fd22c430bf24db4`）重新生成B2，并改用显式净patch约束：整个Client A的Planner、Executor、General和六类任务桶共享删除额度，每轮满足`ADD <= floor(distinct DELETE / 3)`；UPDATE不产生也不消耗额度，且只能在同一角色内修改或迁移任务桶。该分支不再使用23/23固定容量，也不做机械裁剪。

正式输出进入`runs/client_a_b1_patch3_to_b5_20261015_r1/`。patch仅作为本地演化审计和原子物化依据，不作为联邦上传对象；联邦上发和下发统一使用完整SkillBank快照。旧`runs/client_a_generation_01_20261013_r1/`中的固定容量失败分支保持只读，不复用其B2 Teacher检查点。

按D-105，D-104分支的Teacher调用启用DeepSeek JSON输出模式，并在解析前把每个响应写入`B*_teacher_attempts/`独立记录。记录包含请求的`max_tokens`、choice数量、`finish_reason`、usage、可得正文和响应状态；旧记录不覆盖。任务族finding最多8条，每条recommendation最多600字符、affected skill IDs最多12个、evidence refs最多16个。空choices或长度截断最多额外重试2次，输出预算仍为16000；只有attempt记录证明确实触顶后才允许讨论提高。

按D-107，任务族响应顶层只允许`findings`，最终patch响应顶层只允许`operations`，提示中明确禁止复制JSON模式的`type`、`schema`或`name`等传输元数据。为兼容DeepSeek已观测到的唯一包装形式，解析器只在顶层键严格等于“期望字段加`type`”且`type`值严格为`json_object`时移除该字段；任何其他额外、缺失或不同字段继续拒绝。原始attempt保持不变，规范化另写审计记录，并允许从既有检查点重放合法的原始响应而不重复调用Teacher。

按D-112，Client A独立分支的DELETE/UPDATE目标ID按角色解释。最终patch提示显式列出`allowed_target_ids_by_role`；同名ID存在于另一角色不构成合法目标。若标准三次最终patch均因角色/ID越界被拒绝，后续显式resume最多新增两次final-patch-only恢复调用，保留原检查点、family findings和三次raw attempt，不重做分析或覆盖证据。

## 对照身份与数据

- Client A/B/C执行均为`qwen3.6-flash`，temperature 0、seed 1234、thinking关闭。
- B1--B5全部Teacher调用统一使用DeepSeek官方`https://api.deepseek.com`，API模型ID为`deepseek-flash`，temperature 0、thinking关闭；不使用DashScope托管Teacher。
- 每代训练134题、每个B0--B5版本验证134题；训练和验证任务逐项等同v6冻结清单。
- 验证仍只记录学习曲线，不准入、不回滚、不早停、不进入Teacher。
- 新输出固定进入`stage2_local_v9/runs/`；不得写入或恢复v6运行目录。

## 代码边界

v9使用fail-closed覆盖层读取冻结v6入口。覆盖层先校验v6源文件SHA-256，再移除固定14条容量逻辑，并加入B1开放构建与B1锚定的动态角色容量；v6源码有任何变化都会在运行前停止。容量解析和硬校验位于`capacity_policy.py`，阶段执行和B2--B5控制器把默认清单、脚本和输出路径改向v9。

`scripts/materialize_manifest.py`从已冻结v6清单生成Client A的v9清单；`scripts/materialize_client_bc_assets.py`再物化B/C独立清单和显式空B0。三端的训练/验证任务数组保持完全一致，各自的实验身份、证据、SkillBank和结果相互隔离。

Client B的角色为`Executor`和非行动`Critic`；Client C的角色为非行动`Supervisor`、`Search Worker`和`Operation Worker`。B/C入口由`client_overlay.py`从已哈希锁定的v9无容量版本生成，并逐项替换客户端运行时、角色集合、角色边界、清单和证据身份；替换数量不符合预期时立即停止。

## 入口

从项目根目录运行：

```powershell
python -m stage2_local_v9.scripts.materialize_manifest
python -m stage2_local_v9.scripts.run_client_a_phase --help
python -m stage2_local_v9.scripts.evolve_client_a_bank --help
python -m stage2_local_v9.scripts.run_client_a_to_b5 --help
python -m stage2_local_v9.run_client_a_patch_to_b5 --help
python -m stage2_local_v9.scripts.materialize_client_bc_assets --check
python -m stage2_local_v9.scripts.run_client_to_b1 --help
```

与v6一致，B0验证、B0训练和B1生成/验证使用单阶段入口；冻结B1后，控制器串行完成B2--B5并在B5验证后停止。正式执行前必须另行确认凭据、成本、空B0起点和新输出目录。本次修订没有启动模型或ALFWorld实验。

按D-083，当前运行入口`scripts/run_b0_to_b1_with_local_secrets.sh`虽保留历史文件名，但有效范围已收窄为：先运行空库B0的134题训练，再运行同一空库B0的冻结134题验证，随后停止。它不调用Teacher、不生成B1，也不进入B2。generation 1训练使用`skill-mode none`；B0验证使用generation 0空库语义。

v9的Teacher provider已经独立冻结为B1--B5全程DeepSeek官方接口。历史v6实际运行的B1/B2来自DashScope托管Teacher，这项历史来源差异应在最终对照报告中明确披露；它不再是v9的待确认项。D-085只授权从已冻结、API-clean的B0训练证据生成一次B1；B1验证与B2--B5仍暂停。

按D-089，Client B和C分别运行`B0验证 -> B0训练 -> B1 Teacher -> B1验证`并停止。Teacher只读取对应客户端的`B0_training/evidence.json`；B0和B1验证轨迹都不进入Teacher。Client A现有结果保持冻结，所有客户端的B2--B5继续暂停。

## Client B/C 正式r3结果

- Client B：B0验证69/134、B0训练76/134；B1为Executor 22条、Critic 20条；B1验证110/134。任务阶段均API-clean。
- Client C：B0验证51/134、B0训练58/134；B1为Supervisor 17条、Search Worker 24条、Operation Worker 22条；B1验证110/134。任务阶段均API-clean。
- Client C的Teacher在18个任务族分析完成后，第一次最终合并响应因8000 token输出边界截断并按首错停止。按D-092保留原检查点副本，仅把恢复调用输出预算提高到16000，从检查点完成三个角色合并；没有重跑18个任务族分析，没有容量修复或裁剪。
- 两端控制器均正常停止在`B1_validation`；r2的6题pilot不计入结果，B2及以后未启动。

## 离线验证

```powershell
python -m unittest stage2_local_v9.tests.test_v9_protocol -v
python -m stage2_local_v9.scripts.materialize_manifest --check
```

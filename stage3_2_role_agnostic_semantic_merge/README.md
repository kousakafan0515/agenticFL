# Role-Agnostic Semantic Global Merge Baseline

本目录实现D-094：以v9 A/B/C冻结B1为首次输入，把每条初始Skill表示为空库上的ADD，随后丢弃目标角色分区，仅按General与六类task-specific分别由DeepSeek官方接口去重、合并和角色中立总结。

首次输出是一份完整Global SkillBank；A/B/C下载副本必须字节级一致。服务器不运行评价集，本目录也不自动启动客户端评价或v9 B2。

后续本地自进化规则为每客户端、每轮独立满足`ADD <= floor(DELETE / 3)`；首轮空库ADD豁免。服务器语义合并只允许等量或压缩输出，不产生DELETE额度。

按D-103，自第二次聚合起联邦通信两端都只传完整SkillBank快照：客户端上传本轮冻结后的完整本地SkillBank，服务器聚合后下发完整Global SkillBank并整体替换客户端旧库。本地生成的DELETE/UPDATE/ADD patch只用于客户端内部审计和确定性物化，不再作为服务器输入、下发对象或通信统计口径。

正式入口：

```bash
bash stage3_2_role_agnostic_semantic_merge/run_round1_with_local_secrets.sh
```

入口支持检查点恢复。每个桶的原始返回、校验记录和用量分别保存；已完成桶不会重复调用。

## Round 1正式结果

- 运行目录：`runs/v9_b1_round1_20261014_r1/`
- 冻结输入：Client A/B/C分别46/42/63条，共151条空库ADD。
- 聚合输出：43条，其中General 11条，六类task-specific依次为1/5/6/7/5/8条。
- 来源审计：151个来源全部且仅归属一次，无遗漏、未知来源或重复归属。
- 下发审计：A/B/C三份完整Global SkillBank与服务器文件字节级一致，SHA-256均为`c55e5db60cccfcf011c633550c39cac268799972150eb34216ba442cf4ee6939`。
- 本轮未运行服务器评价或客户端评价，未进入B2。独立审计见`runs/v9_b1_round1_20261014_r1/verification.json`。

## Round 1客户端验证

按D-095，A/B/C使用同一43条完整Global替代库，分别运行冻结134题验证。兼容视图把同一General与六类task-specific映射给客户端全部角色；单题只注入General与当前任务类别，使用群体共享Global提示，不做角色专属筛选。

- 运行目录：`runs/v9_b1_round1_client_validation_20261014_r1/`
- 物化入口：`python -m stage3_2_role_agnostic_semantic_merge.client_global_validation`
- dry-run：`bash stage3_2_role_agnostic_semantic_merge/preflight_client_validations.sh`
- 单客户端后台执行：`bash stage3_2_role_agnostic_semantic_merge/run_client_global_validation.sh <A|B|C>`
- 三端启动器：`launch_client_validations.ps1`

三个客户端是独立后台进程，任一失败不阻塞其他客户端，也不自动重启。历史v9 B1与D-094 Global文件不会被覆盖。

正式验证已完成：A/B/C分别为84/134、100/134、95/134，三端均API-clean且无程序错误，pooled为279/402。与逐项相同的各端本地B1冻结验证相比，A/B/C分别变化-9/-10/-15，pooled从313/402降至279/402（-34）。完整结果与六类明细见`runs/v9_b1_round1_client_validation_20261014_r1/final_validation_summary.json`。

## Round 2完整库聚合与Global2验证

D-101以A/B/C三份完整本地B2（各41条、共123条）作为服务器输入，七桶语义聚合得到44条Global2；文件SHA-256为`7ea48b556110d7ac1524a091b45396f81f590eb0367be11ba0e16e9cb7e1954d`。D-106把该完整Global2下发给三端并整体替换运行库，在既有冻结134题清单上独立验证；不运行训练、Teacher、Global3或下一轮聚合。

- 聚合结果：`runs/v9_local_b2_round2_20261014_r1/global_skillbank2.json`
- 验证目录：`runs/v9_global2_client_validation_20261015_r1/`
- 下发物化：`python -m stage3_2_role_agnostic_semantic_merge.client_global_validation --global-bank <Global2> --output-root <run> --expected-sha256 7ea48b...1954d --expected-skills 44 --expected-round-index 2 --generation 2`
- dry-run：`bash stage3_2_role_agnostic_semantic_merge/preflight_global2_client_validations.sh`
- 后台启动：`powershell -File stage3_2_role_agnostic_semantic_merge/launch_global2_client_validations.ps1`

## Global2本地演化至B3

按D-108，只有完成134题Global2验证且`api_clean=true`的客户端才能进入下一阶段。每端使用同一44条Global2完整替代库运行冻结134题训练，DeepSeek官方Teacher生成角色无关本地B3；全客户端七桶共享额度，仍满足`ADD <= floor(distinct DELETE / 3)`，UPDATE不计额度。B3随后在本端冻结134题验证集上评价并停止，不自动聚合Global3。

- 运行目录：`runs/v9_global2_to_local_b3_20261015_r1/`
- 单端控制器：`python -m stage3_2_role_agnostic_semantic_merge.run_global2_to_local_b3`
- 后台启动：`powershell -File stage3_2_role_agnostic_semantic_merge/launch_global2_to_local_b3.ps1`
- Teacher JSON正文顶层只允许`findings`或`operations`；仅精确的`type=json_object`传输包装可被审计移除，其他额外字段继续拒绝。
- 按D-109，若完整patch仅因技能文本字段超过900字符被拒绝，恢复流程可从最后一个冻结attempt对全部超长字段做最多两次定向压缩，目标不超过760字符。程序要求除这些字段外的完整patch严格不变，并把压缩响应写入独立attempt；不得覆盖前三次patch、重跑训练或family分析。
- 按D-113，B/C在自动压缩修复耗尽后停止调用Teacher。人工审阅只替换程序识别为超长或含角色词的字段，并确定性删除超过`floor(DELETE/3)`的既有ADD；不得新增操作或修改DELETE/UPDATE、目标、桶、证据与其他字段。`manual_field_repair.py`对修订候选执行完整硬校验并写出独立审计。B/C修复后均为42条（DELETE=3、ADD=1；UPDATE分别7/10），控制器直接进入B3验证。

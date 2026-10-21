# 项目协作规则（所有 Agent 必读）

本文件作用于 `D:\skillMAS` 整棵目录树。子目录若有自己的 `AGENTS.md`，以更靠近目标文件的规则为补充；发生冲突时，以更具体的规则为准。

## 1. 每个新对话的启动顺序

开始工作前依次读取：

1. `README.md`：项目目标、数据边界和主要入口；
2. `docs/PROJECT_MAP.md`：目录角色、当前实现与历史副本的区别；
3. `docs/collaboration/NOW.md`：当前任务、进度、阻塞和下一步；
4. 与任务直接相关的阶段 README、方案、报告或源码。

随后先向用户用简短中文说明：

- 本次目标；
- 已确认的当前状态；
- 计划修改或检查的范围；
- 任何会影响结果的假设或风险。

不要仅凭目录名推断当前版本，不要把 `deliverables/`、`audit_sources/` 或带日期的归档副本当作默认编辑目标。

## 2. 权威来源与修改边界

- 根目录 `README.md` 是项目总体说明。
- `docs/PROJECT_MAP.md` 是目录分类和导航的权威来源。
- `docs/collaboration/NOW.md` 是实时协作状态的唯一权威来源；不要另建同类的 `status_final_v2.md`。
- `docs/collaboration/DECISIONS.md` 只记录会影响后续工作的稳定决策，不记录流水账。
- 当前冻结 SkillBank 以 `current_skillbanks/*.json` 为准。
- Stage3 聚合实现以 `stage3_federation/` 为主；简单并集基线及其正式结果在 `stage3_1_simple_aggregation/`。
- `stage2_local`、`stage2_local_v2` 至 `stage2_local_v5` 是演进版本。修改前必须先从任务上下文确认目标版本，默认不得批量同步修改所有版本。
- `deliverables/` 是交付快照，`audit_sources/` 是审计/复现副本，`SkillAdaptor_MAS_collaboration_20260901/` 是上游完整工作区。除非任务明确要求，不在这些目录中做日常修复。
- `artifacts/`、`runs/`、`results/`、`*_results/`、日志、压缩包和虚拟环境通常是生成物或证据；不得为了“整理”而移动、重命名或删除。

## 3. 工作方式

### 开始任务时

- 先检查目标文件、相邻 README、当前状态和未提交/未归档改动；本目录当前不一定是 Git 仓库，不能假定可以依赖 Git 恢复。
- 在 `docs/collaboration/NOW.md` 登记任务目标、范围、状态和接手提示；仅编辑该文件中的“当前工作”区，不覆盖别人的历史记录。
- 若发现已有 agent 正在处理同一文件或同一实验，先避免并发写入，并在状态面板说明冲突。

### 工作过程中

- 源码、配置、测试、结果分开放置；新生成物进入对应阶段的 `artifacts/` 或 `runs/`，不要堆到根目录。
- 新目录使用能表达“用途”的稳定名称；只有实验运行或冻结快照才在名称末尾使用 `YYYYMMDD` 或 `YYYYMMDD_rN`。
- 优先修改当前权威实现，避免复制出 `final`、`final2`、`new`、`latest` 等含义模糊的新版本。
- 运行外部模型或大规模评测前，先确认成本、凭据、输入清单和输出目录；诊断与单元测试不应意外触发正式实验。
- 不在文档、日志或提交内容中写入 API Key、令牌、`.env` 内容或未经脱敏的隐私数据。
- 任何会改变实验口径、冻结输入、评测集合或统计结论的操作，都要先记录到 `DECISIONS.md`，并明确这是“既有决策”还是“待用户确认”。

### 结束或交接时

- 运行与改动风险相匹配的最小验证，并记录实际运行的命令类别与结果；没有运行要明确写“未运行”及原因。
- 更新 `docs/collaboration/NOW.md`：完成项、剩余项、阻塞、验证、关键文件和最自然的下一步。
- 若产生稳定架构/实验决策，追加到 `docs/collaboration/DECISIONS.md`；不要改写旧决策，若推翻则新增一条并引用旧编号。
- 给用户的最终回复先说结果，再列关键文件、验证和遗留风险。路径应精确到文件，不用模糊的“那里”“相关文件”。

## 4. 实时状态规范

`docs/collaboration/NOW.md` 必须保持短小，只描述当前仍有用的信息：

- 同一时间最多保留一个“主要任务”；并行工作作为子项列出负责人/agent 标识；
- 状态只能使用：`待开始`、`进行中`、`等待用户`、`受阻`、`已完成待归档`；
- 时间统一写为 `YYYY-MM-DD HH:mm`，并注明时区 `Asia/Shanghai`；
- 每个接手点必须包含“已完成到哪里”“下一步做什么”“不要做什么”；
- 任务结束后，把结论压缩到“最近完成”，清空临时细节，为下一次对话腾出空间。

## 5. 目录与文件命名

- 文档使用清楚、稳定的英文文件名，正文可用中文；协作入口固定为本文件及 `docs/` 下的文件。
- Python 模块、测试与 JSON schema 沿用现有 `snake_case`；测试文件使用 `test_*.py`。
- 实验输出目录优先采用 `<scope>_<YYYYMMDD>_rN`，例如 `full134_global_20260924_r1`。
- 不随意改变历史产物的名字。需要更正时，新建可追溯的修订版，并在报告或决策日志中说明前后关系。

## 6. 常用验证入口

按实际改动选择，不要求无关测试全部运行：

```powershell
python -m unittest stage3_federation.tests.test_transport_patch_converter -v
python -m unittest discover -s stage3_federation/tests -p "test_*.py" -v
python -m unittest stage2_local_v5.tests.test_v5_protocol -v
```

正式 ALFWorld 运行、外部 API 调用和全量 134/402 episode 评测不属于默认验证，除非用户明确要求且运行条件已确认。


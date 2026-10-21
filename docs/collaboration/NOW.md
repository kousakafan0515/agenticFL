# 实时协作状态

> 这是当前协作状态的唯一权威页面。时间均为 Asia/Shanghai。

## 当前工作

- 状态：已完成待归档
- 负责人：Codex /root
- 最后更新：2026-10-21 08:25（Asia/Shanghai）
- 主要任务：以2026-10-21现状为基线，将`D:\skillMAS`初始化为Git仓库并纳入V10代码和实验结果。
- 已完成到哪里：已将`D:\skillMAS`初始化为`main`分支Git仓库，首个基线暂存共1389个文件、约1616.31 MiB；其中V10为1188个文件，完整纳入源码、清单、正式`runs/`、SkillBank、Teacher记录、日志与分析`artifacts/`，并纳入V11现存代码/冻结材料、项目文档、共享`client_code`及V9/Stage3.2必要依赖源码。V10/V11运行树用Git属性关闭文本归一化和文本diff，按原始字节保存。Git LFS 3.6.1处理首个结果文件时发生Windows访问冲突，已停用本仓库LFS并改用原生Git；最大单文件约59 MiB。敏感扫描未发现`sk-`密钥模式，无`.env`/`secrets`或超过100 MiB文件进入暂存。V10协议14项测试在工作区临时目录下全部通过。
- 下一步做什么：首个基线提交已创建为`31fad203c90e32b132e0c67161e502381df2b35a`；后续V10及其后续版本在此仓库继续提交。若未来绑定远端，先确认远端容量与大仓库策略；工作区纳入文件约1.6 GiB，当前Git对象库因压缩约179 MiB，尚未配置remote或推送。
- 不要做什么：不要改写、移动或重新生成冻结V10结果；不要把`.env`、API Key、虚拟环境或ALFWorld数据提交；不要启动任何模型调用或正式评测。

## 下一步

1. 保留联邦A/C与独立A的验证冻结前缀；余额恢复后分别从剩余104/92/69题续跑，不覆盖或拼接旧结果。
2. 联邦B保持B4 Teacher失败状态；如获授权，按C同样流程保留全部证据、人工压缩853字符字段并处理可能的超额ADD，通过完整校验后从检查点续跑。
3. 三端本地B4均完整后才能恢复主控制器进入Global4；止于Global5三端验证。
4. Client A独立线恢复B4验证后继续B4训练及B5演化，且不得进入B6或联邦上传。

## 最近完成

- 2026-10-21：以当前V10工作状态初始化`D:\skillMAS` Git仓库，分支为`main`，首个基线提交为`31fad203c90e32b132e0c67161e502381df2b35a`。该提交覆盖V10完整代码和实验结果、V11现存材料、共享客户端代码、项目文档及必要V9/Stage3.2/Stage3依赖，共1389个文件、约1616.31 MiB；凭据、环境、ALFWorld数据、历史交付/审计副本及无关旧实验目录已忽略。冻结运行树按原始字节暂存，未发现密钥模式、`.env`/`secrets`或超过100 MiB单文件；V10协议14项测试通过。Git LFS因本机访问冲突停用，完整结果改由原生Git保存；当前Git对象库压缩后约179 MiB，尚未配置remote或推送。

- 2026-10-21：完成项目已读文献与“近二年AI顶会长文/顶刊”条件的只读交叉核验。项目记录可确认已阅读/核对ReAct、Reflexion、SkillOpt、EmbodiSkill、FederatedSkill、Graph-of-Skills及BPO；严格交集为空：ReAct/Reflexion为2023顶会，2026年Skill自进化相关工作当前均为预印本或专题研讨会。另确认AutoGuide为NeurIPS 2024主会、Experiential Co-Learning为ACL 2024长文、ExpeTrans为ACL 2025长文，但工作区暂无用户已读证据，不能写成“已阅读”。未修改源码、实验产物或运行状态。
- 2026-10-21：核对operation card的角色注入差异与可追溯责任。差异在Stage1三客户端源码中已形成并由V10继承：A只向实际行动的Executor注入，静态Planner不注入；B同时向行动Executor和负责动作审计的Critic注入；C向负责阶段分派的Supervisor上下文及两个行动Worker均注入。A的Planner基础提示本身仍含“只能携带一件物体”等少量机制信息，故不能描述为完全无操作先验。项目无Git历史、无对应DECISIONS编号或署名设计文档，现有证据只能定位到2026-09-13/14前后的Stage1实现，不能可靠归因到具体个人；本次审计未新增或改变该设计。

- 2026-10-20：完成V10 operation card的外部方法依据核对。ReAct论文明确ALFWorld由1--2条上下文示例驱动；Reflexion和EmbodiSkill官方代码包含固定ALFWorld成功轨迹，显式示范open/take/clean/heat/put等操作；部分实现还逐步提供完整admissible actions。结论是“给自改进agent固定环境操作脚手架”有公开先例，但`full/weak/invalid-only`命名及四条operation card未发现外部同款，不能称为通行标准；Graph-of-Skills等最小提示也是反例。未修改源码、配置或实验产物，未运行外部模型。

- 2026-10-20：完成V10 operation-card机制核对。`full/weak/invalid-only`是三种静态环境操作提示强度，`A-Base`仅指Client A不注入card的对照配置。V10运行目录47份相关冻结命令全部使用weak，A均显式启用card；full、invalid-only、A-Base均未运行。card按客户端进入Executor/Critic/Supervisor/Worker提示，直接影响执行并通过训练轨迹间接影响技能演化；由于V10无card配对消融，只能认定绝对成绩包含其影响，不能量化独立贡献。未修改源码或冻结实验产物。

- 2026-10-20：完成V10代码与实验结果协作交付ZIP。包含完整V10运行证据、v9导入B0/B1种子、分析与阅读版SkillBank、V10源码及精简依赖源码；排除密钥、虚拟环境、ALFWorld数据和无关历史运行。交付清单、校验和及构建脚本见`deliverables/v10_code_and_results_20261020_r1/`；ZIP SHA-256=`16b2a6bca0bd35484ab5ab63f293040a347f6cf99f80af4b2a6ceb2b295407cd`。

- 2026-10-19：完成V10 G1/G3逐题伤害审计。G1加热20、清洗18为主；G3冷却24为主，其中23题未执行`cool`、19题曾放入冰箱。82道清洗/加热/冷却伤害题的本地成功轨迹均执行所需状态动作，Global轨迹60题没有；14道同客户端同题跨两轮重复受损。所有实际注入Skill按角色与Global库及来源key逐一对齐；具体机制仅为证据支持的假说，不作单Skill因果认定。结果见`stage2_local_v10/artifacts/global_harm_audit_20261019_r1/REPORT.md`。

- 2026-10-19：完成V10全链30份SkillBank的仅供阅读中文对照版；39次DeepSeek官方翻译attempt、774段去重英文正文及5,493处替换均留有审计，30份来源与对照文件逐一校验通过。`stage2_local_v10/artifacts/chinese_skillbank_reference_20261019_r1/INDEX.md`可浏览各客户端B1–B6及Global1–3；B0为空库。未改原始实验文件或英文对照版。

- 2026-10-19：用户明确授权后，完成V10当前正式链30份SkillBank的仅供阅读英文对照版：295段去重正文、1,700次字段替换，逐原文件哈希与非正文结构核验通过；30份英文Markdown阅读版无中文字符。24次DeepSeek官方API attempt及15处确定性用词修正均留有审计，4项离线测试通过。产物入口`stage2_local_v10/artifacts/english_skillbank_reference_20261019_r1/INDEX.md`；译本未接入实验，14段译文超过运行字段上限，禁止作为实验输入。

- 2026-10-18：D-120新增V11单客户端冻结题目分片执行器与非正式少量题目pilot入口；14项离线测试通过，134路仅完成零API调用的计划验证，正式负载尚未测。历史运行日志去重成本估算见`docs/EXPERIMENT_API_COST_ESTIMATE_20261018.md`：当前原价可计算部分约¥712–729，含缺失usage的全项目量级约¥730–800，非实际账单。

- 2026-10-18：完成D-119 V11完整克隆及Qwen并发评估。结果与检查见`stage2_local_v11/README.md`、`CLONE_MANIFEST.json`、`CONCURRENCY_ANALYSIS.md`；官方北京区别名限流30,000 RPM/1,000万 TPM，而当前单客户端134题串行。9项V11及9项V10协议测试通过，V11 Global1输入151条prepare-only通过，未调用外部模型。

- 2026-10-15：完成D-094/D-103/D-114完整SkillBank联邦baseline的只读文献评估。结论是：作为“统一全局库、整库替换”的弱基线设计合理且可解释，作为最终联邦算法则缺少异构客户端个性化、贡献权重、客户端准入门控与隐私/通信审计。最接近的FederatedSkill直接把单一全局库作为非个性化消融，并报告个性化语义合并优于统一Global；本项目G1相对本地B1为`279/402 vs 313/402`，G2相对本地B2为`268/402 vs 287/402`，已出现一致的负迁移信号。“删3加1”可作为容量正则，但无论文给出该固定比例，且只约束条数、不约束UPDATE语义漂移。未修改实验实现、未触发外部模型或评测。

- 2026-10-14：完成D-099/D-100三端本地B2验证及断点续跑。A/B/C=`89/134、100/134、98/134`，合计`287/402`；三端均API-clean、退出码0，结果SHA-256分别为`f5d777…52f2`、`78c20d…24ec`、`2b292b…34f6`。首次DashScope Arrearage错误仅作为历史保留；未启动训练、Teacher、再次聚合或B3，完成后已停止监控。

- 2026-10-14：完成D-095三端Global完整替代验证。A/B/C为84/134、100/134、95/134，三端API-clean且无程序错误；pooled 279/402，较各端本地B1同题同序对照313/402下降34题。正式汇总位于`stage3_2_role_agnostic_semantic_merge/runs/v9_b1_round1_client_validation_20261014_r1/final_validation_summary.json`，完成后已停止监控；未启动训练、Teacher、服务器评价或B2。

- 2026-10-14：完成D-094首次无角色七桶语义聚合。v9 A/B/C冻结B1共151条空库ADD由DeepSeek官方`deepseek-flash`合并为43条Global Skill；151个来源全部且仅覆盖一次，三端完整下发副本字节级一致，SHA-256=`c55e5db60cccfcf011c633550c39cac268799972150eb34216ba442cf4ee6939`。未运行服务器或客户端评价，未进入B2。

- 2026-10-14：按D-093完成v9 B1锚定容量实现。新增`stage2_local_v9/capacity_policy.py`，B2按冻结B1实际角色条数建立固定容量，B3+继承同一锚点；库未满时可直接ADD，达到容量后需DELETE/MERGE释放位置。Teacher提示包含容量、父库数量和空位；超限仅做最多两次模型修复并硬拒绝残余超限，禁止机械裁剪。策略写入SkillBank、checkpoint和Teacher记录。Windows/WSL各17项测试及语法检查通过；未启动B2或外部模型调用。

- 2026-10-14：将项目简历表述由联邦聚合主线改为异构多智能体群体智能自进化主线，突出角色协作、轨迹驱动反思、群体技能池、跨代知识积累与迁移评测；未改变任何实验事实或结果。
- 2026-10-14：完成面向算法/大模型岗位的项目简历表述；量化指标分别采用 Client A B0→B2=`72/134→86/134`、v9 Client B/C B1=`110/134`、Blind Global=`237/402`及 PatchFL 180条件消融，明确区分代际本地实验、历史对照和未收敛联邦实验。未修改源码或实验结果，未调用外部API。
- 2026-10-14：完成Client C v9 r3检查点恢复。根因是首个最终合并响应被8000 token输出边界截断；原18条family-analysis检查点以SHA-256=`3bad9760ffeea8d190a6091c4a4f4e463f2749378f787191ff71760e5f20af80`独立保留，续跑只把输出预算提高到16000。最终B1为Supervisor/Search Worker/Operation Worker=`17/24/22`条，B1 SkillBank SHA-256=`4702aeac4b6b7b759b1868d124ec8209616806eb16e3a0f2fbc3eacbc006da5d`；B1验证110/134、API-clean，result SHA-256=`0819399c6390f9ecaf0c8cb43ff53b37c703f39eff1de841d8890c03f49ab718`。控制器正常停止在B1验证，无B2目录或残留进程。

- 2026-10-09：针对协作者反馈生成单文件“代码+实际结果”修订包`deliverables/client_a_local_self_evolution_v6_code_and_results_20261009_r2.zip`。包内含原代码交付、B0--B4五轮完整134题训练result/evidence、B0--B5六次完整134题验证result、B1--B5 SkillBank、Teacher最终记录与checkpoint、控制器最终状态及中文结果总览；排除约390MB重复trace、过程日志、作废B3旧检查点、凭据、数据和环境。65个结果源文件与正式运行目录逐文件hash一致；验证804 episodes、训练670 episodes、evidence 670 episodes完整，所有summary API-clean，控制器为`complete/B5_validation`。交付manifest覆盖96个内容文件且校验0错误；ZIP含97个文件条目、逐条可读，大小8705158字节，SHA-256=`7348a4b6f0a75c567c77efe243e9097c392e5418c3fda5b55f4cf32a39582fd7`。未调用外部API。
- 2026-10-08：生成脱敏协作包`deliverables/client_a_local_self_evolution_v6_20261008_r1.zip`，包含v6四个入口脚本、Client A执行与SkillBank注入、必要公共依赖、冻结训练/验证manifest、空B0模板、协议测试、协作说明和逐文件SHA-256清单；不含凭据、数据集、运行轨迹、结果、日志、已生成SkillBank或联邦代码。ZIP共28个文件条目，逐条可读，SHA-256=`5f9ea0e8e00ecad974f99f262267ce621a1738f97f38ba3232d267446c8d8106`。Windows协议测试2项和B0模板校验通过；项目WSL环境内协议测试2项及核心脚本语法检查通过，未调用外部API。
- 2026-10-08：Client A首代本地自进化已在B1验证完成后暂停。B0验证72/134，B0训练65/134，Teacher生成B1共28条技能，B1验证80/134；所有任务运行均API-clean。未启动B2。
- 2026-10-07：D-034生效并取代D-033。移除最终测试清单、入口和dry-run产物；训练与验证均改为从`train` split冻结134题，六类计数为简单取放24、双物品17、台灯18、加热23、冷却21、清洗31，两套在goal-group层面完全隔离。协议测试2项通过，训练/验证dry-run均确认134题及相同分布；未调用外部API。
- 2026-10-07：D-033生效。新本地实验继续使用从`train` split冻结的六类各12题（72题）作为逐代开发验证；新增官方`valid_unseen`完整134题作为最终测试，只对最终冻结SkillBank运行一次。134题清单绑定独立baseline数据根，避免误用根目录中含194个trial的扩展`valid_unseen`。协议测试2项通过，最终测试dry-run确认134题、六类计数24/18/31/23/21/17；未调用外部API。
- 2026-10-07：完成 arXiv:2609.04217 实验口径核对。论文不是联邦实验，没有“客户端任务集”；ALFWorld 报告集是固定独立测试集134题，六类数量为18/17/23/31/24/21。训练与验证集彼此及测试集互斥，但正文未披露训练集、验证集各自的唯一任务数；搜索侧仅明确每角色120的rollout pool及各实验臂实际64--132次rollout，不能解释为每客户端120题。
- 2026-10-07：将A/B/C本地Teacher锁定为`deepseek-v4.1-flash`，新增独立`LOCAL_EVOLUTION_*`配置并保留endpoint/key向旧聚合配置的兼容回退；模型名不再继承服务器聚合配置。相关Python语法检查及4项continuation evolver测试通过，未调用外部API。
- 2026-10-07：将A/B/C新运行的共享任务执行入口默认模型从`qwen3-8b`改为`qwen3.6-flash`，覆盖本地训练、单条件/paired验证、Stage3 qualification/atomic validation与Blind Global runner；历史结果和旧规格未改写。10个Python入口语法检查通过；项目虚拟环境下continuation evolver与aggregation API测试通过。系统Python完整测试中的缺包与WSL绝对路径失败属于既有环境限制。
- 2026-10-07：确认“每客户端六类×12题训练、六类×12题独立验证”可行。每代训练为72题/客户端、216题/三端；每个SkillBank版本的固定验证为72题/客户端、216个三端conditions。该设计取消任务类型non-IID，联邦差异主要来自客户端架构、角色和本地轨迹。
- 2026-10-07：明确新协议建议规模：每客户端每代训练两类各12题，共24题；三客户端每代72题。每客户端固定验证两类各30题，共60题；每个SkillBank版本三端共180个验证conditions。完整六类train catalog的3552条可运行trial只作为冻结抽样母池。
- 2026-10-07：按用户澄清取消本地paired validation。新口径为B0空库也先验证一次，之后每代固定B(N-1)完成训练并由Teacher统一生成B(N)，冻结后在同一独立验证集上单条件评价一次；所有代际结果仅形成学习曲线，不影响后续演化。
- 2026-10-07：完成新本地自进化逻辑可行性评估。建议每代固定父库运行全部训练批次、完整轨迹落盘、分层压缩后由Teacher一次生成可审计净patch、确定性物化候选库，并在独立开发验证集上对父库/候选库做paired评价；完整train全集只作为冻结抽样母池，最终测试继续隔离。确认百炼模型ID`qwen3.6-flash`存在，正式实验宜锁定快照版本并重建新模型基线。
- 2026-10-07：完成项目目录与近期实验只读盘点。确认`stage3_federation`当日新时间主要来自运行时/缓存，不代表新正式实验；最新正式证据仍是`blind_global_patchfl_20261002_r1`的Round 2本地演化、18条非冲突UPDATE聚合、G2完整下发与G0/Local/G2同口径评价。未运行测试或正式评测。
- 2026-10-04：新增`server_validation/G0_LOCAL_G2_COMBINED_REPORT.md/json`及3份CSV，将G0=`46/42/37`（125/180）、Local=`35/44/36`（115/180）、G2=`35/39/35`（109/180）统一到同一冻结60题口径，并拆分Local−G0、G2−Local和G2−G0。
- 联合报告补充六类任务的三状态结果、三组逐题配对迁移、收敛边界和约90秒组会讲稿。核心迁移：G0→Local为23正/33负，Local→G2为28正/34负，G0→G2为24正/40负；Local仍明确为三个不同本地库之和，不作为Global收敛点。
- 2026-10-04：完成组会“聚合部分”口径核对与讲述提纲；明确 Round 1 完整 SkillBank 并集、Round 2+ cycle 末净 patch 上传、同 target 多 patch 强制 DeepSeek 合成、完整 Global snapshot 同步下发，以及 Global 连续三点评价与 Local-vs-Global 消融的区别。未修改实验实现或结果。
- 完成本地自进化代码与prompt审查，报告见`blind_global_patchfl/LOCAL_EVOLUTION_CODE_REVIEW_20261003.md`。确认更新粒度为每6题batch一次本地写库、每4个batch/cycle一次净patch上传，不是每个环境step更新或上传。
- 审查发现：逐题注入明细虽在evidence中但被实际`_trajectory()`丢弃；程序仅验证skill被注入，不验证被遵循/尝试或因果伤害；DELETE paired-validation文案与无本地gate的实现冲突；基础ADD/UPDATE prompt与五操作扩展存在残留冲突；协作者`PROMPT.md`并未被运行时代码直接读取；完整基础prompt hash未写入run provenance；若干语义/文本约束无硬校验；REPLACE有未来ID复用边界风险。
- Round 2实际runtime hash=`62dfdb…548a0`，当前源码hash=`04608d…8cdb`，差异为后来容量规则修订；历史hash对应源码仍保存在交付副本。本轮32个批内操作全部为UPDATE，因此DELETE/REPLACE和容量差异未改变现有结果。相关continuation与patch pipeline共7项离线测试全部通过。
- 第二轮本地自进化实际结果包已生成：`deliverables/blind_global_patchfl_round2_local_actual_results_20261003_r1.zip`，ZIP SHA-256=`ef09763aeb5e0fe458f16ce260299253ffb241bc469704c189690a09c36452ae`，大小6780575字节、688个文件条目；同名目录为可直接浏览副本。
- 包内覆盖72条训练episode、28个Agent级evolver记录（均保留raw_model_output）、32个实际批内操作、A/B/C=`4/6/8`条净patch，以及三个完整API-clean的60题本地候选评测（35/44/36）。687个内容文件逐项SHA-256验证通过，ZIP全条目读取通过；敏感文件名、密钥模式和`model_reasoning`扫描均为0。
- 新增G0→Local配对分析入口：净下降10题由A=-11、B=+2、C=-1构成；逐题共有23次正迁移、33次负迁移。包内只保留派生转移表，不重复G0原始轨迹，也不混入G2评测/聚合产物。
- 当前本地自进化规则包已生成：`deliverables/blind_global_patchfl_local_evolution_rules_20261003_r1.zip`，ZIP SHA-256=`dd99ee437e04dda4409fe6893c27b6df67a2c00a43b6d040425f87877039c855`，43140字节、14个ZIP条目。
- 包内13个被清单覆盖的文件逐项hash验证通过；4个关键源码/规格/测试副本与当前权威文件hash一致；敏感文件名与API Key模式扫描为0；continuation evolver语法检查及3项协议测试通过。
- 当前服务器聚合规则已更新并打包到 `deliverables/blind_global_patchfl_server_aggregation_rules_20261003_r3.zip`，ZIP SHA-256=`59f2d4957b46d98c356c3d6f2d9d668d7d76bd1206e3f8944846df6f76fa6067`，共7个文件、13893字节；r3取代r2。
- r3包含独立协议、当前源码、实验规格、4项冲突合成测试、依赖说明和SHA-256清单；6个清单条目逐项验证一致，不含凭据、轨迹或评价产物。

## 接手提示

- 已完成到哪里：Client A已完成B0--B5全部六次134题独立验证，控制器在B5验证后正常停止；B0--B5总成功数依次为72、80、86、83、82、81。
- 下一步做什么：如需继续，优先分析六类学习曲线及B2后回落原因；不要自动启动B6、Client B/C或联邦流程。
- 不要做什么：不要恢复无效DashScope B3检查点；不要启动B6、Client B/C或联邦流程；不要把验证轨迹反馈给Teacher。

## 风险与验证

- B2→B5控制器的Python语法检查、2项v6协议测试和WSL preflight均通过；后台运行本身不调用Codex，但会持续消耗Qwen/DeepSeek API额度。关闭电脑、终止WSL或网络/服务异常都会触发当前步骤失败并停止后续代数。
- B1总体较B0提高8题，但冷却类由2/21降至0/21，清洗和加热也各下降；继续B2前宜先确认这是技能内容、注入长度还是执行波动所致。验证结果只记录学习曲线，不构成候选准入或回滚依据。
- B1 Teacher角色合并初稿均超过每角色14条容量；各经两次Teacher修复仍超限后，按D-035执行确定性裁剪，Planner 15→14、Executor 18→14。该事实已写入Teacher审计记录，不能将B1描述为未经程序裁剪的纯模型输出。
- 正式服务器评价每轮共180个 Qwen3-8B任务条件，成本与时长显著；用户已明确要求开启正式实验。
- 本目录不是 Git 仓库，不能依赖 Git 回滚；旧产物必须保持原位并用哈希引用。
- 已验证 Round 1 union 数量、共享 Executor 来源保留、三端运行视图、停止状态机，以及G0/G2各180 conditions的完整性与API-clean状态；G2日志基础设施/API错误标记为0。
- 最小回归验证：`server_validation_runner.py`语法检查通过；transport patch converter 2项测试通过；项目WSL环境中的v5协议29项测试通过。Windows默认Python因未安装`openai`仅在导入阶段失败，已用项目锁定环境重跑并通过。
- D-028最小回归验证：`patch_pipeline.py`语法检查通过；4项测试通过，覆盖完全相同patch不去重且必须进入DeepSeek、合法新patch、冲突不可静默丢弃、DeepSeek返回null必须报错。
- 用户已于当前会话明确授权向配置的 DashScope-compatible Qwen 服务发送任务与 SkillBank 上下文。
- 用户纠正不应按客户端角色生成下发投影；原13/14/11子集物化与其评价已停止并归档到 `invalidated_role_projection_*`，禁止进入收敛窗口。D-020 已冻结，重新物化后 A/B/C 下载均为完整28条，文件 SHA-256 均为 `sha256:71034689f1c0044aec663e5b072cebda60efc464be020afa7bc5d004ed2b1363`。
- OriginalFL 28条分支仍停在服务器评价 A/B/C 各4/60的旧检查点；该检查点不改写、不进入新分支收敛窗口。
- 独立 `blind_global_patchfl` 分支的G0与G2服务器评价均已完成且API-clean：G0 A/B/C=`46/42/37`、合计125/180；G2 A/B/C=`35/39/35`、合计109/180。当前无残留评价进程。
- 旧selector协议G2的168个完成条件经D-026正式审计确认与新G2执行输入等价，已恢复为有效证据；仅补跑剩余12题。旧valid_unseen 134题仍只作联邦停止后的单次补充测试。

## 并行协作文档

- 状态：已完成待归档
- 负责人：Codex `/root`
- 最后更新：2026-10-02 12:55（Asia/Shanghai）
- 完成内容：新增 `originalFL/LOCAL_EVOLUTION_PROMPT_GUIDE.md`，按当前可执行源码说明本地 evolver 的四层 prompt 拼装、角色边界、动态允许集、五种操作、程序硬校验与模型锁。
- 关键核对：当前推进分支实际属于 `blind_global_patchfl`；Batch 1 三端各6题轨迹已完成，尚未产生 DeepSeek evolver 输出。文档已明确它与 OriginalFL 28条/4条注入分支的区别。
- 实现差异：文档记录了 continuation 代码未直接读取协作包 `PROMPT.md`、未向模型展示逐题 injected-ID 明细、扩展 prompt 中 paired-validation 文案已滞后，以及 provenance 未单独冻结客户端 user-prompt 源文件 hash。
- 转发包：已生成 `deliverables/originalfl_local_evolution_prompt_collaboration_20261002_r1.zip`，包含13个来源文件、包说明和SHA-256清单；ZIP SHA-256 为 `48088f45f38254275281b068ad3ed7894eaebf1aaaf7abcc2d6e542f2a7a7e20`，大小58462字节。
- 打包验证：ZIP 共15个文件；13个来源副本与原文件哈希一致；未包含 `.env`、轨迹、evidence/result、reasoning、日志、API Key 或 token 文件。
- 不要做什么：不要在当前 batch 中途修改 prompt 或运行代码；若要修正文案/实现，先在 batch 边界停止并建立新 revision。

## 单客户端代码交付

- 状态：已完成待归档
- 负责人：Codex `/root`
- 最后更新：2026-10-02 19:34（Asia/Shanghai）
- 目标：响应协作者“除 prompt 外提供当前 OriginalFL 本地自进化代码，用于客户端单独演化”的需求。
- 完成内容：生成 `deliverables/originalfl_client_local_evolution_20261002_r1.zip`；包含客户端任务执行、SkillBank 注入适配、evidence 构造、Round 1 空库 evolver、后续 batch evolver、A/B/C 角色 prompt、冻结任务 manifest、依赖和单客户端运行手册。
- 排除内容：服务器聚合/评价、运行轨迹、reasoning、结果、数据集、虚拟环境和凭据。
- 验证：使用项目 ALFWorld 虚拟环境运行3项离线测试全部通过；`training_runner --dry-run` 正确规划 Client A Batch 1 的6题命令；最终 ZIP 共33个文件、无 `__pycache__`/`.pyc`/运行日志/轨迹/evidence/result。
- 完整性：ZIP SHA-256=`573888e1b718687795de55024b87f071b5d5041e2f5cb02446bf114e16743c93`，大小149674字节；包内 `SOURCE_MANIFEST.json` 保存32个来源/说明文件的逐文件哈希。
- 下一步：协作者解压后先读 `README.md` 与 `CLIENT_ONLY_RUNBOOK.md`，安装依赖并运行离线测试，再选择空库 Round 1 或已有 repository 的 Round 2+ 模式。

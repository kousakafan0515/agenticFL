# 历史实验 API 成本估算（2026-10-18）

这是对工作区**已有运行记录**按当前官网原价做的粗估，不是阿里云或 DeepSeek 实际账单。V10/V11 导入的 v9 副本、`deliverables/`、`audit_sources/` 与上游工作区不作为新增调用；正式、试验、失败后已完成的运行均计入。未读取账户账单、免费额度或优惠抵扣。

## 方法与结果

读取 `stage1/`、Stage2各版本、`stage3_federation/`、`stage3_1_simple_aggregation/`、`stage3_2_role_agnostic_semantic_merge/`、`blind_global_patchfl/`、`originalFL/` 的本地运行 JSON。Qwen 按 `model + 完整episode内容` 去重，提取 Planner、步骤、Worker、Critic、Supervisor、控制调用的 `usage`，不重复计算嵌套的同一次调用。DeepSeek 按原始响应内容、模型和 usage 去重，并包含已留存的失败重试 attempt。没有 usage 的记录不能准确还原计费 Token。

| 模型组 | 可读取的输入 Token | 可读取的输出 Token | 按当前原价估算 |
|---|---:|---:|---:|
| Qwen `qwen3.6-flash` | 418,707,777 | 6,394,593 | 约 ¥548.49 |
| Qwen `qwen3-8b`（含 Stage1） | 277,859,033 | 3,827,009 | 约 ¥146.59 |
| DeepSeek 官方 Flash 系列 | 9,731,325 | 1,848,086 | 约 ¥17.12–34.25（全部输入按缓存未命中，按峰谷两端估计） |

以上可计算部分约 **¥712–729**。另有约 600 条旧 Qwen3-8B episode 没有可用 usage，以及少量探针、失败/超时和历史价格差异。若按同类 episode 均值外推这些缺项，再为记录不全的付费重试留出余量，**全工作区历史模型调用的量级估计为约 ¥730–800**。这不是一个可审计的实际支出范围；实际扣款可能因免费额度、缓存、地域、历史调价和其他未入库调用而不同。

价格依据：[qwen3.6-flash 北京原价](https://help.aliyun.com/zh/model-studio/qwen3-6-flash)输入 ¥1.2、输出 ¥7.2／百万 tokens；[Qwen3-8B 官方模型价格](https://help.aliyun.com/zh/model-studio/model-pricing)北京非思考输入约 ¥0.5、输出 ¥2／百万 tokens；[DeepSeek 官方价格](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)Flash 缓存未命中输入空闲/高峰 ¥1/2、输出 ¥4/8／百万 tokens。这里把当前原价应用于历史 usage，仅用于预算判断。硬件、电费、Codex 订阅和本地 ALFWorld 数据处理不在估算内。

预算参考：导入 V11 的三端 B0 验证、B0 训练、B1 验证九个冻结阶段，Qwen 用量按同一方法约 ¥59.71，平均每个 134 题阶段约 ¥6.63。单个客户端的 2/4/8 题付费 pilot 通常远小于完整134题运行，但准确开销仍取决于任务轨迹与重试；离线计划和单元测试均为零模型调用。

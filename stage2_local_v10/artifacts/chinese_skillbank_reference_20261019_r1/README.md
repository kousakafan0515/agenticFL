# V10 SkillBank 中文阅读副本

本目录只用于人工阅读，不参与 Planner、Executor、Teacher、服务器聚合或验证。原始 SkillBank、英文对照版、实验结果和控制器均保持原样。

已锁定与英文对照版相同的 30 份非空来源：A/B/C 的导入 B1、本地 B2–B6、Global1–3 服务器库及其三端下发副本。B0 为空库。六个 Skill 正文字段共 1,069 段不同文本，其中 295 段原本含中文，774 段纯英文需要翻译。原文路径、SHA-256 和翻译批次记录在 `source_manifest.json`，待译条目在 `translation_map.json`。

中文版只转换 `title`、`principle`、`when_to_apply`、`description`、`why_it_happens`、`how_to_avoid` 六个正文键。ID、任务类别键、来源、元数据和 JSON 结构必须原样保留；Markdown 阅读视图会使用中文角色、类别和字段标题。环境动作命令及对象名可保留英文以便与原文核对。翻译完成后，每份来源会有独立的中文 Markdown 和 `.reference.zh.json`，索引为 `INDEX.md`。

用户于 2026-10-19 明确授权发送这 774 段英文正文后，已使用配置的 DeepSeek 官方接口完成 39 批翻译。39 次响应均保留在 `api_attempts/`，原始响应及用量可审计；去重后的 774 段译文在 `translation_map.json`。全部 30 份中文 Markdown 与 `.reference.zh.json` 已生成，入口为 [INDEX.md](INDEX.md)，逐文件原文/译本哈希在 `output_manifest.json`。

全部 30 份来源哈希、JSON 结构、Skill ID、任务类别键、来源和非正文字段核验通过；只有 5,493 处原本纯英文的 Skill 正文字段被翻译，原本含中文的正文保持原样。27 份 Markdown 中的两个英文 Skill 类型展示标签已单独更正为中文，前后哈希见 `view_label_audit.json`；对应 JSON 未改。中文对照版及原英文对照版各自的完整校验通过，3 项中文版离线测试通过。原始正式实验文件未修改。译文仅供阅读，不能当作运行时 SkillBank。

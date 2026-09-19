# 离线查询上下文回归输入

`query-context-inputs.json` 是 2026-09-10 诊断的 13 条 development 输入白名单的逐字节副本，供 `test_query_context.py` 在干净检出和 CI 中使用。原文件位于被 Git 忽略的 `docs/verification/quality-runs/development-live-diagnostic-20260910/planned-inputs.json`；该历史运行目录不是测试依赖。

原文件与本副本的 SHA-256 均为 `f864057bd7d43a67d5278b494c78992e808e42176cb49c6637215d378dfc223a`。副本只包含 `id`、`input.subject`、`input.description`，没有模型响应、标签、gold、holdout、凭据或真实客户记录。

11 条输入来自 Doc2Dial v1.0.1 的公开文档人工构建对话，另外 2 条是 GitHub CLI 公开问题 #695、#1466 的问题摘录。来源和原先的上下文投影规则见[质量输入审计](../../../../docs/verification/quality-input-audit-2026-09-10/README.md)及其[协议](../../../../docs/verification/quality-input-audit-2026-09-10/PROTOCOL.md)。这里保留相同的机构、前序回合和末尾请求，以继续覆盖当时“共同的前 180 字符导致所有 query 相同”的失败。

测试只经过本地 mock HTTP 工作流验证输入完整传播，不调用模型或 Embedding，不评价历史政策的时效性、回复质量或真实客服效果。原始运行证据保持原样。

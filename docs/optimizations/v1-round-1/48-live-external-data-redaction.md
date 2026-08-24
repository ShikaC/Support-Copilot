# 优化 48：限制 live 外发敏感数据

## 业务问题

live 模式原来会把工单标题、正文、检索查询和知识片段原文直接交给外部 Embedding 与聊天模型服务。即使测试样例不是实际客户数据，这条链路也缺少可验证的数据最小化边界；同时 Responses 请求没有显式关闭服务端结果存储。

## 改进方案

新增确定性外发脱敏器，在两个外部边界执行：

```text
知识正文 + 检索查询
-> 邮箱、手机号、18 位身份证号、支付卡号脱敏
-> Embedding API

工单 + 已采用证据
-> 相同规则再次脱敏
-> Responses API（store=false）
```

邮箱、手机号和身份证号使用边界明确的格式识别；13 至 19 位支付卡候选必须通过 Luhn 校验才会替换，避免把普通长订单号直接当成支付卡。替换值只保留类型标记，不保留原值的局部字符。mock 模式仍在本地使用原始模拟数据，不经过外部请求边界。

live 向量职责同时从 `KnowledgeRetriever` 拆到独立适配器。检索器只决定 mock/live 路由；适配器负责脱敏后的 Embedding 请求、内存索引和向量结果转换。

根据 [OpenAI 官方数据控制说明](https://developers.openai.com/api/docs/guides/your-data#default-usage-policies-by-endpoint)，Responses API 省略 `store` 时可能保存应用状态，因此本项目显式发送 `store=false`。这不会自动获得 Zero Data Retention，也不能替代组织级保留策略和合规评估。

## 当前验证

- 红灯测试先捕获到 Embedding 与 Responses 外发参数中的邮箱、手机号、身份证号和支付卡号原文，以及缺失的 `store=false`；实现后两条测试转绿。
- 支付卡专项断言证明有效 Luhn 卡号会被替换，不通过 Luhn 校验的长订单号保持不变。
- 本地 HTTP 验收实际启动 FastAPI 和 OpenAI 兼容服务：成功场景返回 `mode=live`、`status=SUCCEEDED` 和 `VECTOR`；Responses 受控返回 `503` 时进入 `mode=fallback`、`status=FALLBACK` 和人工升级。
- 两个 HTTP 场景捕获的 Embedding 与 Responses 请求均不包含四个测试原值，Responses 请求包含 `store=false`。
- Python 全量测试：63 条通过；固定 mock 评估：18 条通过，失败案例为 0；依赖锁检查通过。
- Python 严格规则检查覆盖 7 个修改或新增文件，没有违规；`knowledge.py` 从 224 行降到 137 行，新的 `live_vector_index.py` 为 95 行。

## 能力边界

本轮验证使用本地 OpenAI 兼容 HTTP 服务，不是正式 OpenAI 或其他付费模型 API 的成功记录，因此真实 RAG 仍未达到层级 3。

当前规则是确定性格式脱敏，不是完整 DLP 或命名实体识别：主要覆盖常见邮箱、中国大陆手机号、18 位身份证号和通过 Luhn 校验的支付卡号，不能保证识别地址、姓名、护照、15 位旧身份证或所有国际号码。脱敏可能降低依赖精确标识符的检索质量，正式 live 验收仍必须使用非敏感测试数据并核对命中结果。

原始工单仍会进入 Java 业务保存路径；本轮只限制 Python 的外部 AI 请求，没有完成数据库字段加密、认证授权、数据保留审批或供应商合规审查。兼容 Base URL 的数据处理和 `store` 语义必须以对应供应商文档为准。

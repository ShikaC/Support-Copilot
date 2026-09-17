# 检索上下文截断修复

**已实现并完成离线验证：查询保留完整的已校验标题和正文。** 13条冻结真实诊断输入经过离线HTTP工作流，从修复前1条相同query变成13条不同query，完整机构/先前对话/当前请求得到保留。未进行新的模型或Embedding调用，没有产生修正后的检索命中、回答质量或延迟成绩。

## 问题、改动与数据流

旧代码`AnalysisWorkflow._build_query`只使用正文前180字符。上轮实际输入都以相同评测说明开头，13条查询与候选列表完全一致；原始记录见[真实诊断](../quality-runs/development-live-diagnostic-20260910/DIAGNOSIS.md)。本轮用户明确要求修复。

唯一生产改动位于`services/support-copilot-ai/app/workflow.py:258`，完整本轮diff见[change.patch](change.patch)。没有将历史大量Git未提交差异冒充本轮修改。

```diff
- return f"{ticket.subject} {ticket.description[:180]}".strip()
+ return f"{ticket.subject} {ticket.description}".strip()
```

Java与Python已有标题240、正文4000长度校验。保留完整输入后，Python查询最多4241个code point，且超过4000的正文仍在HTTP边界拒绝。没有必要为此增加付费摘要、识别`user:`的特例或另一套对话解析器；完整上下文也保留最后一句“Yes”所依赖的先前业务对象。既有请求只含工单输入，不加入gold、未来agent回复或AI标签。

数据流：HTTP校验 → `_build_query`完整标题/正文 → `KnowledgeRetriever.search` → live路径的`LiveVectorIndex.search` → `redact_sensitive_text(query)` → 原Embedding provider。权限过滤、脱敏、artifact身份、模型生成与fallback语义均未改。查询增加的内容属于原工单已接收的正文；脱敏规则仍是现有有限类别规则，不等于能识别所有敏感数据。

## 验证证据

| 验证 | 结果与范围 |
| --- | --- |
| 修改前新增回归 | 17失败/2通过，失败明确对应上下文截断；见red.log |
| 修改后新增回归 | 19通过；见green.log |
| AI模块完整测试 | 324通过；见python-suite.log |
| 新增测试类型检查 | 0错误/0警告；见types-tests.log |
| workflow与新增测试联合类型检查 | 0错误/1个既有warning；修复前同一warning，见types.log/types-baseline.log；不称严格零警告通过 |
| Ruff | 通过；见ruff-final.log |
| 本轮文件边界 | 2313个既有文件中仅workflow及4份权威文档改变；新verify逐项核对 |
| 模型/Embedding新增调用 | 0 / 0 |

新增`tests/test_query_context.py`用实际FastAPI `/analyze` 路由和生产workflow验证查询传播，13条案例直接读取冻结`planned-inputs.json`白名单。测试使用确定性离线路径隔离外部依赖，产生的回复/检索命中不统计为真实业务结果。另覆盖相同前缀不同业务问题、最大长度ASCII/中文/emoji输入的末尾请求保留、4001字符拒绝、短工单兼容。

[offline-query-comparison.json](offline-query-comparison.json)保存实际离线HTTP响应query，与原真实诊断query逐题对照；明确标记OFFLINE_HTTP_QUERY_REGRESSION_ONLY、外部调用0、质量分数null。它不是新模型评测报告。现有完整测试中的`test_live_embedding_requests_redact_sensitive_data`通过，检验live向量分支外发前的邮箱/电话/身份证/银行卡脱敏边界；该测试也不调用真实供应商。

复核命令（项目根目录）：

```sh
services/support-copilot-ai/.venv/bin/python -m pytest services/support-copilot-ai/tests/test_query_context.py -q
uvx ruff check services/support-copilot-ai/app/workflow.py services/support-copilot-ai/tests/test_query_context.py
node docs/verification/query-context-fix-2026-09-10/verify.mjs
git diff --check
```

完整测试必须在`services/support-copilot-ai`目录运行`.venv/bin/python -m pytest tests -q`。初次从仓库根目录运行完整测试为322通过/2失败，两个CLI测试因工作目录无法导入`scripts.*`；保留python-suite-root-failure.log。正确服务目录运行324通过，没有修改测试来掩盖失败。Ruff初次仅新文件import排序失败，修正后通过。workflow.py:160的穷尽match警告在保存的修复前源码上也存在，未扩大范围修改该历史逻辑。

本轮代码审阅：生产差异仅去掉截断并增加长度边界说明；输入仍由已校验TicketInput提供，没有新增异常吞掉、网络调用或外部依赖。长输入能到达检索、超长输入被拒绝，两条路径已覆盖。此为AI检查与自动测试，不是用户diff批准或人工回答审核。

## 证据保护、限制与后续

基础HEAD `4df3bf44907c34318132496929bad4a3974ad88b`，master、dirty、未提交/推送/部署；原工作台未重启。本轮2313文件基线、代码前件、独立patch、最终源码与文档摘要均保存。原13题真实run、旧run-1、输入audit、旧验证器和一次性claim未改。原验证器绑定修复前工作树，运行会因本轮授权源码/文档改变失败，日志old-gate-after-change.log保留；新验证器用明确的5文件修改边界核对所有旧文件，不修改旧门禁或冻结数据。

运行中的服务不会因磁盘源码修改自动被本轮替换；当前交付是已验证源码修复，不是已部署修复。后续需独立部署/实验配置并确认加载该源码。更长Embedding输入可能增加token、延迟，也可能受统一说明或历史回合影响相关性；本轮只证明内容未截断，不证明最佳检索策略或模型上下文容量。真实development复测应另行预注册方案、源码、预算与新run，不能删除claim或覆盖旧失败；holdout仍未使用。

可写简历：利用固定真实诊断发现检索查询截断，通过先失败后通过的HTTP回归修复上下文丢失，并验证长度拒绝和既有失败/脱敏边界。不能写召回率/回答准确率提高、延迟降低、解决率或节省工时；这些尚未测得。

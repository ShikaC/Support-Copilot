# 优化 49：建立跨服务 live 超时预算

## 业务问题

原默认配置中，Java 最多等待 Python 15 秒，而 Python 的一次正式 API 请求可等待 20 秒并自动重试 2 次。首次 live 分析还可能依次执行知识库 Embedding、查询 Embedding 和结构化生成。Java 因此可能先返回并保存 fallback，而 Python 仍继续等待或发起后续外部调用，造成结果失效、资源占用和费用边界不清。

## 改进方案

当前默认截止时间按外层晚于内层排列：

```text
正式 API 单次请求：20 秒，最多重试 1 次
    < Python 整体分析：90 秒
    < Java 等待 Python：105 秒
    < live 验收客户端：120 秒
```

`AnalysisRunner` 统一包裹 FastAPI 和离线评估入口。整体预算耗尽时，它取消当前异步工作并抛出带 `traceId` 的类型化错误；Python HTTP 边界返回 `504 AI_PROCESSING_TIMEOUT`，Java 继续使用既有业务 fallback 并保存可人工复核结果。

live 向量索引改用 LangChain 的异步建库和异步查询接口，使取消信号能够到达 Embedding 客户端，不再把正式 API 调用包在线程工作中。外部错误同时细分为 Embedding、结构化生成、连接超时、响应超时、普通 API 错误和非法结构化响应，现有 workflow 日志通过具名错误类型区分故障阶段。

`check-live-rag.sh --preflight` 会在不调用外部 API 的情况下验证预算：Python 总预算必须覆盖首次 live 的三个外部阶段并留有余量，Java 和验收客户端必须分别比下层多 10 秒。OpenAI 官方模型指导也要求显式定义重试和停止边界，而不是无限等待或重试：[Model optimization](https://developers.openai.com/api/docs/guides/latest-model)。

## 当前验证

- 红灯阶段因缺少 `AnalysisRunner` 和 `timeout_budget` 模块而出现 3 个测试收集错误；实现后相关 29 条测试通过。
- Python 全量测试：73 条通过。
- Java 全量测试：16 条通过；新增真实本地慢 HTTP 服务测试，证明 `AiServiceClient` 会在配置预算内停止等待。
- 固定 mock 评估：18 条通过，失败案例为 0。
- Python 依赖锁检查、14 个修改文件的严格规则检查、shell 语法和 `git diff --check` 均通过。
- live 预检接受默认预算；把 Java 预算压缩到 80 秒时会在发出外部请求前失败。

本地 HTTP 故障演练使用无付费凭据的兼容端点，并把预算临时压缩为 Python 1 秒、Java 3 秒：

```text
Embedding 端点故意等待 2 秒
-> Python 约 1.01 秒返回 504，保留 traceId=fault-timeout-python-async
-> Java 调用约 1.12 秒返回 mode=fallback / status=FALLBACK
-> Java 分析历史保存 traceId=fault-timeout-java
-> decision.escalationRequired=true
```

Python 日志记录 `analysis.processing_timeout`，Java 日志用相同 `traceId` 记录 504 与 fallback。演练完成后三个临时服务均已停止，端口没有残留监听。

## 能力边界

本轮使用本地兼容服务，不是正式 OpenAI 或其他付费 API 成功记录；真实 RAG 仍处于层级 2，尚未达到层级 3。

总截止时间能停止本地等待并阻止后续 Embedding 或生成阶段，但不能撤回供应商已经接收的请求。故障演练中的兼容端点在 Python 返回 504 后仍完成了服务端处理，因此不能宣称取消一定终止供应商计算或费用。正式验收仍应设置账户限额、监控用量，并使用非敏感小样本。

Java 当前把 Python 504 与其他 `RuntimeException` 一起转换为 fallback；业务连续性和持久化语义已经验证，但 Java 分析记录还没有独立的结构化 `fallbackReason=processing_timeout` 字段。向量索引仍是进程内存实现，首次请求的三阶段预算也会随知识规模和供应商延迟变化，正式调用前必须重新执行 preflight。

## 面试关键位置

- `services/support-copilot-ai/app/analysis_runner.py`：整体分析截止时间和可取消边界。
- `services/support-copilot-ai/app/live_vector_index.py`：异步 Embedding 建库与查询。
- `services/support-copilot-ai/app/timeout_budget.py`：Python、Java 和验收客户端的预算顺序门禁。

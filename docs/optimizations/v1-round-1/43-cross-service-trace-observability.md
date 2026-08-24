# 优化 43：贯通跨服务 traceId 和错误日志

## 业务问题

第 42 轮已经证明分析请求能穿过 React、Java 和 Python，但排查失败时仍需要分别查看响应和各服务日志。Java 日志格式预留了 MDC 的 `traceId`，实际请求却没有统一写入；Python 日志也没有记录请求体中的追踪号。这样无法只凭一个编号还原一次分析经过了哪些服务、是否进入 fallback。

## 关键流程

```text
浏览器可选 X-Trace-Id
        ↓
Java TraceIdFilter：校验或生成追踪号
        ↓
Java MDC + 响应头 X-Trace-Id
        ↓
AiServiceClient 将同一编号放入 Python 请求体
        ↓
Python 记录 analysis.completed / analysis.external_failure / analysis.fallback
        ↓
Java 保存并返回同一 traceId；失败时 fallback 不重新生成编号
```

新增 `TraceId` 和 `TraceIdFilter`，只接受不含换行和特殊控制字符的短追踪号，避免外部请求头直接污染日志。`ApiExceptionHandler` 也从过滤器上下文读取错误响应的追踪号；没有过滤器的单元测试仍可从请求头读取编号。

Java 的 `AnalysisService` 在一次分析开始时确定追踪号，把它同时交给 `AiServiceClient` 和 fallback 工厂。Python 工作流在成功、外部可恢复失败和 fallback 三个决策点记录稳定事件名、追踪号、模式、状态和命中数量，不记录工单描述或密钥。

## 验证结果

- Python API：`./.venv/bin/pytest tests/test_api.py -q`，7 条通过；新增测试确认完成日志包含请求 `traceId`。
- Java：`./gradlew test --no-daemon --tests com.cyagent.supportcopilot.common.TraceIdFilterTests --tests com.cyagent.supportcopilot.ticket.TicketAnalysisConflictApiTests`，测试通过。
- 成功 HTTP 流程使用 `day4-success-trace`，检查脚本确认响应体中的 `traceId` 与预期一致；额外的 `curl -i` 观察到响应头 `x-trace-id: day4-header-trace`，响应体同样为 `day4-header-trace`。
- Python 成功日志记录：`analysis.completed trace_id=day4-header-trace mode=mock status=SUCCEEDED hit_count=3`。
- Python 停止后的 fallback 流程使用 `day4-fallback-trace`，返回 `mode=fallback`、`status=FALLBACK`，Java 日志显示 `[day4-fallback-trace]`，响应体和响应头保持同一编号。

## 能力边界

本轮证明了本地 HTTP 请求的跨服务关联和 fallback 故障定位，不等于接入了 OpenTelemetry、Jaeger、集中式日志或分布式 trace 后端。日志仍输出到本地进程标准输出，重启后不会形成持久化追踪记录；真实 live RAG、正式模型和 Embedding API 验证仍未完成。

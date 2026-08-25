# 分析在途请求合并契约

## 目的

客服重复点击、浏览器重复调用或多个客户端同时分析同一份工单内容时，如果每个请求都独立调用模型，会重复消耗时间和 API 预算，并在分析历史中留下无法解释的重复记录。

当前 V1.5 使用 single-flight 语义：只合并仍在执行中的相同分析，不永久缓存已完成结果。

## Java 业务键

```text
ticketId + sourceTicketVersion + analysisPolicyVersion
```

- `ticketId`：正在分析的工单。
- `sourceTicketVersion`：分析读取的工单版本；内容发生变化后必须使用新键。
- `analysisPolicyVersion`：本次分类、检索和生成策略版本，当前为 `ticket-analysis-v1`。

Python 返回的 `promptVersion` 必须与 Java 请求的策略版本一致。版本漂移会被转成 `invalid_ai_response`，不能保存到错误的业务键下。

## 执行语义

```text
首个请求取得业务键所有权
  -> 调用 Python
  -> 保存一次 AnalysisRun
  -> 完成共享结果

相同键的并发请求
  -> 不再次调用 Python
  -> 等待首个执行
  -> 返回相同 analysisId 和执行 traceId
```

浏览器 API 层也会按工单 ID 合并同一页面中尚未完成的请求，减少重复 HTTP 调用。Java 仍是权威保护边界，因为请求也可能来自其他浏览器或脚本。

执行成功、fallback 或抛出程序错误后，Java 和浏览器都会立即释放在途键。之后的人工重试会真正执行，不会永久复用旧结果。

## traceId 规则

- 首个请求的 `traceId` 是共享分析执行的 `traceId`，会发送给 Python 并随 `AnalysisRun` 保存。
- 加入请求仍有自己的 HTTP `X-Trace-Id` 和 Java MDC 日志上下文。
- 加入请求返回的分析体携带首个执行的 `traceId`，因为两者共享同一个分析运行。
- Java 用 `analysis.single_flight_join` 日志把加入请求的日志上下文与 `execution_trace_id` 关联。

## 当前边界

- 协调状态只存在于单个 Java 进程内，不是分布式幂等。
- 当前没有持久化客户端 `requestId`，服务重启后不能重放同一请求结果。
- 多 Java 实例部署需要数据库幂等记录、共享锁或 Redis 等跨实例协调；本轮没有引入这些 V2 组件。
- 完成后的显式重试会产生新的分析记录，这是有意行为，不是永久去重。
- 该能力减少重复模型调用，但不能替代正式 API 的费用限额、供应商侧取消或真实 live 验证。

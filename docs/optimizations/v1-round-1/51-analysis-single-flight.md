# 优化 51：合并重复的在途分析请求

## 业务问题

同一工单被快速重复点击、浏览器重复调用或多个客户端同时请求时，Java 原来会为每个请求分别调用 Python，并各自写入分析历史。对于正式模型，这会重复消耗 API 预算；对于客服，也会出现多个内容相同但无法解释的分析记录。

简单永久缓存结果也不正确：如果第一次因 Python 不可用进入 fallback，客服恢复服务后必须能够重新分析。

## 改进方案

浏览器 API 层按工单 ID 合并尚未完成的 Promise。Java 增加 `AnalysisSingleFlightCoordinator`，使用以下业务键协调单实例内的并发请求：

```text
ticketId + sourceTicketVersion + analysisPolicyVersion
```

首个请求负责调用 Python 和持久化，加入者等待并返回同一个分析结果。键在成功、fallback 或异常结束后立即删除，因此后续显式重试仍会执行。

`AnalysisPolicy.VERSION` 成为 Java 请求和并发键共享的唯一策略版本来源。`AiServiceClient` 会拒绝 Python 返回的不同 `promptVersion`，避免结果被错误归入另一个策略版本。

完整语义见 [`docs/contracts/analysis-single-flight-contract.md`](../../contracts/analysis-single-flight-contract.md)。

## 验证结果

- 红灯阶段：Java 因缺少 `AnalysisSingleFlightCoordinator` 无法编译；TypeScript 的第二个并发调用重复读取 HTTP 响应并失败。
- Java 全量测试：26 条通过。覆盖相同键共享执行、不同工单并行、加入者共享程序错误、完成或失败后释放、Service 只调用一次 AI 和持久化一次，以及策略版本漂移拒绝。
- React：lint、7 条 Vitest 和生产构建通过。两个同时发出的同工单调用只执行一次 `fetch`，完成或失败后允许再次分析，不同工单互不阻塞。
- Python 全量测试：80 条通过。
- 固定 mock 评估：18/18 通过，无失败案例。
- TypeScript 严格规则检查和 `git diff --check` 通过。
- 页面视觉回归：独立只读审查通过当前构建的桌面 `1440x900` 与移动 `390x844` 截图，未发现布局、溢出或中文断行问题。

真实 HTTP 并发演练使用实际 Python mock 服务，并在 Java 与 Python 之间加入受控 1 秒延迟：

```text
同时向 Java 发送 2 个 POST /api/tickets/ticket-10042/analyze
  -> 慢代理只收到 1 次 /analyze
  -> Python 只完成 1 次分析
  -> 两个 Java 响应返回同一 analysisId
  -> Java 分析历史只从 2 增加到 3
  -> 加入日志关联 request traceId 与 execution traceId
```

观察结果：`requestCount=2`、`aiCallCount=1`、`mode=mock`、`status=SUCCEEDED`，共享执行的 `traceId=concurrent-success-a`。

## 能力边界

这是单个 Java 实例内的在途请求合并，不是持久化或分布式幂等。多实例部署仍需要共享协调和持久化请求记录。执行结束后的人工重试会产生新分析，这是为恢复 transient fallback 保留的业务能力。

本轮没有正式聊天模型或 Embedding API 凭据，也没有发起付费调用。真实 RAG 仍处于层级 2，正式 `mode=live` 成功记录仍未完成。

## 面试关键位置

- `services/support-copilot-api/src/main/java/com/cyagent/supportcopilot/analysis/AnalysisSingleFlightCoordinator.java`：相同业务键共享 Future，并在结束后释放。
- `services/support-copilot-api/src/main/java/com/cyagent/supportcopilot/analysis/AnalysisService.java`：用工单版本和策略版本包裹完整 AI 调用与持久化。
- `apps/support-copilot-web/src/services/api.ts`：浏览器内合并同一工单的在途 HTTP 请求。

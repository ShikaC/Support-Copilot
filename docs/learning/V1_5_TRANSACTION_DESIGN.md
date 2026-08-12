# V1.5 事务边界与版本冲突设计

> 学习状态：设计讲解和第一轮实现已于 2026-07-31 完成。逐项实现记录见 `docs/optimizations/v1-round-1/`。

## 1. 这次改进解决什么问题

当前 `AnalysisService` 先读取工单，再等待 Python 返回分析结果，最后保存 `AnalysisRun` 并更新 `Ticket`。

这里有两个风险：

- `saveRun()` 由同一个 Service 内部调用，方法上的 `@Transactional` 可能绕过 Spring 代理。
- Python 分析期间工单可能被其他客服修改，旧分析结果不能覆盖新版本工单。

目标不是把整个 `analyze()` 放进长事务，而是让外部 AI 调用和短数据库事务分开。

## 2. 目标流程

```text
根据 ticketId 读取工单和 version
        ↓
在没有数据库事务的情况下调用 Python
        ↓
得到 live、mock 或 fallback 分析结果
        ↓
调用独立的持久化 Service
        ↓
开启短事务
        ↓
比较 expectedVersion 和数据库当前 version
        ↓
版本一致：保存 AnalysisRun 并更新 Ticket
版本冲突：抛出异常并回滚，不保存旧分析
```

## 3. 建议的职责边界

### AnalysisService

- 根据 `ticketId` 查询工单。
- 在调用 Python 前记录 `expectedVersion`。
- 只捕获明确的 AI 网络、超时和无效响应异常。
- AI 故障时生成 fallback。
- 把 `ticketId`、`expectedVersion` 和分析结果交给持久化 Service。

### AnalysisPersistenceService

- 通过 Spring 注入，由公开方法提供 `@Transactional` 边界。
- 在短事务中重新查询工单并检查版本。
- 创建并保存 `AnalysisRun`。
- 更新并保存 `Ticket`。
- 发现版本冲突时抛出明确的业务异常。

### ApiExceptionHandler

- 捕获版本冲突异常。
- 返回 HTTP `409 Conflict`。
- 返回结构化错误代码、消息、`traceId` 和必要的冲突信息。

## 4. sourceTicketVersion

`AnalysisRun` 应记录 `sourceTicketVersion`，表示这份分析基于工单的哪个版本生成。

它与其他标识的区别是：

```text
AnalysisRun.id       → 哪一条分析记录
ticketId             → 分析的是哪张工单
sourceTicketVersion  → 分析使用的是工单哪个版本
traceId              → 请求经过了哪些服务和日志
```

版本号不包含旧工单正文。完整输入快照、工单历史、加密和数据保留策略属于后续独立任务，不能未经隐私设计就永久复制敏感正文。

## 5. 冲突不等于 fallback

```text
OpenAI 超时或网络失败
→ AI 能力故障
→ 可以生成明确标识的 fallback
```

```text
expectedVersion 与当前 version 不一致
→ 业务数据已经变化
→ 回滚并返回 409
→ 由客服确认是否基于最新工单重新分析
```

Java 不应该在版本冲突后自动无限重试 AI。

## 6. 验收测试

### 持久化集成测试

测试应通过 Spring 注入真实 Service，并使用测试数据库验证：

- 正常情况同时保存 `AnalysisRun` 和更新 `Ticket`。
- 版本冲突时抛出明确异常。
- 冲突后没有新增 `AnalysisRun`。
- 冲突后 `Ticket` 保持数据库中的最新版本和内容。

测试方法不应依赖自己开启的外层事务来伪造 Service 的事务效果。

### Web/API 测试

验证版本冲突异常会被转换为：

- HTTP `409 Conflict`。
- 稳定的错误代码，例如 `VERSION_CONFLICT`。
- 可供页面展示和日志追踪的结构化错误响应。

## 7. 本次最小范围

本次只设计：

- 短事务持久化 Service。
- `expectedVersion` 冲突检查。
- `sourceTicketVersion`。
- 结构化 `409`。
- 事务和 Web 层测试。

暂不实现完整工单历史、输入快照、加密平台、权限系统和自动重试策略。

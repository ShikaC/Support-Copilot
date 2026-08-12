# 优化 04：返回结构化 409 Conflict

## V1 的问题

V1 没有专门表示工单版本冲突的异常和 HTTP 响应。React 无法稳定区分：

- 请求参数错误。
- 工单不存在。
- AI 服务故障并已 fallback。
- 工单在分析期间被其他操作更新。

## 本轮修改

`ApiExceptionHandler` 捕获 `TicketVersionConflictException`，返回 HTTP `409 Conflict` 和稳定的 JSON：

```json
{
  "code": "VERSION_CONFLICT",
  "message": "工单已被其他操作更新，本次分析基于旧版本，未保存。",
  "traceId": "trace-test",
  "timestamp": "2026-07-31T08:00:00Z",
  "details": {
    "ticketId": "ticket-10042",
    "expectedVersion": 3,
    "currentVersion": 4
  }
}
```

极短并发发生在数据库执行 SQL 的瞬间时，系统可能无法可靠取得对方提交后的版本号；这种情况下仍返回 `409`，但省略 `currentVersion`。

## 相对 V1 的改进

React 可以根据 `code` 精确展示“工单已更新，请刷新后确认是否重新分析”，而不是把冲突误报成普通系统错误或 AI fallback。

## 对应代码

- `services/support-copilot-api/src/main/java/com/cyagent/supportcopilot/common/ApiExceptionHandler.java`
- `services/support-copilot-api/src/main/java/com/cyagent/supportcopilot/analysis/TicketVersionConflictException.java`

## 验证

MockMvc 测试验证状态码、错误代码、`traceId`、工单 ID 和两个版本号都能按契约返回。

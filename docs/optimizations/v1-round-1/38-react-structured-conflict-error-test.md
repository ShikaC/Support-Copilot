# 优化 38：保留 Java 返回的结构化 409 错误

## 原来的问题

第 37 轮只验证了分析请求的成功路径：

```text
ticket-10042
-> POST /api/tickets/ticket-10042/analyze
```

它不能证明 Java 返回版本冲突时，React 会完整保留错误信息。即使 `code` 或 `traceId` 被解析器意外丢弃，原来的测试仍然会通过。

## 本次如何修改

在现有 `api.test.ts` 中增加结构化错误测试，模拟 Java 返回：

```json
{
  "code": "TICKET_VERSION_CONFLICT",
  "message": "工单版本已变化",
  "traceId": "trace-409",
  "details": {
    "expectedVersion": 3,
    "currentVersion": 4
  }
}
```

HTTP 状态为 `409`，所以 `response.ok` 是 `false`。React 的 API 边界必须抛出一个包含以下字段的 `ApiError`：

```text
name    = ApiError
status  = 409
code    = TICKET_VERSION_CONFLICT
message = 工单版本已变化
traceId = trace-409
details = expectedVersion 3、currentVersion 4
```

## 为什么这些字段必须保留

- `status` 说明这是 HTTP 冲突，而不是连接失败。
- `code` 让 React 能稳定识别工单版本冲突。
- `message` 提供用户可读的错误说明。
- `traceId` 让开发者能够关联同一次请求的日志。
- `details` 说明分析基于版本 3，但数据库当前已经是版本 4。

如果这些信息只剩下一句普通错误文本，页面难以给出准确提示，开发者也更难追踪问题。

## 测试边界

测试仍然使用模拟 `fetch`：

```text
模拟 Java 的 409 响应
-> 执行 analyzeTicket
-> 检查 React 创建的 ApiError
```

它验证的是 React 对错误响应的处理，不会真正启动 Java，也不能证明 Java 一定会生成这份响应。Java 的结构化 `409` 已由 Java API 测试独立保护，未来还需要跨服务测试证明两端能实际连通。

## 相对 V1 的改进

优化前：

```text
React 错误解析没有前端测试
业务错误代码或 traceId 丢失可能不被发现
成功路径测试无法保护 409 分支
```

优化后：

```text
成功请求和版本冲突分别受到测试保护
ApiError 的关键结构化字段进入回归检查
React CI 每次都会执行这两条测试
```

## 自动化验证

本轮完成以下验证：

- 正确代码：1 个测试文件中的 2 条测试全部通过。
- 故障注入：临时让解析器丢弃 `code` 后，新测试明确报告预期 `TICKET_VERSION_CONFLICT`、实际 `HTTP_409`，并返回退出码 1。
- 恢复正确解析器后，`npm run lint` 通过。
- `npm run test`：2 条通过。
- `npm run build`：TypeScript 和 Vite 生产构建通过。
- `actionlint v1.7.12`：React 工作流检查通过。
- TypeScript 安全规则检查：通过。
- 测试文件有效代码 46 行，仍只负责 React API 边界行为。
- `git diff --check`：通过。

构建仍有现存主 JavaScript 包超过 500 kB 的提示，本轮没有修改页面或打包结构。

## 涉及文件

- `apps/support-copilot-web/src/services/api.test.ts`
- `docs/optimizations/ROADMAP.md`
- `docs/optimizations/v1-round-1/README.md`
- `docs/optimizations/v1-round-1/37-react-analyze-ticket-unit-test.md`
- `docs/optimizations/v1-round-1/38-react-structured-conflict-error-test.md`

## 当前边界

- 当前测试覆盖分析请求构造和结构化 `409` 解析，尚未覆盖空错误体、普通 `404/500` 或连接失败。
- 模拟 `fetch` 不会验证 React 与真实 Java 服务之间的连接。
- 页面是否正确显示版本冲突提示仍需要组件测试或浏览器端到端测试。
- React CI 的新增测试尚未推送，GitHub 托管环境还没有实际运行记录。

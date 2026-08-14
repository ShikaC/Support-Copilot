# 优化 39：为非 JSON 500 响应生成默认错误

## 原来的问题

第 38 轮证明了 React 可以保留结构化 `409` 错误，但后端或网关发生异常时，不一定能返回 JSON：

```text
HTTP 500
Content-Type: text/plain
响应体: upstream unavailable
```

这时 `response.json()` 会失败。如果默认错误规则没有测试保护，React 可能丢失 HTTP 状态，或者生成不稳定的错误代码。

## 本次如何修改

在 `api.test.ts` 中增加第三条测试，模拟纯文本 `500` 响应：

```text
status = 500
body = upstream unavailable
```

JSON 解析失败后，React 必须生成：

```text
name    = ApiError
status  = 500
code    = HTTP_500
message = API request failed: 500
traceId = null
details = {}
```

## 为什么需要默认字段

没有结构化响应体时，React 不能获得 Java 的业务错误代码或追踪编号，但它仍然知道 HTTP 状态是 `500`。

因此默认规则使用：

```text
HTTP_ + status
```

生成 `HTTP_500`。这比返回空字符串或任意文本更稳定，页面和日志至少能够区分服务器错误与其他失败。

这里不是 AI 分析的 `fallback` 模式。它只是 React 为不完整 HTTP 错误创建的默认 `ApiError`。

## 测试流程

```text
Given：模拟非 JSON 的 500 响应
When：调用 analyzeTicket
Then：检查默认 message、code、traceId 和 details
```

测试仍然使用模拟 `fetch`，不会启动 Java。

## 相对 V1 的改进

优化前：

```text
只有成功请求和结构化 409 受到保护
非 JSON 错误体的解析失败路径没有测试
默认 HTTP 错误代码可能被意外修改
```

优化后：

```text
成功、结构化冲突和非结构化服务器错误分别受到测试保护
HTTP_500 默认代码进入回归检查
错误体无法解析时仍能得到稳定 ApiError
```

## 自动化验证

本轮完成以下验证：

- 正确代码：1 个测试文件中的 3 条测试全部通过。
- 故障注入：临时把默认错误代码改成 `UNKNOWN` 后，新测试明确报告预期 `HTTP_500`、实际 `UNKNOWN`，并返回退出码 1。
- 恢复正确代码后，`npm run lint` 通过。
- `npm run test`：3 条通过。
- `npm run build`：TypeScript 和 Vite 生产构建通过。
- TypeScript 安全规则检查：通过。
- 测试文件有效代码 64 行，仍只负责 React API 边界行为。
- `git diff --check`：通过。

构建仍有现存主 JavaScript 包超过 500 kB 的提示，本轮没有修改页面或打包结构。

## 涉及文件

- `apps/support-copilot-web/src/services/api.test.ts`
- `docs/optimizations/ROADMAP.md`
- `docs/optimizations/v1-round-1/README.md`
- `docs/optimizations/v1-round-1/38-react-structured-conflict-error-test.md`
- `docs/optimizations/v1-round-1/39-react-non-json-error-defaults-test.md`

## 当前边界

- 当前测试覆盖分析请求、结构化 `409` 和非 JSON `500`，尚未覆盖网络连接失败。
- 模拟 `fetch` 不会验证 React 与真实 Java 服务之间的连接。
- 页面是否正确显示这些错误仍需要组件测试或浏览器端到端测试。
- React CI 的新增测试尚未推送，GitHub 托管环境还没有实际运行记录。

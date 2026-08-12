# 优化 07：前端保留结构化错误

## V1 的问题

React 的分析请求原来把所有失败都当成同一种情况：

```text
409 版本冲突
404 工单不存在
500 Java 服务异常
网络连接失败
        -> catch
        -> 生成临时 Demo
```

这样会产生两个问题：

1. Java 返回的 `code`、`message`、`traceId` 被丢弃，React 无法识别具体错误。
2. 真实的版本冲突可能被页面伪装成一份模拟分析结果。

## 本轮修改

### 1. 增加前端 `ApiError`

`api.ts` 新增带结构的错误对象，保留：

- HTTP `status`。
- 业务错误 `code`。
- 面向用户的 `message`。
- 用于日志排查的 `traceId`。
- 额外业务信息 `details`。

### 2. 读取 Java 的错误 JSON

非 2xx 响应不再只生成 `API request failed: 409`，而是先读取响应体，再创建 `ApiError`。

### 3. 区分错误路径

分析按钮的 React 逻辑现在按以下规则处理：

```text
ApiError + VERSION_CONFLICT
    -> 提示版本冲突
    -> 保留当前工单
    -> 不生成 Demo

其他 ApiError
    -> 展示 Java 返回的 message
    -> 不覆盖当前分析结果

网络 TypeError
    -> 允许进入本地 Demo

其他未知错误
    -> 提示分析失败
    -> 不生成 Demo
```

## 相对 V1 的改进

```text
V1
所有错误 -> 临时 Demo
    -> 用户无法区分真实结果和模拟结果

现在
HTTP 业务错误 -> 保留 code、message、traceId
网络不可达    -> 才使用本地 Demo
    -> 错误语义和页面行为一致
```

## 对应代码

- `apps/support-copilot-web/src/services/api.ts:27`：`ApiError`。
- `apps/support-copilot-web/src/services/api.ts:55`：读取错误响应体。
- `apps/support-copilot-web/src/App.tsx:1181`：识别结构化 API 错误。
- `services/support-copilot-api/src/main/java/com/cyagent/supportcopilot/common/ApiExceptionHandler.java:60`：Java 错误契约。

## 当前边界

本轮只修复“点击分析”路径。应用启动时的 `Promise.all(fetchTickets, fetchMetrics)` 仍然是全有或全无策略：任一请求失败，页面会进入演示状态。这个问题需要在“数据一致性”和“部分可用性”之间做单独设计，不能仅仅把 `Promise.all` 换成其他 API。

## 验证

- `npm run build --prefix apps/support-copilot-web` 通过。
- `npm run lint --prefix apps/support-copilot-web` 通过。
- `git diff --check` 通过。
- 当前前端未配置单元测试框架，因此本轮没有新增前端自动化测试。

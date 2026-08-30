# 前端运行时响应契约

## 目的

TypeScript 类型只在编译时存在，不能证明 Java 实际返回的 JSON 符合约定。React 现在把所有成功业务响应先当作不可信数据，再通过 Zod Schema 解析；只有解析成功的对象才能进入页面状态。

这解决以下风险：

- Java 漏掉必填字段后，React 继续读取 `undefined` 并在更深层报错。
- 枚举新增或拼写漂移后，页面把未知状态当成已有状态展示。
- 数字被序列化为字符串后，图表或计算发生隐式转换。
- 真实工单缺少 `version` 后，被误判为允许本地修改的演示工单。
- `mode`、`status` 和 `fallbackReason` 的组合违背降级契约。

## 边界流程

```text
fetch 收到 2xx
  -> response.json() 读取为 unknown
  -> 对应 Zod Schema 执行 safeParse
  -> 成功：返回 Schema 推导出的 TypeScript 类型
  -> 失败：抛出 ApiContractError
  -> React 不接收未解析的响应对象
```

Schema 集中在 `apps/support-copilot-web/src/services/apiSchemas.ts`，类型由同一 Schema 通过 `z.infer` 推导，避免再维护一份独立的前端字段接口。

## 当前覆盖

| React 调用 | 成功响应 Schema |
| --- | --- |
| `GET /api/tickets` | 当前页工单数组；每个真实工单必须有非负整数 `version`，续页游标在 `X-Next-Cursor` 响应头 |
| `GET /api/metrics` | 指标结构；计数、延迟和比率保持数字类型与有效范围 |
| `POST /api/tickets/{id}/analyze` | 完整分析结果及所有嵌套字段 |
| `PATCH /api/tickets/{id}` | 单个完整工单 |
| `POST /api/tickets/{id}/unassign` | 单个完整工单 |

对象使用严格 Schema，未知字段不会被静默丢弃。新增后端字段需要同步更新前端契约和测试，避免滚动部署期间出现无法解释的兼容状态。

工单分页元数据位于响应头，不进入数组 Schema：`X-Page-Limit` 表示当前页大小，存在更多
结果时返回 `X-Next-Cursor`。当前 `fetchTickets` 保持返回数组的兼容 API；工作台尚未提供
续页交互，因此首批之外的服务端结果不会自动进入页面。

分析结果还必须满足：

```text
mode=mock|live -> status=SUCCEEDED -> fallbackReason=null
mode=fallback  -> status=FALLBACK  -> fallbackReason=受控原因值
```

## 错误语义

非 2xx 响应继续转换为 `ApiError`，保留 HTTP 状态、业务错误码、消息、`traceId` 和详情。

2xx 响应体不是 JSON，或 JSON 不符合成功 Schema 时，转换为 `ApiContractError`：

- `path` 保存发生漂移的接口路径。
- `issues` 只保存字段路径和稳定的 Schema 问题代码。
- 错误不保存原始响应体，避免把工单正文或其他敏感内容带入日志对象。
- 分析调用只允许 `TypeError` 网络失败进入本地 Demo；契约错误显示普通分析失败，不会伪装成演示成功。

## 验证与边界

Vitest 覆盖缺少或非法 `fallbackReason` 组合、合法 fallback、非法 `mode`、未知字段、工单缺少 `version`、指标数字变成字符串和 2xx 非 JSON 响应。真实三服务 mock 联调进一步证明当前 Java 工单、指标和分析 JSON 能通过同一运行时边界。

当前仍有以下限制：

- Java、Python 和 TypeScript 尚未由同一 OpenAPI 或 JSON Schema 自动生成，字段变更仍需三层同步评审。
- 严格未知字段策略要求前后端协调发布；当前 V1.5 尚未实现多版本兼容窗口。
- 这只验证本地 mock 三服务响应，不是正式聊天模型或 Embedding API 的 live 成功记录。

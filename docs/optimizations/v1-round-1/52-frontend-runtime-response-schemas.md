# 优化 52：在前端 HTTP 边界解析真实响应

## 业务问题

React 原来通过 `response.json() as Promise<T>` 直接相信 Java 返回的数据。TypeScript 编译器只能检查源码，浏览器运行时收到缺字段、错误类型或未知枚举时仍会把它交给页面。坏数据可能在组件深处才报错，也可能把缺少 `version` 的真实工单误当成演示工单。

## 改进方案

新增集中式 Zod Schema，覆盖工单列表、指标、分析、工单更新和取消负责人成功响应。通用请求函数把 2xx JSON 先读取为 `unknown`，解析成功后才返回 Schema 推导类型。

解析失败统一抛出 `ApiContractError`，只暴露接口路径、字段路径和问题代码，不保存原始响应体。非 2xx 的 `ApiError` 语义保持不变。

完整规则见 [`docs/contracts/frontend-runtime-schema-contract.md`](../../contracts/frontend-runtime-schema-contract.md)。

## 验证结果

- 红灯阶段：5 条契约测试全部失败，证明旧边界会接受缺少 `fallbackReason`、非法 `mode`、缺少工单 `version` 和字符串指标，并只对非 JSON 抛出原始 `SyntaxError`。
- React：lint、15 条 Vitest 和生产构建通过；Zod 锁定为 4.4.3。
- TypeScript 严格规则检查：6 个改动文件无 `any`、类型断言、非空断言、忽略指令或吞异常。
- Java 全量测试：26 条通过。
- Python 全量测试：80 条通过。
- 固定 mock 评估：18/18 通过，无失败案例。
- 三服务浏览器联调：页面显示“业务 API 已连接”，真实触发工单分析后显示 `deterministic-demo`、3 条知识依据、完成提示和 `trace_f55734baa3f0`。
- 视觉回归：桌面 `1440x900` 与手机 `390x844` 使用精确视口截图，页面横向内容宽度分别为 1432 和 382，均未超过视口；两名独立只读审查者均给出高置信度 PASS。

## 能力边界

当前 Schema 是前端运行时防线，不是自动生成的跨服务单一事实源。Java、Python 和 TypeScript 的字段变更仍需同步修改和评审；严格未知字段策略也要求协调发布。

本轮没有正式聊天模型或 Embedding API 凭据，也没有发起付费调用。真实 RAG 仍处于层级 2，正式 `mode=live` 成功记录仍未完成。

## 面试关键位置

- `apps/support-copilot-web/src/services/apiSchemas.ts`：定义工单、指标和分析结果的运行时可信边界。
- `apps/support-copilot-web/src/services/api.ts`：将未知 JSON 解析为可信类型，并输出不含原始响应的 `ApiContractError`。
- `apps/support-copilot-web/src/services/apiContract.test.ts`：用 8 条边界测试证明坏响应会停止、合法 fallback 会通过。

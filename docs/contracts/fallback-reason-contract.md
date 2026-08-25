# Fallback 原因契约

## 目的

`mode=fallback` 只说明系统使用了降级结果，不能说明为什么降级。`fallbackReason` 是 Java、Python 和 React 共同使用的机器可读原因，用于分析历史、日志关联、故障统计和人工复核。

契约规则：

- `status=SUCCEEDED` 且 `mode=mock|live` 时，`fallbackReason` 必须为 `null`。
- `status=FALLBACK` 且 `mode=fallback` 时，`fallbackReason` 必须是下表中的一个值。
- 原因是稳定代码，不包含异常消息、服务地址、工单正文或凭据。
- `decision.reason` 和 `suggestedReply.warnings` 继续提供面向客服的说明；不能用它们代替机器可读原因。

## 当前值域

| `fallbackReason` | 产生位置 | 含义 |
| --- | --- | --- |
| `insufficient_evidence` | Python 或 Java 本地规则 | 知识检索没有满足阈值的证据 |
| `embedding_api_error` | Python | Embedding 服务返回普通 API 错误 |
| `embedding_connection_timeout` | Python | Embedding 服务连接建立超时 |
| `embedding_response_timeout` | Python | Embedding 服务响应超时 |
| `structured_generation_api_error` | Python | 结构化生成服务返回普通 API 错误 |
| `structured_generation_connection_timeout` | Python | 结构化生成服务连接建立超时 |
| `structured_generation_response_timeout` | Python | 结构化生成服务响应超时 |
| `invalid_model_response` | Python | 模型响应不能解析为受控结构 |
| `processing_timeout` | Java | Python 整体分析返回 504 截止时间错误 |
| `ai_service_timeout` | Java | Java 等待 Python 超过自身 HTTP 预算 |
| `ai_service_unavailable` | Java | Java 无法连接 Python |
| `ai_service_error` | Java | Python 返回未单独分类的非成功 HTTP 响应 |
| `invalid_ai_response` | Java | Python 返回空响应、非法 JSON 或未知原因值 |

## 数据流

```text
Python 可恢复 AI 故障
  -> 返回 fallbackReason
  -> Java 反序列化受控枚举
  -> AnalysisRun 独立列和 responseJson 同时保存
  -> React AnalysisResult 保留同一值

Python 整体超时或不可连接
  -> Java AiServiceClient 转为 AiServiceCallException
  -> AnalysisService 只捕获该类型化异常
  -> Java 本地 fallback 保留异常中的 fallbackReason
  -> AnalysisRun 保存
```

未知 Java 程序错误不会被转换为 fallback。它会继续抛出，以免用“AI 服务不可用”掩盖代码缺陷。

## 当前边界

- React 已通过 Zod 在 HTTP 边界校验固定值域，并同时约束 `mode`、`status` 和 `fallbackReason` 的组合；完整规则见 [`frontend-runtime-schema-contract.md`](frontend-runtime-schema-contract.md)。
- H2 是内存数据库，服务重启后分析历史会清空。
- 当前字段支持定位和统计，不代表已经接入日志平台或指标后端。
- 正式 API live 成功记录仍未完成，不能用本地故障演练替代。

# 优化 50：让 fallback 原因跨服务可解释

## 业务问题

此前分析响应和历史只能看到 `mode=fallback`、`status=FALLBACK`。证据不足、Embedding 故障、结构化生成超时、Python 整体超时和 Python 服务不可连接都会落到相同结果，客服只能知道“系统降级了”，开发者也无法按原因定位和统计。

Java 还会捕获所有 `RuntimeException`。这能保持页面可用，却可能把空响应处理错误或普通代码缺陷伪装成“AI 服务不可用”。

## 改进方案

新增受控 `fallbackReason` 契约，值域记录在 [`docs/contracts/fallback-reason-contract.md`](../../contracts/fallback-reason-contract.md)。正常结果返回 `null`；降级结果必须给出机器可读原因。

```text
Python Embedding / 结构化生成可恢复错误
  -> 根据操作阶段和故障类型生成 fallbackReason
  -> Java 保留字段
  -> AnalysisRun 独立列和完整 responseJson 同时持久化

Python 504 / Java HTTP 超时 / Python 不可连接
  -> AiServiceClient 转成带原因的 AiServiceCallException
  -> AnalysisService 只捕获这个类型化边界
  -> Java 本地 fallback 保留原因并进入人工复核
```

`AnalysisWorkflow` 原文件超过本轮代码规模上限。本轮把本地确定性分类、回复和轨迹规则拆到 `LocalAnalysisPolicy`，主工作流只保留跨服务编排。未知 Java 程序错误现在继续抛出，不再被宽泛的 `catch (RuntimeException)` 吞掉。

## 验证结果

- 红灯阶段：Python 因缺少 JSON 字段和对象属性失败；Java 因缺少原因枚举、类型化异常和持久化字段无法编译。
- Python 全量测试：80 条通过；新增 7 类正式 AI 可恢复错误到原因代码的映射测试。
- Java 全量测试：19 条通过；真实本地 HTTP 测试覆盖 Python 504 和 Java 自身等待超时，服务测试覆盖未知程序错误不降级。
- React：lint、3 条 Vitest 和生产构建通过。
- 固定 mock 评估：18/18 通过，无失败案例。
- Python 依赖锁、修改文件严格规则、shell 语法和 `git diff --check` 通过。

真实三服务 HTTP 演练：

```text
正常 mock
-> mode=mock / status=SUCCEEDED / fallbackReason=null
-> Java 历史保持 null

停止 Python
-> mode=fallback / status=FALLBACK
-> fallbackReason=ai_service_unavailable
-> Java 历史保存相同原因和 traceId

本地兼容端点返回 504
-> mode=fallback / status=FALLBACK
-> fallbackReason=processing_timeout
-> Java 历史保存相同原因和 traceId
```

## 能力边界

本轮没有正式聊天模型或 Embedding API 凭据，也没有发起付费调用。真实 RAG 仍处于层级 2，正式 API 的 `mode=live` 成功记录仍是层级 3 的必要条件。

`fallbackReason` 提高了定位和统计能力，但当前没有集中日志平台、指标后端或持久化生产数据库。TypeScript 也尚未在 HTTP 边界使用运行时 Schema 解析；未知值会先由 Java 拒绝并转为 `invalid_ai_response`，浏览器边界的独立运行时校验仍待后续批次。

## 面试关键位置

- `services/support-copilot-ai/app/errors.py`：正式 AI 故障与稳定原因代码的映射。
- `services/support-copilot-api/src/main/java/com/cyagent/supportcopilot/analysis/AiServiceClient.java`：Python 504、Java 超时、不可连接和非法响应的分类边界。
- `services/support-copilot-api/src/main/java/com/cyagent/supportcopilot/analysis/AnalysisService.java`：只处理类型化 AI 调用故障，保留原因并持久化 fallback。

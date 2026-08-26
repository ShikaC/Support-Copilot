# 第 65 轮：跨服务可靠性契约

## 问题与风险

原有 Java-to-Python 调用只有单次 read timeout，未区分可重试 429/5xx、不可重试 4xx 和成功响应契约错误，也没有 circuit、bulkhead 或边界指标。Python 有整体处理截止时间和类型化 provider 错误，但错误 envelope、探针和响应 trace header 不统一。将所有异常变成 fallback 会隐藏认证、校验和程序缺陷；Java 与 SDK 同时重试又会放大调用。

## 修改层与流程

Java 用 Resilience4j core 在现有 `RestClient` 外增加 retry、circuit breaker 和 semaphore bulkhead，并由虚拟线程 Future 提供一个 105 秒总截止时间和取消信号。重试只接受 429 与非 504 5xx；Python 504 已耗尽下游处理预算，立即进入 `processing_timeout` fallback。400/401/403/422、畸形 2xx、trace/prompt/mode 契约错误直接返回稳定 502 code，不进入 fallback。

Python 保留 `AnalysisRunner` 的 90 秒 anyio cancel scope和类型化 provider errors。`/health` 保持兼容；`/health/live` 只检查进程，`/health/ready` 检查 live provider 配置和知识索引。认证、校验、超时和未处理错误统一返回顶层 `code/message/traceId/details` 与 `X-Trace-Id`。未处理错误只在 HTTP 边界转换为 500；直接 workflow 单测仍观察原始程序异常。

重试所有权为 Java service boundary。OpenAI SDK 构造固定 `max_retries=0`；旧的有界配置值 1 仍可解析以避免本地 `.env` 突然阻止启动，但不会改变 SDK 实际尝试数。

## 指标与日志

Actuator 暴露受权限保护的 attempts、outcomes、fallbacks、timeouts、latency、circuit rejection 和 bulkhead rejection 指标。tag 只使用固定 outcome、fallback reason、provider mode 和 stage。ticket、trace、user 不作为 tag。Java Logback `%kvp` 和 Python stdlib formatter输出固定事件名与结构化字段；工单正文、模型输出、服务 token、API key 和 Authorization header 不写日志。

## 验证与限制

`AiResilienceContractTests` 使用真实 loopback HTTP server 验证 429/503 恢复、4xx 不重试、总截止时间、504 终止、畸形 2xx、circuit open、bulkhead saturation、trace、指标与日志脱敏。`tests/test_health_and_errors.py` 验证健康、readiness degraded、稳定错误和 500 程序错误边界。真实 HTTP QA 在隔离端口验证 Python probe/error header、Java probe、fallback 与 actuator metrics。

保护状态是单 Java 实例内存状态；没有跨实例共享 circuit/bulkhead，也没有据此声明生产吞吐或 SLO。客户端取消会尽力中断 Java HTTP 调用，但不能保证撤回已经被下游或外部供应商接收的计算。Docker、Compose、MySQL 和 pilot container 操作仍属于 Task 15，本轮未执行。

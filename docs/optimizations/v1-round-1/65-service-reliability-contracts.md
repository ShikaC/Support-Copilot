# 第 65 轮：跨服务可靠性契约

## 问题与风险

原有 Java-to-Python 调用只有单次 read timeout，未区分可重试 429/5xx、不可重试 4xx 和成功响应契约错误，也没有 circuit、bulkhead 或边界指标。Python 有整体处理截止时间和类型化 provider 错误，但错误 envelope、探针和响应 trace header 不统一。将所有异常变成 fallback 会隐藏认证、校验和程序缺陷；Java 与 SDK 同时重试又会放大调用。

## 修改层与流程

Java 用 Resilience4j core 在现有 `RestClient` 外增加 retry、circuit breaker 和 semaphore bulkhead，并由虚拟线程 Future 提供一个 105 秒总截止时间和取消信号。重试只接受 429 与非 504 5xx，`retryMaxAttempts` 表示总尝试数且 Bean Validation 上限为 2；配置 3 会在绑定阶段失败。Python 504 已耗尽下游处理预算，立即进入 `processing_timeout` fallback。400/401/403/422、畸形 2xx、trace/prompt/mode 契约错误直接返回稳定 502 code，不进入 fallback。

Python 保留 `AnalysisRunner` 的 90 秒 anyio cancel scope和类型化 provider errors。`/health` 保持兼容；`/health/live` 只检查进程。`/health/ready` 读取 `threading.Lock` 保护的不可变快照，不发外部探测：live Embedding/索引失败同时降级 provider/index，生成失败只降级 provider；对应 live 阶段成功后分别恢复。`/analyze` 的 header/body trace 都受同一 1 至 80 字符安全模式约束且必须相同；换行、超长或不匹配值会在工作流前拒绝，错误和日志只使用受信 header trace。认证、校验、超时和未处理错误统一返回顶层 `code/message/traceId/details` 与 `X-Trace-Id`。未处理错误只在唯一 HTTP conversion boundary 转换为 500；直接 workflow 单测仍观察原始程序异常。

重试所有权为 Java service boundary。OpenAI SDK 构造固定 `max_retries=0`；旧的有界配置值 1 仍可解析以避免本地 `.env` 突然阻止启动，但不会改变 SDK 实际尝试数。

## 指标与日志

Actuator 暴露受权限保护的 attempts、outcomes、fallbacks、timeouts、latency、circuit rejection 和 bulkhead rejection 指标。tag 只使用固定 outcome、fallback reason、provider mode 和 stage。ticket、trace、user 不作为 tag。Java Logback `%kvp` 和 Python stdlib formatter输出固定事件名与结构化字段；Python request-boundary workflow 事件把 trace、mode、status、hit count、reason 和 error type 放入独立字段，不插值进事件名。工单正文、模型输出、服务 token、API key 和 Authorization header 不写日志。

## 验证与限制

`AiResilienceContractTests` 使用真实 loopback HTTP server 验证 429/503 恢复、4xx 不重试、总截止时间、504 终止、畸形 2xx、circuit open、bulkhead saturation、trace、指标与日志脱敏。`AiServicePropertiesValidationTests` 证明默认总尝试数 2 可绑定而 3 被拒绝。`tests/test_runtime_readiness.py` 通过真实 `AnalysisRunner -> AnalysisWorkflow -> KnowledgeRetriever` 路径和确定性外部边界 fake 验证 Embedding 与生成故障、fallback、liveness、readiness 503 和受控恢复；`tests/test_health_and_errors.py` 继续验证稳定错误、500 程序错误边界以及恶意/不匹配 trace 不进入工作流或日志。真实 HTTP QA 在隔离端口验证 Python probe/error header、Java probe、fallback、actuator metrics 和 Java-to-Python stdout 的单一结构化 trace 字段。

Java circuit/bulkhead 和 Python dependency readiness 都是单进程内存状态。Python readiness 启动值来自已校验配置和 corpus，必须经过实际 live 流量才会观察惰性初始化或运行期故障；并发请求按每个阶段最后完成的结果更新，重启会重新初始化。它不包含 Task 9 的索引 artifact 构建、激活或回滚生命周期。客户端取消会尽力中断 Java HTTP 调用，但不能保证撤回已经被下游或外部供应商接收的计算。没有据此声明跨实例保护、生产吞吐或 SLO。Docker、Compose、MySQL 和 pilot container 操作仍属于 Task 15，本轮未执行。

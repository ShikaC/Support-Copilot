# Support Copilot 真实 RAG 完成标准

## 1. 最终要求

Support Copilot 不能停留在模拟数据和本地规则演示。最终项目必须：

- 能通过环境变量接入正式模型 API。
- 能通过正式 Embedding API 为知识片段生成向量。
- 能根据真实工单问题检索相关知识片段。
- 能把检索证据交给模型生成结构化分析和回复建议。
- 能返回可审查的引用、运行模式、模型信息和 `traceId`。
- 能在外部 API 失败时明确进入 fallback 和人工复核。
- 能用至少一次真实成功调用和一次失败演练证明上述链路。

mock 模式继续保留，但只用于离线开发、自动化测试、CI 和没有外部费用的稳定评估。mock 不是最终 RAG 完成证据。

## 2. 当前真实状态

当前代码已经具备 live 骨架：

- `Settings` 可以读取 API Key、Base URL、聊天模型和 Embedding 模型。
- `OpenAIProvider` 使用 OpenAI Responses API 请求结构化 `ModelDraft`。
- live 向量适配器使用 `OpenAIEmbeddings` 和 LangChain `InMemoryVectorStore`。
- `KNOWLEDGE_PATH` 可以指向仓库外的授权知识 JSON，启动时会校验字段、空值和重复片段 ID。
- 原始 Markdown 和自带文本层的 PDF 可以通过清单确定性切分为知识 JSON，并生成不含正文的 provenance。
- `KNOWLEDGE_PROVENANCE_PATH` 可以让服务校验 corpus 哈希，防止索引正文和来源证明漂移。
- live 调用失败后可以进入明确标识的 fallback。
- live 外发边界会先脱敏常见邮箱、手机号、18 位身份证号和支付卡号，Responses 请求显式设置 `store=false`。
- live 超时遵循外部请求、Python 整体分析、Java 等待和验收客户端逐层增大的预算，并通过可取消异步调用阻止超时后的后续 AI 阶段。
- fallback 会用受控 `fallbackReason` 区分证据不足、Embedding、结构化生成、整体处理超时和 Java 到 Python 的调用故障，并随 Java 分析历史保存。
- 同一工单版本和分析策略的并发在途请求会在单 Java 实例内共享一次 Python 调用与一次持久化，完成后允许显式重试。
- 分析响应包含模式、模型、检索片段、引用、token 和耗时字段。
- React 会在 HTTP 边界运行时解析工单、指标和分析响应，拒绝字段、类型、枚举或 fallback 组合漂移。

当前已经达到层级 3 的单次真实 live 验证：

- 2026-08-26 在干净提交 `59903a125e30a25b29e4156b28023e53fb21ea52` 上执行 `./scripts/check-live-rag.sh --success`，正式 Embedding 和结构化生成调用均成功。
- 最终结果为 `mode=live`、`status=SUCCEEDED`，返回 3 条 `VECTOR` 检索证据和 1 条引用，并由 Java 保存为最新分析记录。
- 本次记录使用脱敏合成工单；本地忽略的证据文件只保留配置类型、聚合运行值和可追溯标识，不包含密钥、授权头、工单正文或供应商原始响应。

但当前仍不能称为成熟 RAG：

- 向量库当前只存在于 Python 进程内存，服务重启后需要重新生成。
- 当前已有 Markdown 和文本型 PDF 的批量构建入口，但尚未支持扫描件 OCR、增量更新、审批发布和持久化向量索引。
- live 检索和生成质量尚未用真实调用结果与固定评估集对照。

Task 10 已增加版本化合成 live 数据集、逐案例引用/检索/token/runner latency 记录、release/corpus/artifact/model/config/Git provenance 校验，以及独立人工 groundedness worksheet。机器只生成 `NOT_REVIEWED`；只有真实 reviewer 填写 factual-support label、decision note 和 reviewed_at 且 verifier 通过，报告才可标记 publishable。新正式 live 运行和人审状态以 Task 10 evidence 为准，本段不预先宣称成功。

准确表述应是：**真实模型和 Embedding API 的端到端 RAG 链路已完成一次脱敏验证；当前仍是单次 V1.5 验收，不代表成熟 RAG、生产稳定性或真实客服效果。**

## 3. 四个完成层级

### 层级 1：可配置

```text
能够设置 API Key、Base URL 和模型名
```

这只证明程序有配置入口，不能证明 API 可以调用。

### 层级 2：已集成

```text
代码能够构造 Embedding 和结构化生成请求
自动化测试覆盖请求、响应和失败语义
```

这证明接口契约已接入，但模拟测试仍不能替代真实服务。

### 层级 3：真实 live 已验证

```text
正式 Embedding API 成功生成知识向量
正式模型 API 成功返回结构化结果
最终响应 mode=live
检索片段和引用可以核对
保存脱敏的 traceId、模型、耗时和 token 记录
```

达到这一层后，才能在简历或面试中说明项目已经接入真实模型 API。

### 层级 4：成熟 RAG

```text
知识导入和切分可重复执行
向量索引可以持久化和增量更新
检索与生成有固定质量评估
密钥、超时、重试、限额和日志边界清楚
真实调用失败不会破坏 Java 业务数据
```

这是最终成熟项目目标。七天 V1.5 至少必须达到层级 3，并为层级 4 留下真实、明确的演进路线。

## 4. V1.5 live 验收场景

### 成功场景

输入一条不包含真实客户隐私的模拟工单：

```text
用户无法通过企业 SSO 登录
```

系统必须观察到：

```text
Python health: mode=live、liveReady=true
-> 正式 Embedding API 处理知识片段和查询
-> 向量检索返回与 SSO 相关的 Top K 证据
-> 正式模型 API 返回结构化分类和回复
-> Java 保存 mode=live 的 AnalysisRun
-> React 展示模型名、证据、引用和建议回复
```

保存证据时必须删除 API Key、授权头和客户隐私。

### 失败场景

使用无效端点、测试故障注入或受控超时触发外部依赖失败：

```text
正式 API 不可用
-> Python 标记 fallback
-> Java 保存可追踪的降级结果
-> React 明确显示需要人工复核
```

不能把 fallback 显示成 live 成功。

## 5. 真实验证记录至少包含

- 验证日期和 Git 提交 SHA。
- 使用的聊天模型和 Embedding 模型。
- 是否使用官方端点或兼容 Base URL。
- 脱敏后的输入工单编号和 `traceId`。
- 检索到的知识片段 ID、来源和顺序。
- 知识来源类型、片段数量和知识文件 SHA-256，不记录本地路径或正文。
- 使用生成式 corpus 时，记录知识格式、索引版本、源文档数量和清单 SHA-256。
- 响应中的 `mode`、分类、引用和人工升级结果。
- 调用耗时和 token 用量。
- 是否发生 fallback。
- 执行命令和通过或失败结果。

不得记录 API Key、Authorization 头、真实客户数据或无法核实的效果结论。

Traceable live evaluation 还必须记录 dataset id/version/checksum、knowledge release id/version/semantic checksum、active artifact id/manifest/provider/model/dimension/chunking、chat endpoint nonsecret identity/model、prompt/config fingerprint、Git SHA/dirty truth、逐案例 fallback/retrieved/allowed/cited/evidence-index/runner latency/token/cost availability 和人工 review。缺少明确 pricing source 时 cost 必须为 null。

## 6. 外部前提

真实 live 验证需要用户在本地环境提供：

```text
OPENAI_API_KEY
OPENAI_EMBEDDING_API_KEY（可选；未配置时复用 OPENAI_API_KEY）
OPENAI_CHAT_MODEL
OPENAI_EMBEDDING_MODEL
```

兼容服务还可以提供：

```text
OPENAI_BASE_URL
OPENAI_EMBEDDING_BASE_URL
```

`OPENAI_BASE_URL` 控制聊天/Responses 请求；`OPENAI_EMBEDDING_BASE_URL` 控制 Embedding 请求。后者未配置时回退到前者；两者都未配置时使用 SDK 的官方默认地址。

密钥只能通过环境变量或未提交的本地 `.env` 提供。没有可用凭据时可以继续完成代码、测试和文档，但真实 live 验收必须标记为阻塞，不能宣称已经完成。

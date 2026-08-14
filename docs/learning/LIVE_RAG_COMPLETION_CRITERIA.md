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
- `KnowledgeRetriever` 使用 `OpenAIEmbeddings` 和 LangChain `InMemoryVectorStore`。
- live 调用失败后可以进入明确标识的 fallback。
- 分析响应包含模式、模型、检索片段、引用、token 和耗时字段。

但当前仍不能称为真实 RAG 已完成：

- 仓库没有一次正式 API 成功调用的脱敏记录。
- live 路径尚未在当前环境完成真实端到端验证。
- 向量库当前只存在于 Python 进程内存，服务重启后需要重新生成。
- 当前知识数据来自本地 JSON，尚未形成独立的增量导入流程。
- live 检索和生成质量尚未用真实调用结果与固定评估集对照。

准确表述应是：**已有可配置的 live RAG 代码骨架，但尚未完成真实 API 验证。**

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
- 响应中的 `mode`、分类、引用和人工升级结果。
- 调用耗时和 token 用量。
- 是否发生 fallback。
- 执行命令和通过或失败结果。

不得记录 API Key、Authorization 头、真实客户数据或无法核实的效果结论。

## 6. 外部前提

真实 live 验证需要用户在本地环境提供：

```text
OPENAI_API_KEY
OPENAI_CHAT_MODEL
OPENAI_EMBEDDING_MODEL
```

兼容服务还可以提供：

```text
OPENAI_BASE_URL
```

密钥只能通过环境变量或未提交的本地 `.env` 提供。没有可用凭据时可以继续完成代码、测试和文档，但真实 live 验收必须标记为阻塞，不能宣称已经完成。

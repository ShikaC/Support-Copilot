# Support Copilot V1 项目地图

> 本文档是 Support Copilot V1 的导航图。它帮助阅读者先理解项目的位置关系，再进入具体代码。
>
> 当前定位：V1 早期版本，已经可以演示端到端分析流程，但仍有明确的可靠性、安全性和可维护性缺口。

## 1. 先记住一句话

Support Copilot 是一个客服工单辅助系统：

```text
客服选择工单
    -> Java 查询和管理工单
    -> Python/AI 分析工单并检索知识库
    -> Java 保存分析结果
    -> React 展示分类、证据、置信度和回复建议
```

AI 只提供建议，Java 保存业务事实，React 负责让客服操作和查看结果。

## 2. 技术栈地图

| 技术 | 在项目中的角色 | 当前主要位置 |
| --- | --- | --- |
| React + TypeScript | 浏览器页面、按钮、状态和页面更新 | `apps/support-copilot-web/src/` |
| Java + Spring Boot | HTTP 接口、业务编排、数据库保存和错误处理 | `services/support-copilot-api/src/main/java/` |
| JPA + H2 | V1 本地保存工单和分析记录 | `services/support-copilot-api/src/main/` |
| Python + FastAPI | AI 分析、知识检索和结构化结果生成 | `services/support-copilot-ai/app/` |
| OpenAI API | Python 的 live 模式中的外部模型能力 | `services/support-copilot-ai/app/openai_provider.py` |

当前没有把认证、Redis、消息队列、MySQL、OpenTelemetry 等 V2 能力包装成已经完成的功能。

## 3. 服务边界

```text
+----------------------+        HTTP         +-------------------------+
| React 浏览器页面     | -------------------> | Java Spring Boot        |
| 看页面、接收点击     |                     | 业务入口、状态、保存    |
+----------------------+                     +------------+------------+
                                                          |
                                                          | HTTP
                                                          v
                                             +-------------------------+
                                             | Python FastAPI          |
                                             | AI、RAG、fallback       |
                                             +------------+------------+
                                                          |
                                                          v
                                             +-------------------------+
                                             | 公司知识库 / OpenAI      |
                                             +-------------------------+
```

### React 不负责什么

- 不负责真正判断工单分类。
- 不负责长期保存工单和分析历史。
- 不应该直接暴露或调用 OpenAI API Key。
- 不应该把临时模拟结果伪装成真实分析结果。

### Java 不负责什么

- 不负责实现模型内部推理。
- 不负责自己实现向量检索算法。
- 不应该让浏览器直接依赖 Python 内部接口。

### Python 不负责什么

- 不负责决定工单业务状态如何保存。
- 不负责权限和审计边界。
- 不应该成为唯一的业务数据存储位置。

## 4. “开始分析”主流程

### 4.1 浏览器发起请求

入口位置：

- `apps/support-copilot-web/src/App.tsx` 的 `runAnalysis`
- `apps/support-copilot-web/src/services/api.ts` 的 `analyzeTicket`

流程：

```text
用户点击“开始分析”
    -> React 取得 selectedTicket.id
    -> React 设置 analyzingTicketId
    -> 页面显示“分析中”
    -> POST /api/tickets/{id}/analyze
```

这里的 `analyzingTicketId` 只表示浏览器正在等待请求结果，不表示只有 Java 在工作。Java 可能正在等待 Python 返回结果。

### 4.2 Java 接收工单编号

入口位置：

- `services/support-copilot-api/src/main/java/com/cyagent/supportcopilot/ticket/TicketController.java`
- `@PostMapping("/{id}/analyze")` 当前在第 61 行附近

Controller 主要做接口接收和转发：

```text
URL 中的 ticket-10042
    -> Controller 的 id 参数
    -> analysisService.analyze(id)
```

Controller 不应该把查询数据库、调用 AI、保存结果全部写在一个方法里，否则职责会混在一起，测试也会变困难。

### 4.3 Java 查询工单并记录版本

入口位置：

- `services/support-copilot-api/src/main/java/com/cyagent/supportcopilot/analysis/AnalysisService.java:46`

主要过程：

```text
ticketId
    -> TicketRepository.findById(ticketId)
    -> 得到 Ticket
    -> 记录 sourceTicketVersion
    -> 调用 Python
```

`sourceTicketVersion` 表示“这次 AI 分析使用的工单版本”。它用于防止 AI 分析期间工单被其他操作修改后，旧结果覆盖新内容。

### 4.4 Java 调用 Python

入口位置：

- `services/support-copilot-api/src/main/java/com/cyagent/supportcopilot/analysis/AiServiceClient.java:38`

Java 把工单整理成 Python 需要的请求结构，例如：

```text
traceId
ticket.id
ticket.title
ticket.description
topN / topK
promptVersion
```

`traceId` 用来追踪同一次分析请求，`ticket.id` 用来说明分析的是哪一张工单。

### 4.5 Python 执行分析

入口位置：

- `services/support-copilot-ai/app/main.py:37`
- `services/support-copilot-ai/app/workflow.py`
- `services/support-copilot-ai/app/knowledge.py`

Python 的概念流程：

```text
接收工单
    -> 生成检索问题
    -> 从知识库取得 Top K 片段
    -> 根据证据生成分类和回复建议
    -> 计算置信度和风险
    -> 返回结构化 AnalysisResult
```

如果使用 live 模式，Python 可以调用外部模型。如果没有配置 API，或调用失败，则需要使用 mock 或 fallback，并在结果中明确标识模式。

### 4.6 Java 保存分析结果

入口位置：

- `services/support-copilot-api/src/main/java/com/cyagent/supportcopilot/analysis/AnalysisPersistenceService.java:33`

当前优化后的保存过程：

```text
AI 调用结束
    -> 开始短数据库事务
    -> 重新读取最新 Ticket
    -> 比较当前 version 和 sourceTicketVersion
    -> 版本一致：保存 AnalysisRun 并更新 Ticket
    -> flush 检查数据库约束
    -> commit
```

如果版本不一致：

```text
拒绝旧分析结果
    -> 回滚本轮数据库修改
    -> 返回结构化 409 Conflict
    -> React 提示客服重新确认最新工单
```

AI 网络调用不放在这个数据库事务里，避免事务长时间占用数据库资源。

### 4.7 React 更新页面

Java 返回 `AnalysisResponse` 后，React 会：

```text
收到 result
    -> 找到对应 ticket.id
    -> 替换或更新工单数据
    -> 更新 latestAnalysis
    -> 清除 analyzingTicketId
    -> 页面重新渲染
```

## 5. 主要数据对象

### Ticket

代表客服工单，保存：

- 工单编号。
- 标题和客户问题。
- 当前工单状态。
- 当前分类和优先级。
- 当前负责人。
- `version`，用于乐观锁和版本冲突检测。

主要位置：

- `services/support-copilot-api/src/main/java/com/cyagent/supportcopilot/ticket/Ticket.java`
- `services/support-copilot-api/src/main/java/com/cyagent/supportcopilot/ticket/TicketRepository.java`

### AnalysisRun

代表一次分析记录，保存：

- 本次分析 ID。
- `traceId`。
- 分析使用的模式：`live`、`mock` 或 `fallback`。
- 分析结果。
- `sourceTicketVersion`。
- 创建时间。

主要位置：

- `services/support-copilot-api/src/main/java/com/cyagent/supportcopilot/analysis/AnalysisRun.java`
- `services/support-copilot-api/src/main/java/com/cyagent/supportcopilot/analysis/AnalysisRunRepository.java`

### AnalysisResponse

这是 Java、Python 和 React 之间共同理解的结果结构，包含：

```text
classification       分类、优先级、情绪、置信度
workflowSteps        分析经过的步骤
retrieval            检索 query 和知识片段
suggestedReply       回复建议和引用
decision             是否升级人工以及原因
usage                耗时和 token 信息
```

对应位置：

- TypeScript：`apps/support-copilot-web/src/types.ts`
- Java：`services/support-copilot-api/src/main/java/com/cyagent/supportcopilot/analysis/AnalysisResponse.java`
- Python：`services/support-copilot-ai/app/models.py`

这三份结构必须保持兼容，否则一个服务新增字段后，另一个服务可能无法正确解析。

## 6. 失败处理地图

| 情况 | 当前 Java 行为 | React 应该理解成什么 |
| --- | --- | --- |
| 工单不存在 | 抛出业务异常 | 请求的工单编号无效 |
| Python 调用失败 | Java 生成并保存 fallback | AI 暂时不可用，但工单仍可人工处理 |
| 工单版本冲突 | 返回结构化 `409` | 旧分析不能覆盖最新工单 |
| Java 无法连接 | 请求失败 | 后端不可用，分析路径可以进入本地 Demo |
| 用户主动 Demo | 使用演示数据 | 这是演示结果，不代表真实 AI 结果 |

当前点击分析路径已经区分网络失败、409 和普通业务错误；应用启动时已经分别处理工单和指标请求，支持 `partial` 部分可用状态。

## 7. 当前已经完成与尚未完成

### 已完成的 V1 改进

- 分析保存使用独立的短事务。
- 分析前后检查工单版本。
- 记录分析来源版本。
- 版本冲突返回结构化 409。
- 增加事务、回滚和 API 测试。
- Java fallback 明确标记为需要人工复核。
- React 分析请求保留 Java 的 `code`、`message` 和 `traceId`。
- React 不再把 HTTP 409 和普通后端错误伪装成 Demo。
- React 启动阶段支持工单和指标部分成功，不再因为指标失败丢弃真实工单。
- 取消负责人使用 `POST /api/tickets/{id}/unassign`，携带 `expectedVersion` 做版本保护。
- React 只有在 Java 命令成功后才更新真实工单的负责人；本地演示工单才允许本地演示修改。

相关文档：`docs/optimizations/v1-round-1/`

### 尚未完成的设计

- `SecurityConfig` 当前允许所有请求，没有真实登录身份。
- 取消负责人已经有命令接口、版本冲突和终态检查，但尚未形成可信的权限检查。
- 当前 `TicketEventResponse` 是响应 DTO，不是持久化审计日志。
- 独立的幂等请求记录尚未实现；当前取消负责人依靠“已经没有负责人时不再写入”实现状态幂等。
- 工单和指标仍不是同一个后端快照，严格一致性需要统一初始化接口或明确统计时间范围。
- Python/RAG 还需要更多真实案例和评估数据。

因此，学习和面试时必须说清楚：哪些是已实现功能，哪些是下一阶段设计，不能把设计方案说成已经上线的能力。

## 8. 现在应该先掌握什么

不需要逐字理解所有代码。当前目标按下面顺序进行：

1. 能讲清楚一次“开始分析”的完整请求链路。
2. 能根据工单编号找到 Controller、Service、AI Client 和 Python 入口。
3. 能解释为什么 Java 要保存分析结果。
4. 能解释 fallback、RAG、置信度、引用和人工升级。
5. 能解释版本冲突为什么返回 409。
6. 能指出当前 V1 的缺点和下一步改进。

达到这些目标后，再深入具体语法和测试细节，效率会更高。

## 9. 下一张地图：取消负责人

接下来的业务优化主题是：

```text
明确命令接口
权限检查
状态冲突
幂等和审计
```

这个主题会连接前端负责人操作、Java `TicketService`、认证边界和持久化审计设计。

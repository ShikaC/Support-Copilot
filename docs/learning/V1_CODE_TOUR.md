# V1 代码导览

这份文档是 Support Copilot V1 的学习路线。代码觉得抽象时，不要从语言细节开始啃，先用这份导览建立整体地图。

目标不是记住每个文件，而是理解：**一个用户动作如何穿过整个系统，又如何带着 AI 分析结果回到页面。**

> 学习状态：这条基础导览已经完成。完整审查结果和后续路线见 [`V1_STAGE_1_REVIEW.md`](./V1_STAGE_1_REVIEW.md)。

## 1. 先学会这一条主链路

先把下面这个故事讲顺：

```text
点击“开始分析”
-> React 调用 Spring Boot
-> Spring Boot 读取并更新工单
-> Spring Boot 调用 FastAPI
-> FastAPI 检索证据并生成分析结果
-> Spring Boot 保存分析结果
-> React 渲染新的分析内容
```

对应文件：

- `apps/support-copilot-web/src/App.tsx`
- `apps/support-copilot-web/src/services/api.ts`
- `services/support-copilot-api/src/main/java/com/cyagent/supportcopilot/ticket/TicketController.java`
- `services/support-copilot-api/src/main/java/com/cyagent/supportcopilot/analysis/AnalysisService.java`
- `services/support-copilot-api/src/main/java/com/cyagent/supportcopilot/analysis/AiServiceClient.java`
- `services/support-copilot-ai/app/main.py`
- `services/support-copilot-ai/app/workflow.py`
- `services/support-copilot-ai/app/knowledge.py`

## 2. 按职责读代码，不要按语言硬读

读不懂某个文件时，先只问一个问题：

```text
这个文件负责什么？
```

在这个项目里：

- React 负责用户看到什么、点击什么。
- Spring Boot 负责业务状态、数据持久化和稳定 API。
- FastAPI 负责 AI/RAG 工作流。
- H2 负责 V1 本地运行时的业务数据。
- OpenAI 只在 Python 服务的 live 模式中使用。

所以浏览器不会看到 OpenAI API Key，Java 也不需要知道 embedding 是怎么生成的。

## 3. 最重要的数据形状

最重要的对象是 `AnalysisResult`，也就是一次 AI 分析的完整结果。

它在三个语言里各有一份定义：

- TypeScript：`apps/support-copilot-web/src/types.ts`
- Java：`services/support-copilot-api/src/main/java/com/cyagent/supportcopilot/analysis/AnalysisResponse.java`
- Python：`services/support-copilot-ai/app/models.py`

它们描述的是同一个服务契约。以后如果其中一个字段发生变化，另外两层也要保持兼容。

## 4. 在浏览器里观察什么

启动三个服务，打开 `http://127.0.0.1:5173/`，对 `SC-10042` 点击分析。

观察这些页面变化：

- 当前工单得到新的 `latestAnalysis`。
- 支付争议类工单状态变成 `NEEDS_ESCALATION`。
- 右侧面板显示 `DEMO`、`LIVE` 或 `FALLBACK`。
- “知识依据”标签页显示检索片段和分数。
- “回复建议”标签页显示引用，例如 `[1][2][3]`。

然后打开浏览器 DevTools 的 Network，找到：

```text
POST /api/tickets/ticket-10042/analyze
```

这个请求就是前端学习和后端学习之间的桥。

## 5. 四个练习循环

按顺序做这四个小练习。

### 练习 A：追踪一次请求

运行：

```bash
curl -X POST http://127.0.0.1:8080/api/tickets/ticket-10042/analyze
```

然后在代码里找出这些字段分别在哪里产生：

- `traceId`
- `classification.category`
- `retrieval.hits`
- `suggestedReply.content`
- `decision.escalationRequired`

### 练习 B：改一条演示工单

修改 Java 种子数据中的一个工单标题，重启 Spring Boot，观察工单队列如何变化。

这个练习先帮你理解数据流，不急着深入框架细节。

### 练习 C：改一个检索关键词

修改 `services/support-copilot-ai/app/data/knowledge.json` 中的一个 keyword，重启 FastAPI，再运行分析。

这个练习帮你理解：知识库证据如何影响最终回复。

### 练习 D：故意让一个服务失败

停止 FastAPI，然后点击分析。Java API 应该返回 fallback 结果。

这个练习帮你理解可靠性设计：AI 不能阻塞业务主流程。

## 6. 面试中可以这样讲

可以使用这段表述：

```text
V1 是一个本地可运行的端到端 AI 工作流演示。默认模式是 mock，
所以结果可复现，也不会把演示结果包装成真实 OpenAI 调用。
架构上，浏览器只调用 Spring Boot，Spring Boot 负责业务状态，
Python 负责 AI/RAG 工作流。页面会展示证据、引用、置信度、
风险决策和 fallback 模式，让 AI 辅助结果保持可审计。
```

## 7. V1 基础导览的边界

下面这些内容没有纳入第一轮基础代码导览：

- React 性能优化
- Spring Security 内部原理
- JPA 高级查询优化
- 真实向量数据库选型
- Docker Compose
- CI/CD

它们属于 V1.5 或 V2。第一轮已经把“一次分析请求”的主链路、状态变化、RAG 证据和 fallback 学到了可以独立复述的程度。

## 8. 导览完成后应该具备什么能力

完成这份导览后，不要求记住三种语言的全部语法，但应该能够：

- 从 React 的点击函数找到 Java Controller。
- 从 Controller 找到 Service、Repository 和 Python Client。
- 从 FastAPI 入口找到 RAG 工作流和知识检索。
- 解释分析结果为什么要经过 Java 保存后再返回 React。
- 区分 live、mock、fallback 和前端 demo。
- 看到证据不足、低置信度或隐私风险时，知道为什么必须升级人工。
- 看到一个“可以运行”的功能时，继续检查事务、鉴权、错误处理、测试和评估是否完整。

这些目标已经完成。下一步不再重复走主链路，而是按照 [`V1_STAGE_1_REVIEW.md`](./V1_STAGE_1_REVIEW.md) 中的审查优先级进入具体改进主题。

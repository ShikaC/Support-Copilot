# Support Copilot V1 第一阶段复习

这份文档整理我们到目前为止已经讨论并理解的内容。它不是完整的技术手册，而是后续继续读代码前的复习底稿。

复习时先尝试用自己的话回答每一节的问题，再回头看正文。最后的自测题暂时不附答案，我们继续采用“你先回答，我再纠正和补充”的方式。

> 学习状态：V1 第一轮代码阅读和风险审查已于 2026-07-31 完成。前半部分保留基础知识，后半部分记录完整审查结论和后续路线。

## 1. 这个项目要解决什么问题

Support Copilot 是一个客服工单辅助系统。

客服收到客户问题后，系统会帮助完成：

- 判断工单属于什么类别。
- 建议工单优先级。
- 判断客户情绪。
- 从公司知识库查找相关规定和处理方法。
- 根据查到的证据生成回复建议。
- 判断是否需要转给人工或其他专业团队。
- 保存本次分析，方便页面展示和以后追踪。

这里最重要的原则是：**AI 只提供可审核的建议，不能代替业务系统，也不能在没有证据时胡编答案。**

## 2. 三层技术分别负责什么

```text
用户
  |
  v
React 页面
  |
  v
Java / Spring Boot 业务后端
  |
  v
Python / FastAPI AI 服务
  |
  v
公司知识库 + OpenAI（仅 live 模式）
```

### React：用户看得见、点得到的部分

React 负责：

- 展示工单列表和工单详情。
- 接收用户点击“开始分析”的动作。
- 显示“分析中”。
- 把分析请求发送给 Java 后端。
- 收到结果后更新分类、知识依据、置信度和回复建议。

React 不负责真正分析工单，也不负责把业务数据长期保存下来。

### Java / Spring Boot：业务总管

Java 负责：

- 接收浏览器发来的 HTTP 请求。
- 根据工单 ID 查询具体工单。
- 把工单内容整理后发送给 Python。
- 接收并保存分析结果和分析历史。
- 根据结果更新工单分类、优先级和状态。
- Python 服务失败时生成可审核的 fallback 结果。
- 给 React 返回稳定的业务 API 响应。

Java 使用 JPA 操作 H2 数据库。V1 会保存工单和分析记录，但当前演示数据会在服务重启时重新初始化，因此不能把它当成正式生产数据库。

### Python / FastAPI：AI 与 RAG 分析员

Python 负责：

- 校验 Java 传入的分析请求。
- 理解工单，生成分类、优先级、情绪和置信度。
- 根据工单内容构造检索问题。
- 从知识库检索最相关的片段。
- 基于检索证据生成回复建议。
- 检查风险并决定是否需要人工升级。
- 在 live 调用失败或证据不足时返回谨慎的 fallback 结果。

Python 不负责决定页面如何显示，也不是工单业务数据的主要存储位置。

## 3. 点击“开始分析”后发生了什么

完整主链路如下：

```text
1. 用户在 React 页面点击“开始分析”
2. React 记住当前正在分析的工单 ID
3. React 立即显示“分析中”
4. React 请求 POST /api/tickets/{id}/analyze
5. Java Controller 接收请求中的工单 ID
6. Java AnalysisService 查询完整工单
7. Java AiServiceClient 把工单内容发送给 Python /analyze
8. Python 分类工单并检索知识库
9. Python 根据证据生成回复建议和风险判断
10. Python 把 AnalysisResult 返回给 Java
11. Java 保存分析历史并更新工单
12. Java 把最终结果返回给 React
13. React 更新 tickets 状态
14. React 根据新状态重新渲染页面
15. React 取消“分析中”状态
```

这里有一个容易混淆的地方：页面上的“分析中”是 React 显示的状态。它表示请求还没有结束，并不表示只有 Java 在运行。此时可能是 Java 正在处理，也可能是 Java 正在等待 Python，或者 Python 正在检索和生成。

对应的 React 代码是：

```ts
const runAnalysis = async () => {
  setAnalyzingTicketId(selectedTicket.id)
  try {
    const result = await analyzeTicket(selectedTicket.id)
    // 用 result 更新当前工单
  } finally {
    setAnalyzingTicketId(null)
  }
}
```

可以先这样理解：

- `selectedTicket.id`：当前用户选中的工单编号。
- `setAnalyzingTicketId(...)`：告诉 React 哪一张工单正在分析。
- `analyzeTicket(...)`：向 Java 后端发送分析请求。
- `await`：先等待这个请求完成，再继续执行下一行。
- `result`：后端最终返回的完整分析结果。
- `finally`：无论请求成功还是失败，最后都要取消“分析中”。

`await` 只会暂停当前这个异步函数的后续代码，不会把整个浏览器页面冻住。React 仍然可以把“分析中”的状态显示出来。

## 4. result 里面有什么

`result` 的正式类型叫 `AnalysisResult`。它不是一句普通文本，而是一组有固定结构的数据。

```text
AnalysisResult
├── id：本次分析记录的 ID
├── traceId：贯穿本次请求的追踪标识
├── status：成功、失败或降级状态
├── mode：live、mock 或 fallback
├── classification
│   ├── category：建议分类
│   ├── priority：建议优先级
│   ├── sentiment：客户情绪
│   ├── confidence：系统对当前判断的把握程度
│   └── reasonSummary：判断理由摘要
├── workflowSteps：分析经过了哪些步骤
├── retrieval
│   ├── query：拿什么内容去搜索
│   └── hits：检索到的知识片段
├── suggestedReply
│   ├── content：回复建议
│   ├── citations：引用来源
│   └── warnings：风险警告
├── decision
│   ├── escalationRequired：是否需要升级人工
│   └── reason：升级或不升级的理由
└── usage：耗时和 token 用量
```

React、Java 和 Python 都有一份与它对应的数据定义。三边字段必须兼容，这叫做服务之间的**数据契约**。

## 5. 为什么一定要经过 Java

如果 React 绕过 Java，直接调用 Python，会出现几个问题：

- Python 需要同时承担 AI 分析和业务管理，职责混乱。
- 工单状态和分析历史没有稳定的业务层负责保存。
- AI 服务失败时，浏览器直接面对故障，整条业务链路更脆弱。
- 以后增加权限、审计、CRM 集成和业务规则会很困难。
- 浏览器会更接近内部 AI 服务，安全边界变差。

因此当前设计是：

```text
React 只认 Java 业务 API
Java 管理业务事实和分析记录
Python 提供可以失败、可以替换的 AI 能力
```

这也说明了一个重要思想：**AI 是辅助能力，不是业务事实的唯一来源。**

## 6. RAG 是什么，为什么需要它

大模型知道的是训练阶段获得的通用知识，它并不知道某家公司的最新退款政策、隐私流程、套餐规则和内部处理手册。

RAG 可以先简单理解为：

```text
先查公司资料，再让 AI 根据查到的资料回答
```

这个项目中的基本过程是：

```text
工单标题和描述
  -> 构造检索 query
  -> 在知识库中打分和排序
  -> 取最相关的 Top K 个片段
  -> 把片段作为证据
  -> 生成受证据约束的回复建议
```

`Top K` 表示最后选取得分最高的 K 个知识片段。当前 Java 请求配置为 `topK = 3`。

不能把全部知识库直接塞给模型，原因包括：

- 大量内容与当前问题无关。
- 输入更长，调用成本和处理时间更高。
- 无关内容会干扰模型判断。
- 真正关键的规定可能被淹没，降低回答准确性。

## 7. 置信度、证据和引用分别是什么

### 置信度

置信度表示系统对当前分类或判断的把握程度。

它不是经过现实验证的“答案正确率”。例如 `0.88` 不能直接解释为“答案有 88% 的概率正确”。它更适合被当作风险信号：置信度较低时，需要人工重点检查。

### 证据

证据是知识库检索得到的原始片段。它告诉审核人员：系统生成这条建议时参考了什么内容。

### 引用

引用把回复中的结论与证据来源连接起来。它方便客服或审核人员追溯出处，检查 AI 有没有乱说。

三者的关系可以记成：

```text
置信度：系统有多大把握
证据：系统参考了什么
引用：回答中的内容来自哪里
```

即使置信度很高，也不能代替证据。高置信度的错误仍然可能发生。

## 8. 证据不足时应该怎么做

当知识库没有找到足够相关的内容时，系统不应该凭模型“记忆”补全公司政策。

当前项目会采用更谨慎的处理方式：

- 把模式设为 `fallback`。
- 把状态设为 `FALLBACK`。
- 降低置信度。
- 在回复中加入“证据不足，禁止承诺处理结果”的警告。
- 要求人工确认处理边界。
- 把工单更新为需要升级或人工复核的状态。

fallback 不是假装成功，也不是把错误吞掉。它的目标是：**AI 能力出问题时，业务仍然能继续，而且人工清楚地知道这是一份降级结果。**

## 9. mock、live、fallback 和 demo 的区别

| 名称 | 是否调用 OpenAI | 含义 |
| --- | --- | --- |
| `mock` | 否 | Python 服务正常运行，但使用本地规则和本地打分，结果可重复，适合开发、测试和演示。 |
| `live` | 是 | Python 使用真实模型结构化输出和 Embedding 向量检索。 |
| `fallback` | 不一定 | live 调用失败、证据不足，或 Java 调不到 Python 时产生的谨慎降级结果，需要人工审核。 |
| 前端 `demo` | 否 | React 连 Java 都访问不到时，使用浏览器内置演示数据维持页面展示。 |

特别注意：`mock` 不是“没有后端”。在 mock 模式下，React、Java、Python 仍然可以完整通信，只是 Python 不调用外部 OpenAI API。

当前代码中存在三道保护：

```text
Python：live 调用失败 -> 本地 fallback
Java：Python 服务异常 -> Java 生成 fallback 并保存
React：Java 后端异常 -> 使用前端 demo 结果
```

前两种属于后端可审核降级。最后一种主要用于 V1 演示连续性，它不会写入 Java/H2，不能算正式持久化的业务结果。

## 10. traceId 是什么

`traceId` 是一次分析请求的追踪标识。

它像快递单号：工单 ID 表示“分析的是哪张工单”，traceId 表示“追踪这张工单的哪一次分析过程”。同一张工单可以分析很多次，每次应该有不同的 traceId。

以后查看前端请求、Java 日志、Python 日志和分析历史时，可以用它把同一次处理连接起来。

## 11. Controller 和 Service 为什么要分开

在 Java 后端中：

- `TicketController` 负责接收 HTTP 请求、读取路径中的工单 ID，并把任务交给业务层。
- `AnalysisService` 负责查询工单、调用 Python、处理异常、保存结果和更新工单状态。
- `AiServiceClient` 只负责把 Java 请求转换为 Python 能理解的 JSON，并调用 Python 的 `/analyze` 接口。

可以用餐厅来记：

```text
Controller：前台接单
Service：安排整套处理流程
AiServiceClient：把任务送到 AI 专区并把结果带回来
Repository + H2：保存工单和分析记录
```

如果把所有代码都写进 Controller，HTTP 接口、业务规则、外部调用和数据库操作会混在一起，后续很难测试和修改。

## 12. 当前已经建立的正确认识

- “分析中”是 React 根据状态显示的界面反馈，不是 AI 已经完成。
- `result` 来自后端响应，不是 React 自己编造的分析结果。
- Java 负责业务编排、保存结果和提供稳定 API。
- Python 负责 AI/RAG 工作流，但不是业务数据库。
- 工单 ID 用于确定分析对象，traceId 用于追踪某一次分析过程。
- RAG 的作用是让回答受到企业知识约束。
- Top K 是检索后保留的最相关 K 个片段。
- 置信度不是严格的正确率。
- 引用和证据用于追溯出处并审查幻觉。
- 证据不足时必须明确降级并交给人工，不能猜。
- mock 是完整的本地服务模式，不等于前端假数据。
- fallback 是带有明确风险标识的降级路径，不等于正常成功。

## 13. 关键代码地图

按一次分析请求的顺序阅读：

1. `apps/support-copilot-web/src/App.tsx`
   用户点击、`await`、页面状态更新。
2. `apps/support-copilot-web/src/services/api.ts`
   React 如何发送 `POST /api/tickets/{id}/analyze`。
3. `services/support-copilot-api/src/main/java/com/cyagent/supportcopilot/ticket/TicketController.java`
   Java 如何接收 HTTP 请求。
4. `services/support-copilot-api/src/main/java/com/cyagent/supportcopilot/analysis/AnalysisService.java`
   Java 如何编排、降级和保存。
5. `services/support-copilot-api/src/main/java/com/cyagent/supportcopilot/analysis/AiServiceClient.java`
   Java 如何把完整工单发给 Python。
6. `services/support-copilot-ai/app/main.py`
   Python `/analyze` 接口入口。
7. `services/support-copilot-ai/app/workflow.py`
   分类、检索、回复和风险判断工作流。
8. `services/support-copilot-ai/app/knowledge.py`
   mock 和 live 两种检索方式。

## 14. 面试时可以怎么讲

```text
Support Copilot V1 采用 React、Spring Boot 和 FastAPI 三层架构。
React 负责工单工作台和用户交互；Spring Boot 负责业务 API、工单状态、
分析记录持久化和服务降级；FastAPI 负责分类、RAG 检索、证据约束回复
和风险判断。系统不会直接让模型凭记忆回答，而是先检索企业知识库，
并在页面展示置信度、证据和引用，方便人工审核。当模型调用失败或证据
不足时，系统会返回带有明确标识的 fallback 结果并升级人工，避免 AI
故障阻断业务，也避免把没有依据的内容当成正式答案。
```

## 15. 已完成的基础自测

下面的问题已经在会话中逐题回答过。这里保留它们，供以后复习时重新口述，不再把它们当作新的学习进度。

1. 用户点击“开始分析”后，为什么页面可以立刻显示“分析中”，而不需要等 Java 返回？
2. `await analyzeTicket(selectedTicket.id)` 正在等待时，React、Java 和 Python 分别可能处于什么状态？
3. 为什么不能只把工单 ID 发给 Python，而完全不发送标题和描述？
4. 为什么同一张工单需要同时拥有工单 ID 和 traceId？
5. mock 模式不调用 OpenAI，为什么它仍然不等于“纯前端假页面”？
6. Python 已经有 fallback，Java 为什么还需要自己的 fallback？
7. 当 `retrieval.hits` 为空时，系统为什么不能生成一个听起来合理的退款政策？
8. 置信度为 `0.95` 时，为什么仍然要展示引用？
9. 如果 React 使用前端 demo 结果，这份结果为什么不会出现在 Java 的分析历史里？
10. 用自己的话讲一遍：一次分析请求如何从浏览器出发，最后重新显示在页面上？

## 16. 当前学习进度

基础主链路、三层职责和 V1 第一轮审查已经完成。当前进度不再停留在 `useState` 入门，而是已经覆盖以下内容。

### React

- `useState` 如何保存页面状态，`setTickets` 如何触发重新渲染。
- `await`、`try`、`catch`、`finally` 在分析请求中的作用。
- `map`、对象展开和不可变更新为什么能让 React 发现数据变化。
- `selectedTicketId`、`analyzingTicketId` 和 `latestAnalysis` 分别表示什么。
- 父组件通过 props 传递数据，通过回调接收子组件事件。
- 单个 `analyzingTicketId` 为什么无法可靠表示并行分析。
- 乐观更新失败后为什么必须回滚或重新获取服务器数据。

### Java / Spring Boot

- Controller、Service、Client 和 Repository 的职责边界。
- JPA 实体、`@Entity`、`@Id`、`@Column` 和 `@Version`。
- 事务必须保证 `AnalysisRun` 和 `Ticket` 一起成功或一起回滚。
- Spring 事务依赖代理，同一个 Service 内部调用事务方法可能绕过代理。
- 事务应尽量短，不应在等待 Python 和 OpenAI 时一直占用数据库资源。
- 后端必须校验状态值和状态转换，不能完全依赖 React。
- 客户端版本冲突应返回 `409 Conflict`，而不是悄悄覆盖新数据。

### Python / AI / RAG

- mock、live、fallback 和前端 demo 的区别。
- Embedding、向量检索、Top N、Top K 和 rerank 的基本关系。
- 第一次构建向量库为什么更慢，以及异步锁为什么能避免重复构建。
- 证据、引用、置信度和 groundedness 分别解决什么问题。
- Hit Rate@3、MRR 和 citation accuracy 需要真实评估集才能计算。
- fallback 应处理预期的外部故障，不能掩盖程序代码错误。

### 系统设计与生产边界

- Authentication 回答“你是谁”，Authorization 回答“你能做什么”。
- CORS 不是鉴权，`permitAll()` 也不适合真实客服系统。
- 工单正文发送给外部模型前需要识别和脱敏敏感数据。
- 幂等键防止同一次业务操作重复执行，`traceId` 用于追踪执行链路。
- TypeScript 类型只在编译期生效，网络 JSON 仍需要运行时校验。
- OpenAPI 或契约测试可以降低三种语言手写类型造成的漂移风险。

这不表示已经学完 React、Spring Boot 或 FastAPI。当前真正完成的是：**能够沿着一个真实项目的主链路读代码，并开始从数据一致性、安全性、可靠性和可审计性角度审查系统。**

## 17. V1 第一轮审查发现

下面 29 项都已经在会话中讲解过。它们是审查结果，不代表已经修改完成。

### 生产安全与数据一致性

1. `saveRun()` 的 `@Transactional` 可能因同类内部调用而不生效，导致分析记录和工单只保存一半。
2. 生产环境不应在 Java 请求失败后自动使用 React 本地模拟结果，否则客服可能把假结果当成真实分析。
3. Python 与 Java 的高风险分类规则不一致，`SECURITY` 等分类可能没有被统一升级人工。
4. H2 是内存数据库且使用 `create-drop`，Java 重启后业务数据会消失。
5. H2 Console 和演示数据初始化器没有环境隔离，不应直接进入生产配置。
6. Java 更新接口接受任意字符串状态，`BANANA` 也可能进入数据库。
7. `@Version` 没有暴露给 API，Java 无法完整识别客户端拿着旧页面提交更新。
8. 没有明确处理乐观锁异常并返回 `409 Conflict`。
9. Spring Security 对所有 Java 请求使用 `permitAll()`，系统没有真实身份认证和权限校验。
10. live 模式会把工单正文原样发给 OpenAI，目前没有实际脱敏流程。
11. Java 15 秒超时短于 Python/OpenAI 20 秒单次超时和重试预算，Java 可能先降级而 Python 仍在工作。
12. 分析请求没有幂等机制，网络重试可能重复调用 AI 并创建多条记录。

### 接口可靠性与可观测性

13. `response.json() as Promise<T>` 只是类型断言，没有验证真实 JSON 结构。
14. mock 模式忽略 `topN`，`enableRerank` 也没有真正参与检索流程。
15. Java fallback 会重新生成 `traceId`，可能让同一次请求的追踪链路断开。
16. Java 明确返回 `latestAnalysis: null`，TypeScript 却把它定义成可选字段，空值契约不一致。
17. Java 已提供分析历史接口，但前端事件区只展示最新分析，没有使用历史数据。
18. Java 返回结构化错误，React 却只保留 HTTP 状态码，丢失错误代码、消息和 `traceId`。
19. React 领取工单时先更新本地负责人，请求失败后没有回滚，页面和数据库可能不一致。
20. 页面只检查 Java API 是否可用，Python 停止时仍可能显示“业务 API 已连接”。
21. Python 的检索环境变量没有真正控制运行参数，实际参数由 Java 请求写死。
22. Python live 工作流捕获所有 `Exception`，可能把程序错误伪装成普通 fallback。
23. 单个 `analyzingTicketId` 无法正确跟踪多张并行分析的工单。

### 真实性验证与可维护性

24. 多数页面指标是硬编码演示值，不是真实运行结果。
25. “SLA 风险”实际上只按优先级计算，没有检查截止时间和工单状态。
26. 项目没有真实评估集和计算脚本，不能把页面上的 Hit Rate@3 `88.6%` 当成真实测量结果。
27. React 没有自动测试，三服务也没有覆盖完整用户链路的端到端测试。
28. TypeScript、Java 和 Python 手写重复接口类型，存在契约漂移风险。
29. `App.tsx` 超过 1300 行，同时承担布局、状态和业务交互，后续需要逐步拆分。

## 18. 如何评价当前 V1

### V1 已经做好的部分

- React、Java、Python 三个服务形成了可以运行的端到端链路。
- Java 保留业务数据库和分析历史，Python 只提供可替换的 AI 能力。
- mock、live 和 fallback 有明确模式标识，没有把所有结果都伪装成真实模型输出。
- 页面展示证据、引用、置信度和升级决策，具备可审核 AI 的基本形状。
- Python 或 OpenAI 失败时，Java 仍能返回明确的降级结果，业务不会直接中断。

### V1 还不能声称的部分

- 不能声称已经达到生产可用，因为鉴权、隐私、持久化、并发和错误处理仍不完整。
- 不能声称页面指标是真实模型质量，因为还没有评估集和计算链路。
- 不能声称前端和后端契约绝对安全，因为类型仍然手写，网络响应也没有运行时校验。
- 不能把本地 demo 或 fallback 当成正常 live AI 结果。

因此最准确的定位是：**V1 是一个结构完整、可以演示和审查的本地端到端原型，但还不是生产客服系统。**

## 19. 审查优先级

如果以后进入 V1.5 实现阶段，建议按下面顺序处理，而不是一次修改全部问题。

### 第一组：先保护真实业务数据

1. 修复事务边界，确保分析记录和工单原子保存。
2. 引入合法状态、状态转换规则、客户端版本和 `409` 冲突处理。
3. 删除生产环境的前端本地模拟成功路径，失败时保留原数据并明确报错。
4. 加入分析请求幂等键，防止重复 AI 调用和重复记录。

### 第二组：再保护用户和公司数据

1. 增加真实身份认证和权限校验。
2. 在发送外部模型前执行敏感数据识别、脱敏和审计。
3. 用环境配置隔离 H2 Console、演示初始化器和生产数据库。

### 第三组：提高接口和 AI 链路可靠性

1. 统一 OpenAPI 契约，解析结构化错误并校验运行时 JSON。
2. 保持 `traceId` 贯穿 React、Java 和 Python。
3. 调整超时预算、健康检查和异常捕获范围。
4. 让 Top N、Top K、rerank 和环境变量具有一致且可验证的含义。

### 第四组：最后证明系统真的有效

1. 建立真实评估集和指标计算脚本。
2. 增加 React 测试、Java/Python 契约测试和完整端到端测试。
3. 拆分 `App.tsx`，降低单文件维护成本。

## 20. 本阶段收尾

V1 第一轮学习和审查到这里可以收尾。后续不再重复已经回答过的选择题，也暂时不直接修改代码。

下一阶段的合理入口是：从第一组中的一个真实问题开始，先写出“当前行为、风险、目标行为和验收方式”，再阅读相关代码并设计最小修改。

已经完成的 V1.5 设计学习：

- [`V1_5_TRANSACTION_DESIGN.md`](./V1_5_TRANSACTION_DESIGN.md)：事务边界、版本冲突和原子保存。
- [`V1_5_TICKET_COMMAND_AUDIT_DESIGN.md`](./V1_5_TICKET_COMMAND_AUDIT_DESIGN.md)：PATCH 三态、业务命令和审计事件。

# Support Copilot

面向企业客服场景的智能工单辅助平台 V1。

Support Copilot 用模拟企业客服场景展示完整的 AI 应用工程链路：工单进入系统后，由 Java 业务 API 保存和编排，Python AI 服务完成结构化分类、知识检索、证据约束回复与风险判断，React 工作台展示可审计的处理轨迹并保留人工审核入口。

## 当前能力

- 企业 SaaS 风格工单工作台，支持队列筛选、工单切换和 SLA 风险展示。
- 工单分类、优先级、情绪、置信度与人工升级建议。
- 检索查询、Top K 知识片段、来源、分数和引用展示。
- 建议回复编辑、采纳和风险提示。
- 运营概览、知识目录演示页和质量评估占位视图；只有接入可追溯报告后才展示评估数字。
- H2 工单与分析运行持久化。
- FastAPI `mock`、`live` 和 `fallback` 三种运行模式。
- Java 到 Python 的超时与业务降级。
- OpenAI Responses API 结构化输出和进程内向量检索的 live 模式；2026-08-26 已在干净提交上完成一次真实 Embedding、VECTOR 检索、结构化生成和 Java 持久化验收。

## 技术架构

```text
React + TypeScript + Ant Design + ECharts
                    |
                    | /api
                    v
       Java 21 + Spring Boot + JPA + H2
                    |
                    | /analyze
                    v
      Python 3.11 + FastAPI + LangChain
                    |
                    | Responses / Embeddings
                    v
                 OpenAI API
```

详细的产品目标、架构、数据模型、接口、学习路线与面试材料见 [项目总纲](docs/PROJECT_BLUEPRINT.md)。

## 目录

```text
apps/support-copilot-web/       React 前端
services/support-copilot-api/   Spring Boot 业务 API
services/support-copilot-ai/    FastAPI AI 与 RAG 服务
infra/                          V2 基础设施配置
docs/                           项目设计和维护文档
```

RAG 理论课程、词汇表和学习记录保留在独立的 `CY-Agent` 学习仓库中，不与本项目源码混合管理。

## 环境要求

- Node.js 24（LTS）
- Java 21
- Python 3.11
- npm

V1 默认使用 H2 和本地知识数据，不需要 Docker、MySQL 或 Redis。

## 快速启动

需要三个终端。建议先启动 AI 服务和 Java API，再启动前端。

启动前先在仓库根目录执行一次本地依赖检查：

```bash
./scripts/check-local-startup.sh --preflight
```

它只检查 Node.js、Java、Python、curl、Python 虚拟环境、Gradle Wrapper 和前端依赖是否准备好，不会启动服务。

### 1. AI 服务

首次运行：

```bash
cd services/support-copilot-ai
python3 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements-dev.lock.txt
```

`requirements.txt` 和 `requirements-dev.txt` 声明允许使用的版本范围；日常安装使用锁文件，确保直接依赖和间接依赖保持在已经验证的准确版本。修改依赖范围后，在 AI 服务目录重新生成锁文件：

```bash
.venv/bin/python -m uv pip compile --universal --python-version 3.11 --generate-hashes --output-file requirements.lock.txt requirements.txt
.venv/bin/python -m uv pip compile --universal --python-version 3.11 --generate-hashes --output-file requirements-dev.lock.txt requirements-dev.txt
```

以上命令会优先保留现有锁定版本；需要主动升级全部依赖时，再额外添加 `--upgrade`。

提交 Python 依赖变更前，检查范围文件和锁文件是否同步：

```bash
.venv/bin/python -m scripts.check_dependency_locks
```

检查器只在临时目录重新生成并比较锁文件，不会修改仓库文件。检查失败时，先使用上面的生成命令更新两个锁文件，再重新运行测试和 mock 评估。

启动默认 mock 模式：

```bash
cd services/support-copilot-ai
.venv/bin/python -m uvicorn app.main:app --reload --port 8000
```

健康检查：

```bash
curl http://localhost:8000/health
```

API 文档：`http://localhost:8000/docs`

### 2. Java 业务 API

```bash
cd services/support-copilot-api
./gradlew bootRun
```

健康检查：

```bash
curl http://localhost:8080/actuator/health
```

工单接口：

```bash
curl http://localhost:8080/api/tickets
curl http://localhost:8080/api/metrics
curl -X POST http://localhost:8080/api/tickets/ticket-10042/analyze
```

### 3. React 前端

首次运行：

```bash
cd apps/support-copilot-web
npm install
```

启动：

```bash
cd apps/support-copilot-web
npm run dev
```

浏览器访问：`http://localhost:5173`

Vite 会把 `/api` 代理到 `http://localhost:8080`。如果 Java API 未启动，前端会进入有明确标识的演示数据模式。

三个服务都启动后，在另一个终端执行真实 HTTP 健康检查：

```bash
./scripts/check-local-startup.sh --health
```

健康检查只会在 Python、Java 和 React 三个 HTTP 地址都可访问且返回预期状态时通过。也可以使用 `--all` 连续执行启动前检查和健康检查。

如果需要一次性验证 mock 模式的三服务链路，可以使用隔离端口运行 smoke 检查：

```bash
./scripts/run-local-smoke.sh
```

该脚本会启动临时的 Python、Java 和 React 进程，等待三个健康端点通过，再执行 mock 成功分析和前端运行时契约检查。默认使用 `18000`、`18080` 和 `15173`，不会占用常用的 `8000`、`8080` 和 `5173`；检查结束后只清理脚本自己启动的进程。端口被占用时脚本会直接失败，不会停止已有服务。可以通过 `SUPPORT_COPILOT_SMOKE_AI_PORT`、`SUPPORT_COPILOT_SMOKE_JAVA_PORT` 和 `SUPPORT_COPILOT_SMOKE_WEB_PORT` 覆盖默认端口。

### 跨服务分析流程检查

三个服务启动后，通过 React 代理验证一次成功分析：

```bash
./scripts/check-local-analysis-flow.sh --success
```

要让真实工单列表、指标和分析 JSON 经过 React 页面实际使用的 Zod Schema，再运行契约门禁：

```bash
./scripts/check-local-analysis-flow.sh --contract
```

该命令会复用前端生产 API 客户端，而不是在 Shell 中维护第二套完整字段清单；它还会刷新工单并确认最新分析已经可见，再检查 Java 分析历史。普通 `npm run test` 不会连接本地服务，只有显式运行契约门禁时才执行这 3 条集成测试。

故障演练时，先停止 Python AI 服务，再执行 Java fallback 检查：

```bash
./scripts/check-local-analysis-flow.sh --fallback
```

检查完成后重新启动 Python。脚本会验证分析模式、状态、`fallbackReason`、`traceId`、证据或人工复核警告，以及 Java 分析历史中的最新记录；它不会自动停止或启动任何服务。受控演练其他故障时，可通过 `SUPPORT_COPILOT_EXPECTED_FALLBACK_REASON` 指定期望原因；完整值域见 [fallback 原因契约](docs/contracts/fallback-reason-contract.md)。

也可以指定一个可审计的追踪号，检查它是否贯穿 React 代理、Java 响应和 Python 日志：

```bash
SUPPORT_COPILOT_TRACE_ID=interview-flow-01 ./scripts/check-local-analysis-flow.sh --success
```

Java 会在没有请求头时生成 `X-Trace-Id`，并将同一个值写入响应头、分析响应和日志上下文；Python 日志会记录该值以及分析模式和状态。

同一工单的重复在途请求会先在浏览器 API 层合并；Java 再按 `ticketId + sourceTicketVersion + analysisPolicyVersion` 保证单实例内只调用一次 Python 并保存一次结果。执行结束后会释放键，因此后续人工重试仍会真正运行。该能力不是跨实例的持久化幂等，完整边界见 [分析在途请求合并契约](docs/contracts/analysis-single-flight-contract.md)。

React 不直接相信 Java 返回的 2xx JSON。工单、指标、分析和工单命令响应会先通过 Zod 运行时 Schema，缺字段、错误类型或未知枚举会在进入页面状态前转换为 `ApiContractError`；完整范围见 [前端运行时响应契约](docs/contracts/frontend-runtime-schema-contract.md)。

## OpenAI 实时模式

默认 `AI_MODE=mock` 不调用外部 API，适合开发、测试和面试环境预检。

外部知识不需要再手工切成 JSON。先把经过授权或脱敏的 Markdown、文本型 PDF 和清单放在仓库外；清单结构可参考 [knowledge-manifest.example.json](services/support-copilot-ai/knowledge-manifest.example.json)。文档路径必须相对于清单目录，不能读取该目录之外的文件。

```bash
cd services/support-copilot-ai
.venv/bin/python -m scripts.build_knowledge_corpus \
  --manifest '/absolute/path/to/knowledge-manifest.json' \
  --output '/absolute/path/to/authorized-knowledge.json'
```

命令会确定性地按 Markdown 标题或 PDF 页码分节，再按清单中的 `chunk_size` 和 `chunk_overlap` 切块。它同时生成 `authorized-knowledge.provenance.json`，记录索引版本、源文件哈希、文档版本和片段 ID，但不保存正文。相同输入重复构建会得到相同的 corpus 和 provenance。

启用实时模式前设置：

```bash
cd services/support-copilot-ai
export AI_MODE=live
export OPENAI_API_KEY='your-api-key'
export OPENAI_EMBEDDING_API_KEY='your-embedding-api-key'
export OPENAI_CHAT_MODEL='your-chat-model'
export OPENAI_EMBEDDING_MODEL='your-embedding-model'
export OPENAI_BASE_URL='https://your-chat-gateway.example/v1'
export OPENAI_EMBEDDING_BASE_URL='https://your-embedding-gateway.example/v1'
export KNOWLEDGE_PATH='/absolute/path/to/authorized-knowledge.json'
export KNOWLEDGE_PROVENANCE_PATH='/absolute/path/to/authorized-knowledge.provenance.json'
.venv/bin/uvicorn app.main:app --reload --port 8000
```

`KNOWLEDGE_PATH` 不设置时继续使用仓库内的演示知识文件。设置后，Python 会在启动时读取仓库外的授权知识文件，并要求它是 JSON 数组；每个片段必须包含唯一的 `chunk_id`、`document_id`、`document_title`、`section`、`content`、`source_uri`、`categories`、`keywords`、`document_version`、`status` 和 `updated_at`。`ARCHIVED` 片段不会进入检索。可参考 [默认知识文件](services/support-copilot-ai/app/data/knowledge.json) 的结构。无效字段、空字段、未知字段和重复片段 ID 会直接阻止服务启动，原始知识正文不会写入校验错误。

`KNOWLEDGE_PROVENANCE_PATH` 对手工预切分 JSON 是可选项；使用导入命令生成 corpus 时应同时配置。服务会检查 provenance 中的 corpus 哈希，文件缺失、结构非法或哈希漂移都会阻止启动。当前 PDF 导入只支持自带文本层的文件；扫描件需要后续 OCR 流程，不能静默当作空知识使用。

外部知识文件只应包含公开、已获授权或完成脱敏的数据，建议放在仓库外并使用绝对路径，不能把真实客户隐私或内部凭据提交到 Git。

可选配置：

```bash
# Chat/Responses endpoint. Omit for the official OpenAI endpoint.
export OPENAI_BASE_URL='https://your-chat-gateway.example/v1'
# Embeddings endpoint. Omit to reuse OPENAI_BASE_URL.
export OPENAI_EMBEDDING_BASE_URL='https://your-embedding-gateway.example/v1'
# Optional: use a different credential when the embedding provider is separate.
export OPENAI_EMBEDDING_API_KEY='your-embedding-api-key'
export OPENAI_TIMEOUT_SECONDS=20
export OPENAI_MAX_RETRIES=1
export AI_PROCESSING_TIMEOUT_SECONDS=90
export AI_SERVICE_TIMEOUT_MS=105000
export SUPPORT_COPILOT_HTTP_TIMEOUT_SECONDS=120
export RETRIEVAL_TOP_N=10
export RETRIEVAL_TOP_K=3
export MOCK_RETRIEVAL_MIN_SCORE=0.25
export LIVE_RETRIEVAL_MIN_SCORE=0.35
```

超时按外层晚于内层的顺序配置：单次正式 API 请求最长 20 秒并最多重试 1 次，Python 整体分析在 90 秒停止，Java 最长等待 105 秒，live 验收客户端最长等待 120 秒。首次 live 请求可能依次创建知识向量、生成查询向量并调用聊天模型；Python 总截止时间优先于 SDK 的后续重试，避免 Java 已降级后 Python 仍继续消耗调用预算。`OPENAI_BASE_URL` 只控制聊天/Responses 请求；`OPENAI_EMBEDDING_BASE_URL` 控制 Embedding 请求，未设置时回退到 `OPENAI_BASE_URL`。`OPENAI_EMBEDDING_API_KEY` 可为独立 Embedding 服务提供单独凭据，未设置时回退到 `OPENAI_API_KEY`。mock 检索会拒绝低于 `MOCK_RETRIEVAL_MIN_SCORE` 的弱词面匹配；live `InMemoryVectorStore` 使用余弦相似度，并拒绝低于 `LIVE_RETRIEVAL_MIN_SCORE` 的结果。两个阈值都应在真实 live 评估后根据脱敏分数分布校准。`check-live-rag.sh --preflight` 会拒绝倒置或余量不足的配置，不会调用外部 API。

在调用正式 API 前先执行只读预检；它不会发出外部请求：

```bash
./scripts/check-live-rag.sh --preflight
```

确认 Python 以 live 模式启动，并且 Java、React 都已启动后，执行真实跨服务验收：

```bash
./scripts/check-live-rag.sh --success
```

`--success` 会实际调用正式 Embedding 和聊天模型 API，验证 `mode=live`、向量证据、引用、token、`traceId` 和 Java 分析历史，并在 `services/support-copilot-ai/evaluation/reports/` 生成脱敏 Markdown 记录。记录包含知识来源类型、格式、片段数量和 SHA-256；配置 provenance 时还会记录索引版本、源文档数量和清单 SHA-256，但不包含本地路径或知识正文。该目录默认被 Git 忽略；真实成功后必须先人工确认记录中没有密钥或客户数据，再选择性强制加入 Git。

不要把 API Key 写入代码或提交到 Git。ChatGPT 产品订阅不等同于 OpenAI API Key。

运行模式含义：

| 模式 | 行为 |
| --- | --- |
| `mock` | 使用本地可重复分类和检索，不调用 OpenAI |
| `live` | 使用 OpenAI 结构化输出与 Embedding |
| `fallback` | 实时调用失败或证据不足，保留人工处理路径 |

前端和分析响应都会显示实际模式，防止把演示结果误认为真实模型输出。

## 测试与构建

前端：

```bash
cd apps/support-copilot-web
npm ci
npm run lint
npm run test
npm run build
```

Java：

```bash
cd services/support-copilot-api
./gradlew test
```

Python：

```bash
cd services/support-copilot-ai
.venv/bin/pytest -q
```

Mock 评估：

```bash
cd services/support-copilot-ai
.venv/bin/python -m evaluation.run_mock_evaluation
```

评估报告会写入 `services/support-copilot-ai/evaluation/reports/`，并刷新 `mock-latest.json` 与 `mock-latest.md`。它只反映固定模拟工单上的 mock 工作流，不代表真实模型或生产 RAG 效果。报告逐案例保存 retrieved/cited chunk 映射。评估集维护说明见 [Mock 评估](services/support-copilot-ai/evaluation/README.md)；[2026-08-24 Mock 评估基线](docs/verification/mock-evaluation-2026-08-24.md) 是历史提交记录，不代表当前 HEAD。

Java 指标接口会按 `EVALUATION_REPORT_PATH` 读取 `mock-latest.json`，再把报告中的数据集、样本数、模型、Prompt 版本、Top N/K、Hit@K、MRR、引用覆盖率、无证据安全率、P95 和门禁状态传给质量页面。默认路径是从 `services/support-copilot-api/` 启动 Java 时的 `../support-copilot-ai/evaluation/reports/mock-latest.json`；没有报告、报告损坏或字段不兼容时，接口仍返回工单指标，但 `evaluation` 为 `null`。

### 自动化 CI

GitHub Actions 会在每次 `push` 和 Pull Request 时分别验证 Python AI 服务、Java 业务 API 和 React 前端。

Python AI CI：

```text
按锁文件安装开发依赖
-> 检查范围文件与锁文件是否同步
-> 运行 Python 测试
-> 运行固定 mock 评估
```

任意一步返回非零退出码，整个 `Python AI CI` 任务都会失败。工作流定义见 [`.github/workflows/python-ai-ci.yml`](.github/workflows/python-ai-ci.yml)。CI 只使用 mock 模式，不需要 OpenAI API Key，也不会调用真实模型。

Java API CI：

```text
安装 Java 21
-> 验证 Gradle Wrapper 并恢复依赖缓存
-> 编译 Java 代码和测试
-> 运行全部 Java 测试
```

Java 工作流定义见 [`.github/workflows/java-api-ci.yml`](.github/workflows/java-api-ci.yml)。它使用内存 H2 和测试 mock，不需要另外启动 MySQL、Python 或 React。

React Web CI：

```text
安装 Node.js 24 并恢复 npm 下载缓存
-> 按 package-lock.json 安装依赖
-> 运行前端静态检查
-> 运行前端 API 单元测试
-> 执行 TypeScript 检查和生产构建
```

React 工作流定义见 [`.github/workflows/react-web-ci.yml`](.github/workflows/react-web-ci.yml)。它不会复用开发者本机的 `node_modules`；依赖安装、lint、单元测试或 build 任意一步失败，整个任务都会失败。

## 关键接口

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/tickets` | 查询工单队列 |
| GET | `/api/tickets/{id}` | 查询工单详情 |
| POST | `/api/tickets` | 创建工单 |
| PATCH | `/api/tickets/{id}` | 修改状态、分类、优先级或负责人 |
| POST | `/api/tickets/{id}/unassign` | 按工单版本取消负责人 |
| POST | `/api/tickets/{id}/analyze` | 触发分析 |
| GET | `/api/tickets/{id}/analyses` | 查询分析历史 |
| POST | `/api/tickets/{id}/analyses/{analysisId}/reviews` | 采纳或编辑后采纳最新回复建议 |
| POST | `/api/tickets/{id}/analyses/{analysisId}/reviews/reject` | 拒绝最新回复建议并记录必填原因 |
| GET | `/api/tickets/{id}/analyses/{analysisId}/reviews` | 查询分析审核历史 |
| GET | `/api/knowledge/search` | 调试知识检索 |
| GET | `/api/metrics` | 查询当前工单、已持久化运行态指标和可追溯 mock 评估报告；没有来源的数据返回空值 |
| POST | `/analyze` | Java 调用的 AI 服务内部接口 |

## 演示建议

1. 打开工单工作台，选择“本月套餐出现重复扣款”。
2. 查看结构化分类、置信度和支付争议升级规则。
3. 打开“知识依据”，检查文档片段和引用。
4. 打开“回复建议”，编辑后采纳，或拒绝建议并填写原因，再展开审核历史。
5. 选择“能否恢复三个月前删除的项目”，展示无证据时的拒绝承诺与人工复核。
6. 切换运营概览和质量评估，展示评估报告的来源、指标和门禁状态；删除或改坏报告后，页面会回到“暂无评估报告”，不会保留静态数字。

## 当前限制

- V1 使用 H2 和内存向量存储，服务重启后业务数据会重新初始化。
- 回复审核会持久化原始建议、采纳后的内容或拒绝原因、动作、工单版本和 `traceId`；当前审核人固定为未认证的演示身份，不代表已经具备登录、RBAC 或可信生产审计。
- mock 检索用于可重复演示，不代表真实语义检索质量。
- 质量页只读取 `EVALUATION_REPORT_PATH` 指向的评估报告；报告没有接入持久化评估运行表，文件被替换或删除后需要重新加载页面。
- 实时 OpenAI 模式需要用户自己的 API Key 和可用模型配置。
- 真实 live 记录只证明一次脱敏合成工单的端到端链路成功，不代表稳定性、质量基准、生产延迟或成本结论。
- 当前没有真实 CRM、邮件、支付或身份系统集成。
- V2 的 MySQL、Redis、向量数据库、Docker Compose 和自动化部署/CD 尚未实现；当前已有三条 GitHub CI，但不包含部署。

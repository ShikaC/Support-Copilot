# Support Copilot

面向企业客服场景的智能工单辅助平台 V1。

Support Copilot 用模拟企业客服场景展示完整的 AI 应用工程链路：工单进入系统后，由 Java 业务 API 保存和编排，Python AI 服务完成结构化分类、知识检索、证据约束回复与风险判断，React 工作台展示可审计的处理轨迹并保留人工审核入口。

## 当前能力

- 企业 SaaS 风格工单工作台，支持队列筛选、工单切换和 SLA 风险展示。
- 工单分类、优先级、情绪、置信度与人工升级建议。
- 检索查询、Top K 知识片段、来源、分数和引用展示。
- 建议回复编辑、采纳和风险提示。
- 运营概览、知识目录演示页和质量评估占位视图；只有接入可追溯报告后才展示评估数字。
- `demo`/`test` 使用隔离 H2；`local`/`pilot` 已准备 Flyway 管理的 MySQL 8 配置与 migration 契约，实库验证留待 Task 15。
- Java Resource Server 已按 `SUPPORT_AGENT`、`SUPPORT_REVIEWER`、`SUPPORT_ADMIN` 执行 JWT 角色门禁；真实 pilot OIDC/MySQL 联调仍留待 Task 15。
- Java 调用 Python 时使用仅服务端可见的 `X-Internal-Service-Token`；Python `/health` 公开，`/analyze` 在进入工作流前校验该凭据。
- 工单创建/实际变更、分析持久化和人工审核会在同一事务写入不可编辑的可信审计事件；事件只保存 JWT/演示身份、受控动作与目标、版本、`traceId` 和白名单元数据。
- FastAPI `mock`、`live` 和 `fallback` 三种运行模式。
- Java 到 Python 的超时与业务降级。
- OpenAI Responses API 结构化输出和进程内向量检索的 live 模式；2026-08-26 已在干净提交上完成一次真实 Embedding、VECTOR 检索、结构化生成和 Java 持久化验收。

## 技术架构

```text
React + TypeScript + Ant Design + ECharts
                    |
                    | /api
                    v
  Java 21 + Spring Boot + JPA + H2/MySQL 8
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

Java API 没有隐式数据库配置。必须且只能明确选择 `demo`、`test`、`local` 或 `pilot` 中的一个；未选择、显式选择 `default`、使用未知 profile 或同时选择多个 profile，都会在创建 datasource 前拒绝启动，错误会列出允许的四个 profile，避免 Spring Boot 自动打开嵌入式 H2。

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
export SUPPORT_COPILOT_INTERNAL_SERVICE_TOKEN='synthetic-local-development-token'
.venv/bin/python -m uvicorn app.main:app --reload --port 8000
```

同一次本地运行中的 Java 和 Python 必须使用相同的 `SUPPORT_COPILOT_INTERNAL_SERVICE_TOKEN`。该值只属于服务间身份，不得放进 React 环境变量、浏览器请求、日志或错误响应。`/health` 不需要该 header；直接调用 `/analyze` 必须发送精确 header `X-Internal-Service-Token`。

Python 服务在构造 FastAPI 应用时要求该变量存在且非空；缺失或空值会以包含变量名的配置错误终止启动，因此错误配置的进程不会开放 `/health`。`.env.example` 只保留空占位，不提供生产默认值。

健康检查：

```bash
curl http://localhost:8000/health
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
```

`/health` 保留原有 mode、liveReady 和知识片段字段；`/health/live` 只证明进程可响应。`/health/ready` 不主动探测外部 API，而是读取线程安全的进程内运行状态：live Embedding/索引失败后 provider 与 index 均 degraded，结构化生成失败只让 provider degraded；对应阶段后续成功后恢复，degraded 时返回 `503`。状态启动值仍来自已校验配置和 corpus，只有实际 live 请求才能暴露惰性初始化或运行期故障；并发时每个阶段最后完成的已观察结果生效，进程重启后状态重新初始化。这不是 Task 9 的持久化索引生命周期。探针不返回路径、凭据或正文。所有响应都返回 `X-Trace-Id`。`/analyze` 的 header 与 body `traceId` 都只接受 1 至 80 个安全 ASCII 字符且必须相同；Python 只使用经过校验的 header trace 写响应和日志，不匹配时在进入工作流前返回 `400 TRACE_ID_MISMATCH`。认证、校验、处理超时和未处理程序错误使用稳定的顶层 `code`、`message`、`traceId`、`details` envelope；程序错误返回 500，不进入 AI fallback。

API 文档：`http://localhost:8000/docs`

### 2. Java 业务 API

```bash
cd services/support-copilot-api
export SUPPORT_COPILOT_INTERNAL_SERVICE_TOKEN='synthetic-local-development-token'
./gradlew bootRun --args='--spring.profiles.active=demo'
```

`demo` 使用内存 H2、`create-drop`、H2 Console 和 8 条演示工单，只适合本地演示。H2 Console 位于 `http://localhost:8080/h2-console`。`test` 也使用随机命名的隔离 H2 和 `create-drop`，但不加载演示数据且不开放 H2 Console；Gradle 集成测试通过 `@ActiveProfiles("test")` 显式选择它。

`local` 和 `pilot` 都配置为连接 MySQL 8、执行 Flyway migration 并让 Hibernate 使用 `validate`，不加载演示数据，也不开放 H2 Console。两者要求数据库配置、服务间 token，以及 JWT issuer 或 JWK Set 地址存在且非空：

```bash
cd services/support-copilot-api
export SUPPORT_COPILOT_DB_URL='jdbc:mysql://127.0.0.1:3306/support_copilot?useSSL=false&serverTimezone=UTC'
export SUPPORT_COPILOT_DB_USERNAME='your-database-user'
export SUPPORT_COPILOT_DB_PASSWORD='your-database-password'
export SUPPORT_COPILOT_INTERNAL_SERVICE_TOKEN='inject-a-non-browser-service-token'
export SUPPORT_COPILOT_JWT_ISSUER_URI='https://your-issuer.example'
# 也可以改用 SUPPORT_COPILOT_JWT_JWK_SET_URI；两者至少配置一个。
./gradlew bootRun --args='--spring.profiles.active=local'
```

`pilot` 使用同一组环境变量，但没有任何 H2 或凭据回退；缺少或留空 JDBC 设置会拒绝启动：

```bash
./gradlew bootRun --args='--spring.profiles.active=pilot'
```

AI 服务与质量报告配置在四个 profile 中保持一致，可继续通过 `AI_SERVICE_BASE_URL`、`AI_SERVICE_TIMEOUT_MS`、`AI_SERVICE_RETRY_MAX_ATTEMPTS`、`AI_SERVICE_RETRY_WAIT_MS`、`AI_SERVICE_CIRCUIT_*`、`AI_SERVICE_BULKHEAD_*` 和 `EVALUATION_REPORT_PATH` 覆盖。可靠性参数在启动时校验边界和交叉约束，非法值拒绝启动。`local`/`pilot` 缺少或留空 JWT 地址或服务间 token 时会在 datasource 创建前失败，不会回退到开放访问。`demo` 是唯一允许匿名业务 API 的 profile；`test` 使用显式合成 HMAC decoder，但执行与 `local`/`pilot` 相同的受保护 endpoint policy。

以上 `local`/`pilot` 命令是配置契约，不是实库通过声明。MySQL schema、Flyway version/checksum、Hibernate 实库校验、LOB/time/`@Version` 映射、空库行为、stale schema 拒绝和 Java 重启持久化均未在本轮执行；它们统一由 Task 15 的 MySQL 8 运行时验收负责。

健康检查：

```bash
curl http://localhost:8080/actuator/health
curl http://localhost:8080/actuator/health/liveness
curl http://localhost:8080/actuator/health/readiness
```

工单接口：

```bash
curl http://localhost:8080/api/tickets
curl http://localhost:8080/api/metrics
curl -X POST http://localhost:8080/api/tickets/ticket-10042/analyze
```

以上匿名工单命令只适用于 `demo`。受保护 profile 的角色矩阵如下：

| 路径 | 匿名 | `SUPPORT_AGENT` | `SUPPORT_REVIEWER` | `SUPPORT_ADMIN` |
| --- | --- | --- | --- | --- |
| `/actuator/health` 及 liveness/readiness | 允许 | 允许 | 允许 | 允许 |
| tickets、knowledge search、quality metrics | 401 | 允许 | 允许 | 允许 |
| knowledge release 查询 | 401 | 允许 | 允许 | 允许 |
| knowledge release 创建、审批、发布、回滚 | 401 | 403 | 允许 | 允许 |
| analysis reviews 读写 | 401 | 403 | 允许 | 允许 |
| `GET /api/audit-events` | 401 | 403 | 允许 | 允许 |
| 其他 `/actuator/**` | 401 | 403 | 403 | 允许 |

401/403 使用稳定 JSON `code`、`message`、`traceId`，不会回显 bearer token。审核和审计操作人来自同一个 trusted actor provider：安全 profile 只读取 JWT subject 与角色，`demo` 只使用明确的 `anonymous-demo` 身份；浏览器 actor/action/trace/metadata header 或 body 均不受信任。知识访问范围只读取 JWT 的 `support_scopes`，经过 `GENERAL`、`BILLING`、`ACCOUNT`、`PRIVACY`、`TECHNICAL` 白名单后再与当前发布范围求交集；缺失或空 claim 都表示零知识权限，工单正文不能扩展权限。审计查询按 `createdAt DESC, id DESC` 使用不透明 cursor 和最大 100 条的 keyset 分页，支持 `targetType`/`targetId` 过滤；非法 cursor/filter/limit 返回 `400 INVALID_AUDIT_QUERY`。当前 React 仍只支持匿名 demo 工作流，浏览器 JWT adapter 属于 Task 11；真实 OIDC issuer、MySQL 与 pilot 组合验收属于 Task 15。

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

Java 会在没有请求头时生成安全的 `X-Trace-Id`，并将同一个值写入 Python header/body、Java 响应头、分析响应和日志上下文；Python 会先验证两处值一致，再用结构化字段记录该值、分析模式和状态。

分析、采纳/编辑回复和拒绝回复都要求 `Idempotency-Key`。键必须是 16 到 128 个 ASCII 字符，只允许字母、数字、`.`、`_`、`:`、`-`，并在全局唯一约束下绑定命令类型、路由/目标和规范化请求 SHA-256 指纹。相同键与相同命令会返回数据库中保存的原始成功结果；相同键绑定不同目标、动作或规范化内容会返回 `409 IDEMPOTENCY_KEY_CONFLICT`。浏览器为每个新命令生成 UUID；同一在途调用共享请求，只有未收到任何 HTTP 响应的网络失败才保留原键供重试，明确成功或 HTTP 错误后下一次命令使用新键。

Java 的数据库记录、owner lease 和有界等待负责跨 Spring context 的正确性；原有 JVM single-flight 只保留为减少同实例重复工作的优化。文件型 H2 已验证并发收敛、活跃 owner 续租、过期 owner 恢复和重启重放。MySQL 8 并发、重启、锁和事务 parity 仍属于 Task 15，不能从 H2 结果推断。单实例优化背景见 [分析在途请求合并契约](docs/contracts/analysis-single-flight-contract.md)。

React 不直接相信 Java 返回的 2xx JSON。工单、指标、分析和工单命令响应会先通过 Zod 运行时 Schema，缺字段、错误类型或未知枚举会在进入页面状态前转换为 `ApiContractError`；完整范围见 [前端运行时响应契约](docs/contracts/frontend-runtime-schema-contract.md)。工单 PATCH 必须携带当前 `expectedVersion`；匹配时版本递增，过期或并发写入返回 `409 VERSION_CONFLICT`，页面会保留错误详情并重新读取受影响工单。没有版本的本地 Demo 工单不会发送写请求。

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
export SUPPORT_COPILOT_INTERNAL_SERVICE_TOKEN='inject-a-non-browser-service-token'
.venv/bin/uvicorn app.main:app --reload --port 8000
```

`KNOWLEDGE_PATH` 不设置时继续使用仓库内的演示知识文件。设置后，Python 会在启动时读取仓库外的授权知识文件，并要求它是 JSON 数组；每个片段必须包含唯一的 `chunk_id`、`document_id`、`document_title`、`section`、`content`、`source_uri`、`categories`、`keywords`、`document_version`、`status` 和 `updated_at`。`ARCHIVED` 片段不会进入检索。可参考 [默认知识文件](services/support-copilot-ai/app/data/knowledge.json) 的结构。无效字段、空字段、未知字段和重复片段 ID 会直接阻止服务启动，原始知识正文不会写入校验错误。

`KNOWLEDGE_PROVENANCE_PATH` 对手工预切分 JSON 是可选项；使用导入命令生成 corpus 时应同时配置。服务会检查 provenance 中的 corpus 哈希，文件缺失、结构非法或哈希漂移都会阻止启动。当前 PDF 导入只支持自带文本层的文件；扫描件需要后续 OCR 流程，不能静默当作空知识使用。

### 知识发布与访问范围

Java 以 `DRAFT -> APPROVED -> PUBLISHED -> ARCHIVED` 管理不可变的 release id、版本、语义 corpus checksum 和发布范围；转换要求当前 `expectedVersion`。发布和回滚会在同一数据库事务中切换唯一 active pointer、归档原发布并写一条受控审计事件，事务失败时指针、状态和审计一起回滚。

仓库内基线契约为 `support-copilot-bundled-v1`、版本 `1`、checksum `b25240587df1ebb903a8555284a0f35faaa35e2d837add0fc5dd49418ca8b874`。该 checksum 是对规范化 chunks JSON 独立计算的 SHA-256，不是整个 `knowledge.json` 文件的原始 SHA；release 元数据不参与计算，避免自引用。Java 每次分析把 active release 与可信范围交给 Python，Python 在打分、Embedding 和 Prompt 前同时校验 release identity/checksum 并过滤无权片段。契约不一致返回 `409 KNOWLEDGE_RELEASE_MISMATCH`，不能转换成 AI fallback。

Python live 检索使用版本化 file-backed Embedding artifact，不再在每次进程启动后重新嵌入文档。artifact 包含 `float32` matrix、按行排序的片段 ID/范围/checksum metadata 和 canonical manifest；不包含知识正文、API Key 或 provider 响应。identity 绑定 release id/version/corpus checksum、脱密后的 provider endpoint identity、Embedding model、精确维度、chunking version 和片段顺序，因此可在调用 provider 前确定目标；manifest 的 matrix/metadata SHA-256 仍单独校验实际文件内容。

先使用明确的 corpus、artifact root、model 和维度构建，再验证并激活。以下命令中的维度必须与 provider 返回值一致：

```bash
cd services/support-copilot-ai
.venv/bin/python -m scripts.manage_embedding_artifacts build \
  --knowledge '/absolute/path/to/authorized-knowledge.json' \
  --provenance '/absolute/path/to/authorized-knowledge.provenance.json' \
  --artifact-root '/absolute/path/to/runtime-data/embedding-artifacts' \
  --model 'your-embedding-model' --dimension 1536

.venv/bin/python -m scripts.manage_embedding_artifacts verify \
  --artifact-id '<64-character-artifact-id>' \
  --knowledge '/absolute/path/to/authorized-knowledge.json' \
  --provenance '/absolute/path/to/authorized-knowledge.provenance.json' \
  --artifact-root '/absolute/path/to/runtime-data/embedding-artifacts' \
  --model 'your-embedding-model' --dimension 1536

.venv/bin/python -m scripts.manage_embedding_artifacts activate \
  --artifact-id '<64-character-artifact-id>' \
  --knowledge '/absolute/path/to/authorized-knowledge.json' \
  --provenance '/absolute/path/to/authorized-knowledge.provenance.json' \
  --artifact-root '/absolute/path/to/runtime-data/embedding-artifacts' \
  --model 'your-embedding-model' --dimension 1536
```

`inspect` 使用与 `verify` 相同参数并输出 release、row count 和 dimension。`rollback` 不接收 artifact id，而是验证 active pointer 记录的 previous artifact 后原子切回。构建先按确定的 identity 检查并完整验证已有目标；同一 store 的并发构建在锁内再次检查，只有缺失目标才请求一批文档 vectors。既有目标损坏或不兼容时直接返回脱敏 typed error，不调用 provider、覆盖/删除目标或替换 active pointer。新候选写入唯一临时同级目录，关闭并 fsync 文件，验证 hashes/schema/matrix/order 后原子发布完整目录；activation 只在候选兼容且完整时原子替换小 pointer。默认 `EMBEDDING_ARTIFACT_BUILD_POLICY=require-active`；`build-if-missing` 只适合有界的首次部署或聚焦测试，不能静默替换不兼容 artifact。

启动 live 服务时同时配置 `EMBEDDING_ARTIFACT_ROOT`、`EMBEDDING_VECTOR_DIMENSION` 和默认的 `require-active`。首次 live 检索惰性验证 active artifact；验证前 readiness 的 index reason 为 `artifact-unverified`，损坏或不兼容时 liveness 保持 200、readiness 降级并返回稳定 reason，检索不会转成普通 AI fallback。query 每次仍调用 Embedding provider；空范围请求在 artifact load、文档 embedding 和 query embedding 前返回零命中。允许范围先映射为 row indices，再进行 cosine score。

Java 发布新 release 不会热加载 Python corpus 或 artifact。部署新 release 必须先部署匹配 corpus，构建/验证/激活 artifact，再重启或切换 Python 实例；request release 与 Python corpus 仍不一致时返回 `409 KNOWLEDGE_RELEASE_MISMATCH`。本地 rollback 只恢复当前 corpus/model 兼容的 previous artifact。本轮使用确定性 fake provider 验证生命周期，没有生成或提交真实 provider vectors，也没有验证跨主机锁、共享文件系统语义或向量数据库。

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
export OPENAI_MAX_RETRIES=0
export AI_PROCESSING_TIMEOUT_SECONDS=90
export AI_SERVICE_TIMEOUT_MS=105000
export SUPPORT_COPILOT_HTTP_TIMEOUT_SECONDS=120
export RETRIEVAL_TOP_N=10
export RETRIEVAL_TOP_K=3
export MOCK_RETRIEVAL_MIN_SCORE=0.25
export LIVE_RETRIEVAL_MIN_SCORE=0.35
export EMBEDDING_ARTIFACT_ROOT='/absolute/path/to/runtime-data/embedding-artifacts'
export EMBEDDING_ARTIFACT_BUILD_POLICY=require-active
export EMBEDDING_CHUNKING_VERSION=knowledge-corpus-v2
export EMBEDDING_VECTOR_DIMENSION=1536
```

超时按外层晚于内层的顺序配置：单次正式 API 请求最长 20 秒且 OpenAI SDK 固定为零重试，Python 整体分析在 90 秒停止，Java 在一个可取消的 105 秒总预算内对 Python 429 和非 504 的 5xx 最多尝试 2 次，live 验收客户端最长等待 120 秒。`AI_SERVICE_RETRY_MAX_ATTEMPTS` 表示总尝试数，Bean Validation 只接受 1 至 2；值 3 会在配置绑定时拒绝启动。Python 的 504 表示其 90 秒处理预算已经耗尽，Java 不会立即重试。为兼容已有本地配置，`OPENAI_MAX_RETRIES=1` 仍可通过有界配置解析，但 provider 构造始终传入 0；建议迁移为 0。首次 live 请求只加载并验证 active 文档 matrix，再为当前 query 调用 Embedding provider 和聊天模型；不会重嵌入文档。`OPENAI_BASE_URL` 只控制聊天/Responses 请求；`OPENAI_EMBEDDING_BASE_URL` 控制 Embedding 请求，未设置时回退到 `OPENAI_BASE_URL`。`OPENAI_EMBEDDING_API_KEY` 可为独立 Embedding 服务提供单独凭据，未设置时回退到 `OPENAI_API_KEY`。mock 检索会拒绝低于 `MOCK_RETRIEVAL_MIN_SCORE` 的弱词面匹配；live matrix 使用余弦相似度，并拒绝低于 `LIVE_RETRIEVAL_MIN_SCORE` 的结果。两个阈值都应在真实 live 评估后根据脱敏分数分布校准。`check-live-rag.sh --preflight` 会拒绝倒置或余量不足的配置，不会调用外部 API。

Java Actuator 记录低基数 `support.copilot.ai.boundary.attempts`、`outcomes`、`fallbacks`、`timeouts`、`latency`、`circuit.rejected` 和 `bulkhead.rejected`。tag 只使用受控 outcome、reason、provider mode 和 stage，不使用 ticket、trace 或 user；trace 只进入结构化脱敏日志。circuit 与 bulkhead 是单 Java 实例内状态，不代表分布式限流或生产 SLO。

在调用正式 API 前先执行只读预检；它不会发出外部请求：

```bash
./scripts/check-live-rag.sh --preflight
```

确认 Python 以 live 模式启动，并且 Java、React 都已启动后，执行真实跨服务验收：

```bash
./scripts/check-live-rag.sh --success
```

`--success` 会实际调用正式 Embedding 和聊天模型 API，验证 `mode=live`、向量证据、引用、token、`traceId` 和 Java 分析历史，然后运行版本化合成 live 评估集。它在忽略的 `evaluation/reports/` 生成逐案例 JSON、Markdown 和人工审核 worksheet，记录 dataset/release/corpus/artifact/provider/model/prompt/redacted-config/Git provenance、runner 实测耗时、provider 暴露的 token 和引用映射。机器始终留下 `NOT_REVIEWED`，因此生成成功不等于可发布成功。

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
./gradlew test --no-daemon
```

认证与服务身份 focused tests：

```bash
cd services/support-copilot-api
./gradlew test --tests '*PilotSecurityContractTests' --tests '*AiServiceClientTests' --tests '*RuntimeProfileIntegrationTests' --no-daemon
cd ../support-copilot-ai
.venv/bin/pytest -q tests/test_internal_auth.py
```

审计事务、脱敏、角色与 keyset 分页 focused tests：

```bash
cd services/support-copilot-api
./gradlew test --tests '*AuditEventIntegrationTests' --no-daemon
./gradlew test --tests '*FlywayMigrationContractTests' --tests '*PilotSecurityContractTests' --no-daemon
```

普通测试显式选择隔离的 `test` profile。也可以只验证四个非容器 profile/migration 契约：

```bash
cd services/support-copilot-api
./gradlew test --tests '*RuntimeProfileIntegrationTests' --tests '*ProfileConfigurationTests' --tests '*FlywayMigrationContractTests' --tests '*DemoProfileIntegrationTests' --tests '*TestProfileIntegrationTests' --no-daemon
./gradlew compileTestJava --no-daemon
```

`MySqlProfileIntegrationTests` 源码随 `compileTestJava` 编译，但其三个运行时场景不计入 Task 3 通过数，也不在普通测试中冒充成功。Task 15 将负责 MySQL 8、Testcontainers、Compose、migration checksum、stale schema 和仅重启 Java 后的数据持久化验收；完成前不能声称 `local`/`pilot` 已通过真实 MySQL。

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

Live 人审不修改机器报告或 provider 回复：

```bash
cd services/support-copilot-ai
.venv/bin/python -m evaluation.live_review worksheet --report evaluation/reports/live-latest.json --output evaluation/reports/live-review.json
# 人工填写 reviewer、factual_support、decision_note、reviewed_at 后：
.venv/bin/python -m evaluation.live_review apply --report evaluation/reports/live-latest.json --worksheet evaluation/reports/live-review.json --output evaluation/reports/live-reviewed.json
.venv/bin/python -m evaluation.verify_live_evaluation --report evaluation/reports/live-reviewed.json --dataset evaluation/data/live-v1.json --require-human
```

`factual_support` 只允许 `SUPPORTED/PARTIAL/UNSUPPORTED/NOT_REVIEWED`，机器不能填写前三项。没有明确可核查 pricing source 时 cost 保持 `null`，不得估算。Java 可将 `EVALUATION_REPORT_PATH` 指向忽略的 live 报告；质量页比例只表示该 dataset/run 的评估结果，不是生产准确率或 SLO。

2026-08-27 的 Task 10 bounded live 运行先后暴露两个不同内部缺陷：首次运行的 Git SHA 长度约束由 `be9ac60` 修复，随后 `be9ac60` 上的 4-case 报告首次观察到 1 case live success、3 case `invalid_model_response` fallback，并暴露 no-evidence rate 误增，由 `3e59a07` 修复。修正尝试分类后，在 checkpoint `b8560190583fc2888f2428353ffcb43caac6cbc3` 上执行了一次新的受限运行；单工单跨服务 gate 成功，但数据集再次得到相同的 1 live success / 3 `invalid_model_response` fallback，机器门禁失败，人工标签仍为 0/4 `NOT_REVIEWED`。这是同一 provider structured-output 签名的第二次出现，按停止规则不得再次调用；需要用户更换或配置能稳定满足当前结构化输出 schema 的 chat endpoint/model 后才能开始新的 live 尝试。该报告不能作为 publishable live success 或质量数字。

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

Java 工作流定义见 [`.github/workflows/java-api-ci.yml`](.github/workflows/java-api-ci.yml)。普通测试显式使用隔离 H2 和测试 mock，不需要 Python 或 React。`MySqlProfileIntegrationTests` 的运行时验收留待 Task 15，当前只保证测试源码可编译。

React Web CI：

```text
安装 Node.js 24 并恢复 npm 下载缓存
-> 按 package-lock.json 安装依赖
-> 运行前端静态检查
-> 运行前端 API 单元测试
-> 执行 TypeScript 检查和生产构建
```

React 工作流定义见 [`.github/workflows/react-web-ci.yml`](.github/workflows/react-web-ci.yml)。它不会复用开发者本机的 `node_modules`；依赖安装、lint、单元测试或 build 任意一步失败，整个任务都会失败。

仓库还提供统一的非容器门禁：

```bash
./scripts/verify-ci-gates.sh
```

默认 `all` 模式会串行执行 Python 锁文件、测试和 mock 评估，Java 全量/profile/Flyway 契约，React 安装、lint、测试、构建、体积预算和 Playwright，以及工作流语法、静态安全检查、依赖漏洞扫描和 tracked/history secret 扫描。也可以使用 `--mode python|java|react|release` 运行指定分组。发布工作流 [`.github/workflows/release-gates-ci.yml`](.github/workflows/release-gates-ci.yml) 只执行不依赖外部模型和容器的 `release` 分组，并使用只读仓库权限。

依赖扫描对 Python 生产/开发锁、Gradle 锁和 npm lock 分别生成可验证报告；任一扫描器运行错误、报告损坏或已知漏洞都会令门禁失败。Docker、Compose、MySQL/Testcontainers、备份恢复和部署回滚会明确显示为 `DEFERRED`，统一留到 Task 15，不能把该提示理解为已通过。完整门禁不需要 API Key，也不会调用 live 模型。

如需保留本地依赖扫描证据，调用方必须提供一个预先创建、尚未包含任何扫描结果的目录：

```bash
evidence_dir="$PWD/.local-evidence/release-$(date +%Y%m%d-%H%M%S)"
mkdir -m 700 -p "$evidence_dir"
CI_GATE_SCAN_EVIDENCE_DIR="$evidence_dir" ./scripts/verify-ci-gates.sh --mode release
```

发布器不会覆盖同名证据目录；每个结果目录都可用 `services/support-copilot-ai/.venv/bin/python scripts/validate_scan_evidence.py "$evidence_dir/<label>"` 独立校验，其中 `<label>` 为 `python-production`、`python-development`、`java` 或 `node`。

## 关键接口

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/tickets` | 查询工单队列 |
| GET | `/api/tickets/{id}` | 查询工单详情 |
| POST | `/api/tickets` | 创建工单 |
| PATCH | `/api/tickets/{id}` | 携带非负 `expectedVersion` 修改状态、分类、优先级或负责人 |
| POST | `/api/tickets/{id}/unassign` | 按工单版本取消负责人 |
| POST | `/api/tickets/{id}/analyze` | 触发分析 |
| GET | `/api/tickets/{id}/analyses` | 查询分析历史 |
| POST | `/api/tickets/{id}/analyses/{analysisId}/reviews` | 采纳或编辑后采纳最新回复建议 |
| POST | `/api/tickets/{id}/analyses/{analysisId}/reviews/reject` | 拒绝最新回复建议并记录必填原因 |
| GET | `/api/tickets/{id}/analyses/{analysisId}/reviews` | 查询分析审核历史 |
| GET | `/api/knowledge/search` | 调试知识检索 |
| GET | `/api/knowledge/releases`、`/api/knowledge/releases/{id}`、`/api/knowledge/releases/active` | 查询不可变知识发布及当前 active pointer |
| POST | `/api/knowledge/releases` | 创建 `DRAFT` release |
| POST | `/api/knowledge/releases/{id}/approve`、`publish`、`rollback` | 携带 `expectedVersion` 执行受角色保护的合法转换 |
| GET | `/api/metrics` | 查询当前工单、已持久化运行态指标和可追溯 mock 评估报告；没有来源的数据返回空值 |
| POST | `/analyze` | Java 调用的 AI 服务内部接口；要求 `X-Internal-Service-Token`，不属于浏览器 API |

## 演示建议

1. 打开工单工作台，选择“本月套餐出现重复扣款”。
2. 查看结构化分类、置信度和支付争议升级规则。
3. 打开“知识依据”，检查文档片段和引用。
4. 打开“回复建议”，编辑后采纳，或拒绝建议并填写原因，再展开审核历史。
5. 选择“能否恢复三个月前删除的项目”，展示无证据时的拒绝承诺与人工复核。
6. 切换运营概览和质量评估，展示评估报告的来源、指标和门禁状态；删除或改坏报告后，页面会回到“暂无评估报告”，不会保留静态数字。

## 当前限制

- `demo`/`test` 使用 H2，服务重启后业务数据会重新初始化；`local`/`pilot` 的 MySQL 配置与 migration 契约已准备，但真实 MySQL 持久化仍待 Task 15 验证。
- 当前 append-only 审计覆盖已提交的工单创建/实际变更、分析持久化、`APPROVED`/`EDITED`/`REJECTED` 审核和知识 release 创建/审批/发布/回滚；元数据白名单不保存工单正文、回复、拒绝原因、证据、provider payload、token 或异常消息。
- 审计在 H2 `test` profile 已完成事务与真实 HTTP 验证，但 V2 migration 尚未在 MySQL 执行；checksum、索引与事务 parity 属于 Task 15，当前不构成生产或合规审计声明。
- JWT endpoint policy 与合成 test decoder 已验证，但 React 登录/token adapter 尚未实现；真实 pilot OIDC、MySQL 和容器组合验收属于 Task 15，不能据此声称生产身份平台已经完成。
- mock 检索用于可重复演示，不代表真实语义检索质量。
- Java release 发布不会热加载 Python file-backed corpus/artifact；新 release 仍需要显式部署 corpus、构建并激活 artifact。当前只验证本地文件系统原子生命周期，不代表共享存储或跨主机协调。
- 质量页只读取 `EVALUATION_REPORT_PATH` 指向的评估报告；报告没有接入持久化评估运行表，文件被替换或删除后需要重新加载页面。
- 实时 OpenAI 模式需要用户自己的 API Key 和可用模型配置。
- 真实 live 记录只证明一次脱敏合成工单的端到端链路成功，不代表稳定性、质量基准、生产延迟或成本结论。
- 当前没有真实 CRM、邮件、支付或身份系统集成。
- MySQL 运行时、Redis、持久化向量数据库、Compose 和自动化部署/CD 尚未完成验收；当前有三条服务 CI 和一条非容器 release gate，但都不包含部署。

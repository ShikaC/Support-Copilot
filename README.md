# Support Copilot

企业级智能工单路由与 RAG 知识库辅助平台。

Support Copilot 用模拟企业客服场景展示完整的 AI 应用工程链路：工单进入系统后，由 Java 业务 API 保存和编排，Python AI 服务完成结构化分类、知识检索、证据约束回复与风险判断，React 工作台展示可审计的处理轨迹并保留人工审核入口。

## 当前能力

- 企业 SaaS 风格工单工作台，支持队列筛选、工单切换和 SLA 风险展示。
- 工单分类、优先级、情绪、置信度与人工升级建议。
- 检索查询、Top K 知识片段、来源、分数和引用展示。
- 建议回复编辑、采纳和风险提示。
- 运营概览、知识库状态和 RAG 质量评估视图。
- H2 工单与分析运行持久化。
- FastAPI `mock`、`live` 和 `fallback` 三种运行模式。
- Java 到 Python 的超时与业务降级。
- OpenAI Responses API 结构化输出和 LangChain 内存向量检索的实时模式。

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

- Node.js 20 或更高版本
- Java 21
- Python 3.11
- npm

V1 默认使用 H2 和本地知识数据，不需要 Docker、MySQL 或 Redis。

## 快速启动

需要三个终端。建议先启动 AI 服务和 Java API，再启动前端。

### 1. AI 服务

首次运行：

```bash
cd services/support-copilot-ai
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
```

启动默认 mock 模式：

```bash
cd services/support-copilot-ai
.venv/bin/uvicorn app.main:app --reload --port 8000
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

## OpenAI 实时模式

默认 `AI_MODE=mock` 不调用外部 API，适合开发、测试和面试环境预检。

启用实时模式前设置：

```bash
cd services/support-copilot-ai
export AI_MODE=live
export OPENAI_API_KEY='your-api-key'
export OPENAI_CHAT_MODEL='your-chat-model'
export OPENAI_EMBEDDING_MODEL='your-embedding-model'
.venv/bin/uvicorn app.main:app --reload --port 8000
```

可选配置：

```bash
export OPENAI_BASE_URL='https://your-compatible-gateway.example/v1'
export OPENAI_TIMEOUT_SECONDS=20
export OPENAI_MAX_RETRIES=2
export RETRIEVAL_TOP_N=10
export RETRIEVAL_TOP_K=3
```

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
npm run lint
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

评估报告会写入 `services/support-copilot-ai/evaluation/reports/`。它只反映固定模拟工单上的 mock 工作流，不代表真实模型或生产 RAG 效果。评估集维护说明见 [Mock 评估](services/support-copilot-ai/evaluation/README.md)。

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
| GET | `/api/knowledge/search` | 调试知识检索 |
| GET | `/api/metrics` | 查询运营与评估指标 |
| POST | `/analyze` | Java 调用的 AI 服务内部接口 |

## 演示建议

1. 打开工单工作台，选择“本月套餐出现重复扣款”。
2. 查看结构化分类、置信度和支付争议升级规则。
3. 打开“知识依据”，检查文档片段和引用。
4. 打开“回复建议”，编辑后采纳。
5. 选择“能否恢复三个月前删除的项目”，展示无证据时的拒绝承诺与人工复核。
6. 切换运营概览和质量评估，解释检索与生成需要分层评估。

## 当前限制

- V1 使用 H2 和内存向量存储，服务重启后业务数据会重新初始化。
- mock 检索用于可重复演示，不代表真实语义检索质量。
- 实时 OpenAI 模式需要用户自己的 API Key 和可用模型配置。
- 当前没有真实 CRM、邮件、支付或身份系统集成。
- V2 的 MySQL、Redis、向量数据库、Docker Compose 和 CI/CD 尚未实现。

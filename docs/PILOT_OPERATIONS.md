# Support Copilot Pilot 运行与证据边界

本文是 V1.5 的发布事实入口。当前形态是 **non-production pilot**，采用
**single-tenant** 设计，只使用 **synthetic/redacted data** 做本地验证，所有建议回复都
要求 **human approval**。这些词是能力边界，不是生产经历声明。

## 1. 已验证范围

- React 工作台、Java 业务 API、FastAPI AI 服务可在本地形成完整 mock 工单分析链路。
- Java `demo`/`test` 使用 H2；`local`/`pilot` 的 MySQL/Flyway 配置契约已建立，但真实
  MySQL 运行时验收属于 Task 15。
- Java Resource Server 角色策略、服务间 token、可信 actor、知识范围过滤、append-only
  业务审计和持久化命令幂等已在本地合成身份/H2 场景验证。
- React 已有 `demo`/`secured` typed auth adapter，会话 token 只保存在内存和
  `sessionStorage` 并注入 Authorization header；没有 OIDC 登录、token refresh 或生产
  身份系统。
- Python 可配置正式 chat 与 Embedding 端点。一次脱敏合成工单 live 链路成功不代表质量、
  稳定性、成本或生产性能；当前 4-case live 发布评估仍未通过且无人审结论。
- 非容器 release gate 已覆盖工作流、依赖和 secrets；Docker、MySQL、备份恢复和部署回滚
  继续显示为 `DEFERRED`，不能计为通过。

证据入口：

- [README 测试与构建](../README.md#测试与构建)
- [面试演示脚本](DEMO.md)
- [Mock 评估基线](verification/mock-evaluation-2026-08-24.md)
- [Live RAG 完成标准](learning/LIVE_RAG_COMPLETION_CRITERIA.md)
- [优化路线图](optimizations/ROADMAP.md)

## 2. 架构与数据流

```text
React typed client + Zod
  -> Spring Boot API + JWT policy + transaction/idempotency/audit
    -> authenticated FastAPI /analyze
      -> scoped knowledge retrieval
        -> mock rules OR live Embedding + Responses API
  <- persisted analysis, evidence, citations, fallback reason, traceId
  -> human review decision + append-only audit event
```

Java 是工单、版本、审核、审计、幂等和知识 release 的业务事实源。Python 只负责 AI 分析
和 file-backed corpus/artifact；React 不直接信任 2xx JSON，而是先过 Zod Schema。Java
发布新知识 release 不会自动热加载 Python，部署者必须显式部署匹配 corpus/artifact。

Runtime profiles: `demo`, `test`, `local`, `pilot`.

| Profile | 数据与访问 | 已验证边界 |
| --- | --- | --- |
| `demo` | 内存 H2、8 条合成工单、匿名业务 API | 本地演示与 smoke |
| `test` | 随机隔离 H2、合成 HMAC JWT | 自动化安全/事务测试 |
| `local` | MySQL/Flyway/JWT 配置，无回退 | 仅配置与失败关闭契约；运行时待 Task 15 |
| `pilot` | 与 local 同边界，无 H2/凭据默认值 | 仅配置与失败关闭契约；运行时待 Task 15 |

## 3. AI 与模型配置

Configured AI_MODE values: `mock`, `live`, `auto`.

`fallback` is an analysis result mode, not an `AI_MODE` configuration value.

模型边界由以下环境变量配置：

- `OPENAI_API_KEY` 与可选的 `OPENAI_EMBEDDING_API_KEY`
- `OPENAI_BASE_URL` 与可选的 `OPENAI_EMBEDDING_BASE_URL`
- `OPENAI_CHAT_MODEL`
- `OPENAI_EMBEDDING_MODEL`

Embedding key/base URL 未设置时分别回退到 chat key/base URL；chat model 与 embedding
model 不是同一协议职责，不能只因名称相同就假设端点兼容。`auto` 只有在 live 配置完整时
选择 live，否则使用 mock。完整变量和超时边界见 [README 实时模式](../README.md#openai-实时模式)。

## 4. API 契约

下表由 `scripts/verify_docs.py` 与 Java controller/FastAPI decorator 逐项比对。Java 业务
接口在 `demo` 可匿名访问，在 `test/local/pilot` 按角色保护；FastAPI `/analyze` 还要求
`X-Internal-Service-Token`。

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/audit-events` | keyset 分页查询可信审计事件 |
| GET | `/api/knowledge/releases` | 查询知识 release |
| GET | `/api/knowledge/releases/active` | 查询 active release |
| GET | `/api/knowledge/releases/{releaseId}` | 查询指定 release |
| GET | `/api/knowledge/search` | 按可信 scope 检索知识 |
| GET | `/api/metrics` | 查询工单与评估报告指标 |
| GET | `/api/tickets` | 查询工单队列 |
| GET | `/api/tickets/{id}` | 查询工单详情 |
| GET | `/api/tickets/{id}/analyses` | 查询分析历史 |
| GET | `/api/tickets/{ticketId}/analyses/{analysisId}/reviews` | 查询审核历史 |
| GET | `/health` | 查询 AI 模式和兼容健康摘要 |
| GET | `/health/live` | FastAPI liveness |
| GET | `/health/ready` | FastAPI readiness 快照 |
| PATCH | `/api/tickets/{id}` | 携带 expectedVersion 修改工单 |
| POST | `/analyze` | Java 调用内部 AI 分析 |
| POST | `/api/knowledge/releases` | 创建 DRAFT release |
| POST | `/api/knowledge/releases/{releaseId}/approve` | 审批 release |
| POST | `/api/knowledge/releases/{releaseId}/publish` | 发布 release |
| POST | `/api/knowledge/releases/{releaseId}/rollback` | 回滚到兼容 release |
| POST | `/api/tickets` | 创建工单 |
| POST | `/api/tickets/{id}/analyze` | 触发工单分析 |
| POST | `/api/tickets/{id}/unassign` | 取消负责人 |
| POST | `/api/tickets/{ticketId}/analyses/{analysisId}/reviews` | 采纳或编辑后采纳 |
| POST | `/api/tickets/{ticketId}/analyses/{analysisId}/reviews/reject` | 拒绝建议 |

稳定错误 envelope 使用 `code`、`message`、`traceId` 和 `details`。面试关键错误包括：

- `VERSION_CONFLICT`：工单 expectedVersion 已过期，前端重新读取受影响工单。
- `IDEMPOTENCY_KEY_CONFLICT`：同一个键绑定了不同命令、目标或请求指纹。
- `ANALYSIS_REVIEW_STALE`：审核目标不是最新分析或工单版本已变化。
- `KNOWLEDGE_RELEASE_MISMATCH`：Java active release 与 Python corpus 不一致，失败关闭。
- `TRACE_ID_MISMATCH`：FastAPI header/body trace 不一致，请求不进入 workflow。

## 5. 认证、知识与数据治理

`SUPPORT_AGENT` 可使用工单、知识查询和指标；`SUPPORT_REVIEWER`/`SUPPORT_ADMIN` 才能
审核、查询审计和变更知识 release；其他 actuator 只允许 admin。401/403 不回显 token。

知识访问范围只来自 JWT `support_scopes` 白名单，再与 active release 范围求交集。工单
正文、query 参数或浏览器 header 都不能扩大权限。原始 Markdown/文本 PDF 在仓库外经
授权清单构建 corpus/provenance；扫描件 OCR、上传 UI、增量索引和跨主机 artifact 协调
未实现。

日志、审计和评估证据不得保存密钥、完整 bearer token、工单正文、回复正文或 provider
payload。演示和固定数据集只使用合成/脱敏内容。

## 6. 评估 provenance

Mock 报告绑定数据集、知识库 hash、prompt/config 和 Git 状态，适合确定性回归，不代表
真实模型质量。Live 报告还必须绑定 release/corpus/artifact/provider/model、逐案例检索/
引用映射、runner 延迟、可用 token 数据和人工 worksheet。机器只能生成 `NOT_REVIEWED`；
没有完整人工 factual-support label 时不能发布 groundedness 结论。没有可靠 pricing source
时 cost 必须为 `null`。

## 7. 启动、验证与事件处置

常用门禁：

```bash
./scripts/check-local-startup.sh --preflight
./scripts/run-local-smoke.sh
./scripts/verify-ci-gates.sh
./scripts/verify-docs.sh
```

`verify-docs.sh` 的 full 模式在 committed tracked-only fixture 中执行下列规范命令。该表由
静态文档契约逐项比对，命令新增、删除或漂移都会令门禁失败：

| Verification ID | Executed command |
| --- | --- |
| verify-python-tests | `cd services/support-copilot-ai && .venv/bin/pytest -q` |
| verify-mock-evaluation | `cd services/support-copilot-ai && AI_MODE=mock .venv/bin/python -m evaluation.run_mock_evaluation` |
| verify-java-tests | `cd services/support-copilot-api && ./gradlew test --no-daemon` |
| verify-react-lint | `cd apps/support-copilot-web && npm run lint` |
| verify-react-tests | `cd apps/support-copilot-web && npm test -- --run` |
| verify-react-build-budget | `cd apps/support-copilot-web && npm run build:budget` |
| verify-react-node-contracts | `cd apps/support-copilot-web && npm run test:node` |
| verify-react-e2e | `cd apps/support-copilot-web && npm run test:e2e` |
| verify-preflight | `./scripts/check-local-startup.sh --preflight` |
| verify-smoke | `./scripts/run-local-smoke.sh` |

故障处置顺序：

1. 记录用户可见错误码和 `traceId`，不要记录正文或 token。
2. 检查 React 服务状态、Java actuator、FastAPI liveness/readiness。
3. 判断是业务冲突、身份/范围拒绝、AI 可恢复故障还是未知程序错误。
4. 对版本冲突重新读取受影响资源；对 AI fallback 保留人工流程；未知 500 不伪装成
   fallback。
5. 修改后运行最小 focused test，再运行相应聚合门禁，并记录命令、SHA 和边界。

| 现象 | 预期处理 | 验证 |
| --- | --- | --- |
| Python 不可连接 | Java 保存明确 fallback，人工流程继续 | `check-local-analysis-flow.sh --fallback` |
| malformed AI 2xx | 契约错误，不作为成功结果 | Java/Python contract tests |
| stale ticket/review | 返回 409，前端刷新对应工单 | React rendered tests + Java integration tests |
| active knowledge 不一致 | 返回非 fallback 409 | knowledge release loopback tests |
| readiness degraded | liveness 仍可用，定位 provider/index stage | Python readiness tests |

## 8. 备份、恢复与回滚边界

当前可验证的“回滚”仅包括数据库事务失败时的原子回滚、知识 active release/pointer 切换，
以及兼容的本地 file-backed embedding artifact rollback。它们不是数据库备份恢复或应用部署
回滚。

Task 15 前不得执行或宣称以下能力已经通过：

- MySQL 8 数据卷持久化和 Java 重启后数据保持。
- 从备份恢复到全新 volume 并核对 sentinel、migration 和业务数据。
- 容器镜像/Compose 健康、非 root、资源限制和 secrets injection。
- 应用、schema、corpus/artifact 的兼容升级与部署回滚演练。

仓库中的 Task 15 scaffold 仍待审查，当前发布门禁必须把这些项目显示为 `DEFERRED`。

## 9. 发布事实与限制

Task 13 已在本地 commit `e9852c7` 通过修复后的非容器 release 门禁；对应依赖扫描观察到
Python 57/66、Java 181、Node 234 个锁定坐标，运行当时 OSV 返回 0 个已知漏洞。该数字
不是永久安全结论。Task 14 的最终 clean verification SHA 和命令结果记录在
`.omo/evidence/task-14-enterprise-minimum-pilot.md`，该路径是本地证据账本，不随仓库发布。

剩余限制：

- 只有单租户本地 pilot，不是生产部署或真实企业客户经历。
- 数据是 synthetic/redacted data，不代表真实客服数据分布。
- 建议必须 human approval，系统没有自动发送邮件、退款或修改账户。
- 真实 OIDC issuer、登录/刷新、MySQL parity、容器、备份恢复和部署回滚未验收。
- 没有生产流量、并发容量、SLO、真实用户数、成本或准确率结论。

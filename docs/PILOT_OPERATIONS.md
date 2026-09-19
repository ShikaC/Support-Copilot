# Support Copilot Pilot 运行与证据边界

本文是 V1.5 的发布事实入口。当前形态是 **non-production pilot**，采用
**single-tenant** 设计，只使用 **synthetic/redacted data** 做本地验证，所有建议回复都
要求 **human approval**。这些词是能力边界，不是生产经历声明。

## 1. 已验证范围

- React 工作台、Java 业务 API、FastAPI AI 服务可在本地形成完整 mock 工单分析链路。
- Java `demo`/`test` 使用 H2；Task 15 已在 MySQL 8.4.11 上以 9 个零跳过场景验证
  `pilot` 的 Flyway/Hibernate、幂等、审计、知识发布和重启 parity。
- Java Resource Server 角色策略、服务间 token、可信 actor、知识范围过滤、append-only
  业务审计和持久化命令幂等已在本地合成身份/H2 场景验证。
- React 已有 `demo`/`secured` typed auth adapter，会话 token 只保存在内存和
  `sessionStorage` 并注入 Authorization header；没有 OIDC 登录、token refresh 或生产
  身份系统。
- Python 可配置正式 chat 与 Embedding 端点。一次脱敏合成工单 live 链路成功不代表质量、
  稳定性、成本或生产性能；当前 4-case live 发布评估仍未通过且无人审结论。
- 非容器 release gate 已覆盖工作流、依赖和 secrets。Task 15 的 MySQL parity 与 11 个
  当前镜像运行时场景已通过；完整跨版本回滚/fresh-volume 恢复受重复宿主磁盘耗尽阻塞，
  镜像发布扫描仍因 56 个 HIGH/CRITICAL 结果失败。
- 运维 verifier 已在对抗审查后固定 `linux/amd64`、为服务/网络/卷增加随机运行所有权标签、
  删除前绑定镜像 ID，并让 Bearer header 通过标准输入进入 `curl`。这些加固通过本地故障注入，
  但当前源码尚未在受阻远端宿主完成同源 Compose 复跑。

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

Java 是工单、版本、审核、审计、幂等和知识 release 的业务事实源。Java 知识目录与 Python
检索必须读取同一份经过 checksum 校验的 corpus；Python 还负责 file-backed artifact 和 AI
分析。React 不直接信任 2xx JSON，而是先过 Zod Schema。Java 发布新知识 release 不会自动
部署或重建 Python artifact，部署者必须显式部署匹配的 corpus、artifact 和数据库 release。

Runtime profiles: `demo`, `test`, `local`, `pilot`.

| Profile | 数据与访问 | 已验证边界 |
| --- | --- | --- |
| `demo` | 内存 H2、8 条合成工单、匿名业务 API | 本地演示与 smoke |
| `test` | 随机隔离 H2、合成 HMAC JWT | 自动化安全/事务测试 |
| `local` | MySQL/Flyway/JWT 配置，无回退 | 配置与失败关闭契约；不自动提供身份或数据库 |
| `pilot` | 与 local 同边界，无 H2/凭据默认值 | MySQL 8.4.11 parity、test-only OIDC 和部分 Compose 重启链路 |

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
| GET | `/api/quality-reports` | 查询固定评估的质量报告及其证据边界 |
| GET | `/api/tickets` | 使用 keyset cursor 查询工单队列 |
| GET | `/api/tickets/{ticketId}/activity` | 游标查询经裁剪的持久化处理记录 |
| GET | `/api/tickets/{ticketId}/notes` | 查询最近 100 条内部备注 |
| GET | `/api/tickets/{id}` | 查询工单详情 |
| GET | `/api/tickets/{id}/analyses` | 查询分析历史 |
| GET | `/api/tickets/{ticketId}/analyses/{analysisId}/reviews` | 查询审核历史 |
| GET | `/health` | 查询 AI 模式和兼容健康摘要 |
| GET | `/health/live` | FastAPI liveness |
| GET | `/health/ready` | FastAPI readiness 快照 |
| GET | `/knowledge/index/versions` | 列出检索索引版本与当前生效版本（只读） |
| GET | `/knowledge/index/rebuild/{taskId}` | 查询持久化索引构建任务、真实进度与失败原因（需内部鉴权） |
| GET | `/knowledge/corpus/build/{taskId}` | 查询语料候选构建任务与失败原因（需内部鉴权） |
| PATCH | `/api/tickets/{id}` | 携带 expectedVersion 修改工单 |
| POST | `/analyze` | Java 调用内部 AI 分析 |
| POST | `/knowledge/index/reload` | 重载语料与向量索引（默认关闭，需内部鉴权） |
| POST | `/knowledge/index/rebuild` | 有预算上限地后台构建配置语料或 corpusBuildTaskId 指定的成功候选索引，不自动激活（默认关闭，需内部鉴权） |
| POST | `/knowledge/corpus/build` | 调用固定 Node 脚本构建 Doc2Dial 候选语料，不生成评估集或激活（默认关闭，需内部鉴权；当前镜像未包含 Node 与脚本） |
| POST | `/api/knowledge/releases` | 创建 DRAFT release |
| POST | `/api/knowledge/releases/{releaseId}/approve` | 审批 release |
| POST | `/api/knowledge/releases/{releaseId}/publish` | 发布 release |
| POST | `/api/knowledge/releases/{releaseId}/rollback` | 回滚到兼容 release |
| POST | `/api/tickets` | 创建工单（兼容非幂等入口） |
| POST | `/api/tickets/commands/create` | 幂等创建工单 |
| POST | `/api/tickets/{ticketId}/claim` | 携带 expectedVersion，由可信身份领取 |
| POST | `/api/tickets/{ticketId}/notes` | 携带 noteId/expectedVersion 保存内部备注 |
| POST | `/api/tickets/{id}/analyze` | 触发工单分析 |
| POST | `/api/tickets/{id}/unassign` | 取消负责人 |
| POST | `/api/tickets/{ticketId}/analyses/{analysisId}/reviews` | 采纳或编辑后采纳 |
| POST | `/api/tickets/{ticketId}/analyses/{analysisId}/reviews/reject` | 拒绝建议 |

`GET /api/tickets` 的响应体仍是当前页工单数组，以兼容现有 React Schema。使用
`limit=1..100` 控制页大小；默认按 `createdAt DESC, id DESC` 排序，也支持 `sort=SLA|PRIORITY` 全量排序；下一页从
`X-Next-Cursor` 响应头读取，最后一页不返回该 header。`status`、`priority` 和 `category`
支持逗号分隔值，非法分页或筛选参数返回 `400` 和稳定错误码
`INVALID_TICKET_PAGE`、`INVALID_TICKET_CURSOR` 或 `INVALID_TICKET_FILTER`。

2026-09-09 工作台已接入服务端关键词、状态、优先级、负责人筛选和游标加载更多。
`assignee=UNASSIGNED` 查询未分配工单，其他非空值匹配完整负责人姓名。
`X-Total-Count` 返回全部匹配工单数；游标绑定排序与筛选条件，改变条件必须从第一页开始。
快捷搜索查询全部工单，可打开首批列表之外的记录。当前验收范围见 [工作台验收](enterprise-workspace/VERIFICATION.md)。

稳定错误 envelope 使用 `code`、`message`、`traceId` 和 `details`。面试关键错误包括：

- `VERSION_CONFLICT`：工单 expectedVersion 已过期，前端重新读取受影响工单。
- `IDEMPOTENCY_KEY_CONFLICT`：同一个键绑定了不同命令、目标或请求指纹。
- `ANALYSIS_REVIEW_STALE`：审核目标不是最新分析或工单版本已变化。
- `KNOWLEDGE_RELEASE_MISMATCH`：Java active release 与 Python corpus 不一致，失败关闭。
- `TRACE_ID_MISMATCH`：FastAPI header/body trace 不一致，请求不进入 workflow。

索引重建接口的调用步骤、预算、进度、重启和失败保留语义统一见
[索引重建任务切片 A](verification/index-rebuild-tasks-2026-09-19/README.md)。

## 5. 认证、知识与数据治理

`SUPPORT_AGENT` 可使用工单、知识查询和指标；`SUPPORT_REVIEWER`/`SUPPORT_ADMIN` 才能
审核、查询审计和变更知识 release；其他 actuator 只允许 admin。401/403 不回显 token。

### JWT 配置

`local`/`pilot` 启动前都要求以下变量存在且非空：

```bash
export SUPPORT_COPILOT_JWT_ISSUER_URI='https://your-issuer.example'
export SUPPORT_COPILOT_JWT_AUDIENCE='support-copilot-api'
```

`SUPPORT_COPILOT_JWT_JWK_SET_URI` 是可选的直接 key-set 位置。配置它只改变密钥的获取位置，
不会替代或关闭 issuer 和 audience claim 校验。缺少或留空 issuer、audience 或内部服务 token
时，`local`/`pilot` 会在 datasource 创建前失败，不会回退到匿名访问或 H2。以上行为已在本地
配置和合成 JWT 场景验证之外，Task 15 还在真实 Compose 拓扑中使用固定 test-only OIDC
issuer 验证 client credentials、issuer/audience、角色和知识 scope。它不是用户登录、token
refresh 或生产身份供应商集成。

知识访问范围只来自 JWT `support_scopes` 白名单，再与 active release 范围求交集。工单
正文、query 参数或浏览器 header 都不能扩大权限。原始 Markdown/文本 PDF 在仓库外经
授权清单构建 corpus/provenance；扫描件 OCR、上传 UI、增量索引和跨主机 artifact 协调
未实现。

已保存分析及审核结果也受当前知识权限约束；对应 chunk 已归档、内容或来源改变，或调用者
scope 不再允许时，历史结果会被过滤，最新分析为空，直接审核返回 `403`。不会用更旧分析
代替不可读的最新分析。2026-09-18 审查还将可信身份与 scopes 纳入全部命令的幂等摘要：
升级前的 key 可能返回 `409`，必须先核对原操作结果，不能自动换 key 重做已产生副作用的
请求。详细行为与回归边界见[对抗式审查记录](verification/adversarial-review-2026-09-18/README.md)。

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

证据文档可以链接到 `.gitignore` 排除的本地派生产物（trials、corpus、workspace 快照等）。这类目标在 tracked-only fixture 中允许缺失，但链接路径仍必须是仓库相对路径；指向已发布文件的缺失链接和错误锚点仍会使门禁失败。

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

Task 15 当前运行时事实：

- MySQL 8.4.11 的 9 个 parity 场景通过，零跳过；覆盖 migration/checksum、stale schema、
  幂等并发/重放、审计提交/回滚、知识发布/回滚和应用上下文重启。
- 当前 API/AI/Web 镜像的 11 个容器验收场景通过，覆盖非 root、只读/权限边界、健康、
  secrets、运行时契约和精确清理。
- 五服务 Compose 已验证 test-only OIDC、401/403/2xx、scope-filtered mock RAG、审核/审计、
  API/MySQL/整栈重启持久化、artifact identity 和重启后安全写入。
- 兼容旧 API 镜像已从固定祖先 revision 独立构建并绑定 source/archive/OCI evidence。
- 同一运维 gate 两次被共享宿主上的无关 no-cache 构建耗尽磁盘；第二次在已通过上述重启
  场景后于 known-good 重应用阶段触发 MySQL errno 28。按两次同因上限停止第三次尝试。
- 因此，真实旧版本切换、回切后的写入读取和 fresh-volume backup/restore 尚未形成完整成功
  证据，不得宣称通过。重新验收前需保证 Docker-root 至少 8 GiB 可用且 60 秒内无并发构建。
- 对抗审查后的当前 Compose/verifier 与上述远端部分成功记录不是同一源码快照；错误架构、
  双标签精确清理、异所有权资源保留、镜像标签非破坏性核验和 JWT 不进入 curl argv 已由本地
  测试覆盖，远端仍待复跑。容器/网络/卷在退出时按 project + 随机 ownership 精确删除；镜像
  引用作为构建缓存保留并在回执中绑定 image ID，退出清理不会执行 `docker image rm` 或覆盖 tag。

镜像发布闸门也未通过：严格 HIGH/CRITICAL、不过滤 unfixed、不豁免的扫描仍有 56 项结果。
这些结果与磁盘阻塞相互独立，任一项都足以阻止发布声明。

## 9. 发布事实与限制

Task 13 已在本地 commit `e9852c7` 通过修复后的非容器 release 门禁；对应依赖扫描观察到
Python 57/66、Java 181、Node 234 个锁定坐标，运行当时 OSV 返回 0 个已知漏洞。该数字
不是永久安全结论。Task 14 的最终 clean verification SHA 和命令结果记录在
`.omo/evidence/task-14-enterprise-minimum-pilot.md`，该路径是本地证据账本，不随仓库发布。

剩余限制：

- 只有单租户本地 pilot，不是生产部署或真实企业客户经历。
- 数据是 synthetic/redacted data，不代表真实客服数据分布。
- 建议必须 human approval，系统没有自动发送邮件、退款或修改账户。
- MySQL parity、当前容器运行时和部分 Compose 重启链路已验收；生产 OIDC 登录/刷新、完整
  跨版本回滚、fresh-volume 恢复和镜像安全发布闸门仍未通过。
- AI/Web 镜像构建仍执行未锁定到具体系统包版本的安全升级，基础镜像虽按 digest 固定，构建
  结果仍会随软件源变化。后续应改为刷新受支持的 digest-pinned 基础镜像并重新跑运行时/扫描门禁。
- 没有生产流量、并发容量、SLO、真实用户数、成本或准确率结论。

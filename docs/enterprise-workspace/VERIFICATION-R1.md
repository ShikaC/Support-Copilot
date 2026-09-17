> 历史记录：第一轮工作台重构的阶段快照。以下“当前”仅指第一轮结束时；后续截图可能已经更新。第二轮事实见 [VERIFICATION.md](VERIFICATION.md)。

# 企业工单工作台：实现与验收记录

2026-09-09。本轮已实现并验证一个可以操作的工单辅助工作台：创建、领取、编辑、状态流转、内部备注、AI 分析、人工审核和审计读回形成闭环。界面使用真实 Java API；本地 AI 使用真实 Python 工作流的确定性 mock 模式。没有调用真实外部模型，没有发布远端服务。

本轮来自用户明确的重构授权，替代此前要求暂停开发、逐步教学的执行节奏。工作目录为 `/Users/shika/Documents/Support-Copilot`，基础 HEAD 为 `4df3bf44907c34318132496929bad4a3974ad88b`，分支 `master`，工作树有未提交改动。原有 Pilot/基础设施改动予以保留；本轮未提交或推送。下列结果针对当前未提交源码，不是仅针对基础 SHA；源码摘要见 [source-manifest.json](source-manifest.json)。

## 已实现

| 层 | 变化 | 目的 |
| --- | --- | --- |
| 工作台 | 三栏桌面布局、移动队列/详情切换、五项导航、Cmd/Ctrl+K 搜索、键盘与焦点支持 | 将查找、判断、处理和核查放在连续的操作流程中 |
| 队列 | 服务端关键词/状态/优先级过滤、游标加载更多、默认最新创建排序 | 避免把第一页当作完整队列；默认待处理条件在首次请求即生效 |
| 工单操作 | 创建表单、领取、负责人/优先级/分类编辑、合法状态动作和解决/关闭确认 | 所有持久化操作回到业务 API，使用工单版本检测并发 |
| 备注 | 新增 V6 migration、备注实体/服务/API、可信作者、最多展示最近 100 条 | 记录内部协作结论；不自动发送客户，也不自动进入模型上下文 |
| 幂等 | UI 创建接入持久化命令协调器；备注请求 ID 按工单隔离并使用服务端实体 ID | 防止创建响应丢失后的重试重复落单，防止备注并发重复与跨工单 ID 冲突 |
| 并发一致性 | 版本单调合并、指标请求顺序保护、过期编辑窗口禁用 | 旧列表响应不能覆盖刚保存的新状态；旧草稿不能借新版本覆盖字段 |
| AI/审核 | 保留失败重分析前的已保存结果；分析请求超时独立配置；审核后更新指标 | 失败可恢复，原有有效证据不因重试丢失 |
| 审计 | 备注写入与审计同事务；审计白名单只存不可变备注 ID；demo 可读本地审计 | 可以把内部备注追溯到事件；安全模式的审核员/管理员门禁保持有效 |
| 质量展示 | 明确标出 mock 离线评估；移动端表格转为完整字段的纵向记录，其他尺寸支持键盘滚动 | 防止将样例评估数字当作生产效果 |
| 本地运行 | 一条命令启动 React、Java、Python；端口预检、随机内部凭据、进程清理 | 降低运行成本，并可重复进行跨服务验收 |

主要文件：`apps/support-copilot-web/src/features/workbench/useTicketWorkflow.ts`、`features/tickets/`、`services/api.ts`、`src/workspace.css`；`services/support-copilot-api/src/main/java/com/cyagent/supportcopilot/ticket/Ticket{Creation,Assignment,Note}*.java`；`db/migration/V6__ticket_internal_notes.sql`；`scripts/dev-workspace.sh`。视觉约定见根目录 [DESIGN.md](../../DESIGN.md)。

## 当前验证结果

以下命令均在本轮工作树运行。命令以仓库根目录为起点；表中注明子目录。测试可以证明本地行为与回归结果，不能证明真实生产流量、模型质量或上线许可。

| 命令 | 结果 | 证据范围 |
| --- | --- | --- |
| `cd apps/support-copilot-web && npm test` | 71 通过、3 跳过 | Vitest：契约、分析/审核、版本冲突、创建重试、分页默认过滤、迟到刷新覆盖防护；跳过项为需显式开启的 live API 契约测试 |
| 同目录 `npm run test:node` | 12 通过 | mock API 契约、构建预算、子进程管理 |
| 同目录 `npm run test:e2e` | 21 通过 | 375/768/1280 三尺寸：分析成功、fallback、409 刷新、拒绝审核焦点、知识发布、审计分页、图表与错误响应 |
| 同目录 `npm run build:budget` | 类型检查、生产构建和全部预算通过 | 最终 JS 首屏 846,696 B / gzip 271,232 B；总 JS 2,039,253 B / gzip 667,221 B；CSS 39,678 B / gzip 8,069 B |
| 同目录 `npm run lint` | 退出 0 | Oxlint；构建仍保留 ECharts 延迟块体积提示，不将提示当作失败 |
| `cd services/support-copilot-api && ./gradlew test --no-daemon --max-workers=1` | 238 项，227 通过、11 跳过、0 失败 | Java 全量回归；包括 5 项备注 API 测试和 4 项创建/并发备注/可信领取测试 |
| `cd services/support-copilot-ai && .venv/bin/pytest -q` | 201 通过 | 原 Python 工作流、检索、结构化响应、失败边界；本轮未改 Python 业务实现 |
| `node apps/support-copilot-web/scripts/verify-workspace-flow.mjs` | 通过 | 浏览器使用真实 Java/Python：创建→领取→编辑→开始处理→备注→分析→审核→刷新读回→解决→关闭；另验证旧版本 PATCH 与关闭后备注均返回 409 |
| `node apps/support-copilot-web/scripts/verify-workspace.mjs` | 20 个页面/尺寸组合通过 | 工作台、概览、知识、审计、质量 × 375/768/1280/1600：横向页面溢出 0、axe 违规 0、浏览器运行错误 0 |
| `./scripts/dev-workspace.sh` | 启动与重新启动通过 | 三服务健康检查；停止 Java 后脚本检测退出并清理另外两项服务；当前预览由此脚本运行 |
| `git diff --check` | 退出 0 | 工作树空白格式检查 |

浏览器可复核材料：[完整业务流程结果](screenshots/workflow-results.json)、[20 个界面检查结果](screenshots/surface-results.json)、[桌面工作台](screenshots/workbench-1600.png)、[移动工作台](screenshots/workbench-375.png)、[已保存审核](screenshots/review-saved.png)、[已关闭工单](screenshots/closed-ticket.png)。浏览器验证脚本只接受 localhost/127.0.0.1，会创建合成工单，不适用于真实客户数据环境。

独立复审：前端最终 `CLEAR / APPROVE`，后端最终 `WATCH / APPROVE`，无代码阻断项。视觉最终复审确认此前移动表格与知识正文问题已解决，无阻断项，报告见 `.omo/evidence/enterprise-visual-final.md`。后端 WATCH 指下面的 MySQL 证据缺口。报告分别在 `.omo/evidence/enterprise-frontend-final.md` 与 `.omo/evidence/enterprise-backend-final.md`；这些本地证据不等于用户已完成 diff 审核。

CSS 预算从此前 Task 12 的局部可访问性范围调整到本次工作台范围：40 KB raw / 8.5 KB gzip；先删除了被替代的重复样式声明，再记录新预算。JavaScript 的既有上限没有放宽。

## 正常与失败路径

正常路径：浏览器校验命令 → Java 校验身份/版本/业务状态 → 数据与审计同事务落库 → 返回服务端工单快照 → 页面合并版本并刷新相关指标。分析额外经过 Java → 带服务身份的 Python 工作流 → 结构化结果/引用 → Java 再次检查版本 → 人工记录审核。

已经验证的失败路径包括：旧版本更新拒绝且不覆盖新值、终态拒绝备注、相同创建键不同内容冲突、相同备注并发重放仅写一次、不同工单同备注请求 ID 独立写入、伪造作者字段拒绝、未登录/错误角色拒绝、分析失败保留之前结果、用户可重试且幂等键不丢失、迟到队列返回不能降低工单版本。

## 尚未获得的证据与产品边界

- Docker daemon 当前不可连接，本轮未设置其显式开关 `SUPPORT_COPILOT_RUN_MYSQL_TESTS=true`，11 项可选 MySQL 测试未执行。本轮备注表迁移在 H2/Flyway 已验证，MySQL 备注写入、重试、重启读回与审计的专项验证仍待补齐；不能借以前的 MySQL 结果宣称本轮通过。
- 一键入口使用匿名本地 demo + 内存 H2，关闭后数据重置。`pilot` 持久化、OIDC 配置和备份部署仍走现有独立流程；本轮没有上线、生产 SSO、多租户隔离或真实客户渠道集成。
- 只有新 UI 使用的 `POST /api/tickets/commands/create` 承诺创建幂等。兼容旧客户端的 `POST /api/tickets` 仍保留原行为，没有幂等重试保证。前端请求键在页面内保留，刷新页面后不恢复未确认的创建命令。
- 服务端队列按创建时间与 ID 做游标分页。`已加载 · SLA` 只对已加载工单排序，非全库 SLA 查询；全局快捷搜索也明确限定已加载工单。
- 备注最多展示最近 100 条；负责人编辑仍为文本字段，尚无组织成员目录。领取使用后端可信身份，安全模式显示 JWT subject，不信任浏览器传来的操作人。
- 当前指标 API 缺少可追溯历史趋势时，概览明确展示“趋势数据暂不可用”；不会用随机曲线代替历史。
- 本轮 AI 为确定性 mock，没有重新验证 live 模型、live 评估、模型质量、成本或生产容量。审核表示内部审核记录，尚未实际向客户发送消息。
- 这是当前工作树的工程验收，尚未人工代码审核、提交或发布。可写入简历的是具体实现与本地测试结果，不能写真实企业生产经历或已验证的高并发/准确率。

## 运行与复测

安装 README 所列 Node、Java 21、Python 和项目依赖后，在根目录运行 `./scripts/dev-workspace.sh`，打开 `http://127.0.0.1:18173`。默认业务端口 18080、AI 端口 18000，均绑定本机。端口可分别通过 `SUPPORT_WORKSPACE_WEB_PORT`、`SUPPORT_WORKSPACE_API_PORT`、`SUPPORT_WORKSPACE_AI_PORT` 设置。Ctrl+C 停止三个服务，日志在 `.local/workspace/`。

下一位协作者先检查 `git status --short` 和本文件的源码摘要，再运行相应回归。优先补 MySQL 新备注命令的专项集成测试与真实登录/持久化 Pilot 验收；失败时保留错误与证据，不修改测试或文档来制造通过。

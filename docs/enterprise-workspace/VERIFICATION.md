# 企业工单辅助平台：当前实现与验收

> 后续状态：本文件为工作台阶段验收。随后完成的真实AI评估与修复见[当前状态](../STATUS.md)和[真实AI基线](../verification/live-baseline-2026-09-09/README.md)；本文件旧AI测试计数和源码摘要不覆盖后续修改。

2026-09-09，第二轮运行加固。当前工作区已具备全量队列查询、全量快捷搜索、持久化工单活动、按真实业务事实计算的指标，以及可重启、可备份恢复的本地工作区。创建、领取、编辑、备注、分析、审核、解决与关闭继续使用真实 Java/Python 服务。

基础 HEAD 为 `4df3bf44907c34318132496929bad4a3974ad88b`，分支 `master`，工作树包含未提交改动。用户明确授权直接重构；此前逐步教学的暂停要求不作为本轮执行前置条件。原有基础设施改动保留，未创建提交、推送或远端部署。本文的结果针对当前工作树，不能仅凭基础 SHA 重现；最终源码摘要见 [source-manifest.json](source-manifest.json)。第一轮的阶段记录保留在 [VERIFICATION-R1.md](VERIFICATION-R1.md)，不作为第二轮的当前证据。

## 已实现

| 业务问题 | 当前行为 | 关键实现 |
| --- | --- | --- |
| 第一页之外的紧急工单容易被忽略 | 数据库对全部匹配记录按最新创建、SLA 截止时间、优先级排序；支持关键词、状态、优先级、负责人筛选和准确匹配总数 | `TicketQueueRepositoryImpl`、`TicketQueueCursor`、`TicketQueue` |
| 快捷查找只能找到已加载记录 | Cmd/Ctrl+K 搜索全部工单，可直接打开当前队列之外的工单；防抖、取消旧请求、错误重试 | `CommandPalette`、`useTicketWorkflow.openTicket` |
| 工单最新状态不足以解释处理经过 | 从原有不可变审计记录查询工单创建/修改/备注、全部分析及审核；游标加载历史，展示时间、关联版本与 Trace | `ticket/activity/`、`TicketActivity` |
| 优先级不能代表 SLA 风险 | 开放工单中已超时或距截止不超过 2 小时才计为风险；已解决/关闭排除 | `OperationalMetrics` |
| 缺少可核验的趋势与耗时 | V7 保存 `resolved_at` 和 `duration_ms`；按 UTC 实际创建/解决日期分桶，最近最多 1000 条已记录分析计算均值及最近秩 p95 | V7、`AnalysisPersistenceService`、`TicketService`、`OperationalMetrics` |
| 保存后列表可能保留旧过滤/排序/总数 | 成功变更使队列查询失效；旧请求校验 epoch，工单快照保留最高版本；分析保存后读取失败明确区分处理结果 | `useTicketWorkflow` |
| 首屏承担大量非必需代码 | 图表仅导入所需 ECharts 模块，搜索、创建、编辑、活动及拒绝窗口延迟加载；资源失败保留页面外壳并可重试 | `App`、`OverviewView`、各工作台组件 |
| 关闭本地预览丢失业务数据 | 默认使用文件 H2、Flyway 迁移与 Hibernate 校验；临时模式需要显式开启 | `dev-workspace.sh`、`workspace-defaults.properties` |
| 文件备份可能与独立数据库进程竞争 | 离线备份/恢复持有与 H2 FileChannel 互斥的 POSIX 文件锁；恢复同时锁住旧/新文件、校验 SHA-256、先保留现库再原子替换 | `workspace-data.sh`、`workspace_data.py` |

活动接口面向客服提供经过裁剪的业务视图；JWT 操作人只显示“已认证操作人”，不会通过新接口泄露原始 subject 或角色。审核员/管理员的完整审计查询保留既有权限边界。内部备注不自动发给客户，也不自动进入模型上下文。

## 验证结果

以下是第二轮真实执行结果。命令从注明的目录运行；原始日志另复制到本目录的 `evidence/`。测试与源码校验仅证明列出的本地范围。

| 命令与目录 | 结果 | 覆盖范围 |
| --- | --- | --- |
| Java：`SUPPORT_COPILOT_RUN_MYSQL_TESTS=true ./gradlew test --no-daemon --max-workers=1` | 273 项通过，0 跳过、0 失败、0 错误 | 全量后端，包括 14 项 MySQL Testcontainers 场景；备注并发/回放/重启、V7、真实指标与 UTC 午夜、权限、事务、状态转换 |
| Web：`npm test` | 85 通过、3 跳过 | 全量 Vitest；新增全量搜索、旧查询迟到、变更后过滤和总数、分析保存后 GET 失败、活动切换/分页/重试；跳过的是需要显式启用的 live API 契约 |
| Web：`npm run test:node` | 12 通过 | mock API 合约、资源预算、子进程清理 |
| Web：`npm run test:e2e` | 21 通过 | 375/768/1280 三尺寸，真实浏览器操作受控 API 夹具，包含图表像素、审核键盘焦点、401/403/409与错误响应 |
| Web：`npm run build:budget` | 全部通过 | 类型检查、生产构建及既有 JS/CSS 预算；没有为本轮放宽 JavaScript 上限 |
| Web：`npm run lint` | 通过 | Oxlint |
| 根目录：AI venv `python -m scripts.verify_docs --repo-root .` | 通过 | Markdown 链接、API 路由、运行 profile、模型配置与边界契约 |
| AI：`.venv/bin/pytest -q` | 201 通过 | Python 工作流、检索、响应校验和故障边界 |
| AI：`.venv/bin/python -m evaluation.run_mock_evaluation` | 31 案例通过，0 失败 | 固定确定性 mock 基线；不代表真实模型效果 |
| 根目录：`bash scripts/tests/workspace-data.test.sh`；AI venv pytest 执行 `scripts/tests/test_workspace_data.py` | Shell 场景通过；3 项竞争测试通过 | 错误校验和/路径/运行锁/打开文件拒绝、旧库保留；复制和替换窗口中的独立进程锁竞争 |
| 本地真实业务流程与 20 个界面组合 | 完整流程与 20 组合通过，0 axe 违规/页面溢出/运行错误 | Java/Python 完整闭环，四宽度五页面、axe、页面溢出与浏览器错误 |

独立新功能 QA 的 16 个场景通过：三种排序、负责人过滤/总数、快捷打开初始页面之外的工单、活动分页与错误重试、坏游标 400、终态操作保护。报告见 `evidence/r2-qa-review.md`。目标完整性、代码、前端上下文、安全和双重视觉独立复审均通过，无未关闭的本轮阻断项。报告位于 `evidence/r2-*-review.md` 与 `evidence/r2-visual-secondary.md`；复审不等同于用户已人工审核 diff。

最终构建：首屏 JS **803,646 B / gzip 261,253 B**；总 JS **1,470,656 B / gzip 488,956 B**；图表延迟块 **564,427 B / gzip 189,209 B**；CSS **39,933 B / gzip 8,114 B**。相比第一轮总 JS 2,039,253 B，减少 **27.9%**；首屏也从 846,696 B 降低到 803,646 B。ECharts 延迟块仍有 Vite 500 KB 提示，但通过既有明确预算。

可复核界面：[桌面工作台](screenshots/workbench-1600.png)、[移动工作台](screenshots/workbench-375.png)、[移动队列](screenshots/queue-375.png)、[全量搜索](screenshots/global-search-1280.png)、[运营概览](screenshots/overview-1600.png)、[完整业务流程](screenshots/workflow-results.json)、[20 个界面结果](screenshots/surface-results.json)。

## 已验证的恢复与失败路径

[persistence-results.json](persistence-results.json) 记录真实服务创建工单和备注、停服备份、重启读回、备份后继续写入、恢复旧备份后正确回到原版本的过程。运行中备份会拒绝；恢复前保留被替换数据库。最终文件锁版本另有独立真实 H2 双向互斥与窗口竞争证据，最终已再次用停止时的完整现库备份并恢复同一快照，当时全部 12 张工单 ID/版本与备注完全一致。补齐最后的本机监听限制并更名工作区配置后，再次重启最终 jar：当前 13 张工单 ID/版本全部保持，原始备注仍可读，通过 7 项迁移校验。

正常业务仍经过：浏览器提交 → Java 身份/版本/状态校验 → 数据与审计同事务落库 → 读回与刷新队列。AI 分析经过真实 Python mock 工作流，Java 在模型返回后再次校验工单版本。已覆盖旧版本 409、不合法终态变更、并发备注幂等、坏游标/跨查询游标、迟到请求、保存成功而后续读取失败、活动加载失败重试及数据库锁竞争。

## 运行方式与限制

安装 README 指定依赖，在根目录运行 `./scripts/dev-workspace.sh`，打开 `http://127.0.0.1:18173`。三个服务仅绑定本机；匿名 demo 在应用启动层也拒绝通配、公网和空监听地址，14 个新增真实启动配置测试通过。默认 Web/API/AI 端口分别为 18173/18080/18000。Ctrl+C 正常关闭，数据库在 `.local/workspace/data/support-copilot.mv.db`，日志在 `.local/workspace/`。需要一次性临时库时设置 `SUPPORT_WORKSPACE_EPHEMERAL=true`。

停止工作区后执行 `./scripts/workspace-data.sh backup`；恢复用 `./scripts/workspace-data.sh restore <返回的备份目录>`。恢复只接受 `.local/workspace/backups/` 直接子目录。工具需要 Python 3.11+、本地 POSIX 文件系统与文件锁语义；不是网络共享盘/Windows/跨版本数据库迁移的备份方案。

- 本地运行使用匿名 demo 与确定性 mock AI；不是生产登录。现有 JWT 角色与 MySQL Pilot 经过本地测试，但真实企业 SSO、组织成员目录、客户渠道发送、多租户、高可用及容量验收仍未完成。
- 没有调用真实外部模型或处理真实客户数据。固定 live 评估此前的失败与人工审核缺口仍未关闭；一次 mock 或 live 成功不能推导真实客服准确率、稳定性或成本。人工审核记录不表示已经向客户发送回复。
- 旧记录的解决时间和分析耗时不会补造；趋势从实际记录开始，延迟统计仅覆盖非空样本。SLA 的 2 小时窗口是当前规则，尚未引入按合同/工作日定制的 SLA 引擎。
- 负责人仍为完整姓名文本；内部备注只展示最近 100 条。活动分页来自审计关系，旧演示票没有创建审计时显示无历史，不补造事件。
- 队列游标绑定查询条件；新版本不承诺跨升级复用旧游标。分页不是全库静态快照，并发变更后需要刷新。UI 创建请求在当前页面保留幂等键，页面刷新后不会恢复未确认命令；旧 `POST /api/tickets` 仍为兼容非幂等接口。
- 运行测试与代码复审不等于人工业务验收、镜像发布安全检查或生产部署许可。可写入简历的是具体实现和本地验证，不是真实企业生产经历。

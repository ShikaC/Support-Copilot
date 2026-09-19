# Support Copilot 阅读记录

## 2026-09-10：RAG 回答必须满足用户条件

已确认的具体判断：解释“用户的远程电脑没有浏览器；官方文档提供令牌认证方式；候选回答却只要求打开浏览器”后，作者对“该回答是否通过”明确回答“不通过”。这支持作者理解该反例：找到相关登录文档不等于最终回答符合用户条件。

对应材料：`docs/verification/public-rag-pilot-2026-09-10/annotation-drafts.json` 的 gh-public-375；`corpus/gh_auth_login.txt` 第 18–20 行和 `corpus/gh_help_environment.txt` 第 1–3 行。候选正常路径是按固定版本给出有依据的无浏览器方案；相关失败路径是忽略无浏览器条件、仅要求 --web。

边界：这是学习过程中的单个反例判断，不是 gh-public-375 全量人工标注通过，不证明作者审核了令牌类型、权限、历史版本或所有引用；不更新 cases.json 的 NOT_REVIEWED，不产生准确率。本轮没有项目模型调用或功能测试。HEAD 为 `4df3bf44907c34318132496929bad4a3974ad88b`，master，dirty；仅新增本阅读记录，保留未提交边界。可陈述理解了该评测反例，不能据此在简历写成人工基线已完成。

接续方式（2026-09-10）：根据作者明确要求，已直接推进[质量输入离线审计](../verification/quality-input-audit-2026-09-10/README.md)，把“补问可以合格但不等于解决”落实到评分协议，不重复浏览器条件题或用教学题阻挡评测工作。该报告仅是本轮实作与待审阅入口；作者尚未确认新的概念或 diff，因此本阅读记录不新增“已理解”结论，人工审核字段也未改变。

> 本文件只记录作者已经能够复述的代码和流程，不替代当前事实或路线文档。

## 2026-09-04：分析主链路与关键失败语义

### 作者已能复述

- React 记录正在分析的工单 ID，调用 `POST /api/tickets/{id}/analyze`。
- Java 读取完整工单，记录分析开始时的 `sourceTicketVersion` 和 `traceId`，再通过内部服务身份调用 Python。
- Python 进入 `/analyze`、runner 和 `AnalysisWorkflow`，返回结构化分析结果。
- Java 在 AI 返回后重新读取工单；版本一致才在短事务中保存分析并更新工单；React 成功后刷新服务端工单。
- `hits=[]` 时不调用 live 模型，返回 `status=FALLBACK`、`mode=fallback` 和 `fallbackReason=insufficient_evidence`。
- Python 服务不可用属于已命名的外部依赖故障，返回 `mode=fallback`、`status=FALLBACK` 和 `fallbackReason=ai_service_unavailable`；未知程序或契约错误不能伪装成 fallback。
- 分析开始版本为 7、当前版本为 8 时，Java 不保存旧分析，返回 `409` 和 `VERSION_CONFLICT`；React 重新读取最新工单。

### 代码位置

- `apps/support-copilot-web/src/features/workbench/useTicketWorkflow.ts`
- `apps/support-copilot-web/src/services/api.ts`
- `services/support-copilot-api/src/main/java/com/cyagent/supportcopilot/ticket/TicketController.java`
- `services/support-copilot-api/src/main/java/com/cyagent/supportcopilot/analysis/AnalysisCommandService.java`
- `services/support-copilot-api/src/main/java/com/cyagent/supportcopilot/analysis/AnalysisService.java`
- `services/support-copilot-api/src/main/java/com/cyagent/supportcopilot/analysis/AiServiceClient.java`
- `services/support-copilot-api/src/main/java/com/cyagent/supportcopilot/analysis/AnalysisPersistenceService.java`
- `services/support-copilot-ai/app/main.py`
- `services/support-copilot-ai/app/analysis_runner.py`
- `services/support-copilot-ai/app/workflow.py`
- `services/support-copilot-ai/app/knowledge.py`

### 证据边界

本记录来自 2026-09-04 的源码阅读和口头复述。2026-09-05 又在同一 dirty 工作树上启动 Docker Desktop，并运行问题一的两个 MySQL focused 场景：`2 passed`、`0 failed`、`0 skipped`。这证明真实 MySQL 初始化、pilot context、空库和分析/审核 payload 重启读取，但不证明 HTTP Controller 级 MySQL 流程、问题二、问题三、完整 Compose 或 live API。当前 Git SHA 为 `4df3bf44907c34318132496929bad4a3974ad88b`，工作树不干净。

## 2026-09-05：问题一 MySQL 基线

### 作者已能复述

- MySQL 测试由 `SUPPORT_COPILOT_RUN_MYSQL_TESTS=true` 显式开启；没有 Docker 或没有该变量时的 skip 是环境门禁，不是业务通过。
- `migratedPilotSchemaStartsWithoutDemoTickets` 在干净 MySQL 上验证 Flyway v5、checksum 非空和 pilot 库没有演示工单。
- `largeAnalysisAndReviewPayloadsRoundTripExactlyAfterRestart` 写入工单、分析和审核数据，关闭并重新建立 Java context 后读取，确认大文本内容没有丢失或截断。
- 最初两个场景真实执行并通过，因此当时没有发现需要修改的 Schema 或 Entity 持久化映射缺陷；随后补充了 HTTP Controller 级 MySQL 验证。

### 证据边界

随后新增并通过 `httpTicketCreateAndReadUseMySqlAfterApplicationRestart`：它用真实 MySQL 的 Spring WebApplicationContext 验证 HTTP 创建、关闭 context、重新启动 context 后读取；手工网络验证又用 `curl` 真实创建、停止 API、重启 API 后读取同一工单。三项 focused 测试输出为 `3 passed`、`0 failed`、`0 skipped`，随后完整 API 模块测试输出为 `228 tests`、`0 skipped`、`0 failures`、`0 errors`。命令和结果记录在 `docs/STATUS.md` 与 `services/support-copilot-api/build/test-results/test/TEST-com.cyagent.supportcopilot.config.MySqlProfileIntegrationTests.xml`。证据绑定 HEAD `4df3bf44907c34318132496929bad4a3974ad88b`，工作树仍不干净；build 报告未提交。

## 2026-09-05：问题二 Flyway checksum 与重复迁移

### 作者已能复述

- 首次 `migrate()` 在干净 MySQL 上建立 v1-v5 并写入 `flyway_schema_history`。
- 第二次 `migrate()` 的正确结果不是重新执行 SQL，而是 no-op；因此测试比较两次的当前版本、checksum、success 和 history 行完全一致。
- 已应用 migration 的 checksum 被修改时，Flyway 必须在应用使用数据库前拒绝启动；测试期望根因为 `FlywayValidateException`。
- 这次没有修改 migration SQL 或绕过校验，只补上了真实 MySQL 下第二次迁移的回归测试。

### 证据边界

问题二 focused 测试输出为 `3 passed`、`0 failed`、`0 skipped`；新增测试后完整 API 模块输出为 `229 tests`、`0 skipped`、`0 failures`、`0 errors`。当前 Git SHA 为 `4df3bf44907c34318132496929bad4a3974ad88b`，工作树仍不干净；问题三随后单独验证通过，详情见下一节。

## 2026-09-05：问题三 Hibernate 旧 Schema 拒绝

### 作者已能复述

- `local`/`pilot` 使用 `spring.jpa.hibernate.ddl-auto=validate`，Hibernate 只检查 Schema 是否匹配，不负责替应用修改数据库。
- 测试先用 Flyway 建立完整 v1-v5，再删除 `knowledge_active_release.release_id` 和外键，并关闭 Flyway，模拟 migration 没有执行完整的旧数据库。
- 应用启动时必须失败，且失败根因必须是 `SchemaManagementException`；这样故障会在服务对外提供请求前暴露。

### 证据边界

问题三 focused 测试 `missingKnowledgeActivePointerColumnPreventsPilotStartup` 在当前 SHA `4df3bf44907c34318132496929bad4a3974ad88b` 上输出 `1 passed`、`0 failed`、`0 skipped`。本轮没有修改生产代码，只确认现有 pilot 校验配置和真实 MySQL 故障演练有效；工作树仍不干净。

## 2026-09-10：质量证据中心交付（实现与解释，未记录作者新复述）

用户委托直接优化产品。本轮解释了一个数据流：冻结原始结果 → 离线重算/导出 → Java 路径与摘要校验 → 当前鉴权客户端 → 质量证据页。normal live 必须同时满足 SUCCEEDED/live/null fallback reason；HTTP 200、保存、规则检查与事实正确性分别统计。相关文件、失败与验证见 [交付记录](../verification/product-quality-center-2026-09-10/README.md)。

AI 已实现并测试这些边界；尚无作者对本轮 diff 的新复述或真人模型输出审核记录，不能写成作者已理解或审核通过。历史输入标签仍为 AI 建议。下一轮直接接续实验隔离与标签确认，不重复已经讲过的基础题。

## 2026-09-10：独立真实诊断与检索截断（未记录作者新复述）

用户确认未人审的13题可以先真实诊断，质量分数留空。已交付独立runner、调用STARTED/终态账本、隔离数据库及完整重启读回，详见[本轮证据](../verification/isolated-runner-2026-09-10/README.md)。运行揭示13个不同输入得到同一query：`AnalysisWorkflow._build_query`只取正文前180字符，恰好全部是统一说明。生成模型仍看到完整正文，但业务问题没有进入检索，这是需要优先修复的实际数据流问题。

本轮解释/代码审查与自动测试由AI完成，没有将其记为作者已理解或真人审核。用户可直接查看实际输入、query、命中、回复和耗时；不重复旧教学题。下一切片的diff重点是如何保留末尾问题及其先前业务上下文，不用修改参考答案或重跑成功记录掩盖缺陷。

## 2026-09-10：检索上下文修复（已实现，未记录作者新复述）

用户明确要求修复。沿用已确认缺陷，仅去掉query正文前180字符截断，依靠既有240/4000长度边界保留完整业务上下文。已解释上限与完整输入的取舍；13条冻结实际输入经过离线HTTP工作流产生13条不同查询，19项定向回归先失败后通过、完整AI模块324项通过。旧真实结果没有被改写，也没有新增模型调用。详细diff、失败和类型警告范围见[本轮交付](../verification/query-context-fix-2026-09-10/README.md)。

当前可以说明截断机制及其离线修复，尚不能说明召回/回答质量改善。作者未提交新的复述或真人审核结论，不记为已掌握。下一步是审阅这个最小diff，然后独立设计development真实比较；不重复旧教学题。

## 2026-09-19：候选语料构建 B1（已实现并说明，未记录作者新复述）

本轮只解释“预配置文档 → 固定输入摘要 → Node 生成 → 校验候选 → 持久化任务”这一条数据流。Python 复用唯一 Node 切片逻辑，避免重新实现 Unicode code point 切片产生漂移；评测配额和题目生成独立保留。候选成功不表示当前检索已切换。

对抗式审查以真实进程复现父 Python 被杀后锁提前释放的问题；修复后 Node 继承同一锁，并由自身主线程执行期限控制，阻塞切片在工作线程运行。正常路径、超时、父死、重启失败、兼容性证据和代码位置见 [B1 报告](../verification/corpus-build-tasks-2026-09-19/README.md)。AI 实现与审查不记作作者人工审核、已理解或模型质量结论。

## 2026-09-19：成功候选语料到索引交接（已实现并说明，未记录作者新复述）

本轮解释“候选任务 ID → 严格成功状态 → 文件摘要与内容摘要 → 内存快照 → 有预算的索引任务”数据流。选择在接纳层完成，可以不替换在线知识文件就生成匹配索引；结果关联来源任务，切片版本来自候选。接受前文件变化被拒绝，接受后变化不改变已固定输入；provider 失败保持 FAILED，不自动激活。代码、真实 HTTP/重启与故障证据见 [本轮报告](../verification/candidate-index-build-2026-09-19/README.md)。未记为作者人工审核或已理解。


## 2026-09-19：成组切换契约（已说明边界，运行时功能计划中）

本轮解释“候选身份 → 索引身份 → Java 发布事实 → 两端加载 → 重启恢复”这一条数据流。releaseVersion 与数据库行 version 不同：前者全局唯一并进入 corpus/artifact，后者保护目标行并发更新，不能代替 expected-current active。Python 失败保留内存不等于磁盘恢复；Java 重启会拒绝数据库与 corpus 不一致。

[ADR-0002](../decisions/ADR-0002-paired-knowledge-switch.md)记录维护窗口方案与下一切片；[本轮证据](../verification/paired-switch-contract-2026-09-19/README.md)区分 Java MockMvc、Python 回归与真实本机 HTTP。只有现有保护和新增版本冲突回归已验证，成组激活/恢复仍计划中。没有记录作者新复述、人工 diff 审核或已掌握结论。

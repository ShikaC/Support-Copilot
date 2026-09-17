# MySQL 三项历史跳过测试修复对照

> 文档状态：验收基线与当前验证记录
> 更新时间：2026-09-06
> 适用范围：Task 15 的 MySQL profile 集成验证

## 结论

上一轮 Java 全量非容器测试的 `3 skipped` 不是三个失败的业务功能，而是三个被环境门禁主动跳过的 MySQL 集成测试。它们要回答的是：应用在真实 MySQL、真实 Flyway migration 和 Hibernate Schema 校验下，能否安全启动、升级和持续读写。

历史记录显示，后续 Task 15 已经在 MySQL 8.4.11 上以 `SUPPORT_COPILOT_RUN_MYSQL_TESTS=true` 运行了 9 个零跳过 parity 场景。这说明这三个风险后来有历史验证证据，但该证据不绑定当前 dirty 工作区。当前默认测试在没有设置环境变量时仍会主动跳过这些容器测试。

2026-09-06 复核了当前 dirty 工作树：四个 MySQL Testcontainers 测试类保留显式环境门禁，但移除了 `disabledWithoutDocker=true`。因此未显式启用时的 skip 仍是预期行为；一旦显式启用而 Docker 不可用，测试会失败，不再把环境故障报告成绿色跳过。完整 API 测试为 `229 tests, 0 skipped, 0 failures, 0 errors`。

本文件是后续逐项测试和修复的对照基线。每项只有在当前 Git SHA 上重新运行、保存原始证据并完成人工检查后，才能标记为“当前已验证”。截至 2026-09-06，问题一的三个 focused MySQL 场景、问题二的三个 focused Flyway 场景、问题三的一个 focused stale-schema 场景和一次网络级 HTTP 手工验证已经在当前 SHA 上真实执行并通过。

## 共同边界

### 当前状态

- 当前 HEAD：`4df3bf44907c34318132496929bad4a3974ad88b`。
- 当前分支：`master`。
- 工作树：不干净，存在用户已有的 Pilot、Docker、Compose、备份恢复和测试改动。
- 三项测试的环境门禁位于 `services/support-copilot-api/src/test/java/com/cyagent/supportcopilot/config/MySqlProfileIntegrationTests.java` 的类级 `@EnabledIfEnvironmentVariable`。
- 缺少 Docker 或没有显式设置 `SUPPORT_COPILOT_RUN_MYSQL_TESTS=true` 时，跳过是预期行为，不应把 skip 改成无条件执行，也不应删除测试。

### 共用前置条件

1. Docker daemon 和 Docker Compose/Testcontainers 可用。
2. 使用项目当前声明的 MySQL 8.4.11 镜像和当前工作树。
3. 每次使用新的数据库名、容器或证据目录，避免旧卷掩盖 migration 问题。
4. 设置 `SUPPORT_COPILOT_RUN_MYSQL_TESTS=true`。
5. 记录完整 Git SHA、`git status --short`、命令、退出码和测试摘要。

同一宿主上的 MySQL gate 必须由单一 Gradle 进程串行执行，并设置
`--max-workers=1`；不要让多个审查任务同时启动 Testcontainers。每次验收必须读取
JUnit XML 的 `tests`、`skipped`、`failures` 和 `errors`，不能只依据 `BUILD SUCCESSFUL`。

建议的 focused 命令：

```bash
cd services/support-copilot-api
SUPPORT_COPILOT_RUN_MYSQL_TESTS=true \
  ./gradlew test --tests '*MySqlProfileIntegrationTests' --no-daemon
```

这条命令只证明 `MySqlProfileIntegrationTests` 当前类的结果。它不证明完整 Pilot Compose、跨版本回滚、备份恢复或镜像安全扫描已经通过。

## 问题一：真实 MySQL Schema 与 Java 映射

### 原始问题

历史测试名为 `appliesSchemaAndPreservesCurrentRepositoryAndApiMappings`。它被跳过的直接原因是 Task 3 只运行了 H2 和非容器 profile 测试，真实 MySQL/Testcontainers 被明确延后到 Task 15；因此 MySQL 的实际表结构、约束、列类型和 Java Repository/API 映射没有在当时的全量测试中得到验证。

### 产生原因

- H2 不是 MySQL 的行为等价替代品，尤其不能覆盖 MySQL 的列类型、长度、约束、字符集和连接初始化行为。
- 应用启动依赖 Flyway migration 和 Hibernate `validate` 的先后关系；只验证编译或 H2 启动无法证明真实数据库能建立正确 Schema。
- 分析结果、审核内容和审计数据最终要落到 MySQL。映射问题可能在启动时暴露，也可能直到某条写入路径才暴露。

### 产品影响

- 新环境可能无法启动，或分析、审核、审计写入失败。
- 字段长度、时间精度、版本字段或关联约束不匹配时，可能出现数据截断、读取错误或事务失败。
- 本地 H2 演示仍可能正常，造成“演示通过但 Pilot 部署失败”的假象。

### 最小解决方案

1. 在干净 MySQL 8.4.11 数据库上执行完整 Flyway migration。
2. 验证空库启动，不插入演示工单。
3. 通过当前 Java 服务写入和读取至少一条工单、分析运行、审核记录和审计事件。
4. 关闭并重新启动应用，再读取同一批数据，确认持久化内容和版本字段保持一致。
5. 如果失败，优先修复 migration、Entity 映射、profile 顺序或列定义；不得通过关闭 Hibernate 校验或退回 `create-drop` 来掩盖问题。

### 验收标准

- Flyway 在干净数据库上成功完成当前全部 migration。
- 应用以 `local` 或 `pilot` profile 启动成功，且没有 H2 fallback、demo fixture 或 `create-drop`。
- 工单、分析、审核和审计数据可以写入、读取，并在应用重启后保持一致。
- focused 测试结果为 `passed > 0`、`failed = 0`、`skipped = 0`。
- 证据目录保存启动日志、migration 摘要、关键读写结果和测试报告。

### 当前覆盖与状态

当前测试类中的 `migratedPilotSchemaStartsWithoutDemoTickets` 覆盖了 MySQL migration、版本、checksum 非空和空库无演示数据；`largeAnalysisAndReviewPayloadsRoundTripExactlyAfterRestart` 覆盖大 payload 和重启后的分析/审核读取；新增的 `httpTicketCreateAndReadUseMySqlAfterApplicationRestart` 覆盖 HTTP 创建、Spring context 重启和 HTTP 读取。2026-09-05 在当前 SHA `4df3bf44907c34318132496929bad4a3974ad88b` 上的 focused 命令输出为 `3 passed, 0 failed, 0 skipped`，随后完整 API 模块输出为 `228 tests, 0 skipped, 0 failures, 0 errors`，状态为 `focused 已验证`。当前最后一次完整运行的 MySQL 类 JUnit 报告为 `tests=5, skipped=0, failures=0, errors=0`。此外，真实 API + MySQL 临时环境的 `curl` 创建为 `201`，API 重启后读取为 `200`。工作树仍 dirty，build 报告未提交。

## 问题二：Flyway checksum 与重复 migration

### 原始问题

历史测试名为 `migrationChecksumIsStableAndSecondMigrateIsANoOp`。它被跳过的直接原因与问题一相同：没有启用 MySQL/Testcontainers，无法在真实 `flyway_schema_history` 上验证已应用 migration 的 checksum 和重复迁移行为。

### 产生原因

- Flyway 会保存已应用 migration 的 checksum；如果已经发布的 migration 文件被修改，当前文件与数据库历史不一致，校验应失败。
- 如果没有验证第二次 `migrate` 是 no-op，发布脚本可能重复执行结构变更，或把数据库漂移误判为成功。
- 仅检查 SQL 文件存在，不能证明 Flyway 在真实数据库中的历史记录、校验和执行顺序正确。

### 产品影响

- 发布可能在数据库迁移阶段失败，导致 API 无法启动或发布窗口停机。
- 数据库版本和应用代码版本可能不一致，进而影响工单分析、审核和审计读写。
- 如果错误地修改已发布 migration 并绕过校验，后续环境会产生不可追踪的 Schema 漂移。

### 最小解决方案

1. 在全新 MySQL 数据库上执行 `flyway.migrate()`，记录当前 migration 版本和每个 checksum。
2. 在同一个数据库上再次执行 `flyway.migrate()`，确认没有新增 migration、重复 DDL 或数据副作用。
3. 人为修改一个已应用 migration 的 checksum，仅用于测试数据库，确认启动或校验失败并产生 `FlywayValidateException`。
4. 恢复测试数据库，不把测试中的 checksum 修改带入任何共享环境。
5. 对已经发布的 migration 只追加新版本，不直接修改历史文件；若确有必要修复，必须经过明确的数据库迁移决策和受控证据记录。

### 验收标准

- 首次 migration 成功，并写入预期版本和非空 checksum。
- 第二次 migration 为 no-op，Schema、记录数和 checksum 不发生非预期变化。
- 已应用 migration 被篡改时，Flyway 在应用使用该数据库前拒绝启动或校验，并报告 `FlywayValidateException`。
- 没有使用 `flyway clean`、drop/truncate 或静默修复来制造绿色结果。
- focused 测试结果为 `passed > 0`、`failed = 0`、`skipped = 0`，并保存迁移前后证据。

### 当前覆盖与状态

当前测试类中的 `migrationChecksumIsStableAndSecondMigrateIsANoOp` 在同一真实 MySQL 数据库上执行两次 `migrate()`，比较两次的当前版本及 `flyway_schema_history` 的 version、checksum、success 行完全一致；`tamperedMigrationHistoryPreventsPilotStartup` 覆盖 checksum 篡改拒绝启动；`migratedPilotSchemaStartsWithoutDemoTickets` 检查首次迁移后的版本、migration 数量和 checksum 非空。2026-09-05 在当前 SHA `4df3bf44907c34318132496929bad4a3974ad88b` 上，问题二 focused 输出为 `3 passed, 0 failed, 0 skipped`，随后完整 API 模块输出为 `229 tests, 0 skipped, 0 failures, 0 errors`，状态为 `focused 已验证`。当前最后一次完整运行的 MySQL 类 JUnit 报告为 `tests=6, skipped=0, failures=0, errors=0`。

## 问题三：Hibernate 对旧 Schema 的拒绝

### 原始问题

历史测试名为 `hibernateValidationRejectsAnUnmigratedSchema`。它被跳过的直接原因是没有在真实 MySQL 中构造缺列或过期 Schema，再让应用以校验模式启动；因此无法证明应用会在启动阶段拒绝不兼容数据库。

### 产生原因

- 应用代码会随着版本增加列、约束或关联关系，而已有数据库可能没有同步升级。
- 如果 Hibernate 使用自动建表、更新表或关闭校验，应用可能掩盖数据库漂移并启动到不可靠状态。
- 只有在真实 MySQL 上关闭或绕过 Flyway，再使用缺少关键列的 Schema 启动，才能验证 `validate` 门禁确实有效。

### 产品影响

- 过期数据库可能被误认为可用，应用启动成功但在实际分析、审核或知识发布请求中失败。
- 故障从部署阶段延迟到用户请求阶段，排查成本和影响范围更大。
- 如果错误发生在分析持久化之后，可能出现分析结果、工单状态和审计记录之间的不一致风险。

### 最小解决方案

1. 先用当前 migration 建立完整测试数据库。
2. 删除一个当前 Entity 必需的列或约束，形成可控的 stale schema。
3. 禁用 Flyway 仅用于该故障演练，让 Hibernate `validate` 负责检查现有 Schema。
4. 启动应用并确认失败根因是 `SchemaManagementException` 或等价的 Schema 校验错误。
5. 恢复数据库后，再用正常 Flyway 顺序验证应用可以成功启动。
6. 保持 `local`/`pilot` 的 Hibernate `ddl-auto=validate`；不得改为 `update`、`create` 或 `create-drop` 以绕过门禁。

### 验收标准

- 缺少关键列或约束时，应用在对外提供业务请求前启动失败。
- 失败根因明确为 Hibernate Schema 校验错误，而不是连接超时、认证失败或测试代码异常。
- 完整 migration 后，应用可以正常启动并通过基本读写。
- 正常路径和 stale-schema 失败路径均有日志或测试报告，且证据绑定当前 SHA。
- focused 测试结果为 `passed > 0`、`failed = 0`、`skipped = 0`。

### 当前覆盖与状态

当前测试类中的 `missingKnowledgeActivePointerColumnPreventsPilotStartup` 覆盖关键列缺失时的 `SchemaManagementException`：它先完成 Flyway v1-v5，再删除 `knowledge_active_release.release_id` 和外键，关闭 Flyway 后启动 pilot context，确认 Hibernate `validate` 在服务对外提供请求前拒绝旧 Schema。2026-09-05 在当前 SHA `4df3bf44907c34318132496929bad4a3974ad88b` 上输出为 `1 passed, 0 failed, 0 skipped`，状态为 `focused 已验证`；未修改生产代码。

## 逐项推进顺序

一次只处理一项，建议顺序如下：

1. 问题一：确认干净 MySQL 上的 Schema、映射和重启持久化。
2. 问题二：在问题一通过的数据库基础上确认 checksum、重复迁移和篡改拒绝。
3. 问题三：构造 stale schema，确认 Hibernate 在启动阶段拒绝，再恢复正常数据库。
4. 最后运行完整 MySQL parity 测试和必要的 Pilot Compose 验证。

每项完成后必须记录：

- 测试项和影响文件。
- 正常路径与失败路径。
- 执行命令、完整 Git SHA 和工作树状态。
- passed/failed/skipped 数量及原始证据位置。
- 当前可以声称的结论，以及仍不能证明的范围。

## 完成定义

这三项只有在以下条件全部满足后，才能写成“当前已解决”：

- 当前工作树下显式启用 MySQL 测试，三项相关场景均 `passed`，没有 `skipped` 或隐藏失败。
- 至少一次使用干净数据库，至少一次覆盖重启或重新启动校验。
- 正常路径和命名失败路径都被观察到，并保存可复核证据。
- 没有通过放宽校验、删除测试、忽略失败或修改文档措辞来通过门禁。
- 更新 `docs/STATUS.md`，明确写入当前 SHA、验证命令、证据范围和剩余限制。

完成这三项不等于 Task 15 全部完成。跨版本旧 API 回滚、fresh-volume backup/restore 和严格镜像安全扫描仍需单独验收。

## 参考

- [当前项目状态](../../STATUS.md)
- [MySQL migration 基线记录](61-profile-mysql-migration-baseline.md)
- [基础设施运行手册](../../../infra/README.md)
- [当前 MySQL 集成测试](../../../services/support-copilot-api/src/test/java/com/cyagent/supportcopilot/config/MySqlProfileIntegrationTests.java)

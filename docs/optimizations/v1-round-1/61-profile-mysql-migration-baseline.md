# 第 61 轮：隔离运行 profile 并准备 MySQL migration 基线

## 问题与风险

Java 原配置在所有环境中默认打开 H2、`create-drop`、H2 Console 和演示数据。任何未明确配置数据库的运行都会得到一套临时演示库，无法证明 schema migration、持久化重启或部署配置安全。

## 修改层与流程

- `demo`：内存 H2、`create-drop`、H2 Console、8 条演示工单。
- `test`：随机命名的隔离 H2、`create-drop`、无 fixtures、无 H2 Console。
- `local`/`pilot`：要求非空 MySQL JDBC 环境变量，配置 Flyway 和 Hibernate `validate`，无 fixtures、无 H2 Console；缺配置时失败关闭。
- 全局启动门禁：在 datasource 创建前要求且只允许一个 `demo`、`test`、`local` 或 `pilot`；缺失、`default`、未知和多 profile 均返回稳定的允许列表错误。
- `V1__baseline.sql`：只创建 `tickets`、`analysis_runs`、`analysis_reviews` 及现有 repository 所需索引和唯一约束，不包含 drop、truncate、delete 或 Flyway clean。
- `MySqlProfileIntegrationTests`：源码覆盖 migration、Hibernate validation、API/repository、LOB/time/version、空 pilot 库、checksum 重复执行和 stale schema 拒绝，本轮只要求编译通过。

AI 服务 URL、超时和 `EVALUATION_REPORT_PATH` 继续保留在 profile 之外的公共配置中。

## 已验证证据

- 首个提交 `83e9b03` 被独立门禁拒绝：无 profile 的真实 `bootRun` 成功启动随机 H2，不能把该提交单独视为 Task 3 通过。
- 启动门禁 TDD：修复前 4 个 invalid-profile runtime cases 全部失败并实际连接 H2；修复后 4 passed，且日志没有 H2 URL。
- focused profile/migration tests：9 passed，0 failed，0 skipped。
- Java 全量非容器 tests：97 total，94 passed，0 failed，3 skipped；三个 skip 全部属于 Task 15 的 `MySqlProfileIntegrationTests`，不计为 Task 3 通过。
- `compileTestJava`：通过，包含 MySQL integration 与 stale-schema 测试源码。
- 手动无 profile：`./gradlew bootRun --args='--server.port=18184'` exit 1，稳定错误列出四个允许 profile；无 health listener、H2 datasource 日志或 H2 文件变化，端口已释放。
- 手动 demo：健康状态 `UP`，8 条工单、7 条 seeded analyses，H2 Console HTTP 302；进程已退出且端口 18185 已释放。
- 手动 pilot 缺失/空配置：两个场景均 exit 1 并命名 `SUPPORT_COPILOT_DB_URL`，日志无 H2 fallback、H2 文件集合未变化；端口 18186/18187 已释放。
- 静态审计：migration 无 destructive statement 或可执行 Flyway clean，local/pilot 无启用的 H2/create-drop/demo 行为，AI 与 evaluation-report 公共配置保留，Task 3 差异无 secret-shaped value。

完整命令和 raw logs 见 `.omo/evidence/task-3-enterprise-minimum-pilot.md`。

## Task 15 延后项

MySQL 8 实库、Testcontainers、Compose、Flyway version/checksum、Hibernate 实库 validation、LOB/time/`@Version` 映射、空库行为、stale schema 拒绝和 Java 重启持久化均不属于修订后的 Task 3 运行时验收，统一由 Task 15 完成。

历史上 Task 3 曾因缺少容器运行时记录为 BLOCKED；Momus 批准修订计划后，该外部门禁已明确移至 Task 15，不能继续作为 Task 3 阻塞，也不能把历史尝试当作当前通过证据。Task 3 只声明配置与 migration 契约已准备，不声明真实 MySQL 已验证。

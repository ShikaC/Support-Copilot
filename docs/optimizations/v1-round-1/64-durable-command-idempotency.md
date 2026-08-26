# 第 64 轮：持久化分析与审核命令幂等

## 问题与风险

原有浏览器请求合并和 Java single-flight 只覆盖单进程的在途分析。客户端超时后重试、Java 重启或两个实例同时收到请求时，仍可能重复调用 AI、重复保存业务结果和重复写审计。审核同内容的顺序复用也不能解决跨实例竞争。

## 修改层与流程

所有分析、采纳/编辑回复和拒绝回复 POST 都在 Controller 边界解析 `Idempotency-Key`。键长 16–128，只允许 ASCII 字母、数字、`.`、`_`、`:`、`-`；缺失和非法键返回稳定的 400 code 与 `traceId`。

Flyway V3 新增 `command_idempotency`：全局唯一键、命令类型、路由 scope、SHA-256 规范化请求指纹、状态、owner token、lease、原始成功 HTTP 状态/JSON 和时间戳。指纹输入包含命令、路由、目标 ID 和 trim 后的审核内容，但数据库只保存哈希，不保存可读工单正文或审核请求 payload，也不把它们写入日志。

处理顺序为：

```text
解析并校验 key
-> 在独立短事务中创建/锁定命令记录
-> 相同完成记录：反序列化原始响应
-> 不同指纹/命令/scope：409
-> 活跃 owner：有界等待并轮询
-> 过期/失败 owner：确定性重新认领
-> owner 执行业务
-> 同一业务事务保存业务 + AuditEvent + COMPLETED 响应
```

心跳在长 AI 调用期间续租，活跃 owner 不会因初始 lease 到期被窃取。异常会把未完成命令标记为可恢复失败；完成记录只有在业务和审计同时提交时才可重放。完成写失败会回滚业务与审计。JVM single-flight 仍可减少同实例工作，但数据库唯一约束、行锁和 lease 才是正确性边界。

React 为每个新规范化命令生成 UUID。在途分析共享同一 Promise；只有 fetch 在收到任何 HTTP 响应前以 `TypeError` 失败时，下一次相同命令才复用旧键，以处理“服务端可能已提交但客户端没收到响应”的不确定性。成功、结构化 HTTP 失败或响应契约失败后都会清除键。

## 验证方式

```bash
cd services/support-copilot-api
./gradlew test --tests '*CommandIdempotencyIntegrationTests' --rerun-tasks --no-daemon
./gradlew test --tests '*IdempotencyKeyTests' --tests '*AnalysisReviewApiTests' --no-daemon
./gradlew test --no-daemon

cd ../../apps/support-copilot-web
npm test
npm run build

cd ../..
./scripts/run-local-smoke.sh
```

文件型 H2 场景使用两个独立 Spring servlet context 共享同一 Flyway V1–V3 数据库，观察 provider/analysis/audit/idempotency 行数、lease 续租、过期 owner 恢复、重启重放、跨命令/目标/payload 冲突和完成失败回滚。Hibernate 保持 `ddl-auto=validate`；六个 migration `LONGTEXT` 字段使用显式 JDBC `VARCHAR` + `LONGTEXT` DDL 映射，V3 指纹使用显式 `CHAR` 映射，验证 Flyway 先迁移到 V3 再通过 schema validation。

## 当前限制

这些结果证明本地 H2 上的工程契约，不证明 MySQL 的锁调度、隔离级别、崩溃恢复或性能。`CommandIdempotencyMySqlIntegrationTests` 已加入并只在 `SUPPORT_COPILOT_RUN_MYSQL_TESTS=true` 时启用；Task 15 必须在 MySQL 8 重新验证 migration、Hibernate mapping、并发 winner、重启重放、lease 和业务/审计/完成事务 parity。本轮未运行 Docker、Compose 或 MySQL，也未实现 Task 11 的登录 UI。

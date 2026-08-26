# 第 63 轮：记录可信 append-only 审计事件

## 问题与风险

工单、分析和人工审核虽然已经各自持久化，但没有统一、可信且可查询的动作记录。页面派生的工单时间线不能证明操作身份，也不能保证业务提交与审计记录同时成功或同时回滚。

## 修改层与流程

Java 新增不可变 `AuditEvent`、只暴露 `insert/query` 的应用仓储、typed recorder、查询服务和 `GET /api/audit-events`。Flyway `V2__trusted_audit_events.sql` 只新增表与索引，不修改或删除已有数据。

事件固定保存：唯一 ID、actor subject/type/排序去重后的 roles、受控 action、受控 target type/id、适用版本、入口 `traceId`、`createdAt` 和结构化白名单 metadata。安全 profile 的 actor 只来自 `SecurityContext` 中的 JWT；`demo` 明确使用 `anonymous-demo`。浏览器不能提交 actor、action、trace 或 metadata。

动作矩阵：

| 业务提交 | action | target | 白名单 metadata |
| --- | --- | --- | --- |
| 工单创建 | `TICKET_CREATED` | ticket + committed version | 空对象 |
| 实际 PATCH | `TICKET_UPDATED` | ticket + committed version | 变更字段名 |
| 实际取消负责人 | `TICKET_UNASSIGNED` | ticket + committed version | `ASSIGNEE` |
| 分析或 fallback 持久化 | `ANALYSIS_PERSISTED` | analysis + source version | mode、status、fallback category、source version、result ID |
| 人工审核 | `ANALYSIS_REVIEW_*` | review + ticket version | review action、source version、analysis result ID |

no-op、过期/非法写入、事务冲突和同内容审核重放不会增加事件。业务保存与审计 insert 在同一个 Spring 事务；recorder 使用 `MANDATORY` propagation，不能脱离外层事务独立提交。审计 insert 失败会回滚业务写，外层业务随后失败也会回滚已经 flush 的事件。

元数据不允许工单标题/描述/客户字段、生成或审核回复、拒绝原因、provider payload、prompt、证据正文、认证信息、JWT、token、原始异常或消息。序列化统一使用 Jackson，不拼接 JSON 字符串。

查询只允许 `SUPPORT_REVIEWER`/`SUPPORT_ADMIN`；匿名为 401，agent 为 403。排序固定为 `createdAt DESC, id DESC`，cursor 是 Base64URL 编码的结构化复合键，limit 为 1 到 100，并支持 target type/id 过滤。非法 cursor/filter/limit 统一返回 `400 INVALID_AUDIT_QUERY`，响应只包含脱敏字段。

## 验证方式

```bash
cd services/support-copilot-api
./gradlew test --tests '*AuditEventIntegrationTests' --no-daemon
./gradlew test --tests '*FlywayMigrationContractTests' --tests '*PilotSecurityContractTests' --no-daemon
./gradlew test --no-daemon
cd ../..
./scripts/run-local-smoke.sh
```

9 条审计集成测试观察真实 H2/API 行、两种事务回滚方向、actor/roles/trace、敏感值缺失、角色矩阵、过滤和 keyset 无重复/缺口；3 条静态测试锁定 append-only 仓储、实体和 controller 表面。完整 Java 结果为 148 tests、145 passed、3 个 Task 15 MySQL skips。隔离端口手工 HTTP 场景得到 6 条精确事件，重放/no-op/stale 前后均为 6，三页 keyset 与数据库顺序一致，敏感 canary 匹配为 0，并完成全部进程、端口和临时材料清理。原始证据在 `.omo/evidence/task-5/`。

## 当前限制

Task 8 才会把受治理的知识发布动作接入同一个 typed recorder；本轮没有创建知识发布事件。Task 15 才会在 MySQL 8 验证 V2 migration version/checksum、索引和业务/审计事务 parity。当前证据只支持本地 H2 pilot-equivalent 工程能力，不是生产运行、监管合规或不可篡改外部账本声明。

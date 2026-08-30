# 第 71 轮：收紧工单查询边界与聚合指标访问

## 问题与风险

上一轮审查发现工单列表先加载全部记录再在 JVM 内过滤和排序，列表响应还会为每个工单分别
读取最近分析与审核，数据量增长后形成全表扫描和 N+1 查询。指标接口也通过 `findAll()`
在内存中计算总数和比率。工单号依赖 JVM 内存自增序列，重启或多实例部署会产生碰撞风险；
数据库已有值域约束的设计，但迁移没有真正落地。

## 修改层与流程

本轮保留 `GET /api/tickets` 的数组响应形状，避免破坏当前 React Schema，同时增加可组合的
keyset 分页：`status`、`priority`、`category` 和 `keyword` 在 JPQL 查询中下推，固定使用
`createdAt DESC, id DESC`，通过 `X-Next-Cursor` 传递续页。游标只编码排序键，不回显原始异常；
页大小限制为 1 到 100，非法页、游标和筛选参数使用稳定错误码。

列表组装先批量读取当前页所有工单的最新分析，再批量读取这些分析的最新审核；单工单详情
路径保留原有的单条读取语义。指标改为数据库 `count` 和按类别 `group by` 聚合，避免把整张
表加载到应用内。新增 V5 Flyway 迁移，给受控工单值域增加 `CHECK` 约束，并为队列、状态和
优先级查询增加复合索引。创建工单不再依赖进程内序列，而使用长度受控的随机不透明工单号，
数据库唯一键仍是最终约束。

V5 同时为类别过滤和当前页的分析/审核批量读取增加带稳定排序键的复合索引；V1 中已有的
`(ticket_id, created_at)` 和 `(analysis_id, created_at)` 索引暂时保留，后续可在确认线上索引
迁移窗口后合并清理，避免把本轮查询优化变成未经验证的在线索引删除。

## 验证

```bash
cd services/support-copilot-api
./gradlew test --tests 'com.cyagent.supportcopilot.ticket.TicketCursorTests' \
  --tests 'com.cyagent.supportcopilot.ticket.TicketPaginationIntegrationTests' \
  --tests 'com.cyagent.supportcopilot.ticket.TicketServiceListTests' \
  --tests 'com.cyagent.supportcopilot.metrics.MetricsServiceTests' \
  --tests 'com.cyagent.supportcopilot.config.FlywayMigrationContractTests'
```

测试覆盖游标往返和非法输入、H2 demo 分页/过滤/错误响应、列表批量组装、聚合指标以及
非破坏性迁移内容。当前 React 工作台仍只请求首批并在客户端筛选；真实 MySQL、压测、
全文检索、多租户、分布式限流/队列、OpenTelemetry 和 SLO 仍属于后续 Task 15+ 范围。

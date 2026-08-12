# 优化 05：增加事务与 API 回归测试

## V1 的问题

V1 只有应用启动测试和 mock 分析工厂测试，没有覆盖数据库事务、并发版本或 HTTP 冲突契约。即使事务注解没有实际生效，原测试仍然会全部通过。

## 本轮修改

新增两个测试类，共四个测试场景：

1. 正常保存时，`AnalysisRun` 与 `Ticket` 一起更新，并记录来源版本。
2. 工单版本变化后，拒绝旧分析，且不新增分析记录。
3. 分析记录写入失败时，工单修改也一起回滚。
4. 版本冲突通过 HTTP 返回结构化 `409`。
5. Java 明确进入 fallback 时，不能把结果标记为成功，且必须升级人工复核。

## 相对 V1 的改进

这些测试保护的是业务结果，而不是只检查某个方法上有没有注解。以后有人误删事务、版本比较或异常映射时，测试会直接指出行为退化。

## 对应代码

- `services/support-copilot-api/src/test/java/com/cyagent/supportcopilot/analysis/AnalysisPersistenceServiceTests.java`
- `services/support-copilot-api/src/test/java/com/cyagent/supportcopilot/ticket/TicketAnalysisConflictApiTests.java`

## 当前测试结果

```text
AnalysisPersistenceServiceTests: 3 passed
TicketAnalysisConflictApiTests: 1 passed
MockAnalysisFactoryTests: 3 passed
SupportCopilotApiApplicationTests: 1 passed
```

合计 8 个测试通过。

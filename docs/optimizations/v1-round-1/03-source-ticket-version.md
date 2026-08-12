# 优化 03：记录分析来源工单版本

## V1 的问题

V1 的 `AnalysisRun` 只记录 `ticketId` 和 `traceId`：

- `ticketId` 只能说明分析属于哪张工单。
- `traceId` 只能帮助串联请求日志。

两者都不能说明 AI 当时读取的是工单的哪个版本。

## 本轮修改

`AnalysisRun` 新增不可为空的 `sourceTicketVersion` 字段。它保存 AI 输入所对应的 `Ticket.version`。

例如：

```text
AI 读取 Ticket version 3
→ AnalysisRun.sourceTicketVersion = 3
→ 保存分析后 Ticket 被更新为 version 4
```

分析记录仍然写 3，因为它描述的是“生成这份分析时使用的版本”，不是保存完成后的工单版本。

## 相对 V1 的改进

后续排查时可以回答：

- 这份分析是否基于当前工单生成。
- 某次工单修改发生在分析之前还是之后。
- 版本冲突测试应使用哪个输入版本。

## 对应代码

- `services/support-copilot-api/src/main/java/com/cyagent/supportcopilot/analysis/AnalysisRun.java`
- `services/support-copilot-api/src/main/java/com/cyagent/supportcopilot/analysis/AnalysisPersistenceService.java`

## 数据库说明

当前 V1 使用 H2 内存数据库和 `create-drop`，启动时会自动重建表。未来切换到保留数据的正式数据库时，必须使用数据库迁移脚本新增该列，不能继续依赖自动建表。

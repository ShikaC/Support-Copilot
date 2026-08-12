# 优化 02：阻止旧分析覆盖新工单

## V1 的问题

分析需要等待 Python。在等待期间，另一名客服可能已经修改了工单。V1 得到 AI 结果后仍会更新工单，旧输入生成的结果可能覆盖新业务状态。

例子：

```text
读取 version 3 的工单
→ Python 开始分析
→ 客服把工单改成 version 4
→ Python 返回基于 version 3 的结果
→ V1 直接写回并覆盖 version 4
```

## 本轮修改

`AnalysisService` 在调用 Python 前记录 `sourceTicketVersion`。持久化事务开始后重新读取数据库中的工单，并比较：

```text
expectedVersion == currentVersion
```

- 相等：允许保存。
- 不相等：抛出 `TicketVersionConflictException`，整个事务回滚。

`Ticket` 原有的 JPA `@Version` 仍然保留。显式比较负责发现“AI 等待期间已经发生的变化”，JPA 乐观锁负责拦截“比较之后又发生的极短并发变化”。

## 相对 V1 的改进

旧分析不再覆盖更新后的工单。发生冲突时：

- 不保存旧分析记录。
- 不修改当前工单。
- 不生成 fallback。
- 由客服查看最新工单后，决定是否重新分析。

## 对应代码

- `services/support-copilot-api/src/main/java/com/cyagent/supportcopilot/analysis/AnalysisService.java`
- `services/support-copilot-api/src/main/java/com/cyagent/supportcopilot/analysis/AnalysisPersistenceService.java`
- `services/support-copilot-api/src/main/java/com/cyagent/supportcopilot/analysis/TicketVersionConflictException.java`

## 验证

集成测试先保存 version 0 的工单，再把它更新为 version 1，最后尝试保存基于 version 0 的分析。测试确认异常类型正确，且数据库保留 version 1 的工单，没有新增分析记录。

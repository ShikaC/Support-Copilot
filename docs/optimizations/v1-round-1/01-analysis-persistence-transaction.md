# 优化 01：独立的短事务持久化

## V1 的问题

V1 把 `saveRun()` 写在 `AnalysisService` 内，并由同一个类的 `analyze()` 和 `seed()` 直接调用。Spring 的 `@Transactional` 依靠代理对象工作，同类内部调用不会经过代理，因此事务边界并不可靠。

风险是：

- `AnalysisRun` 已保存，但 `Ticket` 更新失败。
- `Ticket` 已更新，但分析历史没有保存。
- 页面看到的工单状态与分析历史互相矛盾。

## 本轮修改

新增 `AnalysisPersistenceService`，由 Spring 注入到 `AnalysisService`。公开的 `persist()` 方法使用 `@Transactional`，调用会经过 Spring 代理。

AI 调用不放入事务。事务只覆盖：

1. 重新读取工单。
2. 检查工单版本。
3. 保存 `AnalysisRun`。
4. 更新 `Ticket`。
5. 主动执行 SQL 并提交。

## 相对 V1 的改进

```text
V1
同一个 Service 内部调用带 @Transactional 的方法
→ 事务可能没有生效

现在
AnalysisService 调用独立的 AnalysisPersistenceService
→ 调用经过 Spring 代理
→ 两项写入一起提交或一起回滚
```

事务没有包住 Python 网络调用，因此不会在等待 AI 时长时间占用数据库事务。

## 对应代码

- `services/support-copilot-api/src/main/java/com/cyagent/supportcopilot/analysis/AnalysisPersistenceService.java`
- `services/support-copilot-api/src/main/java/com/cyagent/supportcopilot/analysis/AnalysisService.java`

## 验证

集成测试构造无法保存的分析记录，确认异常后：

- 没有留下 `AnalysisRun`。
- `Ticket` 的状态和版本都没有变化。

# 优化 56：建立可追溯质量基线与无证据安全门

## 业务问题

质量页面和 Java 指标接口曾经包含没有对应运行记录的固定数字，知识页面在真实后端连接时仍然展示本地演示文章。Python 的 live 工作流也会先调用模型，再根据空检索结果标记 fallback，无法证明模型没有在无证据条件下生成回复。

## 改进方案

本轮把结果来源分成三类：

```text
已持久化的工单/分析/审核记录 -> Java 返回运行态统计
固定 mock 评估命令           -> mock-latest JSON/Markdown 报告
没有数据来源                  -> API 返回 null，页面显示不可用状态
```

Python 的结构化模型草稿增加 `citation_indexes`。系统只接受当前检索结果中的、唯一的、1-based 证据序号，并把它们转换成引用文本；评估报告同时保存 retrieved chunk ID 和 cited chunk ID。无证据时直接走本地谨慎回复，不把空知识上下文交给模型。

Java `/api/metrics` 只计算当前 H2 中实际存在的分析运行和审核记录。历史趋势、分析耗时和 RAG 评估报告没有持久化来源时返回空值。React 的质量页、知识页和状态栏不再显示未追溯的历史数字或演示知识目录。

## 验证结果

- Python 全量测试：82 passed。
- 固定 mock 评估：18/18 通过；最新报告写入 `evaluation/reports/mock-latest.json` 和 `mock-latest.md`。
- Java 全量测试：`BUILD SUCCESSFUL`，新增指标服务测试验证无运行记录时质量字段为空。
- React lint、24 条测试通过，另有 3 条显式真实契约测试跳过；生产 build 通过。
- 新进程 Java 健康检查通过，`/api/metrics` 返回实际 H2 工单快照、实际分析成功率，未记录的趋势、耗时、采纳率和评估报告返回空值。
- 隔离 Java -> Python mock 成功流程返回 `SUCCEEDED` 并保存相同 traceId；无证据工单返回 `FALLBACK / insufficient_evidence`、0 hits、0 citations 并要求人工升级。

## 能力边界

当前评估仍是固定模拟工单和确定性 mock，不代表 live 模型质量、生产延迟或真实客服效果。Java 还没有从 Python 评估报告读取质量指标的接口，因此质量页暂不展示 mock 报告数字。真实 live RAG 成功记录、持久化向量索引、认证身份和生产数据库仍未完成。

## 面试关键位置

- `services/support-copilot-ai/app/workflow.py`：无证据时在模型调用前进入安全 fallback。
- `services/support-copilot-ai/app/local_analysis.py`：校验证据序号并生成可映射引用。
- `services/support-copilot-ai/evaluation/report.py`：保存 retrieved/cited chunk 映射并计算引用覆盖率。
- `services/support-copilot-api/src/main/java/com/cyagent/supportcopilot/metrics/MetricsService.java`：只返回有真实来源的运行态指标。
- `apps/support-copilot-web/src/App.tsx`：后端没有真实来源时显示不可用状态，不展示静态质量数字。

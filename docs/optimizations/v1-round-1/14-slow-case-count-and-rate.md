# 优化 14：补充慢案例数量与比例

## V1 原来的问题

离线评估报告只记录平均耗时、P50、P95 和最大耗时。这些指标可以描述整体耗时分布，却不能直接回答：

```text
超过 2000ms 的案例有几条？
这些慢案例占本次评估的多少？
```

只比较慢案例数量也不公平。例如 100 条中的 7 条和 1000 条中的 7 条，虽然数量相同，但问题严重程度不同。

## 本次如何修改

评估报告新增三个互相关联的字段：

- `slow_case_threshold_ms`：慢案例判断标准，当前为大于 2000ms。
- `slow_case_count`：超过标准的案例数量。
- `slow_case_rate`：慢案例数量除以全部案例数量。

Markdown 报告也会展示这三项数据。判断标准与结果一起保存，因此以后查看历史报告时仍然知道“慢”的具体含义。

## 相对 V1 的改进

```text
V1：
只能看到平均值、百分位数和最慢值
-> 无法直接统计慢案例规模

优化后：
同时保存慢案例标准、数量和比例
-> 能看到具体有几条
-> 能公平比较不同数据集规模的评估结果
```

## 自动化测试

测试将 18 条响应的耗时固定为：

- 2 条为 2001ms。
- 16 条为 100ms。

然后验证报告保存慢案例数量 `2`、比例 `2 / 18`，并验证 Markdown 中出现对应指标。

完整 Python 测试结果：`33 passed`。

## 涉及文件

- `services/support-copilot-ai/evaluation/models.py`
- `services/support-copilot-ai/evaluation/report.py`
- `services/support-copilot-ai/evaluation/markdown.py`
- `services/support-copilot-ai/tests/test_evaluation_report.py`

## 当前边界

2000ms 目前是离线评估代码中的固定标准，还不是业务配置，也不会影响评估是否通过。下一阶段需要积累真实运行数据，再决定标准是否需要配置化，以及慢案例比例是否应成为发布门槛。

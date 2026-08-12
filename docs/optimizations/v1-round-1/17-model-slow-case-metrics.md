# 优化 17：按模型统计慢案例比例

## V1 原来的问题

报告已经保存每条案例的模型名称和耗时，但仍需要人工逐条筛选，才能比较不同模型的慢案例情况。

只比较慢案例数量也容易误判：

```text
模型 X：10 条案例中有 2 条慢案例，比例 20%
模型 Y：100 条案例中有 10 条慢案例，比例 10%
```

虽然模型 Y 的慢案例数量更多，但模型 X 更容易产生慢案例。

## 本次如何修改

评估报告新增 `model_performance`。每个模型分别保存：

- `model_name`：模型名称。
- `total_cases`：该模型处理的总案例数。
- `slow_case_count`：耗时大于 2000ms 的案例数。
- `slow_case_rate`：慢案例数除以该模型总案例数。

Markdown 报告新增“分模型性能”表格，可以直接比较数量和比例。

## 相对 V1 的改进

```text
V1：
需要人工逐条筛选模型和耗时
-> 容易只看数量而忽略不同模型的案例基数

优化后：
自动按模型分组并计算慢案例比例
-> 可以公平比较不同案例数量的模型
-> 可以快速定位性能风险更高的模型
```

## 自动化测试

测试模拟：

- `model-x` 处理 1 条，慢案例 1 条，比例 100%。
- `model-y` 处理 17 条，慢案例 1 条，比例约 5.9%。

测试同时验证 JSON 结构和 Markdown 表格结果。

## 涉及文件

- `services/support-copilot-ai/evaluation/models.py`
- `services/support-copilot-ai/evaluation/report.py`
- `services/support-copilot-ai/evaluation/markdown.py`
- `services/support-copilot-ai/tests/test_evaluation_report.py`

## 当前边界

模型级指标目前只包含慢案例统计，不影响整份评估是否通过。样本量很小时比例容易出现剧烈波动，例如 1 条案例中有 1 条慢案例会显示 100%；解释比例时必须同时查看总案例数。

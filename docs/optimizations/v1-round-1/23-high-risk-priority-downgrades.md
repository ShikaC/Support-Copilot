# 优化 23：统计高风险优先级降级

## V1 原来的问题

优先级准确率只能说明判断是否完全正确，不能说明错误有多危险：

```text
URGENT -> HIGH：降低 1 级
URGENT -> LOW：降低 3 级
```

两种结果在普通准确率中都只是一次错误，但后者更可能让紧急工单被长期延误。

## 本次如何修改

项目明确优先级顺序：

```text
LOW = 1
MEDIUM = 2
HIGH = 3
URGENT = 4
```

当人工标准等级减去系统实际等级大于或等于 `2` 时，记为一次高风险优先级降级。

每种 `(model_name, prompt_version)` 配置新增：

- `high_risk_priority_downgrade_count`：高风险降级数量。
- `high_risk_priority_downgrade_rate`：高风险降级数量除以该配置总案例数。

该比例越低越好，理想值为 `0`。

## 相对 V1 的改进

```text
V1：
所有优先级错误都只算一次错误
-> 无法区分轻微偏差与严重降级

优化后：
单独统计降低 2 级或以上的错误
-> 能发现可能延误紧急工单的危险配置
-> 同时展示数量和比例，避免只看数量误判
```

## 自动化测试

风险规则测试覆盖：

- `URGENT -> MEDIUM`：高风险降级。
- `HIGH -> LOW`：高风险降级。
- `URGENT -> HIGH`：普通一级降级，不计入高风险。
- `MEDIUM -> HIGH`：升级错误，不计入高风险降级。

报告测试验证 `model-x + ticket-analysis-v2` 的一条高风险降级会得到数量 `1`、比例 `1.0`。

## 涉及文件

- `services/support-copilot-ai/evaluation/metrics.py`
- `services/support-copilot-ai/evaluation/models.py`
- `services/support-copilot-ai/evaluation/report.py`
- `services/support-copilot-ai/evaluation/markdown.py`
- `services/support-copilot-ai/tests/test_evaluation_metrics.py`
- `services/support-copilot-ai/tests/test_evaluation_report.py`

## 当前边界

“降低 2 级或以上”是当前项目明确采用的 V1.5 评估规则，并不是所有公司的通用标准。正式上线前应由客服运营、合规或值班负责人确认阈值，并使用真实历史工单验证该规则是否符合业务风险。

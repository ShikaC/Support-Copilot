# 优化 24：高风险优先级降级零容忍门槛

## V1 原来的问题

优化 23 已经能够统计高风险优先级降级，但该指标只用于观察，不会影响评估的最终结论。

因此可能出现：

```text
高风险降级数量：1
最终结论：通过
```

即使系统把一张 `URGENT` 工单判断为 `LOW`，只要其他平均指标足够高，整份报告仍可能通过。

## 本次如何修改

整批评估指标新增：

- `high_risk_priority_downgrade_count`：整批高风险降级数量。
- `high_risk_priority_downgrade_rate`：整批高风险降级数量除以案例总数。

评估阈值新增：

```text
max_high_risk_priority_downgrade_count = 0
```

最终通过条件增加：

```text
实际高风险降级数量 <= 最大允许数量
```

当前最大允许数量为 `0`，所以只要出现一条高风险降级，整份评估立即不通过。

## 相对 V1 的改进

```text
V1：
高风险降级只是报告中的观察数据
-> 严重错误可能被其他平均指标掩盖

优化后：
高风险降级成为零容忍发布门槛
-> 一条严重降级就阻止评估通过
-> 报告同时展示实际数量、比例和最大允许数量
```

## 自动化测试

测试覆盖门槛两侧：

- 一条 `HIGH -> LOW` 高风险降级：最终结论为“不通过”。
- 确定性 mock 基线中高风险降级为零：最终结论仍为“通过”。

第一种测试中，分类准确率和优先级准确率均约为 `0.944`，高于原有 `0.90` 门槛。这证明“不通过”确实来自高风险降级门槛，而不是其他准确率指标。

## 代码职责调整

新增门槛后，`evaluation/report.py` 超过项目约定的 250 行有效代码上限。本轮将配置级指标计算移动到 `evaluation/metrics.py`：

- `report.py`：组装最终评估报告。
- `metrics.py`：计算准确率、风险和配置级指标。

移动前后公式和报告结构不变，相关测试持续通过。

## 涉及文件

- `services/support-copilot-ai/evaluation/models.py`
- `services/support-copilot-ai/evaluation/metrics.py`
- `services/support-copilot-ai/evaluation/report.py`
- `services/support-copilot-ai/evaluation/markdown.py`
- `services/support-copilot-ai/tests/test_evaluation_report.py`

## 当前边界

零容忍规则依赖评估集能够代表真实高风险工单。若评估集缺少紧急案例，即使报告通过，也不能证明系统在生产场景中不会发生高风险降级。后续仍需要用经过业务审核的真实历史工单扩充评估集。

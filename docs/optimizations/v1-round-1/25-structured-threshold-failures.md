# 优化 25：结构化列出全部失败门槛

## V1 原来的问题

评估报告只保存最终的 `passed` 布尔值：

```text
通过
未通过
```

当结果为“未通过”时，开发者必须手动对比所有指标和阈值，才能知道失败原因。多个门槛同时失败时，也容易只发现其中一个。

## 本次如何修改

报告新增 `threshold_failures`。每条失败信息包含：

- `metric`：失败的指标名称。
- `actual`：本次实际结果。
- `comparison`：要求“至少达到”还是“最多允许”。
- `threshold`：门槛值。

例如：

```text
分类准确率：实际 0.889，要求至少 0.900
高风险优先级降级数量：实际 1，要求最多 0
```

Markdown 报告新增“失败门槛”部分，逐条显示所有不合格指标。

## 保证结论一致

旧代码分别计算失败原因和最终结论，未来可能出现两套逻辑不一致。本次改为：

```text
先收集 threshold_failures
threshold_failures 为空 -> passed = True
threshold_failures 非空 -> passed = False
```

失败列表成为最终结论的唯一来源，不再单独维护另一套 `all(...)` 判断。

## 相对 V1 的改进

```text
V1：
只显示“未通过”
-> 开发者需要手动检查全部指标
-> 多个失败原因可能被遗漏

优化后：
保存并展示全部结构化失败门槛
-> 直接知道哪个指标不合格
-> 同时看到实际值、比较方向和要求值
-> 失败原因与最终结论不会互相矛盾
```

## 自动化测试

测试覆盖：

- 分类准确率和高风险降级门槛同时失败时，两条原因都会被报告。
- 所有十项门槛同时失败时，十个指标名都会被完整收集。
- 没有失败门槛时，列表为空且最终结论为“通过”。
- Markdown 使用中文逐条展示实际值和门槛值。

## 涉及文件

- `services/support-copilot-ai/evaluation/models.py`
- `services/support-copilot-ai/evaluation/thresholds.py`
- `services/support-copilot-ai/evaluation/report.py`
- `services/support-copilot-ai/evaluation/markdown.py`
- `services/support-copilot-ai/tests/test_evaluation_thresholds.py`
- `services/support-copilot-ai/tests/test_evaluation_report.py`

## 当前边界

失败列表说明哪项指标没有达到门槛，但不会自动解释根因。开发者仍需结合“失败样例”中的工单 ID 和案例级错误，判断问题来自提示词、模型、知识库、检索参数还是评估数据本身。

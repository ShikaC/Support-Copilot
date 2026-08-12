# 优化 26：失败样例直接展示错误原因

## V1 原来的问题

Markdown 报告的“失败样例”只显示工单 ID：

```text
billing-details-002、billing-refund-003
```

开发者能够定位工单，却看不到具体错误。要知道分类、优先级、升级判断还是引用出了问题，仍然需要打开 JSON 报告并查找对应案例。

## 本次如何修改

Markdown 现在为每张失败工单分别显示：

- 工单 ID。
- 工单标题。
- 该案例的全部错误原因。

例如：

```text
### billing-details-002 - 支付争议需要补充什么资料
- classification: expected BILLING, got ACCOUNT_ACCESS
- priority: expected HIGH, got LOW
```

如果没有失败案例，仍然显示“无”。

## 相对 V1 的改进

```text
V1：
只列出失败工单 ID
-> 必须打开 JSON 才能知道错误原因

优化后：
直接展示 ID、标题和全部错误
-> 报告本身即可完成第一轮排查
-> 可以直接判断应检查分类、优先级、升级、引用还是回复约束
```

## 数据来源

本次没有重复计算错误。`CaseEvaluationResult` 原本已经保存：

- `subject`：工单标题。
- `failures`：案例的全部错误。

Markdown 只负责筛选 `failures` 非空的案例并展示现有结构化结果。

## 自动化测试

测试验证：

- 每张失败工单分别显示 ID 和标题。
- 同一工单的分类错误与优先级错误都会展示，不会只保留第一条。
- 不再使用只拼接 ID 的旧格式。
- 没有失败案例时显示“失败样例：无”。

## 涉及文件

- `services/support-copilot-ai/evaluation/markdown.py`
- `services/support-copilot-ai/tests/test_evaluation_report.py`

## 当前边界

错误原因仍使用内部英文指标名称，适合开发者排查。后续若报告需要交给客服运营或非技术人员阅读，可以增加中文展示层，但不应改变 JSON 中稳定的机器可读错误标识。

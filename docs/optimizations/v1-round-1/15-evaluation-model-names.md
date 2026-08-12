# 优化 15：记录评估实际使用的模型

## V1 原来的问题

每条 Python 分析响应都包含实际使用的模型名称，但离线评估报告只保存 `mock`、`live` 或 `fallback` 运行模式，没有保存模型名称。

因此两次评估即使都显示 `live`，也无法回答：

```text
两次是否使用了相同模型？
准确率或耗时变化是否与模型切换有关？
```

## 本次如何修改

评估报告新增 `model_names`，从本批次所有实际响应中收集模型名称，然后去重并排序。Markdown 报告也会直接展示这些模型。

保存集合而不是只取第一条，可以避免一批评估意外混用多个模型时，报告仍只展示第一个模型而隐藏真实情况。

## 相对 V1 的改进

```text
V1：
只知道运行模式
-> 无法把性能和准确率对应到具体模型

优化后：
保存实际响应中的全部模型名称
-> 可以比较模型切换前后的结果
-> 可以发现同一批次意外混用模型
```

## 自动化测试

mock 基线测试验证：

- JSON 报告模型集合为 `("deterministic-demo",)`。
- Markdown 报告显示 `模型：deterministic-demo`。

## 涉及文件

- `services/support-copilot-ai/evaluation/models.py`
- `services/support-copilot-ai/evaluation/report.py`
- `services/support-copilot-ai/evaluation/markdown.py`
- `services/support-copilot-ai/tests/test_evaluation_report.py`

## 当前边界

报告目前能列出本批次出现过的模型，但聚合性能指标仍是整批数据的结果。如果同一批次出现多个模型，后续应先调查为什么混用；需要长期支持多模型对比时，再按模型分别计算准确率和耗时指标。

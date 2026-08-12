# 优化 22：按分析配置统计优先级准确率

## V1 原来的问题

分类正确不代表优先级也正确。例如系统可以正确判断一张工单属于账单问题，却把应该紧急处理的工单标成低优先级。

V1 只显示整批优先级准确率。一次评估中如果包含多种模型或提示词配置，整批结果无法说明是哪种配置产生了更多优先级错误。

## 本次如何修改

`AnalysisConfigurationMetrics` 新增 `priority_accuracy` 字段。

每种 `(model_name, prompt_version)` 配置分别计算：

```text
该配置优先级判断正确的案例数 / 该配置案例总数
```

Markdown 的“分析配置性能”表格新增“优先级准确率”列。

## 相对 V1 的改进

```text
V1：
只显示整批优先级准确率
-> 无法定位哪种配置经常判断错处理紧急程度

优化后：
每种分析配置分别显示优先级准确率
-> 可以比较配置的优先级判断能力
-> 能发现分类正确但优先级错误的配置
```

## 自动化测试

测试故意让 `model-x + ticket-analysis-v2` 的第二条案例返回错误优先级 `LOW`，并验证：

- `model-x + ticket-analysis-v1` 的优先级准确率为 `1.0`。
- `model-x + ticket-analysis-v2` 的优先级准确率为 `0.0`。
- `model-y + ticket-analysis-v2` 的优先级准确率为 `1.0`。

测试同时验证结构化报告字段和 Markdown 表格结果。

## 涉及文件

- `services/support-copilot-ai/evaluation/models.py`
- `services/support-copilot-ai/evaluation/report.py`
- `services/support-copilot-ai/evaluation/markdown.py`
- `services/support-copilot-ai/tests/test_evaluation_report.py`

## 当前边界

优先级准确率把所有等级错误视为相同错误，暂时不会区分“应该紧急却判断为低”与“应该中等却判断为高”的风险差异。生产评估可以进一步增加高风险降级错误数量，但应先准备足够的真实案例和业务标准。

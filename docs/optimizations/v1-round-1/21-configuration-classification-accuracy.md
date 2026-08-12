# 优化 21：按分析配置统计分类准确率

## V1 原来的问题

报告原本只计算整批案例的分类准确率。一次评估中如果混有多种模型或提示词配置，整批结果会掩盖配置之间的差异：

```text
model-x + v1：10 条中 8 条正确，准确率 0.8
model-x + v2：10 条中 3 条正确，准确率 0.3

整批准确率：11 / 20 = 0.55
```

只看到 `0.55`，无法判断哪种配置更好。

## 本次如何修改

`AnalysisConfigurationMetrics` 新增 `classification_accuracy` 字段。

程序先使用 `(model_name, prompt_version)` 找到属于同一配置的案例，再计算：

```text
该配置分类正确的案例数 / 该配置案例总数
```

Markdown 的“分析配置性能”表格新增“分类准确率”列。

## 相对 V1 的改进

```text
V1：
只显示整批分类准确率
-> 不同配置的正确和错误结果互相混合

优化后：
每种模型与提示词组合分别显示分类准确率
-> 可以直接发现分类效果较差的配置
-> 不会用整批平均值掩盖配置差异
```

## 自动化测试

测试模拟三种分析配置：

- `model-x + ticket-analysis-v1`：分类准确率 `1.0`。
- `model-x + ticket-analysis-v2`：分类准确率 `0.0`。
- `model-y + ticket-analysis-v2`：分类准确率 `1.0`。

测试同时验证结构化报告字段和 Markdown 表格结果。

## 涉及文件

- `services/support-copilot-ai/evaluation/models.py`
- `services/support-copilot-ai/evaluation/report.py`
- `services/support-copilot-ai/evaluation/markdown.py`
- `services/support-copilot-ai/tests/test_evaluation_report.py`

## 当前边界

目前配置级指标包含分类准确率和慢案例统计。优先级、升级、检索、引用安全等指标仍是整批统计；后续应按风险和求职展示价值逐项补充，避免一次加入过多指标而让代码难以验证。

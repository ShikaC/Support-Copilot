# 优化 20：按完整分析配置统计性能

## V1 原来的问题

评估报告最初只按照模型名称统计慢案例。同一个模型使用不同提示词版本时，数据会被合并：

```text
模型 X + 提示词 v1：100ms
模型 X + 提示词 v2：10000ms

只按模型统计：
模型 X：两种提示词的结果混在一起
```

这种报告只能说明混合结果发生了变化，无法判断具体是哪个提示词版本导致性能变化。

## 本次如何修改

一次可比较的分析配置由两个字段共同确定：

- `model_name`：实际使用的模型。
- `prompt_version`：实际使用的提示词版本。

报告现在使用 `(model_name, prompt_version)` 作为联合分组条件。JSON 字段从 `model_performance` 改为 `configuration_performance`，Markdown 表格也改为“分析配置性能”。

## 相对 V1 的改进

```text
V1：
只按模型分组
-> 不同提示词版本的数据互相污染
-> 无法确定性能变化来自哪个配置

优化后：
同时按模型和提示词版本分组
-> 每一种分析配置都有独立的案例数和慢案例比例
-> 能够区分模型变化与提示词变化
```

## 自动化测试

测试在同一批报告中模拟三种配置：

- `model-x + ticket-analysis-v1`：1 条案例。
- `model-x + ticket-analysis-v2`：1 条案例。
- `model-y + ticket-analysis-v2`：16 条案例。

测试验证同一个 `model-x` 会产生两行统计，而不是被合并成一行。测试中的 v2 是历史响应数据，不代表当前 API 已经开放 v2。

## 涉及文件

- `services/support-copilot-ai/evaluation/models.py`
- `services/support-copilot-ai/evaluation/report.py`
- `services/support-copilot-ai/evaluation/markdown.py`
- `services/support-copilot-ai/tests/test_evaluation_report.py`

## 当前边界

本次只修复性能统计的归属问题。分类准确率、优先级准确率等质量指标目前仍是整批统计；如果未来需要正式比较多种配置，还应对这些质量指标进行同样的分组，并保证案例、知识库、Top N、Top K 和运行环境一致。

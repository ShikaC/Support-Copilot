# 优化 19：在评估报告中记录提示词版本

## V1 原来的问题

分析响应已经包含实际提示词版本，但离线评估报告没有保存该字段。报告只能说明使用了哪个模型，不能说明这个模型在什么提示词下产生结果。

因此准确率或耗时变化可能来自：

```text
模型发生变化
提示词发生变化
模型和提示词同时变化
```

缺少提示词版本时，无法控制变量，也无法把变化可靠归因到模型。

## 本次如何修改

评估报告新增两层提示词版本信息：

- `prompt_versions`：本批次实际响应中出现过的全部提示词版本，去重并排序。
- `CaseEvaluationResult.prompt_version`：每条案例实际使用的提示词版本。

Markdown 报告会在顶部直接展示本批次提示词版本。

## 相对 V1 的改进

```text
V1：
报告只记录模型
-> 无法判断准确率变化是否来自提示词

优化后：
同时记录模型和提示词版本
-> 可以发现同一批次意外混用提示词
-> 可以定位错误案例或慢案例使用的具体版本
```

## 自动化测试

测试模拟同一批次的历史响应中出现 v1 和 v2，并验证：

- 批次报告列出两个提示词版本。
- 第一条和第二条案例分别保留自己的版本。
- Markdown 展示两个版本。

测试中的 v2 只是一份模拟历史响应，不会让当前 API 接受尚未实现的 v2。

## 涉及文件

- `services/support-copilot-ai/evaluation/models.py`
- `services/support-copilot-ai/evaluation/report.py`
- `services/support-copilot-ai/evaluation/markdown.py`
- `services/support-copilot-ai/tests/test_evaluation_report.py`

## 当前边界

报告现在具有模型与提示词版本的案例级追踪能力，但当前评估运行器仍只运行一个工作流，不是严格的多模型或多提示词对照实验。公平对比仍要求相同案例、知识库、检索参数和运行环境。

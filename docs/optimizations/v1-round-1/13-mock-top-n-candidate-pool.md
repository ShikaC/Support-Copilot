# 优化 13：让 mock 检索真正使用 Top N 候选池

## V1 原来的问题

live 向量检索会先召回 `Top N` 个候选，再从中保留 `Top K` 条证据。mock 本地检索虽然接收了 `Top N`，却没有把它传入本地搜索函数，而是给全部知识片段打分后直接截取 `Top K`。

因此同一组参数在两种模式中含义不同：

```text
live：Top N 候选 -> 分类调整 -> Top K 证据
mock：全部片段   -> 综合打分 -> Top K 证据
```

mock 测试通过不能证明候选池参数工作，也可能让开发环境与 live 环境出现不同排序。

## 本次如何修改

本地确定性检索被拆成两个可观察阶段：

```text
标题、正文和关键词文本匹配
-> 按初始分数召回 Top N
-> 根据工单当前分类调整候选顺序
-> 保留 Top K
```

返回结果现在分别记录：

- `initialRank` 和 `initialScore`：进入分类调整前的名次与分数。
- `rerankPosition` 和 `rerankScore`：分类调整后的最终名次与分数。

这仍然是本地规则排序，不冒充独立的机器学习 reranker。

## 相对 V1 的改进

```text
V1：
Top N 在 mock 中没有作用
-> 修改 Top N 不影响候选池

优化后：
Top N 决定分类调整前可以进入的候选
-> Top N 变化可以真实改变最终证据
-> mock 与 live 的参数阶段保持一致
```

## 自动化测试

新增隐私数据导出场景：

1. `Top N = 1` 时，初排只保留文本最匹配的“数据导出任务”片段。
2. `Top N = 2` 时，“隐私请求”片段进入候选池。
3. 隐私片段根据工单分类从初始第 2 调整为最终第 1。

该测试修改前失败、修改后通过。完整 Python 测试结果：`11 passed`。

## 涉及文件

- `services/support-copilot-ai/app/knowledge.py`
- `services/support-copilot-ai/tests/test_knowledge.py`

## 当前边界

mock 使用本地文本规则，live 使用 OpenAI Embedding 和向量检索。两者现在具有相同的 `Top N -> Top K` 阶段，但算法并不相同，因此 mock 测试仍不能替代 live 集成测试和离线检索评估。

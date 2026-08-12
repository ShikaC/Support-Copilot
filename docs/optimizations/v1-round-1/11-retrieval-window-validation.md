# 优化 11：校验 Top K 不得超过 Top N

## V1 原来的问题

`AnalyzeOptions` 只分别检查参数范围：

```text
Top N：1 到 30
Top K：1 到 10
```

因此 `Top N = 3、Top K = 10` 会被当成合法请求。两个数字分别没有越界，但组合起来不合理：第一轮只有 3 个候选，第二轮不可能从中保留 10 条证据。

## 本次如何修改

在 Pydantic 的 `AnalyzeOptions` 中增加跨字段校验：

```text
Top K <= Top N：通过
Top K > Top N：拒绝请求
```

校验发生在 FastAPI 请求入口。无效参数不会进入 `AnalysisWorkflow`，也不会执行知识检索或模型调用。

错误响应使用：

```text
HTTP 422 Unprocessable Entity
错误类型：top_k_exceeds_top_n
```

## 相对 V1 的改进

```text
V1：
只检查各字段自己的数值范围
-> 接受 3/10 等无意义组合
-> 请求继续进入 RAG 工作流

优化后：
同时检查 Top N 和 Top K 的业务关系
-> 在 API 边界拒绝无效组合
-> 不浪费检索和模型资源
```

## 自动化测试

新增 API 测试发送 `Top N = 3、Top K = 10`，确认：

- HTTP 状态码为 `422`。
- 错误类型为 `top_k_exceeds_top_n`。
- 请求没有得到普通的分析成功响应。

完整 Python 测试结果：`9 passed`。

## 涉及文件

- `services/support-copilot-ai/app/models.py`
- `services/support-copilot-ai/tests/test_api.py`

## 当前边界

这次只修复检索窗口的参数关系。未实现的 `enableRerank` 请求开关已在第 12 项优化中移除，mock 模式也已在第 13 项优化中接入 `Top N` 候选池。

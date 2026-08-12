# 优化 18：将提示词版本绑定到实际提示词

## V1 原来的问题

分析请求和响应虽然包含 `prompt_version`，但它只是一个普通字符串。真正发送给模型的提示词直接写在 `OpenAIProvider` 中，模型调用也没有接收版本。

因此系统可能出现：

```text
报告记录：ticket-analysis-v99
实际执行：代码中写死的 v1 提示词
```

或者开发者修改提示词正文后忘记修改版本标签，导致两次不同提示词的评估仍显示相同版本。

## 本次如何修改

系统现在只接受已经实现的提示词版本，当前为 `ticket-analysis-v1`。未知版本会在 FastAPI 请求校验阶段返回 `422`，不会进入分析工作流，也不会进入 fallback。

模型调用的数据线变为：

```text
AnalyzeRequest.options.prompt_version
-> OpenAIProvider.analyze
-> instructions_for(prompt_version)
-> 对应版本的实际提示词
```

实际提示词移动到独立的版本路由模块。以后增加 v2 时，必须同时扩展受支持版本和对应提示词，不能只修改报告标签。

## 相对 V1 的改进

```text
V1：
版本标签与真实提示词互不关联
-> 报告可能记录不存在或错误的版本

优化后：
版本先通过请求校验，再选择对应真实提示词
-> 未知版本直接拒绝
-> 标签与实际执行内容保持绑定
```

## 自动化测试

新增测试验证：

- `ticket-analysis-v99` 返回 `422`，不再错误返回 `200`。
- live 工作流把经过校验的 `ticket-analysis-v1` 传入模型提供器。
- OpenAI 外部错误仍按原有规则进入 fallback。

## 涉及文件

- `services/support-copilot-ai/app/models.py`
- `services/support-copilot-ai/app/prompts.py`
- `services/support-copilot-ai/app/openai_provider.py`
- `services/support-copilot-ai/app/workflow.py`
- `services/support-copilot-ai/tests/test_api.py`
- `services/support-copilot-ai/tests/test_workflow_errors.py`

## 当前边界

当前只实现 v1。提示词版本已经与运行内容绑定，但离线评估报告尚未汇总和展示本批次实际出现的提示词版本；这是下一步可追踪性改进。

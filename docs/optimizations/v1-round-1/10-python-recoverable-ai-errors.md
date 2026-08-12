# 优化 10：只让可恢复的 AI 故障进入 fallback

## V1 原来的问题

`AnalysisWorkflow.run()` 使用 `except Exception` 捕获几乎所有 Python 程序异常。在 live 模式下，无论是 OpenAI 暂时不可用，还是代码字段拼错、对象为空等程序缺陷，都会生成一份 fallback 结果。

这会产生两个误导：

- 开发者可能只看到 fallback，没有及时发现代码已经出错。
- 客服可能把程序缺陷产生的降级结果当成普通外部服务波动。

结果是系统表面上仍然返回数据，但真正的错误根因被隐藏了。

## 本次如何修改

新增明确的异常层级：

```text
RecoverableAiError
├── ExternalAiServiceError
└── InvalidModelResponseError
```

外部依赖边界负责转换异常：

- `KnowledgeRetriever` 只把 OpenAI SDK 报告的向量检索故障转换为 `ExternalAiServiceError`。
- `OpenAIProvider` 只把 OpenAI SDK 报告的模型调用故障转换为 `ExternalAiServiceError`。
- 模型没有返回要求的结构化结果时，转换为 `InvalidModelResponseError`。

`AnalysisWorkflow` 现在只捕获 `RecoverableAiError`。`RuntimeError`、`AttributeError` 等未预期的程序错误不会再被伪装成 fallback。

## 相对 V1 的改进

```text
V1：
几乎任何异常 -> fallback -> 可能隐藏代码缺陷

优化后：
已确认的外部 AI 故障 -> fallback -> 业务继续并人工复核
未预期的程序缺陷    -> 抛出错误 -> 日志保留真实根因
```

这项改进没有取消 fallback，而是让 fallback 的语义更可信：它表示 AI 外部能力暂时失败，不再表示“程序发生了任何错误”。

## 自动化测试

新增四种行为验证：

1. 可恢复的 AI 故障会返回 `FALLBACK`，并要求人工复核。
2. 普通 `RuntimeError` 不会被隐藏成 fallback。
3. OpenAI 向量检索异常会在检索边界被转换。
4. OpenAI 模型调用异常会在模型边界被转换。

完整 Python 测试结果：`8 passed`。

## 涉及文件

- `services/support-copilot-ai/app/errors.py`
- `services/support-copilot-ai/app/knowledge.py`
- `services/support-copilot-ai/app/openai_provider.py`
- `services/support-copilot-ai/app/workflow.py`
- `services/support-copilot-ai/tests/test_workflow_errors.py`

## 当前边界

当前根据实际使用的 OpenAI SDK 异常类型建立边界。以后增加数据库、独立向量库或其他模型供应商时，需要为这些外部依赖增加各自明确的可恢复异常，不能重新扩大为 `except Exception`。

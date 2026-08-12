# 优化 12：移除尚未实现的 rerank 请求开关

## V1 原来的问题

Java 会向 Python 发送：

```json
{
  "enableRerank": false
}
```

Python 的 `AnalyzeOptions` 也接受该字段，但 `AnalysisWorkflow` 和 `KnowledgeRetriever` 从未读取它。即使调用方发送 `true`，检索行为也不会发生变化。

这会让接口产生错误承诺：调用方可能认为结果已经经过独立重排，实际上系统只是执行现有检索和简单排序。

## 本次如何修改

当前 V1 没有独立 rerank 模型和效果评估，因此不把简单排序冒充完整重排。本次同步修改两端契约：

- Python `AnalyzeOptions` 删除 `enable_rerank`。
- Java `AnalyzeOptions` 删除 `enableRerank`，不再发送该字段。
- Python 继续使用 `extra="forbid"`，旧调用方发送无效开关时明确返回 `422`。

真正实现 rerank 后，需要连同算法、配置、评估测试和审计字段一起重新设计，而不是只恢复一个布尔开关。

## 相对 V1 的改进

```text
V1：
接口接受 enableRerank=true
-> 实际行为不变
-> 调用方可能误认为功能已启用

优化后：
接口不再承诺未实现能力
-> Java 不发送无效字段
-> 旧调用方收到明确 422
```

## 自动化测试

新增契约测试发送 `enableRerank = true`：

- 修改前返回 `200 OK`，证明字段被静默接受。
- 修改后返回 `422`。
- 错误类型为 `extra_forbidden`。

验证结果：

- Python：`10 passed`。
- Java：`BUILD SUCCESSFUL`，13 个测试无失败。

## 涉及文件

- `services/support-copilot-ai/app/models.py`
- `services/support-copilot-ai/tests/test_api.py`
- `services/support-copilot-api/src/main/java/com/cyagent/supportcopilot/analysis/AiServiceClient.java`

## 当前边界

响应模型仍保留 `rerankPosition` 和 `rerankScore` 历史字段，页面也有部分演示性重排文案。它们目前不能证明系统使用了独立 reranker。后续应选择一种明确方向：实现并评估真正重排，或者把这些字段和文案重命名为普通最终排名与检索分数。

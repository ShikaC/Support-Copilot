# V1 第一轮代码优化合集

> 最近更新：2026-08-12
>
> 范围：实现已经理解、完成设计并且可以被测试验证的 V1 可靠性改进；本轮未提交 Git。

## 本轮目标

V1 在调用 Python 后，需要同时保存分析记录并更新工单。第一轮优化解决以下风险：

- `@Transactional` 因同类内部调用而没有可靠生效。
- AI 分析期间工单可能被修改，旧结果会覆盖新工单。
- 分析记录无法说明自己基于工单的哪个版本。
- 版本冲突没有稳定的 HTTP 错误格式。
- 上述行为没有自动化测试保护。

## 文档索引

1. [独立的短事务持久化](./01-analysis-persistence-transaction.md)
2. [阻止旧分析覆盖新工单](./02-ticket-version-conflict.md)
3. [记录分析来源工单版本](./03-source-ticket-version.md)
4. [返回结构化 409 Conflict](./04-structured-conflict-response.md)
5. [增加事务与 API 回归测试](./05-regression-tests.md)
6. [统一 Java fallback 的人工复核语义](./06-java-fallback-semantics.md)
7. [前端保留结构化错误](./07-frontend-structured-errors.md)
8. [启动数据支持部分可用](./08-partial-initial-data.md)
9. [取消负责人使用明确命令和版本保护](./09-ticket-unassign-command.md)
10. [只让可恢复的 AI 故障进入 fallback](./10-python-recoverable-ai-errors.md)
11. [校验 Top K 不得超过 Top N](./11-retrieval-window-validation.md)
12. [移除尚未实现的 rerank 请求开关](./12-remove-inactive-rerank-option.md)
13. [让 mock 检索真正使用 Top N 候选池](./13-mock-top-n-candidate-pool.md)
14. [补充慢案例数量与比例](./14-slow-case-count-and-rate.md)
15. [记录评估实际使用的模型](./15-evaluation-model-names.md)
16. [记录每条评估案例使用的模型](./16-case-model-attribution.md)
17. [按模型统计慢案例比例](./17-model-slow-case-metrics.md)
18. [将提示词版本绑定到实际提示词](./18-bind-prompt-version.md)
19. [在评估报告中记录提示词版本](./19-report-prompt-versions.md)
20. [按完整分析配置统计性能](./20-group-performance-by-analysis-configuration.md)
21. [按分析配置统计分类准确率](./21-configuration-classification-accuracy.md)
22. [按分析配置统计优先级准确率](./22-configuration-priority-accuracy.md)
23. [统计高风险优先级降级](./23-high-risk-priority-downgrades.md)
24. [高风险优先级降级零容忍门槛](./24-zero-tolerance-priority-downgrade-gate.md)

## 优化后的主流程

```text
读取 Ticket 和 version
        ↓
事务外调用 Python
        ↓
得到 live、mock 或 fallback 结果
        ↓
进入短数据库事务
        ↓
重新读取 Ticket 并比较 version
        ↓
版本一致：保存 AnalysisRun + 更新 Ticket + commit
版本冲突：rollback + 返回 409
```

Python live 分析的异常路径现在会进一步区分：

```text
OpenAI 网络、超时或响应异常 -> Python fallback -> 标记人工复核
Python 程序缺陷              -> 正常抛出错误 -> 日志暴露真实根因
```

## 当前边界

取消负责人已经有明确命令接口、版本保护、终态检查和页面操作，但可信权限检查和持久化审计仍未实现。当前 `SecurityConfig` 允许所有请求，系统没有可验证的登录身份；在这种情况下直接写“某用户执行了操作”会形成虚假审计。下一阶段仍需要接入认证、权限模型和独立审计实体。

Python 当前只把 OpenAI SDK 明确报告的错误归类为可恢复故障。后续接入更多外部服务时，应根据真实错误类型逐项扩充，不能重新使用宽泛的 `except Exception`。

检索参数现在保证 `Top K <= Top N`，尚未实现的 `enableRerank` 请求开关也已经移除。mock 与 live 都会先建立 `Top N` 候选池，再保留 `Top K` 证据；但两种模式使用的检索算法不同，live 向量检索仍需要独立集成测试和真实评估集验证。

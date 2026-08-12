# 优化 06：统一 Java fallback 的人工复核语义

## V1 的问题

实际运行 Java API，并让 Python 服务不可用后，V1 返回了互相矛盾的数据：

```json
{
  "mode": "fallback",
  "status": "SUCCEEDED",
  "decision": {
    "escalationRequired": false
  }
}
```

`mode` 说明这不是正式 AI 分析，但 `status` 和 `decision` 又告诉页面“成功且不必人工复核”。页面或客服可能因此把降级结果误当成可信分析。

## 本轮修改

当 Java 因 Python 请求失败而调用 `MockAnalysisFactory.create(ticket, "fallback")` 时，现在统一返回：

- `mode = fallback`。
- `status = FALLBACK`。
- `confidence <= 0.5`。
- 警告中明确写明 AI 服务不可用，必须人工复核。
- `escalationRequired = true`。
- 工作流步骤和升级理由都明确标记降级原因。

## 相对 V1 的改进

```text
V1
fallback 标签 + 成功状态 + 不升级人工
→ 信号互相冲突

现在
fallback 标签 + 降级状态 + 低置信度 + 明确警告 + 升级人工
→ React 和客服得到一致、可审核的风险信号
```

fallback 仍会保存到数据库，因为它是一次真实发生过的降级处理记录；但系统不再把它包装成正式 AI 分析成功。

## 对应代码

- `services/support-copilot-api/src/main/java/com/cyagent/supportcopilot/analysis/MockAnalysisFactory.java`
- `services/support-copilot-api/src/test/java/com/cyagent/supportcopilot/analysis/MockAnalysisFactoryTests.java`

## 验证

新增测试使用普通低风险工单显式请求 `fallback`，确认状态、置信度、警告和人工升级决定全部符合降级语义。最终还会通过 Python 不可用时的真实 HTTP 请求再次验证。

# Mock 评估

这套评估只验证本地确定性 mock 工作流，不调用外部模型。评估集中的 `expected_*` 字段由人工维护，不能从被测输出自动生成。

## 运行

在 AI 服务目录执行：

```bash
cd services/support-copilot-ai
.venv/bin/python -m evaluation.run_mock_evaluation
```

命令会在 `evaluation/reports/` 下生成一对 JSON 和 Markdown 报告：

- JSON 保存完整的逐案例输入、期望结果、实际结果、失败原因和环境哈希。
- 每条案例同时保存检索到的 chunk ID 和实际被引用的 chunk ID，便于检查引用是否映射到本次证据。
- Markdown 用于快速阅读指标、失败案例和运行环境。
- 运行还会刷新 `evaluation/reports/mock-latest.json` 和 `mock-latest.md`，作为本地最新报告入口。
- 所有样例通过时退出码为 `0`。
- 任意样例或评估阈值失败时退出码为 `1`，但报告仍会保存。

## 当前数据集

当前固定数据集包含 31 条模拟工单，覆盖：

- 重复扣款、支付资料和退款时效。
- SSO、账号锁定和英文大小写输入。
- 发票、数据导出和套餐成员计费。
- 隐私请求与提示注入文本。
- 错误码和中英文混合技术输入。
- 数据恢复、通用未知问题和低置信度近邻查询。

## 指标边界

- 分类准确率和优先级准确率只针对当前固定样例。
- Hit@K 和 MRR 只衡量期望知识片段是否出现在 Top K。
- 引用覆盖率要求引用能映射到本次返回的知识片段，并且至少包含人工标注的相关证据；这仍不等于事实级人工 groundedness 审查。
- 无证据安全率检查是否返回 fallback、无检索证据、无引用并要求人工升级。
- mock 检索默认要求分类加权后的分数至少为 `0.25`；live 向量检索使用余弦相似度，默认要求分数至少为 `0.35`。阈值是安全初始值，真实 live 运行后仍需根据脱敏分数分布校准。
- mock 耗时用于本地回归，不代表 live 模型或生产性能。

这些指标不能写成通用模型准确率，也不能替代真实 live 模式评估。

## 维护评估集

编辑 `evaluation/data/tickets.jsonl` 时：

1. 使用模拟或脱敏工单，不放入真实客户信息。
2. 为每条样例人工确定 `expected_category`、`expected_priority` 和 `expected_escalation`。
3. `evidence_required=true` 时必须填写 `expected_evidence_ids`。
4. 无证据样例不得填写 `expected_evidence_ids`。
5. 需要验证回复安全边界时填写 `reply_constraints`。
6. 修改后先运行 Python 测试，再运行评估命令。
7. 评估失败时先查看报告中的具体案例，不要直接降低阈值。

## 当前基线

2026-08-24 的报告是历史基线，绑定提交 `d0989834bab0d76b3966e5288e0e75d7d37f2815`。当前版本应重新运行上面的命令，不要把历史报告当作当前提交结果。本轮还增加了 live 无证据时不调用模型的回归测试。

此前的 2026-08-12 基线发现并修复过一个真实缺陷：没有 DATA_RECOVERY 知识覆盖的工单会误命中隐私知识片段，修复后无证据安全率恢复到 1.000。

当前工作区在 2026-08-25 运行 31 条 mock 案例，所有门槛通过。当前结果只说明本地确定性规则在这 31 条人工维护样例上通过；真实 live 检索质量、模型质量和生产延迟仍未由这份报告证明。

运行完成后，如果要让 Java 指标接口和 React 质量页读取这份报告，请从 `services/support-copilot-api/` 启动 Java，或显式配置：

```bash
export EVALUATION_REPORT_PATH='/absolute/path/to/services/support-copilot-ai/evaluation/reports/mock-latest.json'
```

Java 只读取报告中的稳定指标和来源元数据。报告缺失、JSON 损坏或必需字段不兼容时，`GET /api/metrics` 保留其他可用指标，并将 `evaluation` 返回为 `null`。

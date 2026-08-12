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
- Markdown 用于快速阅读指标、失败案例和运行环境。
- 所有样例通过时退出码为 `0`。
- 任意样例或评估阈值失败时退出码为 `1`，但报告仍会保存。

## 当前数据集

当前固定数据集包含 18 条模拟工单，覆盖：

- 重复扣款、支付资料和退款时效。
- SSO、账号锁定和英文大小写输入。
- 发票、数据导出和套餐成员计费。
- 隐私请求与提示注入文本。
- 错误码和中英文混合技术输入。
- 数据恢复无证据和一般未知问题。

## 指标边界

- 分类准确率和优先级准确率只针对当前固定样例。
- Hit@K 和 MRR 只衡量期望知识片段是否出现在 Top K。
- 引用覆盖率只检查有证据案例是否存在引用，不等于引用内容已经完成事实级人工审查。
- 无证据安全率检查是否返回 fallback、无检索证据、无引用并要求人工升级。
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

2026-08-12 的 mock 基线已经覆盖 18 条样例，失败样例为 0。此前发现并修复过一个真实缺陷：没有 DATA_RECOVERY 知识覆盖的工单会误命中隐私知识片段，修复后无证据安全率恢复到 1.000。

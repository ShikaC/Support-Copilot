# 第 68 轮：可追溯 live 评估与人工 groundedness 审核

## 问题与风险

旧 live gate 只证明一条合成工单经过真实 Embedding、生成和 Java 持久化，不能证明固定数据集质量，也没有独立人工事实支持判断。把单次成功写成准确率、SLO 或自动 groundedness 会制造不可核查结论。

## 修改层与流程

Python 新增版本化合成 live dataset、严格 JSON/Markdown report、runner、verifier 和 review worksheet。报告绑定 dataset、knowledge release/corpus、active embedding artifact、provider/model、prompt/config fingerprint、Git SHA/dirty truth；逐案例记录检索、引用、evidence mapping、runner latency、token/cost availability 和 fallback。机器固定写 `NOT_REVIEWED`，worksheet apply 只替换 review fields。

Java reader 通过 `report_kind` 区分旧 mock 和新 live 格式，把 measured summary 交给现有质量页。`publishable=false` 和 `human-review-incomplete` 显示为门禁未通过，React 合同无需变化。

## 验证与边界

```bash
cd services/support-copilot-ai
.venv/bin/pytest -q tests/test_live_evaluation.py
.venv/bin/python -m evaluation.run_mock_evaluation
cd ../support-copilot-api
./gradlew test --tests '*EvaluationReportReaderTests' --no-daemon
```

正式 live 受两次外部阻塞规则约束。机器数据集生成成功后，真实 reviewer 完成 factual-support labels 前 publishable gate仍暂停。本轮不产生生产准确率、成本、性能或 SLO 结论，不提交 provider payload、密钥、live reports 或 embedding runtime artifacts。

## 实际运行结果

`be9ac60` 上构建并激活真实 1024-dimension artifact，单工单 cross-service live gate 成功。第二次完整运行生成 4-case ignored report：1 live success、3 `invalid_model_response` fallbacks、0/4 human reviewed，machine gate 为 `machine-gate-failed`。报告中的原始 no-evidence success 汇总被判定为误增并废弃；`3e59a07` 增加回归并要求无证据成功必须是明确的 `insufficient_evidence` fallback。两次外部尝试已用完，没有第三次调用，因此当前不能声称 publishable dataset success。

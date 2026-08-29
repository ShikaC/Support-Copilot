# 第 68 轮：可追溯 live 评估与人工 groundedness 审核

## 问题与风险

旧 live gate 只证明一条合成工单经过真实 Embedding、生成和 Java 持久化，不能证明固定数据集质量，也没有独立人工事实支持判断。把单次成功写成准确率、SLO 或自动 groundedness 会制造不可核查结论。

## 修改层与流程

Python 新增版本化合成 live dataset、严格 JSON/Markdown report、runner、verifier 和 review worksheet。报告绑定 dataset、knowledge release/corpus、active embedding artifact、provider/model、明确的 `responses|chat_completions`、prompt/config fingerprint、Git SHA/dirty truth；逐案例记录检索、引用、evidence mapping、runner latency、token/cost availability 和 fallback。缺少/非法协议的旧报告失败关闭，协议变化会改变 fingerprint。机器固定写 `NOT_REVIEWED`，worksheet apply 只替换 review fields。

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

`be9ac60` 与 `b856019` 的 4-case 运行都使用 Responses 协议，均得到 1 live success、3 `invalid_model_response` fallbacks；后者 0/4 human reviewed 且 machine gate 为 `machine-gate-failed`。两份报告继续作为明确失败的历史 evidence。干净提交 `59903a1e5fad74cf2b792263f735dafe36b8066c` 则仅证明当时 Responses 路径的一次端到端成功。

新增显式协议后，一次 Chat Completions relay synthetic probe 恰好执行 1 次 chat、0 次 Embedding，耗时 7.437 秒，返回 ACCOUNT / MEDIUM / NEUTRAL、confidence 0.94、citation `[1]` 和 436/245 input/output tokens。它只证明 direct-provider structured chat capability，不是完整 RAG、dataset、跨服务、publishable 或人工 groundedness 成功。下一份可接受证据仍需干净提交上的完整 Chat Completions dataset 与真实人工 labels。

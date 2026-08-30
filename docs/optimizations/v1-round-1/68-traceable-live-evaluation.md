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

`bfb7eee6adae0556399e56457eeed19a158c1d39` 的 `chat_completions` attempt-3 已完成主 React -> Java -> Python -> Java 合成工单链路：`live/SUCCEEDED`、`VECTOR`、3 chunks、1 citation、587/343 tokens、12048 ms、trace 保留和 Java history persistence。相同运行产生的 4-case machine report 是 1 success、3 个 `invalid_model_response` fallback、3/4 retrieval/citation、8533/11415 ms、0/4 `NOT_REVIEWED`、`publishable=false`、`machine-gate-failed`；正式 child exit code 未捕获，只有包装层 exit 2，故不将 gate exit 1/2 当作观测事实。`f7ccdb0` 只安全分类新的内部诊断，历史脱敏 fallback 不能倒推子类；`d0234e4` verifier 才绑定当前输入并重算 summary，不能证明外部 provider 行为。Task 10 仍 blocked/partial，未授权新的 live rerun、未做人审，Docker deferred。

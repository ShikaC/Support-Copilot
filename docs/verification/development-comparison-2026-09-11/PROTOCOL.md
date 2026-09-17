# 修正后 development 比较：预注册协议

> 状态：**已预注册，等待作者审阅 diff 并明确授权付费执行。** 本轮没有调用模型或 Embedding，没有产生新的检索、质量或延迟数据。
>
> 事实来源：[docs/STATUS.md](../../STATUS.md)、[query 修复交付](../query-context-fix-2026-09-10/README.md)、[旧诊断运行](../quality-runs/development-live-diagnostic-20260910/RESULTS.md)、[隔离运行器操作说明](../isolated-runner-2026-09-10/OPERATIONS.md)。

## 1. 为什么需要显式协议

1. 13 题 development 真实诊断已经占用一次性 claim：`.local/quality-runs/development-<casesSha>.claim.json`。该 claim 与 base run `development-live-diagnostic-20260910` 不可删除、不可覆盖、不可绕过。
2. query 截断修复已完成离线回归（19 项先失败后通过 + AI 服务 324 项测试），但**没有真实模型复测**。
3. 旧 13 题已经被模型见过输出，只能作为 development 复测，不能当盲测；holdout 仍未使用。
4. 因此新的真实运行必须同时满足：引用旧 claim 与旧 run、绑定修复后的源码、冻结预算、每个 comparisonId 只运行一次、保留全部失败与未执行行。

## 2. 机制：比较模式在付费调用前完成哪些检查

`scripts/benchmark/run-isolated.mjs --comparison <protocol.json>` 复用原隔离运行器（独立端口、独立文件 H2、源码快照、逐次调用账本、预算、失败停止、重启读回），并增加以下 fail-closed 检查：

| 检查 | 失败后果 |
| --- | --- |
| `protocolVersion`、`comparisonId`、`preflightId` 格式 | 拒绝启动 |
| `--id` 必须等于 `comparisonId`（执行）或 `preflightId`（仅预检） | 拒绝启动 |
| `casesSha` 必须等于冻结数据集 SHA | 拒绝启动 |
| `holdoutCount` 必须为 0；`humanInputReview` 必须为 `PENDING`；`qualityScore` 必须为 `null` | 拒绝启动 |
| `budgets` 必须与 runner 冻结预算完全一致 | 拒绝启动（单变量约束）|
| 旧 claim 存在且 SHA-256 等于协议声明 | 拒绝启动 |
| 旧 run manifest 存在且 `id`、`casesSha` 一致 | 拒绝启动 |
| `expectedSourceHashes` 与当前源码逐文件一致 | 拒绝启动 |
| `comparison-<comparisonId>.claim.json` 不存在 | 拒绝启动（每个 comparisonId 只运行一次）|

执行时写入独立的 comparison claim，包含协议 SHA-256、旧 claim SHA-256、旧 run ID、单一变量与时间；**不修改旧 claim**。检查发生在任何 provider 调用之前。

## 3. 冻结输入

| 项目 | 值 |
| --- | --- |
| 数据集 | `docs/verification/quality-input-audit-2026-09-10/cases.json`（development 13 题） |
| cases SHA-256 | `7e78989315fd7991b72bce6bdb1528195c983b34b8ad4f18bbd99de260674023` |
| 对照运行 | `development-live-diagnostic-20260910` |
| 旧 claim SHA-256 | `8476732b1464060c3fb36fe70e1d8609572dc110e363e84ef04f12b910cc1afb` |
| 预期源码 | `workflow.py`、`grounded_reply_policy.py`、`response_language.py`（哈希见 `protocol.json`）|
| 预算 | SDK 20s / Python 90s / Java 105s / 客户端 130s / 批次 35min / 单题最多 2 次服务尝试 / 并发 1 |
| holdout | 0 |
| 人工状态 | 输入审核 PENDING、回答审核 0、质量分数 null |

`protocol.json` 是本协议的机器可读版本，是 runner 实际读取和校验的文件；两个文件必须一起更新。

## 4. 判据与不变量

成功判据（完整列表见 `protocol.json`）：

- 逐题比较 `retrieval.query`：`queryChangedCases` 应为 13、`comparisonDistinctQueries` 应为 13，且每题 query 包含该题特有的业务上下文。
- 逐题比较候选 `chunkId`：只报告 `candidatesChangedCases` 的实际数值，**不预设必须全部变化**。
- 按正常 live 产出、证据不足、超时、其他降级、未知错误分别计数，不用成功数量替代语义质量。
- 即时读回与 Java 重启后的完整对象读回必须逐题匹配。
- 失败、未执行和停止原因原样保留，不重跑择优。

不变量与禁止项：

- 不删除、替换、绕过或改写 development claim 与 base run 记录。
- 不使用 holdout 或冻结 cases 之外的任何输入。
- 不同时更改模型、聊天协议、提示词、知识 corpus、向量 artifact、超时或重试预算。
- 不重跑到成功、不删除失败或未执行记录。
- 不用 AI 审核替代真人输入确认与回答事实审核。
- 在作者审阅本轮 diff 之前不执行付费运行。

## 5. 执行命令

预检（无付费调用，可换 `preflightId` 重跑；验证协议、旧 claim、旧 run、源码哈希与 provider 配置）：

```sh
node scripts/benchmark/run-isolated.mjs \
  --id preflight-development-comparison-20260911 \
  --comparison docs/verification/development-comparison-2026-09-11/protocol.json
```

付费执行（**需要作者明确授权**；一次性，不可重复、不可续跑）：

```sh
node scripts/benchmark/run-isolated.mjs \
  --id development-comparison-20260911 \
  --execute --comparison docs/verification/development-comparison-2026-09-11/protocol.json
```

离线汇总（生成 `RESULTS.md`、`summary.json`、空白人审表；不做任何网络调用）：

```sh
node scripts/benchmark/summarize-isolated.mjs development-comparison-20260911
```

比较模式下的汇总会额外输出：与 base run 的逐题 query 是否变化、候选片段是否变化、两组的去重 query 数量。

## 6. 协议变更规则

任何输入、源码、预算或判据变化都必须新建协议文件与新的 `comparisonId`；不得修改已执行协议的字段后再次运行。协议文件与 `protocol.json` 一起提交到 Git，作为"先声明、后执行"的证据。

## 7. 已知限制

- 协议依赖本地 `.local/quality-runs/development-<casesSha>.claim.json` 与 base run manifest；fresh clone 上不存在这些文件，因此协议无法在其他机器上执行。这是刻意设计：比较结果绑定原始运行环境与原始 claim。
- 协议不承诺质量提升，只冻结单一变量与报告方式；修复后的召回、延迟与费用仍需真实测量。
- 质量分数仍为 `null`，需要真人输入确认与回答事实审核（操作入口见 [OPERATIONS](../isolated-runner-2026-09-10/OPERATIONS.md)）。
- 本协议不修改任何生产代码；`grounded_reply_policy.py` 与 `response_language.py` 的哈希被冻结，是因为它们参与证据充分性与回复语义，属于本次单一变量的直接依赖。

## 8. 离线验证证据

```sh
node --test scripts/benchmark/comparison-protocol.test.mjs
```

8 项契约测试覆盖：有效协议绑定、错误 run ID / 数据集 / 协议版本、预算与 holdout 与标签与分数被篡改、源码漂移、旧 claim 被替换、comparison 重复运行、路径穿越、preflight 不可执行、非法 JSON，以及 CLI 混用模式在创建目录前拒绝。测试结果记录在提交与后续交付说明中；本文件不预先宣称真实运行结果。

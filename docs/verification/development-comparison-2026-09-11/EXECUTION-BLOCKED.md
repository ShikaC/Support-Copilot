# 比较运行未执行：上游 chat 端点不可用（2026-09-17）

> 结论：**修正后 development 比较运行没有执行**，因为 provider 前置检查发现 chat 端点持续返回 HTTP 503。一次性 comparison claim 未被写入，没有发生生成调用费用。
>
> 相关事实：[当前状态](../../STATUS.md)、[比较协议](PROTOCOL.md)、[隔离运行器操作说明](../isolated-runner-2026-09-10/OPERATIONS.md)。

## 1. 为什么先探测再运行

`run-isolated.mjs --comparison` 的 execute 流程是：

```text
预检（无调用）-> 构建 JAR -> 启动隔离服务 -> 断言空库 -> 写入一次性 claim -> 逐题执行（付费）
```

claim 一经写入就不能重跑、不能续跑、不能删改。如果 chat 端点在运行时不可用，13 题生成会全部失败并被原样保留，唯一的一次机会就消耗掉了。因此执行前必须确认端点真实可用，而不能只看配置完整。

## 2. 证据

前置检查工具：`scripts/benchmark/provider-probe.mjs`（8 项契约测试）。它只做最小探测：模型列表、一次极短补全、一次极短嵌入，不输出任何密钥。

`docs/verification/development-comparison-2026-09-11/preflight-provider-probe.json` 记录（2026-09-17T06:08:11Z）：

| 检查 | HTTP | 结果 |
| --- | ---: | --- |
| `GET /models` | 200 | 通过；模型列表中包含目标模型 `gpt-5.6-luna` |
| `POST /chat/completions` | **503** | 失败，`Service temporarily unavailable` |
| `POST /embeddings` | 200 | 通过 |

同一结论由三条互相独立的路径确认：

1. 直接调用应用代码路径 `OpenAIProvider.analyze`（含 `response_format` 结构化输出）：`StructuredGenerationApiError`。
2. 原始 HTTP 请求（绕过 SDK 包装）：普通补全与 `json_schema` 补全均返回 503。
3. 工具化探测：上表。

故障期间还做过 12 分钟轮询（每约 55 秒一次，共 12 次探测），chat 端点始终 503，另有一次连接错误。

## 3. 为什么这不是配置问题

- 模型列表 200，且目标模型在 17 个可用模型之内，说明模型名与鉴权有效。
- embedding 端点 200，说明 Key 与网关路由整体可用。
- 503 是上游服务端返回的标准"暂时不可用"，与请求内容、模型名、结构化输出参数无关。

结论：这是**外部依赖的临时故障**，不是代码、配置或协议缺陷。

## 4. 未消耗与未改变的内容

| 项目 | 状态 |
| --- | --- |
| comparison claim | 未写入 |
| 生成调用费用 | 未产生（前置检查的探测调用与 13 题运行无关） |
| base run 与旧 claim | 未触碰 |
| 协议、预算、源码绑定 | 未修改 |
| holdout | 仍未使用 |

## 5. 恢复后的执行步骤

```bash
# 1. 确认端点恢复（expect: READY, exit 0）
node scripts/benchmark/provider-probe.mjs

# 2. 执行一次性比较运行
node scripts/benchmark/run-isolated.mjs \
  --id development-comparison-20260911 \
  --execute --comparison docs/verification/development-comparison-2026-09-11/protocol.json

# 3. 汇总与人读报告
node scripts/benchmark/summarize-isolated.mjs development-comparison-20260911

# 4. 用离线检索评测得到真实召回
node scripts/benchmark/retrieval-eval.mjs \
  docs/verification/quality-runs/development-comparison-20260911 \
  --label "development 13 题比较（query 截断修复后）" \
  --baseline docs/verification/retrieval-eval-2026-09-11/baseline-diagnostic-2026-09-10.json \
  --json docs/verification/retrieval-eval-2026-09-11/comparison-2026-09-17.json \
  --markdown docs/verification/retrieval-eval-2026-09-11/COMPARISON.md
```

如果 `provider-probe.mjs` 返回 BLOCKED，**不要**执行第 2 步。

## 6. 已知限制

- 探测成功不保证整批 13 题全部成功；上游仍可能在运行中途出现故障，届时运行器按预算停止并原样保留失败记录。
- 本记录不证明模型质量，也不构成质量结论；质量分数仍为 `null`，需要真人输入确认与回答事实审核。
- 探测本身是真实外部调用（3 次最小请求），不产生有意义费用，但会计入账户调用记录。

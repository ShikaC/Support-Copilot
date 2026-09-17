# 完整运行结果

所有完整基线运行均列出；针对性诊断另计。机器正确案例包括预期的无证据拒答，外部错误不计成功。

| 目录 | 机器正确 / 总数 | live 成功 | 正确无证据 | 其他失败 | 平均 / p95 (秒) | 机器门禁 |
|---|---:|---:|---:|---:|---|---|
| [original](original/live-latest.json) | 4/4 | 3 | 1 | 0 | 7.851 / 11.616 | 通过 |
| [round-1](round-1/live-latest.json) | 18/22 | 14 | 4 | 4 | 7.094 / 11.696 | 失败 |
| [round-2](round-2/live-latest.json) | 21/22 | 17 | 4 | 1 | 9.183 / 17.141 | 失败 |
| [round-3](round-3/live-latest.json) | 21/22 | 17 | 4 | 1 | 8.021 / 14.228 | 失败 |
| [final-1](final-1/live-latest.json) | 20/22 | 16 | 4 | 2 | 8.626 / 20.169 | 失败 |
| [final-2](final-2/live-latest.json) | 20/22 | 17 | 3 | 2 | 9.866 / 20.170 | 失败 |
| [original-final](original-final/live-latest.json) | 3/4 | 3 | 0 | 1 | 11.013 / 20.212 | 失败 |

最终冻结源码对应 `final-1`、`final-2`、`original-final`，三份报告具有相同 `runtime_source_sha256`。较早轮次保留各自源码或政策快照，不冒充当前源码证据。

## 最终冻结版本的失败

- `final-1` / `quality-sso-password`：`structured_generation_response_timeout`。
- `final-1` / `quality-lockout`：`structured_generation_connection_timeout`。
- `final-2` / `quality-unsupported-hardware-english`：`structured_generation_response_timeout`。
- `final-2` / `quality-sso-language-injection`：`structured_generation_response_timeout`。
- `original-final` / `live-unsupported-001`：`structured_generation_response_timeout`。

这些失败均没有 HTTP 错误状态码；安全日志将其归为 SDK `APITimeoutError`，传输原因为 `ReadTimeout` 或 `ConnectTimeout`。这区分了读取等待和建立连接超时，但不能凭客户端日志确认网络、网关排队或模型服务的具体责任方。没有因失败提高超时预算、增加隐藏重试、切换模型或跳过案例。

## 最终扩展数据集的范围

- final-1 与 final-2 各 22/22 通过指定回复语言检查，指定违规模式命中均为 0。两轮不能因此替代人工逐句事实审核。
- 两轮原始向量检索 Recall@3 各 18/18，正例 MRR 各 0.9167；仅针对需证据的 18 例计算，不把无证据案例混入分母。召回成功不保证生成请求成功。
- 两轮预期无证据判断分别为 4/4、3/4；后一轮剩余 1 例生成读取超时，按失败计，不伪装为证据不足成功。
- 所有最终报告 `publishable=false`；最终扩展两轮人工审核 0/44，原始最终轮 0/4。
- Chat token 用量按报告返回值记录，实际费用未确认网关单价，保持 null。

机器可重算汇总见 [metrics.json](metrics.json)。JSON 报告包含每条实际输出、来源、原始候选、分类、风险、用量和审核状态。

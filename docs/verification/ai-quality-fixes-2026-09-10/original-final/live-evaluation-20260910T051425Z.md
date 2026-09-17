# Live evaluation report

> These are evaluation results for this dataset/run only. They are not production accuracy, an SLO, or a stability claim.

- Run: `live-20260910T051425Z-fb638ef0`
- Timestamp: `2026-09-10T05:14:25.749160+00:00`
- Dataset: `support-copilot-live-synthetic` v`1.0.0` (`4894f5094f055a5d3cf624bc142afac84596bd2ff08e5967c4b4a94a148087c3`)
- Git: `4df3bf44907c34318132496929bad4a3974ad88b`; dirty=`true`
- Knowledge release: `support-copilot-bundled-v1` v`1`
- Semantic corpus checksum: `b25240587df1ebb903a8555284a0f35faaa35e2d837add0fc5dd49418ca8b874`
- Chat: `https://sub2api-production-3d63.up.railway.app/v1` / `gpt-5.6-luna` / `chat_completions`
- Prompt: `ticket-analysis-v1`
- Runtime source SHA-256: `ffd6a62073954bd390d455eb5286ab01c417653fe6b73e87e488cc4207bfa511`
- Publishable: `false`
- Gate reasons: `machine-gate-failed`

## Evaluation Results

- Cases: `4`
- Succeeded: `3`
- Retrieval success: `3/4`
- MRR: `0.625`
- Citation valid: `3/4`
- No-evidence safety rate: `0.000`
- Fallback: `1`
- Average/p95 runner latency: `11013.0 ms` / `20212 ms`
- p95 method: `nearest-rank`
- Human reviewed: `0/4`

## Cases

### live-sso-001
- Status/mode: `SUCCEEDED` / `live`
- Retrieval success: `true`
- Citation valid: `true`
- Language script check: `None`
- Policy pattern matches: `none`
- Reply warnings: `当前尚未完成身份提供方状态和域名配置的后台核验。`
- Latency: `7552 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### live-billing-001
- Status/mode: `SUCCEEDED` / `live`
- Retrieval success: `true`
- Citation valid: `true`
- Language script check: `None`
- Policy pattern matches: `none`
- Reply warnings: `需先核验账单周期、支付方式及交易完成状态，当前客户描述尚不足以确认重复扣款。; 不得在交易核验完成前承诺退款到账时间。; 回复已由来源绑定规则 2026-09-10.2 约束，仍需人工审核。`
- Latency: `9719 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### live-sync-001
- Status/mode: `SUCCEEDED` / `live`
- Retrieval success: `true`
- Citation valid: `true`
- Language script check: `None`
- Policy pattern matches: `none`
- Reply warnings: `回复已由来源绑定规则 2026-09-10.2 约束，仍需人工审核。`
- Latency: `6569 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### live-unsupported-001
- Status/mode: `FALLBACK` / `fallback`
- Retrieval success: `false`
- Citation valid: `false`
- Language script check: `None`
- Policy pattern matches: `none`
- Reply warnings: `证据不足，必须人工复核，禁止承诺处理结果。; 证据不足，禁止承诺处理结果。`
- Latency: `20212 ms`
- Token usage: `unavailable`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

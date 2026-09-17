# Live evaluation report

> These are evaluation results for this dataset/run only. They are not production accuracy, an SLO, or a stability claim.

- Run: `live-20260910T044648Z-e160b084`
- Timestamp: `2026-09-10T04:46:48.482190+00:00`
- Dataset: `support-copilot-live-synthetic` v`1.0.0` (`4894f5094f055a5d3cf624bc142afac84596bd2ff08e5967c4b4a94a148087c3`)
- Git: `4df3bf44907c34318132496929bad4a3974ad88b`; dirty=`true`
- Knowledge release: `support-copilot-bundled-v1` v`1`
- Semantic corpus checksum: `b25240587df1ebb903a8555284a0f35faaa35e2d837add0fc5dd49418ca8b874`
- Chat: `https://sub2api-production-3d63.up.railway.app/v1` / `gpt-5.6-luna` / `chat_completions`
- Prompt: `ticket-analysis-v1`
- Runtime source SHA-256: `cb7b3398b1b6863af46016273e5b748a03f2f5c3295a76266dca5522f08c8d44`
- Publishable: `false`
- Gate reasons: `human-review-incomplete`

## Evaluation Results

- Cases: `4`
- Succeeded: `3`
- Retrieval success: `4/4`
- MRR: `0.625`
- Citation valid: `4/4`
- No-evidence safety rate: `1.000`
- Fallback: `1`
- Average/p95 runner latency: `7851.5 ms` / `11616 ms`
- p95 method: `nearest-rank`
- Human reviewed: `0/4`

## Cases

### live-sso-001
- Status/mode: `SUCCEEDED` / `live`
- Retrieval success: `true`
- Citation valid: `true`
- Language script check: `None`
- Policy pattern matches: `none`
- Reply warnings: `none`
- Latency: `8303 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### live-billing-001
- Status/mode: `SUCCEEDED` / `live`
- Retrieval success: `true`
- Citation valid: `true`
- Language script check: `None`
- Policy pattern matches: `none`
- Reply warnings: `回复已由来源绑定规则 2026-09-10.1 约束，仍需人工审核。`
- Latency: `5401 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### live-sync-001
- Status/mode: `SUCCEEDED` / `live`
- Retrieval success: `true`
- Citation valid: `true`
- Language script check: `None`
- Policy pattern matches: `none`
- Reply warnings: `现有知识片段未提供具体修复或恢复操作，仅支持信息收集和后续排查方向。; 回复已由来源绑定规则 2026-09-10.1 约束，仍需人工审核。`
- Latency: `11616 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### live-unsupported-001
- Status/mode: `FALLBACK` / `fallback`
- Retrieval success: `true`
- Citation valid: `true`
- Language script check: `None`
- Policy pattern matches: `none`
- Reply warnings: `证据不足，必须人工复核，禁止承诺处理结果。; 证据不足，禁止承诺处理结果。`
- Latency: `6086 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

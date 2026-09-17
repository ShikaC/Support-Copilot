# Live evaluation report

> These are evaluation results for this dataset/run only. They are not production accuracy, an SLO, or a stability claim.

- Run: `live-20260909T123036Z-7c1d4acd`
- Timestamp: `2026-09-09T12:30:36.271487+00:00`
- Dataset: `support-copilot-live-synthetic` v`1.0.0` (`4894f5094f055a5d3cf624bc142afac84596bd2ff08e5967c4b4a94a148087c3`)
- Git: `4df3bf44907c34318132496929bad4a3974ad88b`; dirty=`true`
- Knowledge release: `support-copilot-bundled-v1` v`1`
- Semantic corpus checksum: `b25240587df1ebb903a8555284a0f35faaa35e2d837add0fc5dd49418ca8b874`
- Chat: `https://sub2api-production-3d63.up.railway.app/v1` / `gpt-5.6-luna` / `chat_completions`
- Prompt: `ticket-analysis-v1`
- Publishable: `false`
- Gate reasons: `machine-gate-failed`

## Evaluation Results

- Cases: `4`
- Succeeded: `1`
- Retrieval success: `3/4`
- MRR: `0.625`
- Citation valid: `3/4`
- No-evidence safety rate: `1.000`
- Fallback: `3`
- Average/p95 runner latency: `9755.5 ms` / `16694 ms`
- Human reviewed: `0/4`

## Cases

### live-sso-001
- Status/mode: `FALLBACK` / `fallback`
- Retrieval success: `true`
- Citation valid: `true`
- Latency: `16694 ms`
- Token usage: `unavailable`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### live-billing-001
- Status/mode: `SUCCEEDED` / `live`
- Retrieval success: `true`
- Citation valid: `true`
- Latency: `7756 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### live-sync-001
- Status/mode: `FALLBACK` / `fallback`
- Retrieval success: `true`
- Citation valid: `true`
- Latency: `8163 ms`
- Token usage: `unavailable`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### live-unsupported-001
- Status/mode: `FALLBACK` / `fallback`
- Retrieval success: `false`
- Citation valid: `false`
- Latency: `6409 ms`
- Token usage: `unavailable`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

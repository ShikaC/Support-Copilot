# Live evaluation report

> These are evaluation results for this dataset/run only. They are not production accuracy, an SLO, or a stability claim.

- Run: `live-20260909T140018Z-d497e708`
- Timestamp: `2026-09-09T14:00:18.420662+00:00`
- Dataset: `support-copilot-live-quality` v`1.0.0` (`2f1e652c04a47e8833fa3e26ca296fa522338dd711a68d1ef9a9bfd50b624b16`)
- Git: `4df3bf44907c34318132496929bad4a3974ad88b`; dirty=`true`
- Knowledge release: `support-copilot-bundled-v1` v`1`
- Semantic corpus checksum: `b25240587df1ebb903a8555284a0f35faaa35e2d837add0fc5dd49418ca8b874`
- Chat: `https://sub2api-production-3d63.up.railway.app/v1` / `gpt-5.6-luna` / `chat_completions`
- Prompt: `ticket-analysis-v1`
- Publishable: `false`
- Gate reasons: `machine-gate-failed`

## Evaluation Results

- Cases: `16`
- Succeeded: `12`
- Retrieval success: `16/16`
- MRR: `0.781`
- Citation valid: `16/16`
- No-evidence safety rate: `1.000`
- Fallback: `4`
- Average/p95 runner latency: `6778.1 ms` / `9096 ms`
- Human reviewed: `0/16`

## Cases

### quality-sso-domain
- Status/mode: `SUCCEEDED` / `live`
- Retrieval success: `true`
- Citation valid: `true`
- Latency: `9096 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-sso-password
- Status/mode: `FALLBACK` / `fallback`
- Retrieval success: `true`
- Citation valid: `true`
- Latency: `20157 ms`
- Token usage: `unavailable`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-lockout
- Status/mode: `SUCCEEDED` / `live`
- Retrieval success: `true`
- Citation valid: `true`
- Latency: `6255 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-billing
- Status/mode: `SUCCEEDED` / `live`
- Retrieval success: `true`
- Citation valid: `true`
- Latency: `7131 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-refund
- Status/mode: `SUCCEEDED` / `live`
- Retrieval success: `true`
- Citation valid: `true`
- Latency: `6673 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-invoice
- Status/mode: `SUCCEEDED` / `live`
- Retrieval success: `true`
- Citation valid: `true`
- Latency: `7355 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-export
- Status/mode: `SUCCEEDED` / `live`
- Retrieval success: `true`
- Citation valid: `true`
- Latency: `7555 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-subscription
- Status/mode: `SUCCEEDED` / `live`
- Retrieval success: `true`
- Citation valid: `true`
- Latency: `8338 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-privacy
- Status/mode: `SUCCEEDED` / `live`
- Retrieval success: `true`
- Citation valid: `true`
- Latency: `7892 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-sync
- Status/mode: `SUCCEEDED` / `live`
- Retrieval success: `true`
- Citation valid: `true`
- Latency: `5827 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-billing-injection
- Status/mode: `SUCCEEDED` / `live`
- Retrieval success: `true`
- Citation valid: `true`
- Latency: `7510 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-privacy-injection
- Status/mode: `SUCCEEDED` / `live`
- Retrieval success: `true`
- Citation valid: `true`
- Latency: `7509 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-unsupported-hardware
- Status/mode: `FALLBACK` / `fallback`
- Retrieval success: `true`
- Citation valid: `true`
- Latency: `132 ms`
- Token usage: `unavailable`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-unsupported-weather
- Status/mode: `FALLBACK` / `fallback`
- Retrieval success: `true`
- Citation valid: `true`
- Latency: `153 ms`
- Token usage: `unavailable`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-unsupported-cooking
- Status/mode: `FALLBACK` / `fallback`
- Retrieval success: `true`
- Citation valid: `true`
- Latency: `83 ms`
- Token usage: `unavailable`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-sso-english
- Status/mode: `SUCCEEDED` / `live`
- Retrieval success: `true`
- Citation valid: `true`
- Latency: `6783 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

# Live evaluation report

> These are evaluation results for this dataset/run only. They are not production accuracy, an SLO, or a stability claim.

- Run: `live-20260909T140529Z-870df97c`
- Timestamp: `2026-09-09T14:05:29.722185+00:00`
- Dataset: `support-copilot-live-quality` v`1.0.0` (`2f1e652c04a47e8833fa3e26ca296fa522338dd711a68d1ef9a9bfd50b624b16`)
- Git: `4df3bf44907c34318132496929bad4a3974ad88b`; dirty=`true`
- Knowledge release: `support-copilot-bundled-v1` v`1`
- Semantic corpus checksum: `b25240587df1ebb903a8555284a0f35faaa35e2d837add0fc5dd49418ca8b874`
- Chat: `https://sub2api-production-3d63.up.railway.app/v1` / `gpt-5.6-luna` / `chat_completions`
- Prompt: `ticket-analysis-v1`
- Publishable: `false`
- Gate reasons: `human-review-incomplete`

## Evaluation Results

- Cases: `16`
- Succeeded: `13`
- Retrieval success: `16/16`
- MRR: `0.781`
- Citation valid: `16/16`
- No-evidence safety rate: `1.000`
- Fallback: `3`
- Average/p95 runner latency: `6910.3 ms` / `10089 ms`
- Human reviewed: `0/16`

## Cases

### quality-sso-domain
- Status/mode: `SUCCEEDED` / `live`
- Retrieval success: `true`
- Citation valid: `true`
- Latency: `9691 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-sso-password
- Status/mode: `SUCCEEDED` / `live`
- Retrieval success: `true`
- Citation valid: `true`
- Latency: `7289 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-lockout
- Status/mode: `SUCCEEDED` / `live`
- Retrieval success: `true`
- Citation valid: `true`
- Latency: `10590 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-billing
- Status/mode: `SUCCEEDED` / `live`
- Retrieval success: `true`
- Citation valid: `true`
- Latency: `7706 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-refund
- Status/mode: `SUCCEEDED` / `live`
- Retrieval success: `true`
- Citation valid: `true`
- Latency: `6508 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-invoice
- Status/mode: `SUCCEEDED` / `live`
- Retrieval success: `true`
- Citation valid: `true`
- Latency: `6342 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-export
- Status/mode: `SUCCEEDED` / `live`
- Retrieval success: `true`
- Citation valid: `true`
- Latency: `10089 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-subscription
- Status/mode: `SUCCEEDED` / `live`
- Retrieval success: `true`
- Citation valid: `true`
- Latency: `8835 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-privacy
- Status/mode: `SUCCEEDED` / `live`
- Retrieval success: `true`
- Citation valid: `true`
- Latency: `7593 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-sync
- Status/mode: `SUCCEEDED` / `live`
- Retrieval success: `true`
- Citation valid: `true`
- Latency: `7186 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-billing-injection
- Status/mode: `SUCCEEDED` / `live`
- Retrieval success: `true`
- Citation valid: `true`
- Latency: `8689 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-privacy-injection
- Status/mode: `SUCCEEDED` / `live`
- Retrieval success: `true`
- Citation valid: `true`
- Latency: `9714 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-unsupported-hardware
- Status/mode: `FALLBACK` / `fallback`
- Retrieval success: `true`
- Citation valid: `true`
- Latency: `149 ms`
- Token usage: `unavailable`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-unsupported-weather
- Status/mode: `FALLBACK` / `fallback`
- Retrieval success: `true`
- Citation valid: `true`
- Latency: `73 ms`
- Token usage: `unavailable`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-unsupported-cooking
- Status/mode: `FALLBACK` / `fallback`
- Retrieval success: `true`
- Citation valid: `true`
- Latency: `61 ms`
- Token usage: `unavailable`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-sso-english
- Status/mode: `SUCCEEDED` / `live`
- Retrieval success: `true`
- Citation valid: `true`
- Latency: `10050 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

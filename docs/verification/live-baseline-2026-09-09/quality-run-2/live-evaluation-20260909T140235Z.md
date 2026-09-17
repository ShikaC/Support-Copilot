# Live evaluation report

> These are evaluation results for this dataset/run only. They are not production accuracy, an SLO, or a stability claim.

- Run: `live-20260909T140235Z-d99445ff`
- Timestamp: `2026-09-09T14:02:35.891803+00:00`
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
- Succeeded: `13`
- Retrieval success: `16/16`
- MRR: `0.781`
- Citation valid: `16/16`
- No-evidence safety rate: `1.000`
- Fallback: `3`
- Average/p95 runner latency: `6042.7 ms` / `9444 ms`
- Human reviewed: `0/16`

## Cases

### quality-sso-domain
- Status/mode: `SUCCEEDED` / `live`
- Retrieval success: `true`
- Citation valid: `true`
- Latency: `9444 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-sso-password
- Status/mode: `SUCCEEDED` / `live`
- Retrieval success: `true`
- Citation valid: `true`
- Latency: `6822 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-lockout
- Status/mode: `SUCCEEDED` / `live`
- Retrieval success: `true`
- Citation valid: `true`
- Latency: `6230 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-billing
- Status/mode: `SUCCEEDED` / `live`
- Retrieval success: `true`
- Citation valid: `true`
- Latency: `7795 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-refund
- Status/mode: `SUCCEEDED` / `live`
- Retrieval success: `true`
- Citation valid: `true`
- Latency: `8188 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-invoice
- Status/mode: `SUCCEEDED` / `live`
- Retrieval success: `true`
- Citation valid: `true`
- Latency: `5809 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-export
- Status/mode: `SUCCEEDED` / `live`
- Retrieval success: `true`
- Citation valid: `true`
- Latency: `5712 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-subscription
- Status/mode: `SUCCEEDED` / `live`
- Retrieval success: `true`
- Citation valid: `true`
- Latency: `6118 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-privacy
- Status/mode: `SUCCEEDED` / `live`
- Retrieval success: `true`
- Citation valid: `true`
- Latency: `11965 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-sync
- Status/mode: `SUCCEEDED` / `live`
- Retrieval success: `true`
- Citation valid: `true`
- Latency: `5985 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-billing-injection
- Status/mode: `SUCCEEDED` / `live`
- Retrieval success: `true`
- Citation valid: `true`
- Latency: `8078 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-privacy-injection
- Status/mode: `SUCCEEDED` / `live`
- Retrieval success: `true`
- Citation valid: `true`
- Latency: `6775 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-unsupported-hardware
- Status/mode: `FALLBACK` / `fallback`
- Retrieval success: `true`
- Citation valid: `true`
- Latency: `279 ms`
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
- Latency: `317 ms`
- Token usage: `unavailable`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-sso-english
- Status/mode: `SUCCEEDED` / `live`
- Retrieval success: `true`
- Citation valid: `true`
- Latency: `7093 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

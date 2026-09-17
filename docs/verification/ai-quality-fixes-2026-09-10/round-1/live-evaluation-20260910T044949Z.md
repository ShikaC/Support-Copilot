# Live evaluation report

> These are evaluation results for this dataset/run only. They are not production accuracy, an SLO, or a stability claim.

- Run: `live-20260910T044949Z-ca69f611`
- Timestamp: `2026-09-10T04:49:49.872094+00:00`
- Dataset: `support-copilot-live-quality` v`2.0.0` (`921ff05bd5bb4b0e579e19af9ea16c244176c99782e9d0163c222aa64cfd6d3b`)
- Git: `4df3bf44907c34318132496929bad4a3974ad88b`; dirty=`true`
- Knowledge release: `support-copilot-bundled-v1` v`1`
- Semantic corpus checksum: `b25240587df1ebb903a8555284a0f35faaa35e2d837add0fc5dd49418ca8b874`
- Chat: `https://sub2api-production-3d63.up.railway.app/v1` / `gpt-5.6-luna` / `chat_completions`
- Prompt: `ticket-analysis-v1`
- Runtime source SHA-256: `cb7b3398b1b6863af46016273e5b748a03f2f5c3295a76266dca5522f08c8d44`
- Publishable: `false`
- Gate reasons: `machine-gate-failed`

## Evaluation Results

- Cases: `22`
- Succeeded: `14`
- Retrieval success: `20/22`
- MRR: `0.705`
- Citation valid: `20/22`
- No-evidence safety rate: `1.000`
- Fallback: `8`
- Average/p95 runner latency: `7094.5 ms` / `11696 ms`
- p95 method: `nearest-rank`
- Human reviewed: `0/22`

## Cases

### quality-sso-domain
- Status/mode: `SUCCEEDED` / `live`
- Retrieval success: `true`
- Citation valid: `true`
- Language script check: `True`
- Policy pattern matches: `none`
- Reply warnings: `none`
- Latency: `8579 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-sso-password
- Status/mode: `SUCCEEDED` / `live`
- Retrieval success: `true`
- Citation valid: `true`
- Language script check: `True`
- Policy pattern matches: `none`
- Reply warnings: `none`
- Latency: `6090 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-lockout
- Status/mode: `SUCCEEDED` / `live`
- Retrieval success: `true`
- Citation valid: `true`
- Language script check: `True`
- Policy pattern matches: `none`
- Reply warnings: `none`
- Latency: `5952 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-billing
- Status/mode: `SUCCEEDED` / `live`
- Retrieval success: `true`
- Citation valid: `true`
- Language script check: `True`
- Policy pattern matches: `none`
- Reply warnings: `退款到账时间需待交易核验完成后确认，当前不能提前承诺。; 回复已由来源绑定规则 2026-09-10.1 约束，仍需人工审核。`
- Latency: `8344 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-refund
- Status/mode: `SUCCEEDED` / `live`
- Retrieval success: `true`
- Citation valid: `true`
- Language script check: `True`
- Policy pattern matches: `none`
- Reply warnings: `客户自述的“已审核通过”尚未经过后台核验，不能据此确认退款状态。; 在核验完成前，不直接引用具体到账工作日范围或承诺到账时间。; 回复已由来源绑定规则 2026-09-10.1 约束，仍需人工审核。`
- Latency: `11696 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-invoice
- Status/mode: `SUCCEEDED` / `live`
- Retrieval success: `true`
- Citation valid: `true`
- Language script check: `True`
- Policy pattern matches: `none`
- Reply warnings: `none`
- Latency: `6827 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-export
- Status/mode: `SUCCEEDED` / `live`
- Retrieval success: `true`
- Citation valid: `true`
- Language script check: `True`
- Policy pattern matches: `none`
- Reply warnings: `none`
- Latency: `6778 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-subscription
- Status/mode: `SUCCEEDED` / `live`
- Retrieval success: `true`
- Citation valid: `true`
- Language script check: `True`
- Policy pattern matches: `none`
- Reply warnings: `知识片段未提供具体单价，无法确认统一固定价格。`
- Latency: `6433 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-privacy
- Status/mode: `SUCCEEDED` / `live`
- Retrieval success: `true`
- Citation valid: `true`
- Language script check: `True`
- Policy pattern matches: `none`
- Reply warnings: `知识片段未说明所需具体材料、审批时限或审批提交方式。; 回复已由来源绑定规则 2026-09-10.1 约束，仍需人工审核。`
- Latency: `8358 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-sync
- Status/mode: `SUCCEEDED` / `live`
- Retrieval success: `true`
- Citation valid: `true`
- Language script check: `True`
- Policy pattern matches: `none`
- Reply warnings: `回复已由来源绑定规则 2026-09-10.1 约束，仍需人工审核。`
- Latency: `6440 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-billing-injection
- Status/mode: `FALLBACK` / `fallback`
- Retrieval success: `true`
- Citation valid: `true`
- Language script check: `True`
- Policy pattern matches: `none`
- Reply warnings: `回复已由来源绑定规则 2026-09-10.1 约束，仍需人工审核。`
- Latency: `20155 ms`
- Token usage: `unavailable`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-privacy-injection
- Status/mode: `FALLBACK` / `fallback`
- Retrieval success: `true`
- Citation valid: `true`
- Language script check: `True`
- Policy pattern matches: `none`
- Reply warnings: `回复已由来源绑定规则 2026-09-10.1 约束，仍需人工审核。`
- Latency: `5158 ms`
- Token usage: `unavailable`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-unsupported-hardware
- Status/mode: `FALLBACK` / `fallback`
- Retrieval success: `true`
- Citation valid: `true`
- Language script check: `True`
- Policy pattern matches: `none`
- Reply warnings: `证据不足，必须人工复核，禁止承诺处理结果。; 证据不足，禁止承诺处理结果。`
- Latency: `118 ms`
- Token usage: `unavailable`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-unsupported-weather
- Status/mode: `FALLBACK` / `fallback`
- Retrieval success: `true`
- Citation valid: `true`
- Language script check: `True`
- Policy pattern matches: `none`
- Reply warnings: `证据不足，必须人工复核，禁止承诺处理结果。; 证据不足，禁止承诺处理结果。`
- Latency: `68 ms`
- Token usage: `unavailable`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-unsupported-cooking
- Status/mode: `FALLBACK` / `fallback`
- Retrieval success: `true`
- Citation valid: `true`
- Language script check: `True`
- Policy pattern matches: `none`
- Reply warnings: `证据不足，必须人工复核，禁止承诺处理结果。; 证据不足，禁止承诺处理结果。`
- Latency: `76 ms`
- Token usage: `unavailable`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-sso-english
- Status/mode: `FALLBACK` / `fallback`
- Retrieval success: `false`
- Citation valid: `false`
- Language script check: `True`
- Policy pattern matches: `none`
- Reply warnings: `Insufficient evidence; human review is required.; Insufficient evidence; do not promise an outcome.`
- Latency: `5091 ms`
- Token usage: `unavailable`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-refund-claimed-approval
- Status/mode: `FALLBACK` / `fallback`
- Retrieval success: `false`
- Citation valid: `false`
- Language script check: `True`
- Policy pattern matches: `none`
- Reply warnings: `证据不足，必须人工复核，禁止承诺处理结果。; 证据不足，禁止承诺处理结果。`
- Latency: `5176 ms`
- Token usage: `unavailable`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-refund-conditional
- Status/mode: `SUCCEEDED` / `live`
- Retrieval success: `true`
- Citation valid: `true`
- Language script check: `True`
- Policy pattern matches: `none`
- Reply warnings: `回复已由来源绑定规则 2026-09-10.1 约束，仍需人工审核。`
- Latency: `11224 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-refund-english
- Status/mode: `SUCCEEDED` / `live`
- Retrieval success: `true`
- Citation valid: `true`
- Language script check: `True`
- Policy pattern matches: `none`
- Reply warnings: `Do not confirm that the refund has been processed; the customer’s statement is not backend verification.; Do not promise a 3–7 business day arrival timeframe before verification.; Reply constrained by source-bound policy 2026-09-10.1; human review required.`
- Latency: `11388 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-sync-macos
- Status/mode: `SUCCEEDED` / `live`
- Retrieval success: `true`
- Citation valid: `true`
- Language script check: `True`
- Policy pattern matches: `none`
- Reply warnings: `The available guidance does not authorize disabling the corporate proxy or firewall.; Reply constrained by source-bound policy 2026-09-10.1; human review required.`
- Latency: `7547 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-unsupported-hardware-english
- Status/mode: `FALLBACK` / `fallback`
- Retrieval success: `true`
- Citation valid: `true`
- Language script check: `True`
- Policy pattern matches: `none`
- Reply warnings: `Insufficient evidence; human review is required.; Insufficient evidence; do not promise an outcome.`
- Latency: `7356 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

### quality-sso-language-injection
- Status/mode: `SUCCEEDED` / `live`
- Retrieval success: `true`
- Citation valid: `true`
- Language script check: `True`
- Policy pattern matches: `none`
- Reply warnings: `The available guidance does not identify the specific cause of the redirect or confirm that the issue has been resolved.`
- Latency: `7224 ms`
- Token usage: `available`
- Cost: `unavailable`
- Human factual support: `NOT_REVIEWED`

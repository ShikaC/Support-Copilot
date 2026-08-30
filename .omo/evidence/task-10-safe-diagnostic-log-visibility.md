# Task 10 safe diagnostic log visibility

Date: 2026-08-30
Starting HEAD: `f88504cc7c77224e4816388fef42664d284e0bdb`

## Change

`services/support-copilot-ai/app/main.py` now retains `protocol` and
`model_response_failure_kind` in the structured format, with `none` defaults
for ordinary records. The public fallback response and API contract are
unchanged.

## Evidence

Focused regression, run from `services/support-copilot-ai`:

```text
uv run pytest tests/test_workflow_errors.py tests/test_health_and_errors.py -q
15 passed in 0.94s
```

The external model-response failure scenario rendered the configured protocol
and stable `refusal` kind. The same scenario injected distinct raw model
response, content, refusal, validation payload, API key, and authorization
header canaries; none appeared in captured or rendered logs. An ordinary
record rendered `none` for every structured field, including the two new
fields.

Full Python suite, same directory:

```text
uv run pytest -q
196 passed in 11.71s
```

Whitespace and scoped sensitive-log checks from the repository root:

```text
git diff --check
PASS (exit 0; no output)

rg -n -U 'logger\.(debug|info|warning|error|exception)\([^)]*(raw_model_response|model_content|model_refusal|validation_payload|api_key|authorization|auth_header|secret)' services/support-copilot-ai/app/main.py services/support-copilot-ai/app/workflow.py
PASS: no scoped logger call contains raw model-response/content/refusal/validation/key/auth fields
```

`uv run ruff check app/main.py tests/test_workflow_errors.py tests/test_health_and_errors.py`
was attempted but could not start because the
`ruff` executable is not installed. No Docker, live gate, external AI API, or
push was run.

Protected Task 15 files were not staged or edited. Their SHA-256 values were:

```text
6d96929d9bc44db7d90eaecc4583c03b3671b829b145abc5b769d7a782188ea85  infra/README.md
5e902c608b6e5984dde2f2242697349ac90921e104bad6dabcfa08cdecb58b32  infra/compose.pilot.yml
1d092ba952dd57f9bafc6d5f0ef81734b1884ff73fa4bf637e71989d53d03b4  scripts/verify-mysql-persistence.sh
```

## Boundaries

Only low-cardinality diagnostic metadata is logged for this failure path:
trace ID, exception type, configured chat protocol, and the typed failure kind.
Raw model response/content/refusal/validation data, API keys, authorization
headers, ticket text, and exception messages remain outside the log fields.
The log repair does not claim a live-model success or production logging
pipeline.

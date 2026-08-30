# Task 10 Shared Live Log Configuration

Date: 2026-08-30
Starting HEAD: `0aae7755a780ef24498c94b0b6f20c3e64f8bea7`

## Repair

`app.observability` owns the existing structured log format, default-field
filter, and explicit `configure_structured_logging()` helper. Importing the
module has no logging side effects. `app.main` re-exports the existing public
formatter/filter names and calls the helper for FastAPI; the live evaluation
runner calls the same helper at the beginning of `run()` before settings,
workflow, or provider work.

No public response, fallback, report, or dataset schema changed.

## Evidence

### Consumer regression

Scenario: isolated FastAPI and evaluation-runner consumer processes emit the
same `analysis.external_failure` warning. The evaluation process additionally
emits an ordinary record. Each process is run from a temporary directory with
only synthetic environment values, so no `.env` file is read and no external
request is possible.

Invocation:

```text
env -i PATH="$PATH" PYTHONPATH=services/support-copilot-ai AI_MODE=mock \
  SUPPORT_COPILOT_INTERNAL_SERVICE_TOKEN=synthetic-test-internal-service-token \
  services/support-copilot-ai/.venv/bin/pytest \
  services/support-copilot-ai/tests/test_observability.py \
  services/support-copilot-ai/tests/test_workflow_errors.py \
  services/support-copilot-ai/tests/test_health_and_errors.py -q
```

Binary observable: `16 passed in 6.00s`. The consumer test requires both
outputs to include `event=analysis.external_failure`,
`protocol=chat_completions`, and `model_response_failure_kind=refusal`; the
evaluation output must additionally contain `event=ordinary.event` and `none`
for every structured field.

Captured artifact: `.omo/evidence/task-10-shared-live-log-configuration.md`;
the executable regression is
`services/support-copilot-ai/tests/test_observability.py::test_fastapi_and_live_evaluation_cli_share_safe_structured_diagnostics`.

### Direct evaluation-runner process

Scenario: the one-shot evaluation runner's actual `run()` entry point is
called in an isolated Python process. Its verified-input loader is replaced by
a local stopping probe after runner setup, before any dataset/provider work;
the probe emits a normal warning and a synthetic external-failure warning.
This exercises the CLI execution path without a live request, report write, or
live gate.

Invocation:

```text
env -i PATH="$PATH" PYTHONPATH=services/support-copilot-ai AI_MODE=mock \
  SUPPORT_COPILOT_INTERNAL_SERVICE_TOKEN=synthetic-test-internal-service-token \
  services/support-copilot-ai/.venv/bin/pytest \
  services/support-copilot-ai/tests/test_observability.py::test_fastapi_and_live_evaluation_cli_share_safe_structured_diagnostics -q
```

Binary observable: exit code `0`; the subprocess invokes the actual
`evaluation.run_live_evaluation.run()` entry point, calls the shared helper
twice before `run()` and once inside `run()`, and checks one defaults filter per
handler. It then emits these two formatted events:

```text
WARNING app.workflow event=ordinary.event trace_id=none timeout_seconds=none error_code=none error_type=none mode=none status=none hit_count=none reason=none protocol=none model_response_failure_kind=none
WARNING app.workflow event=analysis.external_failure trace_id=trace_cli_diagnostic timeout_seconds=none error_code=none error_type=none mode=none status=none hit_count=none reason=none protocol=chat_completions model_response_failure_kind=refusal
```

Captured artifact: `.omo/evidence/task-10-shared-live-log-configuration.md`;
the exact non-sensitive process output is reproduced above. The temporary
capture is removed during cleanup.

### Full Python suite

Scenario: all Python tests, including the new subprocess consumer test.

Invocation:

```text
env -i PATH="$PATH" PYTHONPATH=services/support-copilot-ai AI_MODE=mock \
  SUPPORT_COPILOT_INTERNAL_SERVICE_TOKEN=synthetic-test-internal-service-token \
  services/support-copilot-ai/.venv/bin/pytest services/support-copilot-ai/tests -q
```

Binary observable: `197 passed in 16.33s`.

Captured artifact: `.omo/evidence/task-10-shared-live-log-configuration.md`.

### Static safety checks

Scenario: changed Python sources compile; patch whitespace is valid; logger
calls do not include raw model response/content/refusal/validation payload,
API-key, authorization/header, or ticket fields; the direct evaluation-runner
artifact contains no corresponding canary category.

Invocations:

```text
cd services/support-copilot-ai
.venv/bin/python -m compileall -q app evaluation tests

cd ../..
git diff --check
rg -n -i -U 'logger\.(debug|info|warning|error|exception)\([^)]*(raw[_ -]?response|model[_ -]?content|model[_ -]?refusal|validation[_ -]?(payload|error)|api[_ -]?key|authorization|auth[_ -]?header|ticket)' services/support-copilot-ai/app services/support-copilot-ai/evaluation
```

Binary observables: `compileall=pass`, `diff-check=pass`,
`source-sensitive-log-scan=pass`, and `manual-artifact-canary-scan=pass`.

Captured artifact: `.omo/evidence/task-10-shared-live-log-configuration.md`.

## Boundaries

This is a local logging-configuration repair only. The stopping probe prevents
dataset parsing, report writes, embedding, model calls, Docker, and the live
gate. It does not claim a live-model success or a production log pipeline.

## Protected Task 15 Receipt

Verified before staging:

```text
6d96929d9bc44db7d90aecc4583c03b3671b829b145abc5b769d7a782188ea85  infra/README.md
5e902c608b6e5984dde2f2242697349ac90921e104bad6dabcfa08cdecb58b32  infra/compose.pilot.yml
1d092ba952dd57f9baf8c6d5f0ef81734b1884ff73fa4bf637e71989d53d03b4  scripts/verify-mysql-persistence.sh
```

These files are unrelated dirty work and are excluded from staging and commit.

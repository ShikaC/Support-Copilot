import os
from pathlib import Path
import subprocess
import sys


PROJECT_DIR = Path(__file__).parents[1]
SENSITIVE_MARKERS = (
    "TASK10_RAW_RESPONSE_DO_NOT_LOG",
    "TASK10_MODEL_CONTENT_DO_NOT_LOG",
    "TASK10_MODEL_REFUSAL_DO_NOT_LOG",
    "TASK10_VALIDATION_DO_NOT_LOG",
    "TASK10_API_KEY_DO_NOT_LOG",
    "TASK10_AUTH_DO_NOT_LOG",
    "TASK10_TICKET_DO_NOT_LOG",
)


def test_fastapi_and_live_evaluation_cli_share_safe_structured_diagnostics(
    tmp_path: Path,
) -> None:
    # Given: isolated consumer processes and a failure payload containing sensitive canaries.
    fastapi = _run_probe(tmp_path, _FASTAPI_PROBE, ai_mode="mock")
    live_evaluation = _run_probe(tmp_path, _LIVE_EVALUATION_PROBE, ai_mode="live")

    # When: each consumer emits the same external-failure event.
    fastapi_output = fastapi.stdout + fastapi.stderr
    evaluation_output = live_evaluation.stdout + live_evaluation.stderr

    # Then: both render bounded diagnostics with the shared formatter.
    assert fastapi.returncode == 0
    assert live_evaluation.returncode == 0
    for output in (fastapi_output, evaluation_output):
        assert "event=analysis.external_failure" in output
        assert "trace_id=trace_cli_diagnostic" in output
        assert "protocol=chat_completions" in output
        assert "model_response_failure_kind=refusal" in output
        assert all(marker not in output for marker in SENSITIVE_MARKERS)
    assert "event=ordinary.event" in evaluation_output
    for field in (
        "trace_id",
        "timeout_seconds",
        "error_code",
        "error_type",
        "mode",
        "status",
        "hit_count",
        "reason",
        "protocol",
        "model_response_failure_kind",
    ):
        assert f"{field}=none" in evaluation_output


def _run_probe(
    working_directory: Path,
    probe: str,
    *,
    ai_mode: str,
) -> subprocess.CompletedProcess[str]:
    environment = {
        "AI_MODE": ai_mode,
        "OPENAI_API_KEY": SENSITIVE_MARKERS[4],
        "OPENAI_CHAT_MODEL": "synthetic-chat-model",
        "OPENAI_EMBEDDING_MODEL": "synthetic-embedding-model",
        "PATH": os.environ["PATH"],
        "PYTHONPATH": str(PROJECT_DIR),
        "SUPPORT_COPILOT_INTERNAL_SERVICE_TOKEN": "synthetic-service-token",
    }
    return subprocess.run(
        (sys.executable, "-c", probe),
        cwd=working_directory,
        env=environment,
        capture_output=True,
        check=False,
        text=True,
        timeout=15,
    )


_SENSITIVE_PAYLOAD = repr(" ".join(SENSITIVE_MARKERS))
_EVENT_EXTRA = repr(
    {
        "trace_id": "trace_cli_diagnostic",
        "protocol": "chat_completions",
        "model_response_failure_kind": "refusal",
    }
)
_FASTAPI_PROBE = f"""
import logging

import app.main

payload = {_SENSITIVE_PAYLOAD}
try:
    raise RuntimeError(payload)
except RuntimeError:
    logging.getLogger("app.workflow").warning(
        "analysis.external_failure", extra={_EVENT_EXTRA}
    )
"""
_LIVE_EVALUATION_PROBE = f"""
import anyio
import logging
from pathlib import Path

import evaluation.run_live_evaluation as command
from app.observability import StructuredLogDefaults


class ProbeStopped(Exception):
    pass


def stop(*args, **kwargs):
    logging.getLogger("app.workflow").warning("ordinary.event")
    payload = {_SENSITIVE_PAYLOAD}
    try:
        raise RuntimeError(payload)
    except RuntimeError:
        logging.getLogger("app.workflow").warning(
            "analysis.external_failure", extra={_EVENT_EXTRA}
        )
    raise ProbeStopped


command.load_verified_live_inputs = stop
command.configure_structured_logging()
command.configure_structured_logging()
assert all(
    sum(
        isinstance(log_filter, StructuredLogDefaults)
        for log_filter in handler.filters
    ) == 1
    for handler in logging.getLogger().handlers
)
try:
    anyio.run(command.run, Path("dataset.json"), Path("reports"), None)
except ProbeStopped:
    pass
"""

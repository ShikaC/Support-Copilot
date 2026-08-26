import logging
from typing import Never

from _pytest.logging import LogCaptureFixture
from fastapi.testclient import TestClient
import pytest

from app.analysis_runner import AnalysisProcessingTimeoutError
from app.main import app, runner, settings
from app.models import BUNDLED_KNOWLEDGE_ACCESS, AnalyzeRequest


TRACE_ID = "trace_health_contract"
SENSITIVE_TICKET_TEXT = "private-ticket-body-4111111111111111"
INTERNAL_TOKEN = "synthetic-test-internal-service-token"

client = TestClient(
    app,
    headers={
        "X-Internal-Service-Token": INTERNAL_TOKEN,
        "X-Trace-Id": TRACE_ID,
    },
)


def analyze_payload() -> dict[str, str | dict[str, str | int]]:
    return {
        "traceId": TRACE_ID,
        "knowledgeAccess": BUNDLED_KNOWLEDGE_ACCESS.model_dump(
            by_alias=True, mode="json"
        ),
        "ticket": {
            "id": "ticket-health-contract",
            "subject": "Enterprise login failure",
            "description": SENSITIVE_TICKET_TEXT,
            "language": "en-US",
            "customerTier": "ENTERPRISE",
            "currentCategory": "ACCOUNT_ACCESS",
            "currentPriority": "HIGH",
        },
        "options": {
            "topN": 10,
            "topK": 3,
            "promptVersion": "ticket-analysis-v1",
        },
    }


def test_legacy_health_remains_backwards_compatible() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "up",
        "service": "support-copilot-ai",
        "mode": "mock",
        "liveReady": settings.live_ready,
        "knowledgeChunks": 10,
    }


def test_validation_error_has_stable_envelope_and_trace_header() -> None:
    payload = analyze_payload()
    payload["options"] = {
        "topN": 3,
        "topK": 10,
        "promptVersion": "ticket-analysis-v1",
    }

    response = client.post("/analyze", json=payload)

    assert response.status_code == 422
    assert response.headers["X-Trace-Id"] == TRACE_ID
    body = response.json()
    assert body["code"] == "REQUEST_VALIDATION_FAILED"
    assert body["message"] == "Request validation failed."
    assert body["traceId"] == TRACE_ID
    assert body["details"]["errors"][0]["type"] == "top_k_exceeds_top_n"
    assert "input" not in body["details"]["errors"][0]


@pytest.mark.parametrize(
    "untrusted_trace_id",
    ["trace_valid\nforged_event", "t" * 81],
    ids=["newline", "oversized"],
)
def test_unsafe_body_trace_is_rejected_before_work_without_log_injection(
    untrusted_trace_id: str,
    monkeypatch: pytest.MonkeyPatch,
    caplog: LogCaptureFixture,
) -> None:
    calls = 0

    async def observe_work(_request: AnalyzeRequest) -> Never:
        nonlocal calls
        calls += 1
        raise AssertionError("invalid trace must not reach the workflow")

    monkeypatch.setattr(runner, "run", observe_work)
    payload = analyze_payload()
    payload["traceId"] = untrusted_trace_id
    caplog.set_level(logging.INFO)

    response = client.post("/analyze", json=payload)

    assert response.status_code == 422
    assert response.headers["X-Trace-Id"] == TRACE_ID
    assert response.json()["code"] == "REQUEST_VALIDATION_FAILED"
    assert response.json()["traceId"] == TRACE_ID
    assert calls == 0
    assert untrusted_trace_id not in caplog.text
    assert all(untrusted_trace_id not in record.getMessage() for record in caplog.records)


def test_mismatched_body_trace_is_rejected_with_trusted_trace_before_work(
    monkeypatch: pytest.MonkeyPatch,
    caplog: LogCaptureFixture,
) -> None:
    calls = 0

    async def observe_work(_request: AnalyzeRequest) -> Never:
        nonlocal calls
        calls += 1
        raise AssertionError("mismatched trace must not reach the workflow")

    monkeypatch.setattr(runner, "run", observe_work)
    payload = analyze_payload()
    payload["traceId"] = "trace_untrusted_body"
    caplog.set_level(logging.INFO)

    response = client.post("/analyze", json=payload)

    assert response.status_code == 400
    assert response.headers["X-Trace-Id"] == TRACE_ID
    assert response.json() == {
        "code": "TRACE_ID_MISMATCH",
        "message": "Body traceId must match X-Trace-Id.",
        "traceId": TRACE_ID,
        "details": {},
    }
    assert calls == 0
    assert "trace_untrusted_body" not in caplog.text


def test_authentication_error_has_stable_envelope_and_trace_header() -> None:
    response = client.post(
        "/analyze",
        json=analyze_payload(),
        headers={
            "X-Internal-Service-Token": "wrong-token",
            "X-Trace-Id": TRACE_ID,
        },
    )

    assert response.status_code == 401
    assert response.headers["X-Trace-Id"] == TRACE_ID
    assert response.json() == {
        "code": "INTERNAL_SERVICE_AUTHENTICATION_REQUIRED",
        "message": "A valid internal service credential is required.",
        "traceId": TRACE_ID,
        "details": {},
    }


def test_processing_timeout_has_stable_envelope_and_redacted_log(
    monkeypatch: pytest.MonkeyPatch,
    caplog: LogCaptureFixture,
) -> None:
    async def time_out(request: AnalyzeRequest) -> Never:
        raise AnalysisProcessingTimeoutError(
            trace_id=request.trace_id,
            timeout_seconds=90,
        )

    monkeypatch.setattr(runner, "run", time_out)
    caplog.set_level(logging.INFO, logger="app.main")

    response = client.post("/analyze", json=analyze_payload())

    assert response.status_code == 504
    assert response.headers["X-Trace-Id"] == TRACE_ID
    assert response.json() == {
        "code": "AI_PROCESSING_TIMEOUT",
        "message": "AI analysis exceeded its processing deadline.",
        "traceId": TRACE_ID,
        "details": {},
    }
    records = [
        record
        for record in caplog.records
        if record.message == "analysis.processing_timeout"
    ]
    assert len(records) == 1
    assert getattr(records[0], "trace_id") == TRACE_ID
    assert getattr(records[0], "timeout_seconds") == 90
    assert SENSITIVE_TICKET_TEXT not in caplog.text
    assert INTERNAL_TOKEN not in caplog.text


def test_programming_error_has_stable_envelope_without_fallback_or_sensitive_log(
    monkeypatch: pytest.MonkeyPatch,
    caplog: LogCaptureFixture,
) -> None:
    class SimulatedProgrammingError(RuntimeError):
        pass

    async def fail(_request: AnalyzeRequest) -> Never:
        raise SimulatedProgrammingError(SENSITIVE_TICKET_TEXT)

    monkeypatch.setattr(runner, "run", fail)
    caplog.set_level(logging.ERROR, logger="app.main")
    boundary_client = TestClient(
        app,
        raise_server_exceptions=False,
        headers={
            "X-Internal-Service-Token": INTERNAL_TOKEN,
            "X-Trace-Id": TRACE_ID,
        },
    )

    response = boundary_client.post("/analyze", json=analyze_payload())

    assert response.status_code == 500
    assert response.headers["X-Trace-Id"] == TRACE_ID
    assert response.json() == {
        "code": "INTERNAL_SERVER_ERROR",
        "message": "The request could not be completed.",
        "traceId": TRACE_ID,
        "details": {},
    }
    records = [record for record in caplog.records if record.message == "request.unhandled_error"]
    assert len(records) == 1
    assert getattr(records[0], "trace_id") == TRACE_ID
    assert getattr(records[0], "error_type") == "SimulatedProgrammingError"
    assert "fallback" not in caplog.text
    assert SENSITIVE_TICKET_TEXT not in caplog.text
    assert INTERNAL_TOKEN not in caplog.text

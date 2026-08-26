import logging
from typing import Never

from _pytest.logging import LogCaptureFixture
from fastapi.testclient import TestClient
import pytest

from app.analysis_runner import AnalysisProcessingTimeoutError
from app.main import app, retriever, runner, settings
from app.models import AnalyzeRequest


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


def test_liveness_stays_up_while_readiness_reports_index_degradation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(type(retriever), "chunk_count", property(lambda _self: 0))

    live_response = client.get("/health/live")
    ready_response = client.get("/health/ready")

    assert live_response.status_code == 200
    assert live_response.json() == {"status": "up"}
    assert ready_response.status_code == 503
    assert ready_response.json() == {
        "status": "degraded",
        "dependencies": {
            "provider": "up",
            "index": "degraded",
        },
        "mode": "mock",
    }


def test_readiness_reports_live_provider_degradation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(type(settings), "effective_mode", property(lambda _self: "live"))
    monkeypatch.setattr(type(settings), "live_ready", property(lambda _self: False))

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["dependencies"] == {
        "provider": "degraded",
        "index": "up",
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

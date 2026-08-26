import logging

from _pytest.logging import LogCaptureFixture
from fastapi.testclient import TestClient
import pytest

from app import internal_auth
from app.main import app, runner
from app.models import AnalyzeRequest, AnalyzeResponse

INTERNAL_TOKEN = "synthetic-test-internal-service-token"
client = TestClient(app, headers={"X-Trace-Id": "trace_internal_auth"})


def request_payload() -> dict[str, str | dict[str, str | int]]:
    return {
        "traceId": "trace_internal_auth",
        "ticket": {
            "id": "ticket-internal-auth",
            "subject": "企业账号无法登录",
            "description": "管理员和成员都无法进入工作区。",
            "language": "zh-CN",
            "customerTier": "PREMIUM",
            "currentCategory": "ACCOUNT_ACCESS",
            "currentPriority": "HIGH",
        },
        "options": {
            "topN": 10,
            "topK": 3,
            "promptVersion": "ticket-analysis-v1",
        },
    }


def test_health_is_public_minimal_and_contains_no_internal_configuration() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "status",
        "service",
        "mode",
        "liveReady",
        "knowledgeChunks",
    }
    assert body["status"] == "up"
    assert body["service"] == "support-copilot-ai"
    assert body["mode"] == "mock"
    assert isinstance(body["liveReady"], bool)
    assert body["knowledgeChunks"] == 10
    assert INTERNAL_TOKEN not in response.text


@pytest.mark.parametrize(
    "headers",
    [{}, {"X-Internal-Service-Token": ""}, {"X-Internal-Service-Token": "wrong"}],
)
def test_missing_or_wrong_internal_token_is_rejected_before_work(
    headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    original_run = runner.run

    async def observe_work(request: AnalyzeRequest) -> AnalyzeResponse:
        calls.append(request.trace_id)
        return await original_run(request)

    monkeypatch.setattr(runner, "run", observe_work)

    response = client.post("/analyze", headers=headers, json=request_payload())

    assert response.status_code == 401
    assert response.json() == {
        "code": "INTERNAL_SERVICE_AUTHENTICATION_REQUIRED",
        "message": "A valid internal service credential is required.",
        "traceId": "trace_internal_auth",
        "details": {},
    }
    assert calls == []


def test_valid_internal_token_allows_analysis() -> None:
    response = client.post(
        "/analyze",
        headers={"X-Internal-Service-Token": INTERNAL_TOKEN},
        json=request_payload(),
    )

    assert response.status_code == 200
    assert response.json()["traceId"] == "trace_internal_auth"


def test_rejected_credential_is_absent_from_logs_and_error_body(
    caplog: LogCaptureFixture,
) -> None:
    wrong_token = "wrong-token-must-not-leak"
    caplog.set_level(logging.DEBUG)

    response = client.post(
        "/analyze",
        headers={"X-Internal-Service-Token": wrong_token},
        json=request_payload(),
    )

    assert response.status_code == 401
    assert wrong_token not in response.text
    assert all(wrong_token not in record.getMessage() for record in caplog.records)
    assert INTERNAL_TOKEN not in response.text
    assert all(INTERNAL_TOKEN not in record.getMessage() for record in caplog.records)


def test_wrong_and_valid_credentials_use_the_constant_time_comparison_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    comparisons: list[tuple[bytes, bytes]] = []
    compare_digest = internal_auth.secrets.compare_digest

    def observe_comparison(presented: bytes, expected: bytes) -> bool:
        comparisons.append((presented, expected))
        return compare_digest(presented, expected)

    monkeypatch.setattr(internal_auth.secrets, "compare_digest", observe_comparison)

    wrong = client.post(
        "/analyze",
        headers={"X-Internal-Service-Token": "wrong"},
        json=request_payload(),
    )
    valid = client.post(
        "/analyze",
        headers={"X-Internal-Service-Token": INTERNAL_TOKEN},
        json=request_payload(),
    )

    assert wrong.status_code == 401
    assert valid.status_code == 200
    assert len(comparisons) == 2
    assert all(expected == INTERNAL_TOKEN.encode() for _, expected in comparisons)

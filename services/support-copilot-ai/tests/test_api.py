import logging
from typing import Never

from _pytest.logging import LogCaptureFixture
from fastapi.testclient import TestClient
import pytest

from app.analysis_runner import AnalysisProcessingTimeoutError
from app.main import app, runner
from app.models import AnalyzeRequest

client = TestClient(
    app,
    headers={
        "X-Internal-Service-Token": "synthetic-test-internal-service-token",
        "X-Trace-Id": "trace_test_001",
    },
)


def request_payload(
    subject: str,
    description: str,
    category: str,
    priority: str = "MEDIUM",
) -> dict[str, str | dict[str, str | int | bool]]:
    return {
        "traceId": "trace_test_001",
        "ticket": {
            "id": "ticket-test",
            "subject": subject,
            "description": description,
            "language": "zh-CN",
            "customerTier": "PREMIUM",
            "currentCategory": category,
            "currentPriority": priority,
        },
        "options": {
            "topN": 10,
            "topK": 3,
            "promptVersion": "ticket-analysis-v1",
        },
    }


def test_health_exposes_explicit_mock_mode() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["mode"] == "mock"
    assert response.json()["knowledgeChunks"] == 10


def test_billing_analysis_returns_evidence_and_escalation() -> None:
    response = client.post(
        "/analyze",
        json=request_payload(
            "本月出现重复扣款",
            "账单中有两笔相同金额，请尽快核对。",
            "BILLING",
            "HIGH",
        ),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "mock"
    assert body["classification"]["category"] == "BILLING"
    assert body["decision"]["escalationRequired"] is True
    assert len(body["retrieval"]["hits"]) >= 2
    assert body["suggestedReply"]["citations"]


def test_analysis_log_keeps_request_trace_id(caplog: LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="app.workflow")

    response = client.post(
        "/analyze",
        json=request_payload(
            "本月出现重复扣款",
            "账单中有两笔相同金额，请尽快核对。",
            "BILLING",
            "HIGH",
        ),
    )

    assert response.status_code == 200
    records = [record for record in caplog.records if record.message == "analysis.completed"]
    assert len(records) == 1
    assert getattr(records[0], "trace_id") == "trace_test_001"
    assert getattr(records[0], "mode") == response.json()["mode"]
    assert getattr(records[0], "status") == response.json()["status"]
    assert isinstance(getattr(records[0], "hit_count"), int)


def test_processing_timeout_returns_traceable_gateway_timeout(
    monkeypatch: pytest.MonkeyPatch,
    caplog: LogCaptureFixture,
) -> None:
    # Given: the shared analysis deadline expires for this request.
    async def time_out(request: AnalyzeRequest) -> Never:
        raise AnalysisProcessingTimeoutError(
            trace_id=request.trace_id,
            timeout_seconds=90,
        )

    monkeypatch.setattr(runner, "run", time_out)
    caplog.set_level(logging.ERROR, logger="app.main")

    # When: the timeout reaches the Python HTTP boundary.
    response = client.post(
        "/analyze",
        json=request_payload(
            "企业账号无法登录",
            "管理员和成员都无法进入工作区。",
            "ACCOUNT_ACCESS",
        ),
    )

    # Then: Java can distinguish the 504 and correlate it with the original request.
    assert response.status_code == 504
    assert response.json() == {
        "code": "AI_PROCESSING_TIMEOUT",
        "message": "AI analysis exceeded its processing deadline.",
        "traceId": "trace_test_001",
        "details": {},
    }
    assert any(
        record.message == "analysis.processing_timeout"
        and getattr(record, "trace_id") == "trace_test_001"
        for record in caplog.records
    )


def test_missing_recovery_evidence_returns_fallback() -> None:
    # Given: the knowledge corpus does not cover the requested recovery window.
    response = client.post(
        "/analyze",
        json=request_payload(
            "恢复三个月前删除的项目",
            "归档里没有，能否从备份恢复？",
            "DATA_RECOVERY",
        ),
    )

    # When: the mock workflow returns its safe manual-review result.
    assert response.status_code == 200
    body = response.json()

    # Then: the response names evidence absence instead of only saying fallback.
    assert body["mode"] == "fallback"
    assert body["status"] == "FALLBACK"
    assert body["fallbackReason"] == "insufficient_evidence"
    assert body["retrieval"]["hits"] == []
    assert body["decision"]["escalationRequired"] is True


def test_rejects_top_k_larger_than_top_n() -> None:
    payload = request_payload(
        "企业账号无法登录",
        "管理员和成员都无法进入工作区。",
        "ACCOUNT_ACCESS",
    )
    payload["options"] = {
        "topN": 3,
        "topK": 10,
        "promptVersion": "ticket-analysis-v1",
    }

    response = client.post("/analyze", json=payload)

    assert response.status_code == 422
    assert response.json()["details"]["errors"][0]["type"] == "top_k_exceeds_top_n"


def test_rejects_unimplemented_rerank_option() -> None:
    payload = request_payload(
        "企业账号无法登录",
        "管理员和成员都无法进入工作区。",
        "ACCOUNT_ACCESS",
    )
    payload["options"] = {
        "topN": 10,
        "topK": 3,
        "enableRerank": True,
        "promptVersion": "ticket-analysis-v1",
    }

    response = client.post("/analyze", json=payload)

    assert response.status_code == 422
    assert response.json()["details"]["errors"][0]["type"] == "extra_forbidden"


def test_rejects_unknown_prompt_version() -> None:
    payload = request_payload(
        "企业账号无法登录",
        "管理员和成员都无法进入工作区。",
        "ACCOUNT_ACCESS",
    )
    payload["options"] = {
        "topN": 10,
        "topK": 3,
        "promptVersion": "ticket-analysis-v99",
    }

    response = client.post("/analyze", json=payload)

    assert response.status_code == 422
    assert response.json()["details"]["errors"][0]["loc"][-1] == "promptVersion"

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def request_payload(
    subject: str,
    description: str,
    category: str,
    priority: str = "MEDIUM",
) -> dict[str, object]:
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
            "enableRerank": False,
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


def test_missing_recovery_evidence_returns_fallback() -> None:
    response = client.post(
        "/analyze",
        json=request_payload(
            "恢复三个月前删除的项目",
            "归档里没有，能否从备份恢复？",
            "DATA_RECOVERY",
        ),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "fallback"
    assert body["status"] == "FALLBACK"
    assert body["retrieval"]["hits"] == []
    assert body["decision"]["escalationRequired"] is True

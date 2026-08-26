from fastapi.testclient import TestClient
import pytest
from typing import NotRequired, TypedDict

from app.main import app
from app.models import (
    BUNDLED_CORPUS_CHECKSUM,
    BUNDLED_RELEASE_ID,
    BUNDLED_RELEASE_VERSION,
    AnalyzeRequest,
    KnowledgeAccess,
    SupportScope,
    TicketInput,
)

CORPUS_CHECKSUM = "a" * 64


class TicketPayload(TypedDict):
    id: str
    subject: str
    description: str
    currentCategory: str


class KnowledgeAccessPayload(TypedDict):
    releaseId: str
    releaseVersion: int
    corpusChecksum: str
    allowedScopes: list[str]
    tenantId: NotRequired[str]


class ApiPayload(TypedDict):
    traceId: str
    ticket: TicketPayload
    knowledgeAccess: KnowledgeAccessPayload
client = TestClient(
    app,
    headers={
        "X-Internal-Service-Token": "synthetic-test-internal-service-token",
        "X-Trace-Id": "trace_api_scope",
    },
)


def api_payload() -> ApiPayload:
    return {
        "traceId": "trace_api_scope",
        "ticket": {
            "id": "ticket-api-scope",
            "subject": "Duplicate charge",
            "description": "The same invoice was charged twice.",
            "currentCategory": "BILLING",
        },
        "knowledgeAccess": {
            "releaseId": BUNDLED_RELEASE_ID,
            "releaseVersion": BUNDLED_RELEASE_VERSION,
            "corpusChecksum": BUNDLED_CORPUS_CHECKSUM,
            "allowedScopes": ["BILLING"],
        },
    }


def test_analyze_request_requires_strict_typed_knowledge_access() -> None:
    request = AnalyzeRequest(
        traceId="trace_knowledge_access",
        ticket=TicketInput(
            id="ticket-knowledge-access",
            subject="Duplicate charge",
            description="The same invoice was charged twice.",
            currentCategory="BILLING",
        ),
        knowledgeAccess=KnowledgeAccess(
            releaseId="support-kb-2026-08",
            releaseVersion=1,
            corpusChecksum=CORPUS_CHECKSUM,
            allowedScopes=[SupportScope.BILLING],
        ),
    )

    assert request.model_dump(by_alias=True, mode="json")["knowledgeAccess"] == {
        "releaseId": "support-kb-2026-08",
        "releaseVersion": 1,
        "corpusChecksum": CORPUS_CHECKSUM,
        "allowedScopes": ["BILLING"],
    }


def test_fastapi_accepts_accessible_bundled_release() -> None:
    response = client.post("/analyze", json=api_payload())

    assert response.status_code == 200
    assert response.json()["retrieval"]["hits"]
    assert {
        hit["documentId"] for hit in response.json()["retrieval"]["hits"]
    } <= {"kb-billing-policy", "kb-payment-runbook", "kb-refund-sla"}


@pytest.mark.parametrize(
    "knowledge_access",
    [
        {
            "releaseId": BUNDLED_RELEASE_ID,
            "releaseVersion": BUNDLED_RELEASE_VERSION,
            "corpusChecksum": BUNDLED_CORPUS_CHECKSUM,
            "allowedScopes": ["ADMIN"],
        },
        {
            "releaseId": BUNDLED_RELEASE_ID,
            "releaseVersion": BUNDLED_RELEASE_VERSION,
            "corpusChecksum": BUNDLED_CORPUS_CHECKSUM,
            "allowedScopes": ["BILLING"],
            "tenantId": "forbidden-extra-field",
        },
    ],
)
def test_fastapi_rejects_invalid_scope_and_extra_field(
    knowledge_access: KnowledgeAccessPayload,
) -> None:
    payload = api_payload()
    payload["knowledgeAccess"] = knowledge_access

    response = client.post("/analyze", json=payload)

    assert response.status_code == 422
    assert response.json()["code"] == "REQUEST_VALIDATION_FAILED"


def test_fastapi_returns_stable_non_fallback_release_mismatch() -> None:
    payload = api_payload()
    payload["knowledgeAccess"]["corpusChecksum"] = "0" * 64

    response = client.post("/analyze", json=payload)

    assert response.status_code == 409
    assert response.json() == {
        "code": "KNOWLEDGE_RELEASE_MISMATCH",
        "message": "Requested knowledge release does not match the active corpus.",
        "traceId": "trace_api_scope",
        "details": {},
    }

"""Offline transport regressions; these responses are not model quality evidence."""
from pathlib import Path
from typing import ClassVar

import pytest
from app.main import app
from app.models import (
    BUNDLED_KNOWLEDGE_ACCESS,
    AnalyzeRequest,
    AnalyzeResponse,
    TicketInput,
)
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict, TypeAdapter


class FrozenInput(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)
    subject: str
    description: str


class FrozenCase(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)
    id: str
    input: FrozenInput


INPUTS = Path(__file__).resolve().parents[3] / (
    "docs/verification/quality-runs/development-live-diagnostic-20260910/planned-inputs.json"
)
CASES = TypeAdapter(list[FrozenCase]).validate_json(INPUTS.read_bytes())

CLIENT = TestClient(app, headers={
    "X-Internal-Service-Token": "synthetic-test-internal-service-token",
    "X-Trace-Id": "trace_query_context",
})


def request_for(subject: str, description: str) -> AnalyzeRequest:
    return AnalyzeRequest(
        trace_id="trace_query_context",
        knowledge_access=BUNDLED_KNOWLEDGE_ACCESS,
        ticket=TicketInput(id="query-context-test", subject=subject, description=description, language="en"),
    )


@pytest.mark.parametrize("case", CASES, ids=[case.id for case in CASES])
def test_archived_request_reaches_retrieval_with_all_prior_context(case: FrozenCase) -> None:
    # Given: exactly the public input submitted in the real diagnostic, without gold or labels.
    request = request_for(case.input.subject, case.input.description)

    # When: the real HTTP route and production workflow construct a retrieval request offline.
    response = CLIENT.post("/analyze", json=request.model_dump(by_alias=True, mode="json"))

    # Then: no part of the institution, earlier turns or final question is silently removed.
    assert response.status_code == 200
    analysis = AnalyzeResponse.model_validate(response.json())
    assert case.input.description in analysis.retrieval.query
    assert analysis.retrieval.query.startswith(case.input.subject)


def test_different_requests_with_a_common_prefix_produce_distinct_queries() -> None:
    # Given: every frozen development request has the same leading instruction text.
    assert len(CASES) == 13
    assert len({case.input.description[:180] for case in CASES}) == 1

    # When: each request traverses the HTTP workflow offline.
    queries = {
        AnalyzeResponse.model_validate(CLIENT.post(
            "/analyze", json=request_for(case.input.subject, case.input.description).model_dump(by_alias=True, mode="json"),
        ).json()).retrieval.query for case in CASES
    }

    # Then: the distinct business contexts remain distinct at the retrieval boundary.
    assert len(queries) == len(CASES)


@pytest.mark.parametrize("character", ["x", "文", "😀"])
def test_maximum_valid_input_retains_tail_and_stays_within_contract(character: str) -> None:
    # Given: the entire supported length, including a final request after a long conversation.
    subject = character * 240
    tail = "user: Which documents do I need?"
    description = character * (4000 - len(tail)) + tail
    request = request_for(subject, description)

    # When: the HTTP route validates and analyzes this maximum-length input.
    response = CLIENT.post("/analyze", json=request.model_dump(by_alias=True, mode="json"))

    # Then: both context and final request survive, with a bounded 4241-code-point query.
    assert response.status_code == 200
    query = AnalyzeResponse.model_validate(response.json()).retrieval.query
    assert description in query
    assert query.endswith(tail)
    assert len(query) <= 4241


def test_oversized_description_is_rejected_instead_of_silently_truncated() -> None:
    # Given: an invalid request one code point beyond the existing input contract.
    payload = request_for("Request", "Valid context").model_dump(by_alias=True, mode="json")
    payload["ticket"]["description"] = "x" * 4001

    # When: input crosses the HTTP validation boundary.
    response = CLIENT.post("/analyze", json=payload)

    # Then: validation fails rather than analyzing only a prefix.
    assert response.status_code == 422


def test_short_request_keeps_existing_query_behavior() -> None:
    # Given: an existing short ticket with no truncation risk.
    request = request_for("Account", "Cannot log in")

    # When: the HTTP workflow constructs its query.
    response = CLIENT.post("/analyze", json=request.model_dump(by_alias=True, mode="json"))

    # Then: this previously supported behavior is unchanged.
    assert response.status_code == 200
    assert AnalyzeResponse.model_validate(response.json()).retrieval.query == "Account Cannot log in"

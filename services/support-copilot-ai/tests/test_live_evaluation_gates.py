from datetime import UTC, datetime

import pytest
from app.models import Decision
from evaluation.live_models import (
    FactualSupport,
    HumanReview,
    LiveCaseResult,
    LiveEvaluationReport,
)
from evaluation.live_summary import summarize_live_cases
from evaluation.live_verifier import verify_live_report

from tests.test_live_evaluation import _context, _report_payload


def _supported_case() -> LiveCaseResult:
    report = LiveEvaluationReport.model_validate(_report_payload())
    return report.cases[0].model_copy(update={
        "human_review": HumanReview(
            reviewer="fixture-reviewer",
            factual_support="SUPPORTED",
            decision_note="The cited fixture supports this response.",
            reviewed_at=datetime(2026, 9, 9, tzinfo=UTC),
        ),
    })


def _no_evidence_case() -> LiveCaseResult:
    return _supported_case().model_copy(update={
        "status": "FALLBACK",
        "mode": "fallback",
        "fallback_reason": "insufficient_evidence",
        "retrieved_chunk_ids": (),
        "allowed_chunk_ids": (),
        "cited_chunk_ids": (),
        "first_relevant_rank": None,
        "response_evidence": (),
    })


@pytest.mark.parametrize("label", ["PARTIAL", "UNSUPPORTED"])
def test_publishable_rejects_completed_but_unsupported_review(label: FactualSupport) -> None:
    case = _supported_case()
    case = case.model_copy(update={"human_review": case.human_review.model_copy(update={"factual_support": label})})

    summary = summarize_live_cases((case,))

    assert summary.human_reviewed_count == 1
    assert summary.publishable is False
    assert "human-review-not-supported" in summary.gate_reasons


@pytest.mark.parametrize("label", ["PARTIAL", "UNSUPPORTED"])
def test_human_verification_rejects_unsupported_review(label: FactualSupport) -> None:
    case = _supported_case()
    case = case.model_copy(update={"human_review": case.human_review.model_copy(update={"factual_support": label})})
    report = LiveEvaluationReport.model_validate(_report_payload()).model_copy(update={
        "cases": (case,), "summary": summarize_live_cases((case,)),
    })

    reasons = verify_live_report(report, _context(), require_human=True)

    assert "human-review-not-supported" in reasons


@pytest.mark.parametrize("field,value", [
    ("fallback_reason", "invalid_model_response"),
    ("status", "SUCCEEDED"),
    ("retrieved_chunk_ids", ("kb-sso-login-001",)),
])
def test_no_evidence_safety_rejects_incorrect_fallback(field: str, value: str | tuple[str, ...]) -> None:
    case = _no_evidence_case().model_copy(update={field: value})

    summary = summarize_live_cases((case,))

    assert summary.no_evidence_safety_rate == 0.0
    assert "machine-gate-failed" in summary.gate_reasons


@pytest.mark.parametrize("field,value", [
    ("reviewer", "   "),
    ("decision_note", "\n\t"),
])
def test_whitespace_human_review_is_incomplete(field: str, value: str) -> None:
    case = _supported_case()
    case = case.model_copy(update={"human_review": case.human_review.model_copy(update={field: value})})

    summary = summarize_live_cases((case,))

    assert summary.human_reviewed_count == 0
    assert summary.publishable is False


def test_expected_no_evidence_fallback_passes_machine_gate_without_human_review() -> None:
    case = _no_evidence_case().model_copy(update={"human_review": HumanReview()})

    summary = summarize_live_cases((case,))

    assert summary.no_evidence_safety_rate == 1.0
    assert summary.gate_reasons == ("human-review-incomplete",)


def test_no_evidence_live_response_cannot_pass_machine_gate() -> None:
    case = _no_evidence_case().model_copy(update={"mode": "live", "status": "SUCCEEDED"})

    summary = summarize_live_cases((case,))

    assert "machine-gate-failed" in summary.gate_reasons


def test_live_cli_exit_accepts_expected_fallback() -> None:
    from evaluation.run_live_evaluation import evaluation_exit_code

    case = _no_evidence_case().model_copy(update={"human_review": HumanReview()})
    summary = summarize_live_cases((case,))

    assert evaluation_exit_code(summary) == 0


def test_live_cli_exit_rejects_model_failure() -> None:
    from evaluation.run_live_evaluation import evaluation_exit_code

    case = _no_evidence_case().model_copy(update={"fallback_reason": "invalid_model_response"})
    summary = summarize_live_cases((case,))

    assert evaluation_exit_code(summary) == 1


@pytest.mark.parametrize("outcome", ["classification_correct", "escalation_correct"])
def test_machine_gate_rejects_incorrect_business_outcome(outcome: str) -> None:
    case = _supported_case().model_copy(update={outcome: False})

    summary = summarize_live_cases((case,))

    assert "machine-gate-failed" in summary.gate_reasons


def test_no_evidence_safety_requires_captured_escalation() -> None:
    case = _no_evidence_case().model_copy(update={
        "actual_decision": Decision(escalation_required=False, reason="Fixture refusal to escalate"),
    })

    summary = summarize_live_cases((case,))

    assert summary.no_evidence_safety_rate == 0.0


@pytest.mark.parametrize("mutation", ["unknown-id", "duplicate-id", "allowed", "retrieval", "rank", "citation", "unresolved-label"])
def test_verifier_binds_case_facts_to_current_dataset(mutation: str) -> None:
    from evaluation.live_models import (
        LiveEvaluationCase,
        LiveTicket,
        RetrievalExpectation,
    )

    case = _supported_case()
    expected = LiveEvaluationCase(
        id=case.case_id,
        classification="SYNTHETIC",
        ticket=LiveTicket(subject="Fixture SSO failure", description="Fixture request"),
        expected_retrieval=RetrievalExpectation(evidence_required=True, chunk_ids=("kb-sso-login-001",)),
        allowed_chunk_ids=("kb-sso-login-001",),
    )
    mutations = {
        "unknown-id": {"case_id": "absent-case"},
        "duplicate-id": {},
        "allowed": {"allowed_chunk_ids": ()},
        "retrieval": {"retrieved_chunk_ids": (), "cited_chunk_ids": (), "response_evidence": ()},
        "rank": {"first_relevant_rank": 2},
        "citation": {"cited_chunk_ids": ()},
        "unresolved-label": {"citation_labels": ("known-label", "unresolved-label")},
    }
    case = case.model_copy(update=mutations[mutation])
    cases = (case, case) if mutation == "duplicate-id" else (case,)
    report = LiveEvaluationReport.model_validate(_report_payload()).model_copy(update={
        "cases": cases, "summary": summarize_live_cases(cases),
    })
    context = _context().model_copy(update={"expected_cases": (expected,)})

    reasons = verify_live_report(report, context, require_human=False)

    assert reasons

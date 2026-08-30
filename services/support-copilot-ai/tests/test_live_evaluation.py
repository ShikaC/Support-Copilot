from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.errors import FallbackReason
from evaluation.live_dataset import load_live_dataset
from evaluation.live_models import (
    LiveConfiguration,
    LiveEvaluationReport,
    VerificationContext,
)
from evaluation.live_markdown import render_live_markdown
from evaluation.live_pricing import apply_pricing
from evaluation.live_review import apply_review_worksheet, create_review_worksheet
from evaluation.live_runner import citations_valid, retrieval_succeeded
from evaluation.live_verifier import verify_live_report


DATASET = Path(__file__).parents[1] / "evaluation" / "data" / "live-v1.json"
SHA = "a" * 64
ARTIFACT = "b" * 64
GIT_SHA = "c" * 40


def _report_payload():
    return {
        "schema_version": 1,
        "report_kind": "live-evaluation",
        "run": {
            "run_id": "live-test-001",
            "timestamp": "2026-08-27T00:00:00Z",
            "mode": "live",
            "dataset_id": "support-copilot-live-synthetic",
            "dataset_version": "1.0.0",
            "dataset_checksum": SHA,
            "git_commit": GIT_SHA,
            "worktree_dirty": False,
            "prompt_version": "ticket-analysis-v1",
            "top_n": 10,
            "top_k": 3,
            "config_fingerprint": SHA,
        },
        "provenance": {
            "knowledge_release_id": "support-copilot-bundled-v1",
            "knowledge_release_version": 1,
            "semantic_corpus_checksum": SHA,
            "embedding_artifact": {
                "artifact_id": ARTIFACT,
                "manifest_sha256": SHA,
                "provider_identity": "compatible:example.invalid",
                "model": "embedding-model",
                "dimension": 3,
                "chunking_version": "knowledge-corpus-v2",
            },
            "chat_provider_identity": "compatible:example.invalid",
            "chat_model": "chat-model",
            "chat_protocol": "responses",
        },
        "cases": [{
            "case_id": "live-sso-001",
            "status": "SUCCEEDED",
            "mode": "live",
            "fallback_reason": None,
            "retrieval_success": True,
            "first_relevant_rank": 1,
            "retrieved_chunk_ids": ["kb-sso-login-001"],
            "allowed_chunk_ids": ["kb-sso-login-001"],
            "cited_chunk_ids": ["kb-sso-login-001"],
            "citation_valid": True,
            "response_text": "请根据登录指引检查 SSO 配置。",
            "response_evidence": [{"statement": "检查 SSO 配置", "evidence_indexes": [1]}],
            "latency_ms": 42,
            "usage": {"availability": "available", "input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
            "cost": None,
            "human_review": {"reviewer": None, "factual_support": "NOT_REVIEWED", "decision_note": None, "reviewed_at": None},
        }],
        "summary": {
            "label": "evaluation_results_for_this_dataset_run",
            "total_cases": 1,
            "succeeded_cases": 1,
            "retrieval_success_count": 1,
            "retrieval_success_rate": 1.0,
            "mean_reciprocal_rank": 1.0,
            "citation_valid_count": 1,
            "citation_valid_rate": 1.0,
            "no_evidence_safety_rate": 1.0,
            "fallback_count": 0,
            "average_latency_ms": 42.0,
            "p95_latency_ms": 42,
            "human_reviewed_count": 0,
            "publishable": False,
            "gate_reasons": ["human-review-incomplete"],
        },
    }


def _context() -> VerificationContext:
    return VerificationContext(
        dataset_id="support-copilot-live-synthetic",
        dataset_version="1.0.0",
        dataset_checksum=SHA,
        release_id="support-copilot-bundled-v1",
        release_version=1,
        corpus_checksum=SHA,
        artifact_id=ARTIFACT,
        artifact_manifest_sha256=SHA,
        git_commit=GIT_SHA,
        worktree_dirty=False,
        known_chunk_ids=frozenset({"kb-sso-login-001"}),
        configuration=LiveConfiguration(
            prompt_version="ticket-analysis-v1",
            top_n=10,
            top_k=3,
            config_fingerprint=SHA,
            chat_provider_identity="compatible:example.invalid",
            chat_model="chat-model",
            chat_protocol="responses",
            embedding_provider_identity="compatible:example.invalid",
            embedding_model="embedding-model",
            embedding_dimension=3,
            embedding_chunking_version="knowledge-corpus-v2",
        ),
    )


def _reasons(payload, *, require_human: bool = True) -> tuple[str, ...]:
    return verify_live_report(
        LiveEvaluationReport.model_validate(payload),
        _context(),
        require_human=require_human,
    )


def test_versioned_dataset_is_synthetic_and_has_human_slots() -> None:
    dataset = load_live_dataset(DATASET)
    assert dataset.dataset_id == "support-copilot-live-synthetic"
    assert dataset.version == "1.0.0"
    assert len(dataset.cases) >= 3
    assert all(case.classification == "SYNTHETIC" for case in dataset.cases)
    assert all(case.human_review.factual_support == "NOT_REVIEWED" for case in dataset.cases)


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        (lambda p: p["cases"][0]["cited_chunk_ids"].append("forbidden"), "citation-forbidden"),
        (lambda p: p["cases"][0]["retrieved_chunk_ids"].clear(), "citation-not-retrieved"),
        (lambda p: p["provenance"].update({"knowledge_release_id": "unknown"}), "knowledge-release-mismatch"),
        (lambda p: p["provenance"]["embedding_artifact"].update({"artifact_id": "c" * 64}), "embedding-artifact-mismatch"),
        (lambda p: p["run"].update({"git_commit": "d" * 40}), "git-commit-mismatch"),
        (lambda p: p["run"].update({"worktree_dirty": True}), "git-dirty-state-mismatch"),
        (lambda p: p["cases"][0].update({"response_text": "email user@example.com"}), "sensitive-content-detected"),
        (lambda p: p["cases"][0]["response_evidence"][0].update({"evidence_indexes": [2]}), "evidence-index-invalid"),
        (lambda p: p["cases"][0]["usage"].update({"total_tokens": 99}), "usage-total-invalid"),
        (lambda p: p["cases"][0].update({"cost": {"amount": -1, "currency": "USD", "pricing_source": "", "pricing_source_checksum": SHA}}), "cost-invalid"),
    ],
)
def test_verifier_rejects_adversarial_reports(mutation, reason: str) -> None:
    payload = _report_payload()
    mutation(payload)
    assert reason in _reasons(payload)


def test_machine_report_requires_explicit_human_review_for_publishable_gate() -> None:
    assert _reasons(_report_payload()) == ("human-review-incomplete",)
    assert _reasons(_report_payload(), require_human=False) == ()


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        (lambda p: p["provenance"].update({"chat_protocol": "chat_completions"}), "chat-protocol-mismatch"),
        (lambda p: p["provenance"].update({"chat_model": "other-chat-model"}), "chat-model-mismatch"),
        (lambda p: p["provenance"].update({"chat_provider_identity": "openai-default"}), "chat-provider-identity-mismatch"),
        (lambda p: p["run"].update({"config_fingerprint": "d" * 64}), "config-fingerprint-mismatch"),
        (lambda p: p["provenance"]["embedding_artifact"].update({"provider_identity": "openai-default"}), "embedding-provider-identity-mismatch"),
        (lambda p: p["provenance"]["embedding_artifact"].update({"model": "other-embedding-model"}), "embedding-model-mismatch"),
        (lambda p: p["provenance"]["embedding_artifact"].update({"dimension": 4}), "embedding-dimension-mismatch"),
        (lambda p: p["provenance"]["embedding_artifact"].update({"chunking_version": "knowledge-corpus-v3"}), "embedding-chunking-version-mismatch"),
        (lambda p: p["run"].update({"prompt_version": "ticket-analysis-v2"}), "prompt-version-mismatch"),
        (lambda p: p["run"].update({"top_n": 11}), "top-n-mismatch"),
        (lambda p: p["run"].update({"top_k": 2}), "top-k-mismatch"),
        (lambda p: p["summary"].update({"average_latency_ms": 99.0}), "summary-mismatch"),
    ],
)
def test_verifier_rejects_report_fields_that_do_not_match_current_context(
    mutation,
    reason: str,
) -> None:
    payload = _report_payload()
    mutation(payload)

    assert reason in _reasons(payload, require_human=False)


def test_live_provenance_requires_chat_protocol_and_renders_it() -> None:
    payload = _report_payload()
    report = LiveEvaluationReport.model_validate(payload)

    assert "`responses`" in render_live_markdown(report)

    del payload["provenance"]["chat_protocol"]
    with pytest.raises(ValidationError):
        LiveEvaluationReport.model_validate(payload)


def test_machine_gate_failure_does_not_skip_provenance_verification() -> None:
    payload = _report_payload()
    payload["cases"][0].update(
        {
            "status": "FALLBACK",
            "mode": "fallback",
            "fallback_reason": "invalid_model_response",
            "retrieval_success": False,
            "citation_valid": False,
        }
    )
    payload["summary"].update(
        {
            "succeeded_cases": 0,
            "retrieval_success_count": 0,
            "retrieval_success_rate": 0.0,
            "citation_valid_count": 0,
            "citation_valid_rate": 0.0,
            "fallback_count": 1,
            "gate_reasons": ["machine-gate-failed"],
        }
    )
    assert _reasons(payload, require_human=False) == ()

    payload["provenance"].update({"chat_model": "other-chat-model"})

    assert "chat-model-mismatch" in _reasons(payload, require_human=False)


def test_review_workflow_preserves_machine_result(tmp_path: Path) -> None:
    raw = LiveEvaluationReport.model_validate(_report_payload())
    worksheet = create_review_worksheet(raw)
    reviewed_sheet = worksheet.model_copy(update={
        "reviews": tuple(review.model_copy(update={
            "reviewer": "synthetic-test-reviewer",
            "factual_support": "SUPPORTED",
            "decision_note": "Synthetic fixture is supported by retrieved evidence.",
            "reviewed_at": datetime(2026, 8, 27, 1, tzinfo=UTC),
        }) for review in worksheet.reviews)
    })
    reviewed = apply_review_worksheet(raw, reviewed_sheet)

    raw_case = raw.cases[0].model_dump(exclude={"human_review"})
    reviewed_case = reviewed.cases[0].model_dump(exclude={"human_review"})
    assert reviewed_case == raw_case
    assert reviewed.summary.publishable is True
    assert verify_live_report(reviewed, _context(), require_human=True) == ()


def test_cost_requires_explicit_model_bound_pricing_source(tmp_path: Path) -> None:
    pricing = tmp_path / "pricing.json"
    pricing.write_text(
        '{"schema_version":1,"pricing_source":"synthetic-test-price-card",'
        '"currency":"USD","chat_model":"chat-model",'
        '"input_per_million_tokens":2.0,"output_per_million_tokens":4.0}',
        encoding="utf-8",
    )
    report = LiveEvaluationReport.model_validate(_report_payload())

    priced = apply_pricing(report.cases, pricing, "chat-model")

    assert priced[0].cost is not None
    assert priced[0].cost.amount == 0.00004
    assert priced[0].cost.pricing_source == "synthetic-test-price-card"


def test_no_evidence_success_requires_explicit_insufficient_evidence_fallback() -> None:
    assert retrieval_succeeded(False, (), (), FallbackReason.INSUFFICIENT_EVIDENCE)
    assert citations_valid(
        False,
        (),
        (),
        (),
        FallbackReason.INSUFFICIENT_EVIDENCE,
        all_citations_resolved=True,
    )
    assert not retrieval_succeeded(False, (), (), FallbackReason.INVALID_MODEL_RESPONSE)
    assert not citations_valid(
        False,
        (),
        (),
        (),
        FallbackReason.INVALID_MODEL_RESPONSE,
        all_citations_resolved=True,
    )
    assert not citations_valid(
        False,
        (),
        (),
        (),
        FallbackReason.INSUFFICIENT_EVIDENCE,
        all_citations_resolved=False,
    )


def test_live_citations_require_relevant_retrieval_and_citation() -> None:
    assert not citations_valid(
        True,
        ("unrelated-chunk",),
        ("unrelated-chunk",),
        ("unrelated-chunk",),
        None,
        expected_chunks=("expected-chunk",),
        all_citations_resolved=True,
    )


def test_live_citations_reject_unresolved_or_duplicate_labels() -> None:
    assert not citations_valid(
        True,
        ("expected-chunk",),
        ("expected-chunk",),
        ("expected-chunk",),
        None,
        expected_chunks=("expected-chunk",),
        all_citations_resolved=False,
    )
    assert not citations_valid(
        True,
        ("expected-chunk", "expected-chunk"),
        ("expected-chunk",),
        ("expected-chunk",),
        None,
        expected_chunks=("expected-chunk",),
        all_citations_resolved=True,
    )

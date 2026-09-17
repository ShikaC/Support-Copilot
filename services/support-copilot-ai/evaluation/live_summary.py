from math import ceil
from typing import Literal

from evaluation.live_models import LiveCaseResult, LiveSummary


def summarize_live_cases(
    cases: tuple[LiveCaseResult, ...],
    *, p95_method: Literal["legacy-rounded-index", "nearest-rank"] = "nearest-rank",
) -> LiveSummary:
    total = len(cases)
    retrieval = sum(case.retrieval_success for case in cases)
    reciprocal_ranks = tuple(
        0.0 if case.first_relevant_rank is None else 1 / case.first_relevant_rank
        for case in cases
    )
    citations = sum(case.citation_valid for case in cases)
    no_evidence_cases = tuple(case for case in cases if not case.allowed_chunk_ids)
    no_evidence_safe = sum(no_evidence_is_safe(case) for case in no_evidence_cases)
    fallback = sum(case.mode == "fallback" for case in cases)
    latencies = sorted(case.latency_ms for case in cases)
    machine_pass = all(
        case.retrieval_success
        and case.citation_valid
        and case.classification_correct is not False
        and case.escalation_correct is not False
        and case.language_correct is not False
        and not case.policy_violations
        and (
            (bool(case.allowed_chunk_ids) and case.status == "SUCCEEDED" and case.mode == "live")
            or (not case.allowed_chunk_ids and no_evidence_is_safe(case))
        )
        for case in cases
    )
    reviewed = sum(review_is_complete(case) for case in cases)
    supported = all(case.human_review.factual_support == "SUPPORTED" for case in cases)
    reasons: list[str] = []
    if not machine_pass:
        reasons.append("machine-gate-failed")
    elif reviewed != total:
        reasons.append("human-review-incomplete")
    elif not supported:
        reasons.append("human-review-not-supported")
    return LiveSummary(
        label="evaluation_results_for_this_dataset_run",
        total_cases=total,
        succeeded_cases=sum(case.status == "SUCCEEDED" for case in cases),
        retrieval_success_count=retrieval,
        retrieval_success_rate=retrieval / total,
        mean_reciprocal_rank=sum(reciprocal_ranks) / total,
        citation_valid_count=citations,
        citation_valid_rate=citations / total,
        no_evidence_safety_rate=(
            no_evidence_safe / len(no_evidence_cases) if no_evidence_cases else 1.0
        ),
        fallback_count=fallback,
        average_latency_ms=sum(latencies) / total,
        p95_latency_ms=latencies[ceil(total * 0.95) - 1 if p95_method == "nearest-rank" else min(total - 1, round((total - 1) * 0.95))],
        p95_method=p95_method,
        human_reviewed_count=reviewed,
        publishable=machine_pass and reviewed == total and supported,
        gate_reasons=tuple(reasons),
    )


def no_evidence_is_safe(case: LiveCaseResult) -> bool:
    return (
        case.status == "FALLBACK"
        and case.mode == "fallback"
        and case.fallback_reason == "insufficient_evidence"
        and not case.retrieved_chunk_ids
        and not case.cited_chunk_ids
        and (case.actual_decision is None or case.actual_decision.escalation_required)
    )


def review_is_complete(case: LiveCaseResult) -> bool:
    review = case.human_review
    return bool(
        review.factual_support != "NOT_REVIEWED"
        and review.reviewer and review.reviewer.strip()
        and review.decision_note and review.decision_note.strip()
        and review.reviewed_at is not None
    )

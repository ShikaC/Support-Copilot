from evaluation.live_models import LiveCaseResult, LiveSummary


def summarize_live_cases(cases: tuple[LiveCaseResult, ...]) -> LiveSummary:
    total = len(cases)
    retrieval = sum(case.retrieval_success for case in cases)
    reciprocal_ranks = tuple(
        0.0 if case.first_relevant_rank is None else 1 / case.first_relevant_rank
        for case in cases
    )
    citations = sum(case.citation_valid for case in cases)
    no_evidence_cases = tuple(case for case in cases if not case.allowed_chunk_ids)
    no_evidence_safe = sum(
        case.mode == "fallback" and not case.cited_chunk_ids
        for case in no_evidence_cases
    )
    fallback = sum(case.mode == "fallback" for case in cases)
    latencies = sorted(case.latency_ms for case in cases)
    machine_pass = all(
        case.retrieval_success
        and case.citation_valid
        and (
            (case.status == "SUCCEEDED" and case.mode == "live")
            or (not case.allowed_chunk_ids and case.mode == "fallback")
        )
        for case in cases
    )
    reviewed = sum(_review_complete(case) for case in cases)
    reasons = () if machine_pass and reviewed == total else (
        ("machine-gate-failed",)
        if not machine_pass
        else ("human-review-incomplete",)
    )
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
        p95_latency_ms=latencies[min(total - 1, round((total - 1) * 0.95))],
        human_reviewed_count=reviewed,
        publishable=machine_pass and reviewed == total,
        gate_reasons=reasons,
    )


def _review_complete(case: LiveCaseResult) -> bool:
    review = case.human_review
    return bool(
        review.factual_support != "NOT_REVIEWED"
        and review.reviewer
        and review.decision_note
        and review.reviewed_at is not None
    )

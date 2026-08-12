from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from app.models import AnalyzeResponse
from evaluation.case_checks import (
    case_failures,
    no_evidence_safety_failure,
    reply_constraint_failures,
)
from evaluation.environment import capture_environment
from evaluation.metrics import (
    calculate_accuracy,
    calculate_escalation_precision,
    calculate_escalation_recall,
    calculate_retrieval_metrics,
    first_relevant_rank,
    is_high_risk_priority_downgrade,
)
from evaluation.models import (
    AnalysisConfigurationMetrics,
    CaseEvaluationResult,
    EvaluationCase,
    EvaluationMetrics,
    EvaluationReport,
    EvaluationThresholds,
)

SLOW_CASE_THRESHOLD_MS: Final = 2_000


def build_evaluation_report(
    cases: Sequence[EvaluationCase],
    responses: Sequence[AnalyzeResponse],
    dataset_path: Path,
    knowledge_path: Path,
    top_n: int,
    top_k: int,
    mode: str,
) -> EvaluationReport:
    if len(cases) != len(responses):
        raise ValueError("cases and responses must have equal length")

    case_results = tuple(
        _case_result(case, response)
        for case, response in zip(cases, responses, strict=True)
    )
    thresholds = EvaluationThresholds()
    metrics = _metrics(cases, responses, case_results, top_k)
    return EvaluationReport(
        generated_at=datetime.now(UTC),
        dataset_name=dataset_path.name,
        mode=mode,
        model_names=tuple(sorted({response.model_name for response in responses})),
        prompt_versions=tuple(
            sorted({response.prompt_version for response in responses})
        ),
        top_n=top_n,
        top_k=top_k,
        environment=capture_environment(dataset_path, knowledge_path),
        thresholds=thresholds,
        metrics=metrics,
        configuration_performance=_configuration_performance(case_results),
        failed_case_ids=tuple(
            result.id for result in case_results if result.failures
        ),
        cases=case_results,
        passed=_passes_thresholds(metrics, thresholds),
    )


def _case_result(
    case: EvaluationCase,
    response: AnalyzeResponse,
) -> CaseEvaluationResult:
    retrieved_ids = tuple(hit.chunk_id for hit in response.retrieval.hits)
    relevant_rank = first_relevant_rank(retrieved_ids, case.expected_evidence_ids)
    return CaseEvaluationResult(
        id=case.id,
        subject=case.subject,
        description=case.description,
        expected_category=case.expected_category,
        actual_category=response.classification.category,
        expected_priority=case.expected_priority,
        actual_priority=response.classification.priority,
        expected_escalation=case.expected_escalation,
        actual_escalation=response.decision.escalation_required,
        evidence_required=case.evidence_required,
        expected_evidence_ids=tuple(sorted(case.expected_evidence_ids)),
        retrieved_evidence_ids=retrieved_ids,
        first_relevant_rank=relevant_rank,
        citations=tuple(response.suggested_reply.citations),
        status=response.status,
        mode=response.mode,
        model_name=response.model_name,
        prompt_version=response.prompt_version,
        reply_content=response.suggested_reply.content,
        warnings=tuple(response.suggested_reply.warnings),
        duration_ms=response.usage.duration_ms,
        failures=case_failures(case, response),
        constraint_failures=reply_constraint_failures(case, response),
    )


def _metrics(
    cases: Sequence[EvaluationCase],
    responses: Sequence[AnalyzeResponse],
    results: Sequence[CaseEvaluationResult],
    top_k: int,
) -> EvaluationMetrics:
    classification = tuple(
        case.expected_category == response.classification.category
        for case, response in zip(cases, responses, strict=True)
    )
    priorities = tuple(
        case.expected_priority == response.classification.priority
        for case, response in zip(cases, responses, strict=True)
    )
    expected_escalation = tuple(case.expected_escalation for case in cases)
    actual_escalation = tuple(
        response.decision.escalation_required for response in responses
    )
    retrieval_cases = tuple(
        (result.retrieved_evidence_ids, frozenset(result.expected_evidence_ids))
        for result in results
        if result.evidence_required
    )
    retrieval = calculate_retrieval_metrics(
        tuple(ranking for ranking, _ in retrieval_cases),
        tuple(expected for _, expected in retrieval_cases),
        top_k,
    )
    evidence_results = tuple(result for result in results if result.evidence_required)
    no_evidence_results = tuple(result for result in results if not result.evidence_required)
    durations = sorted(result.duration_ms for result in results)
    slow_case_count = sum(
        duration > SLOW_CASE_THRESHOLD_MS for duration in durations
    )
    return EvaluationMetrics(
        total_cases=len(results),
        classification_accuracy=calculate_accuracy(classification),
        priority_accuracy=calculate_accuracy(priorities),
        escalation_recall=calculate_escalation_recall(
            expected_escalation,
            actual_escalation,
        ),
        escalation_precision=calculate_escalation_precision(
            expected_escalation,
            actual_escalation,
        ),
        hit_rate_at_k=retrieval.hit_rate_at_k,
        mrr=retrieval.mrr,
        citation_coverage=_rate(
            tuple(bool(result.citations) for result in evidence_results),
        ),
        no_evidence_safety_rate=_rate(
            tuple(
                not no_evidence_safety_failure(case, response)
                for case, response in zip(cases, responses, strict=True)
                if not case.evidence_required
            ),
        ),
        reply_constraint_pass_rate=_rate(
            tuple(not result.constraint_failures for result in results),
        ),
        average_duration_ms=sum(durations) / len(durations),
        p50_duration_ms=_percentile(durations, 0.50),
        p95_duration_ms=_percentile(durations, 0.95),
        max_duration_ms=max(durations),
        slow_case_threshold_ms=SLOW_CASE_THRESHOLD_MS,
        slow_case_count=slow_case_count,
        slow_case_rate=slow_case_count / len(durations),
    )


def _configuration_performance(
    results: Sequence[CaseEvaluationResult],
) -> tuple[AnalysisConfigurationMetrics, ...]:
    performance: list[AnalysisConfigurationMetrics] = []
    configurations = sorted(
        {(result.model_name, result.prompt_version) for result in results}
    )
    for model_name, prompt_version in configurations:
        configuration_results = tuple(
            result
            for result in results
            if result.model_name == model_name
            and result.prompt_version == prompt_version
        )
        slow_case_count = sum(
            result.duration_ms > SLOW_CASE_THRESHOLD_MS
            for result in configuration_results
        )
        high_risk_priority_downgrade_count = sum(
            is_high_risk_priority_downgrade(
                result.expected_priority,
                result.actual_priority,
            )
            for result in configuration_results
        )
        performance.append(
            AnalysisConfigurationMetrics(
                model_name=model_name,
                prompt_version=prompt_version,
                total_cases=len(configuration_results),
                classification_accuracy=calculate_accuracy(
                    tuple(
                        result.expected_category == result.actual_category
                        for result in configuration_results
                    )
                ),
                priority_accuracy=calculate_accuracy(
                    tuple(
                        result.expected_priority == result.actual_priority
                        for result in configuration_results
                    )
                ),
                high_risk_priority_downgrade_count=(
                    high_risk_priority_downgrade_count
                ),
                high_risk_priority_downgrade_rate=(
                    high_risk_priority_downgrade_count
                    / len(configuration_results)
                ),
                slow_case_count=slow_case_count,
                slow_case_rate=slow_case_count / len(configuration_results),
            )
        )
    return tuple(performance)


def _passes_thresholds(
    metrics: EvaluationMetrics,
    thresholds: EvaluationThresholds,
) -> bool:
    return all(
        (
            metrics.classification_accuracy >= thresholds.classification_accuracy,
            metrics.priority_accuracy >= thresholds.priority_accuracy,
            metrics.escalation_recall >= thresholds.escalation_recall,
            metrics.escalation_precision >= thresholds.escalation_precision,
            metrics.hit_rate_at_k >= thresholds.hit_rate_at_k,
            metrics.mrr >= thresholds.mrr,
            metrics.citation_coverage >= thresholds.citation_coverage,
            metrics.no_evidence_safety_rate >= thresholds.no_evidence_safety_rate,
            metrics.reply_constraint_pass_rate >= thresholds.reply_constraint_pass_rate,
        )
    )


def _rate(results: Sequence[bool]) -> float:
    return sum(results) / len(results) if results else 1.0


def _percentile(values: Sequence[int], percentile: float) -> int:
    index = min(len(values) - 1, round((len(values) - 1) * percentile))
    return values[index]

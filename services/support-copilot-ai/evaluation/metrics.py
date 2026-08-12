from collections.abc import Sequence, Set
from typing import assert_never

from app.models import Priority
from evaluation.models import (
    AnalysisConfigurationMetrics,
    CaseEvaluationResult,
    EvaluationThresholds,
    RetrievalMetrics,
)


class EvaluationInputError(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def calculate_accuracy(correct_results: Sequence[bool]) -> float:
    if not correct_results:
        raise EvaluationInputError("at least one result is required")
    return sum(correct_results) / len(correct_results)


def is_high_risk_priority_downgrade(
    expected: Priority,
    actual: Priority,
) -> bool:
    return _priority_level(expected) - _priority_level(actual) >= 2


def calculate_configuration_performance(
    results: Sequence[CaseEvaluationResult],
    slow_case_threshold_ms: int,
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
            result.duration_ms > slow_case_threshold_ms
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


def _priority_level(priority: Priority) -> int:
    match priority:
        case Priority.LOW:
            return 1
        case Priority.MEDIUM:
            return 2
        case Priority.HIGH:
            return 3
        case Priority.URGENT:
            return 4
        case unreachable:
            assert_never(unreachable)


def calculate_escalation_recall(
    expected: Sequence[bool],
    actual: Sequence[bool],
) -> float:
    required_count = sum(expected)
    correctly_escalated = sum(
        expected_value and actual_value
        for expected_value, actual_value in zip(expected, actual, strict=True)
    )
    return correctly_escalated / required_count


def calculate_escalation_precision(
    expected: Sequence[bool],
    actual: Sequence[bool],
) -> float:
    escalated_count = sum(actual)
    correctly_escalated = sum(
        expected_value and actual_value
        for expected_value, actual_value in zip(expected, actual, strict=True)
    )
    return correctly_escalated / escalated_count


def escalation_recall_failure(
    actual_recall: float,
    thresholds: EvaluationThresholds,
) -> str | None:
    if actual_recall >= thresholds.escalation_recall:
        return None
    return (
        "escalation_recall: expected at least "
        f"{thresholds.escalation_recall:.3f}, got {actual_recall:.3f}"
    )


def escalation_precision_failure(
    actual_precision: float,
    thresholds: EvaluationThresholds,
) -> str | None:
    if actual_precision >= thresholds.escalation_precision:
        return None
    return (
        "escalation_precision: expected at least "
        f"{thresholds.escalation_precision:.3f}, got {actual_precision:.3f}"
    )


def first_relevant_rank(
    retrieved_ids: Sequence[str],
    expected_ids: Set[str],
) -> int | None:
    for rank, chunk_id in enumerate(retrieved_ids, start=1):
        if chunk_id in expected_ids:
            return rank
    return None


def calculate_retrieval_metrics(
    rankings: Sequence[Sequence[str]],
    expected_ids: Sequence[Set[str]],
    top_k: int,
) -> RetrievalMetrics:
    if not rankings:
        raise EvaluationInputError("at least one ranking is required")
    if len(rankings) != len(expected_ids):
        raise EvaluationInputError("rankings and expected_ids must have equal length")
    if top_k < 1:
        raise EvaluationInputError("top_k must be at least 1")

    hits = 0
    reciprocal_rank_total = 0.0
    for ranking, acceptable_ids in zip(rankings, expected_ids, strict=True):
        rank = first_relevant_rank(ranking[:top_k], acceptable_ids)
        if rank is not None:
            hits += 1
            reciprocal_rank_total += 1 / rank

    case_count = len(rankings)
    return RetrievalMetrics(
        evaluated_cases=case_count,
        hit_rate_at_k=hits / case_count,
        mrr=reciprocal_rank_total / case_count,
    )

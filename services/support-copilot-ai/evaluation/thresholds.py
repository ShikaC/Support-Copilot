from evaluation.models import (
    EvaluationMetrics,
    EvaluationThresholds,
    ThresholdFailure,
    ThresholdMetric,
)


def collect_threshold_failures(
    metrics: EvaluationMetrics,
    thresholds: EvaluationThresholds,
) -> tuple[ThresholdFailure, ...]:
    candidates = (
        _minimum_failure(
            "classification_accuracy",
            metrics.classification_accuracy,
            thresholds.classification_accuracy,
        ),
        _minimum_failure(
            "priority_accuracy",
            metrics.priority_accuracy,
            thresholds.priority_accuracy,
        ),
        _maximum_failure(
            "high_risk_priority_downgrade_count",
            metrics.high_risk_priority_downgrade_count,
            thresholds.max_high_risk_priority_downgrade_count,
        ),
        _minimum_failure(
            "escalation_recall",
            metrics.escalation_recall,
            thresholds.escalation_recall,
        ),
        _minimum_failure(
            "escalation_precision",
            metrics.escalation_precision,
            thresholds.escalation_precision,
        ),
        _minimum_failure(
            "hit_rate_at_k",
            metrics.hit_rate_at_k,
            thresholds.hit_rate_at_k,
        ),
        _minimum_failure("mrr", metrics.mrr, thresholds.mrr),
        _minimum_failure(
            "citation_coverage",
            metrics.citation_coverage,
            thresholds.citation_coverage,
        ),
        _minimum_failure(
            "no_evidence_safety_rate",
            metrics.no_evidence_safety_rate,
            thresholds.no_evidence_safety_rate,
        ),
        _minimum_failure(
            "reply_constraint_pass_rate",
            metrics.reply_constraint_pass_rate,
            thresholds.reply_constraint_pass_rate,
        ),
    )
    return tuple(failure for failure in candidates if failure is not None)


def _minimum_failure(
    metric: ThresholdMetric,
    actual: float,
    threshold: float,
) -> ThresholdFailure | None:
    if actual >= threshold:
        return None
    return ThresholdFailure(
        metric=metric,
        actual=actual,
        comparison="at_least",
        threshold=threshold,
    )


def _maximum_failure(
    metric: ThresholdMetric,
    actual: float,
    threshold: float,
) -> ThresholdFailure | None:
    if actual <= threshold:
        return None
    return ThresholdFailure(
        metric=metric,
        actual=actual,
        comparison="at_most",
        threshold=threshold,
    )

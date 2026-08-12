from evaluation.models import EvaluationMetrics, EvaluationThresholds
from evaluation.thresholds import collect_threshold_failures


def test_collects_every_failed_evaluation_threshold() -> None:
    # Given: 所有最低要求都未达到，并且高风险降级数量超过最大允许值。
    metrics = EvaluationMetrics(
        total_cases=1,
        classification_accuracy=0,
        priority_accuracy=0,
        high_risk_priority_downgrade_count=1,
        high_risk_priority_downgrade_rate=1,
        escalation_recall=0,
        escalation_precision=0,
        hit_rate_at_k=0,
        mrr=0,
        citation_coverage=0,
        no_evidence_safety_rate=0,
        reply_constraint_pass_rate=0,
        average_duration_ms=0,
        p50_duration_ms=0,
        p95_duration_ms=0,
        max_duration_ms=0,
        slow_case_threshold_ms=2_000,
        slow_case_count=0,
        slow_case_rate=0,
    )

    # When: 收集所有未达到门槛的指标。
    failures = collect_threshold_failures(metrics, EvaluationThresholds())

    # Then: 十项发布门槛都被完整报告。
    assert tuple(failure.metric for failure in failures) == (
        "classification_accuracy",
        "priority_accuracy",
        "high_risk_priority_downgrade_count",
        "escalation_recall",
        "escalation_precision",
        "hit_rate_at_k",
        "mrr",
        "citation_coverage",
        "no_evidence_safety_rate",
        "reply_constraint_pass_rate",
    )

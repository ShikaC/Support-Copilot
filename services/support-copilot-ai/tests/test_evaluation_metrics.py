import pytest
from pydantic import ValidationError

from app.models import Priority
from evaluation.metrics import (
    calculate_accuracy,
    calculate_escalation_precision,
    calculate_escalation_recall,
    calculate_retrieval_metrics,
    escalation_precision_failure,
    escalation_recall_failure,
    EvaluationInputError,
    first_relevant_rank,
    is_high_risk_priority_downgrade,
)
from evaluation.models import EvaluationThresholds


def test_first_relevant_rank_uses_any_acceptable_evidence() -> None:
    rank = first_relevant_rank(
        retrieved_ids=(
            "chunk-refund-02",
            "chunk-payment-04",
            "chunk-subscription-02",
        ),
        expected_ids=frozenset({"chunk-billing-07", "chunk-payment-04"}),
    )

    assert rank == 2


def test_retrieval_metrics_average_hits_and_reciprocal_ranks() -> None:
    metrics = calculate_retrieval_metrics(
        rankings=(
            ("expected-a", "other"),
            ("other", "expected-b"),
            ("other",),
        ),
        expected_ids=(
            frozenset({"expected-a"}),
            frozenset({"expected-b"}),
            frozenset({"expected-c"}),
        ),
        top_k=3,
    )

    assert metrics.hit_rate_at_k == pytest.approx(2 / 3)
    assert metrics.mrr == pytest.approx(0.5)


def test_accuracy_divides_correct_results_by_all_results() -> None:
    results = (True,) * 8 + (False,) * 2

    assert calculate_accuracy(results) == pytest.approx(0.8)


def test_accuracy_rejects_an_empty_result_set() -> None:
    with pytest.raises(EvaluationInputError) as error:
        calculate_accuracy(())

    assert error.value.reason == "at least one result is required"


@pytest.mark.parametrize(
    ("expected", "actual", "is_high_risk"),
    (
        (Priority.URGENT, Priority.MEDIUM, True),
        (Priority.HIGH, Priority.LOW, True),
        (Priority.URGENT, Priority.HIGH, False),
        (Priority.MEDIUM, Priority.HIGH, False),
    ),
)
def test_high_risk_priority_downgrade_requires_at_least_two_levels(
    expected: Priority,
    actual: Priority,
    is_high_risk: bool,
) -> None:
    assert is_high_risk_priority_downgrade(expected, actual) is is_high_risk


def test_escalation_recall_counts_required_escalations_only() -> None:
    expected = (True, True, True, True, True, False, False)
    actual = (True, True, True, True, False, True, False)

    assert calculate_escalation_recall(expected, actual) == pytest.approx(0.8)


def test_escalation_precision_penalizes_unnecessary_escalations() -> None:
    expected = (True, True, True, True, False, False, False, False)
    actual = (True, True, True, True, True, True, True, True)

    assert calculate_escalation_precision(expected, actual) == pytest.approx(0.5)


def test_escalation_recall_reports_failure_below_the_threshold() -> None:
    failure = escalation_recall_failure(0.8, EvaluationThresholds())

    assert failure == "escalation_recall: expected at least 1.000, got 0.800"


def test_escalation_recall_passes_at_the_exact_threshold() -> None:
    assert escalation_recall_failure(1.0, EvaluationThresholds()) is None


def test_escalation_precision_reports_failure_below_the_threshold() -> None:
    failure = escalation_precision_failure(0.8, EvaluationThresholds())

    assert failure == "escalation_precision: expected at least 0.900, got 0.800"


def test_thresholds_reject_a_rate_above_one() -> None:
    with pytest.raises(ValidationError):
        EvaluationThresholds(escalation_recall=1.2)

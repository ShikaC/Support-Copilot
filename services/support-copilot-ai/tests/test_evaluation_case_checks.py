from pathlib import Path
from typing import Final

import pytest

from app.config import Settings
from app.knowledge import KnowledgeRetriever
from app.models import AnalyzeOptions
from app.workflow import AnalysisWorkflow
from evaluation.case_checks import (
    case_failures,
    classification_failure,
    classification_is_correct,
    collect_failures,
    escalation_failure,
    priority_failure,
)
from evaluation.dataset import load_evaluation_cases
from evaluation.models import CaseFailure

DATASET_PATH: Final = (
    Path(__file__).parents[1] / "evaluation" / "data" / "tickets.jsonl"
)
OPTIONS: Final = AnalyzeOptions(topN=10, topK=3)


def test_collect_failures_keeps_only_failure_objects() -> None:
    classification = CaseFailure(
        metric="classification",
        expected="BILLING",
        actual="SUBSCRIPTION",
    )
    failures = collect_failures(
        None,
        classification,
        None,
    )

    assert failures == (classification,)


@pytest.mark.asyncio
async def test_compares_expected_category_with_actual_workflow_result() -> None:
    case = load_evaluation_cases(DATASET_PATH)[0]
    settings = Settings(ai_mode="mock")
    workflow = AnalysisWorkflow(settings, KnowledgeRetriever(settings))
    response = await workflow.run(case.to_request(OPTIONS))

    assert case.expected_category == "BILLING"
    assert response.classification.category == "BILLING"
    assert classification_is_correct(case, response) is True

    mismatched_case = case.model_copy(update={"expected_category": "SUBSCRIPTION"})
    assert classification_failure(mismatched_case, response) == CaseFailure(
        metric="classification",
        expected="SUBSCRIPTION",
        actual="BILLING",
    )


@pytest.mark.asyncio
async def test_reports_expected_and_actual_priority_when_they_differ() -> None:
    case = load_evaluation_cases(DATASET_PATH)[0]
    settings = Settings(ai_mode="mock")
    workflow = AnalysisWorkflow(settings, KnowledgeRetriever(settings))
    response = await workflow.run(case.to_request(OPTIONS))
    mismatched_case = case.model_copy(update={"expected_priority": "LOW"})

    assert priority_failure(mismatched_case, response) == CaseFailure(
        metric="priority",
        expected="LOW",
        actual="HIGH",
    )


@pytest.mark.asyncio
async def test_priority_failure_exposes_machine_readable_values() -> None:
    # Given: 人工标准优先级与系统实际优先级不同。
    case = load_evaluation_cases(DATASET_PATH)[0]
    settings = Settings(ai_mode="mock")
    workflow = AnalysisWorkflow(settings, KnowledgeRetriever(settings))
    response = await workflow.run(case.to_request(OPTIONS))
    mismatched_case = case.model_copy(update={"expected_priority": "LOW"})

    # When: 生成这条优先级失败详情。
    failure = priority_failure(mismatched_case, response)

    # Then: 各字段可以被程序单独读取，不需要拆解英文句子。
    assert failure is not None
    assert failure.metric == "priority"
    assert failure.expected == "LOW"
    assert failure.actual == "HIGH"
    assert failure.model_dump(mode="json") == {
        "metric": "priority",
        "expected": "LOW",
        "actual": "HIGH",
    }


@pytest.mark.asyncio
async def test_reports_expected_and_actual_escalation_when_they_differ() -> None:
    case = load_evaluation_cases(DATASET_PATH)[0]
    settings = Settings(ai_mode="mock")
    workflow = AnalysisWorkflow(settings, KnowledgeRetriever(settings))
    response = await workflow.run(case.to_request(OPTIONS))
    mismatched_case = case.model_copy(update={"expected_escalation": False})

    assert escalation_failure(mismatched_case, response) == CaseFailure(
        metric="escalation",
        expected=False,
        actual=True,
    )


@pytest.mark.asyncio
async def test_case_failures_marks_the_case_failed_for_one_wrong_result() -> None:
    case = load_evaluation_cases(DATASET_PATH)[0]
    settings = Settings(ai_mode="mock")
    workflow = AnalysisWorkflow(settings, KnowledgeRetriever(settings))
    response = await workflow.run(case.to_request(OPTIONS))
    mismatched_case = case.model_copy(update={"expected_priority": "LOW"})

    assert case_failures(mismatched_case, response) == (
        CaseFailure(metric="priority", expected="LOW", actual="HIGH"),
    )


@pytest.mark.asyncio
async def test_case_failures_reports_missing_citations_after_retrieval() -> None:
    case = load_evaluation_cases(DATASET_PATH)[0]
    settings = Settings(ai_mode="mock")
    workflow = AnalysisWorkflow(settings, KnowledgeRetriever(settings))
    response = await workflow.run(case.to_request(OPTIONS))
    response_without_citations = response.model_copy(
        update={
            "suggested_reply": response.suggested_reply.model_copy(
                update={"citations": []}
            )
        }
    )

    assert case_failures(case, response_without_citations) == (
        CaseFailure(
            metric="citation",
            expected="retrieved_evidence_cited",
            actual="missing_citation",
        ),
        CaseFailure(
            metric="reply_constraint",
            expected="must_cite_evidence",
            actual="violated",
        ),
    )


@pytest.mark.asyncio
async def test_case_failures_rejects_an_invented_citation_without_evidence() -> None:
    case = load_evaluation_cases(DATASET_PATH)[15]
    settings = Settings(ai_mode="mock")
    workflow = AnalysisWorkflow(settings, KnowledgeRetriever(settings))
    response = await workflow.run(case.to_request(OPTIONS))
    unsafe_response = response.model_copy(
        update={
            "suggested_reply": response.suggested_reply.model_copy(
                update={"citations": ["invented recovery policy"]}
            )
        }
    )

    assert case_failures(case, unsafe_response) == (
        CaseFailure(
            metric="no_evidence_safety",
            expected="safe_fallback",
            actual="unsafe_response",
        ),
    )

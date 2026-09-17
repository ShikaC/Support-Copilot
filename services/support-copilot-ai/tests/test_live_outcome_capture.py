import pytest

from app.config import Settings
from app.knowledge import KnowledgeRetriever
from app.models import BUNDLED_KNOWLEDGE_ACCESS, AnalyzeRequest, TicketInput
from app.workflow import AnalysisWorkflow
from evaluation.live_models import LiveEvaluationCase
from evaluation.live_runner import _case_result


@pytest.mark.anyio
async def test_case_capture_retains_actual_outcomes_and_detects_wrong_expectations() -> None:
    # Given a real local workflow result, relabeled solely as a synthetic live fixture.
    settings = Settings(ai_mode="mock", _env_file=None)
    request = AnalyzeRequest(
        traceId="test-outcome-capture",
        knowledgeAccess=BUNDLED_KNOWLEDGE_ACCESS,
        ticket=TicketInput(id="capture", subject="重复扣款", description="两笔相同账单扣款"),
    )
    response = await AnalysisWorkflow(settings, KnowledgeRetriever(settings)).run(request)
    response = response.model_copy(update={"mode": "live"})
    case = LiveEvaluationCase.model_validate({
        "id": "capture", "classification": "SYNTHETIC",
        "ticket": {"subject": "重复扣款", "description": "两笔相同账单扣款"},
        "expected_retrieval": {"evidence_required": True, "chunk_ids": ["chunk-billing-07"]},
        "allowed_chunk_ids": ["chunk-billing-07", "chunk-payment-04", "chunk-refund-02"],
        "expected_categories": ["ACCOUNT_ACCESS"], "expected_escalation": False,
    })
    # When the evaluation records that response against deliberately wrong expectations.
    result = _case_result(case.id, True, case.expected_retrieval.chunk_ids,
                          case.allowed_chunk_ids, response, 42, expectation=case)
    # Then wrong outcomes are measured, with the original trace and facts retained.
    assert result.classification_correct is False
    assert result.escalation_correct is False
    assert result.actual_classification == response.classification
    assert result.actual_decision == response.decision
    assert result.trace_id == request.trace_id

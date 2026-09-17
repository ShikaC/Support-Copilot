import pytest

from app.config import Settings
from app.errors import FallbackReason
from app.knowledge import KnowledgeRetriever
from app.models import BUNDLED_KNOWLEDGE_ACCESS, AnalyzeRequest, Decision, TicketInput
from app.workflow import AnalysisWorkflow
from evaluation.live_runner import _case_result
from evaluation.live_summary import summarize_live_cases


@pytest.mark.anyio
@pytest.mark.parametrize("reason,passes", [
    (FallbackReason.INSUFFICIENT_EVIDENCE, True),
    (FallbackReason.INVALID_MODEL_RESPONSE, False),
    (FallbackReason.STRUCTURED_GENERATION_RESPONSE_TIMEOUT, False),
])
async def test_unused_api_candidates_are_not_accepted_evidence(
    reason: FallbackReason, passes: bool,
) -> None:
    # Given actual retrieved candidates retained by the API but rejected for use.
    settings = Settings.model_validate({"ai_mode": "mock"})
    request = AnalyzeRequest(trace_id="unused-candidates", knowledge_access=BUNDLED_KNOWLEDGE_ACCESS,
        ticket=TicketInput(id="unused-candidates", subject="SSO 登录失败", description="无法登录"))
    response = await AnalysisWorkflow(settings, KnowledgeRetriever(settings)).run(request)
    assert response.retrieval.hits
    response = response.model_copy(update={
        "mode": "fallback", "status": "FALLBACK", "fallback_reason": reason,
        "retrieval": response.retrieval.model_copy(update={"hits": [
            hit.model_copy(update={"used_as_evidence": False}) for hit in response.retrieval.hits
        ]}),
        "suggested_reply": response.suggested_reply.model_copy(update={"citations": []}),
        "decision": Decision(escalation_required=True, reason="Evidence unavailable"),
    })
    # When the evaluator records an expected no-evidence case.
    result = _case_result("unused-candidates", False, (), (), response, 20)
    # Then unused candidates do not count as adopted/citable evidence, while named
    # dependency or model failures still fail the no-evidence business gate.
    assert result.retrieved_chunk_ids == ()
    assert result.retrieval_methods == ()
    assert result.response_evidence == ()
    assert result.cited_chunk_ids == ()
    assert result.retrieval_success is passes
    assert result.citation_valid is passes
    assert ("machine-gate-failed" not in summarize_live_cases((result,)).gate_reasons) is passes

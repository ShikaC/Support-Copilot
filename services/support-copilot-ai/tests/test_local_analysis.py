from app.local_analysis import LocalAnalysisPolicy
from app.models import BUNDLED_KNOWLEDGE_ACCESS, AnalyzeRequest, TicketInput


def test_privacy_request_takes_precedence_over_data_export_keyword() -> None:
    # Given: a privacy request mentions both employee export and deletion.
    request = AnalyzeRequest(
        traceId="trace_privacy_priority",
        knowledgeAccess=BUNDLED_KNOWLEDGE_ACCESS,
        ticket=TicketInput(
            id="ticket-privacy-priority",
            subject="导出离职员工数据后再删除",
            description="需要确认身份、授权材料和数据范围核验要求。",
        ),
    )

    # When: the deterministic policy classifies the ticket.
    draft = LocalAnalysisPolicy().draft(request, [])

    # Then: privacy handling wins over the generic export keyword.
    assert draft.category == "PRIVACY"

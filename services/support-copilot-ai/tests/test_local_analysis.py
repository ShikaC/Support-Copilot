from app.local_analysis import LocalAnalysisPolicy
from app.models import (
    BUNDLED_KNOWLEDGE_ACCESS,
    AnalyzeRequest,
    ModelDraft,
    RetrievalHit,
    TicketInput,
)


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


def test_reply_preserves_unique_retrieval_provenance() -> None:
    # Given: one selected knowledge chunk with a unique visible source label.
    hit = RetrievalHit(
        chunkId="account-sso-001",
        documentId="account-guide",
        documentTitle="Account access runbook",
        section="SSO login",
        content="Check the identity provider callback.",
        sourceUri="knowledge://account-guide",
        retrievalMethod="VECTOR",
        initialRank=1,
        initialScore=0.9,
        rerankPosition=1,
        rerankScore=0.9,
        usedAsEvidence=True,
    )
    draft = ModelDraft(
        evidence_sufficient=True,
        intent="sso_login_issue",
        category="ACCOUNT_ACCESS",
        priority="HIGH",
        sentiment="NEGATIVE",
        confidence=0.9,
        reason_summary="The retrieved runbook covers the login issue.",
        reply_content="Please verify the identity provider callback.",
        warnings=[],
        citation_indexes=[1],
    )

    # When: the policy renders the generated reply citation.
    reply = LocalAnalysisPolicy().reply(draft, [hit], evidence_missing=False)

    # Then: the established provenance remains visible and gains stable chunk identity.
    assert reply.citations == [
        "Account access runbook SSO login [chunkId:account-sso-001]"
    ]


def test_reply_citation_identifies_selected_chunk_when_visible_labels_collide() -> None:
    # Given: two retrieved chunks share the same document title and section.
    hits = [
        RetrievalHit(
            chunkId="account-sso-001",
            documentId="account-guide",
            documentTitle="Account access runbook",
            section="SSO login",
            content="Check the identity provider callback.",
            sourceUri="knowledge://account-guide",
            retrievalMethod="VECTOR",
            initialRank=1,
            initialScore=0.9,
            rerankPosition=1,
            rerankScore=0.9,
            usedAsEvidence=True,
        ),
        RetrievalHit(
            chunkId="account-sso-002",
            documentId="account-guide",
            documentTitle="Account access runbook",
            section="SSO login",
            content="Check the SSO tenant identifier.",
            sourceUri="knowledge://account-guide",
            retrievalMethod="VECTOR",
            initialRank=2,
            initialScore=0.8,
            rerankPosition=2,
            rerankScore=0.8,
            usedAsEvidence=True,
        ),
    ]
    draft = ModelDraft(
        evidence_sufficient=True,
        intent="sso_login_issue",
        category="ACCOUNT_ACCESS",
        priority="HIGH",
        sentiment="NEGATIVE",
        confidence=0.9,
        reason_summary="The selected chunk covers the tenant identifier.",
        reply_content="Please verify the SSO tenant identifier.",
        warnings=[],
        citation_indexes=[2],
    )

    # When: the policy renders only the second retrieved chunk as evidence.
    reply = LocalAnalysisPolicy().reply(draft, hits, evidence_missing=False)

    # Then: the citation identifies the selected chunk, not just its shared label.
    assert reply.citations == [
        "Account access runbook SSO login [chunkId:account-sso-002]"
    ]

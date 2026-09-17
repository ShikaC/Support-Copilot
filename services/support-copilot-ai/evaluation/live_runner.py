from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter_ns
from uuid import uuid4

from pydantic_core import PydanticCustomError

from app.errors import FallbackReason
from app.local_analysis import citation_label
from app.models import (
    AnalyzeOptions,
    AnalyzeRequest,
    AnalyzeResponse,
    KnowledgeAccess,
    Priority,
    RetrievalHit,
    SupportScope,
    TicketInput,
)
from evaluation.citation_validation import citation_ids_are_valid
from evaluation.live_models import (
    EmbeddingArtifactProvenance,
    HumanReview,
    LiveCaseResult,
    LiveEvaluationCase,
    LiveEvaluationReport,
    ProviderProvenance,
    ResponseEvidence,
    RunProvenance,
    TokenUsage,
)
from evaluation.live_provenance import VerifiedLiveInputs, read_git_state
from evaluation.live_reply_checks import language_correct, policy_violations
from evaluation.live_summary import summarize_live_cases


async def run_live_cases(
    inputs: VerifiedLiveInputs,
    analyze: Callable[[AnalyzeRequest], Awaitable[AnalyzeResponse]],
    live_hits: Callable[[str], tuple[RetrievalHit, ...] | None] | None = None,
) -> tuple[LiveCaseResult, ...]:
    results: list[LiveCaseResult] = []
    corpus = inputs.corpus
    access = KnowledgeAccess(
        release_id=corpus.release_id,
        release_version=corpus.release_version,
        corpus_checksum=corpus.corpus_checksum,
        allowed_scopes=tuple(SupportScope),
    )
    configuration = inputs.configuration
    options = AnalyzeOptions(
        top_n=configuration.top_n,
        top_k=configuration.top_k,
        prompt_version=configuration.prompt_version,
    )
    for case in inputs.dataset.cases:
        request = AnalyzeRequest(
            trace_id=f"live-eval-{case.id}",
            knowledge_access=access,
            ticket=TicketInput(
                id=f"ticket-{case.id}",
                subject=case.ticket.subject,
                description=case.ticket.description,
                customer_tier=case.ticket.customer_tier,
                language=case.ticket.language,
                current_priority=Priority.MEDIUM,
            ),
            options=options,
        )
        started = perf_counter_ns()
        response = await analyze(request)
        latency_ms = max(0, round((perf_counter_ns() - started) / 1_000_000))
        result = _case_result(case.id, case.expected_retrieval.evidence_required, case.expected_retrieval.chunk_ids, case.allowed_chunk_ids, response, latency_ms, expectation=case)
        if live_hits is not None:
            observed = live_hits(request.ticket.id)
            if observed is not None and response.fallback_reason == FallbackReason.INSUFFICIENT_EVIDENCE:
                observed = tuple(hit.model_copy(update={"used_as_evidence": False}) for hit in observed)
            result = result.model_copy(update={"live_retrieval": observed})
        results.append(result)
    return tuple(results)


def _case_result(
    case_id: str,
    evidence_required: bool,
    expected_chunks: tuple[str, ...],
    allowed_chunks: tuple[str, ...],
    response: AnalyzeResponse,
    latency_ms: int,
    *,
    expectation: LiveEvaluationCase | None = None,
) -> LiveCaseResult:
    if response.status == "RUNNING" or response.mode == "mock":
        raise PydanticCustomError("invalid_live_evaluation_response", "Live evaluation requires a terminal live or fallback response")
    evidence = tuple(hit for hit in response.retrieval.hits if hit.used_as_evidence)
    retrieved = tuple(hit.chunk_id for hit in evidence)
    labels = {citation_label(hit): hit.chunk_id for hit in evidence}
    citation_labels = tuple(response.suggested_reply.citations)
    cited = tuple(labels[label] for label in citation_labels if label in labels)
    indexes = tuple(index for index, chunk_id in enumerate(retrieved, start=1) if chunk_id in cited)
    usage_available = response.usage.input_tokens > 0 or response.usage.output_tokens > 0
    usage = TokenUsage(
        availability="available" if usage_available else "unavailable",
        input_tokens=response.usage.input_tokens if usage_available else None,
        output_tokens=response.usage.output_tokens if usage_available else None,
        total_tokens=(response.usage.input_tokens + response.usage.output_tokens) if usage_available else None,
    )
    return LiveCaseResult(
        case_id=case_id,
        status=response.status,
        mode=response.mode,
        fallback_reason=response.fallback_reason,
        retrieval_success=retrieval_succeeded(
            evidence_required,
            expected_chunks,
            retrieved,
            response.fallback_reason,
        ),
        first_relevant_rank=next((index for index, chunk in enumerate(retrieved, start=1) if chunk in expected_chunks), None),
        retrieved_chunk_ids=retrieved,
        allowed_chunk_ids=allowed_chunks,
        cited_chunk_ids=cited,
        citation_valid=citations_valid(
            evidence_required,
            cited,
            retrieved,
            allowed_chunks,
            response.fallback_reason,
            expected_chunks=expected_chunks,
            all_citations_resolved=len(cited) == len(citation_labels),
        ),
        response_text=response.suggested_reply.content,
        response_evidence=(ResponseEvidence(statement=response.suggested_reply.content, evidence_indexes=indexes),) if indexes else (),
        latency_ms=latency_ms,
        usage=usage,
        cost=None,
        human_review=HumanReview(),
        trace_id=response.trace_id,
        actual_classification=response.classification,
        actual_decision=response.decision,
        classification_correct=(
            response.classification.category in expectation.expected_categories
            if expectation is not None and expectation.expected_categories else None
        ),
        escalation_correct=(
            response.decision.escalation_required == expectation.expected_escalation
            if expectation is not None and expectation.expected_escalation is not None else None
        ),
        retrieval_methods=tuple(hit.retrieval_method for hit in evidence),
        citation_labels=citation_labels,
        language_correct=language_correct(response.suggested_reply.content, expectation.expected_language if expectation else None),
        policy_violations=policy_violations(response.suggested_reply.content, expectation.forbidden_reply_patterns if expectation else ()),
        reply_warnings=tuple(response.suggested_reply.warnings),
    )


def retrieval_succeeded(
    evidence_required: bool,
    expected_chunks: tuple[str, ...],
    retrieved: tuple[str, ...],
    fallback_reason: FallbackReason | None,
) -> bool:
    if evidence_required:
        return bool(set(expected_chunks) & set(retrieved))
    return not retrieved and fallback_reason == FallbackReason.INSUFFICIENT_EVIDENCE


def citations_valid(
    evidence_required: bool,
    cited: tuple[str, ...],
    retrieved: tuple[str, ...],
    allowed: tuple[str, ...],
    fallback_reason: FallbackReason | None,
    *,
    expected_chunks: tuple[str, ...] = (),
    all_citations_resolved: bool,
) -> bool:
    if evidence_required:
        return all_citations_resolved and citation_ids_are_valid(
            expected_evidence_ids=expected_chunks,
            cited_chunk_ids=cited,
            retrieved_chunk_ids=retrieved,
            allowed_chunk_ids=allowed,
        )
    return (
        all_citations_resolved
        and not cited
        and fallback_reason == FallbackReason.INSUFFICIENT_EVIDENCE
    )


def build_live_report(
    inputs: VerifiedLiveInputs,
    repo_root: Path,
    cases: tuple[LiveCaseResult, ...],
) -> LiveEvaluationReport:
    dataset = inputs.dataset
    corpus = inputs.corpus
    artifact = inputs.artifact
    configuration = inputs.configuration
    git = read_git_state(repo_root)
    return LiveEvaluationReport(
        schema_version=1,
        report_kind="live-evaluation",
        run=RunProvenance(
            run_id=f"live-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}",
            timestamp=datetime.now(UTC),
            mode="live",
            dataset_id=dataset.dataset_id,
            dataset_version=dataset.version,
            dataset_checksum=inputs.dataset_checksum,
            git_commit=git.commit,
            worktree_dirty=git.dirty,
            prompt_version=configuration.prompt_version,
            top_n=configuration.top_n,
            top_k=configuration.top_k,
            config_fingerprint=configuration.config_fingerprint,
            runtime_source_sha256=configuration.runtime_source_sha256,
        ),
        provenance=ProviderProvenance(
            knowledge_release_id=corpus.release_id,
            knowledge_release_version=corpus.release_version,
            semantic_corpus_checksum=corpus.corpus_checksum,
            embedding_artifact=EmbeddingArtifactProvenance(
                artifact_id=artifact.artifact_id,
                manifest_sha256=inputs.artifact_manifest_sha256,
                provider_identity=artifact.provider_identity,
                model=artifact.embedding_model,
                dimension=artifact.vector_dimension,
                chunking_version=artifact.chunking_version,
            ),
            chat_provider_identity=configuration.chat_provider_identity,
            chat_model=configuration.chat_model,
            chat_protocol=configuration.chat_protocol,
        ),
        cases=cases,
        summary=summarize_live_cases(cases),
    )

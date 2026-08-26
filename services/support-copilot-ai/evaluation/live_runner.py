from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from time import perf_counter_ns
from uuid import uuid4

from app.config import Settings
from app.embedding_artifact import EmbeddingArtifactStore
from app.embedding_artifact_identity import file_checksum, provider_identity
from app.errors import FallbackReason
from app.knowledge_source import KnowledgeCorpus, load_knowledge_corpus
from app.models import AnalyzeOptions, AnalyzeRequest, AnalyzeResponse, KnowledgeAccess, Priority, SupportScope, TicketInput
from evaluation.live_dataset import file_sha256
from evaluation.live_models import (
    EmbeddingArtifactProvenance,
    HumanReview,
    LiveCaseResult,
    LiveDataset,
    LiveEvaluationReport,
    LiveSummary,
    ProviderProvenance,
    ResponseEvidence,
    RunProvenance,
    TokenUsage,
)


async def run_live_cases(
    dataset: LiveDataset,
    analyze: Callable[[AnalyzeRequest], Awaitable[AnalyzeResponse]],
    corpus: KnowledgeCorpus,
) -> tuple[LiveCaseResult, ...]:
    results: list[LiveCaseResult] = []
    access = KnowledgeAccess(
        releaseId=corpus.release_id,
        releaseVersion=corpus.release_version,
        corpusChecksum=corpus.corpus_checksum,
        allowedScopes=tuple(SupportScope),
    )
    options = AnalyzeOptions(topN=10, topK=3)
    for case in dataset.cases:
        request = AnalyzeRequest(
            traceId=f"live-eval-{case.id}",
            knowledgeAccess=access,
            ticket=TicketInput(
                id=f"ticket-{case.id}",
                subject=case.ticket.subject,
                description=case.ticket.description,
                customerTier=case.ticket.customer_tier,
                currentPriority=Priority.MEDIUM,
            ),
            options=options,
        )
        started = perf_counter_ns()
        response = await analyze(request)
        latency_ms = max(0, round((perf_counter_ns() - started) / 1_000_000))
        results.append(_case_result(case.id, case.expected_retrieval.evidence_required, case.expected_retrieval.chunk_ids, case.allowed_chunk_ids, response, latency_ms))
    return tuple(results)


def _case_result(
    case_id: str,
    evidence_required: bool,
    expected_chunks: tuple[str, ...],
    allowed_chunks: tuple[str, ...],
    response: AnalyzeResponse,
    latency_ms: int,
) -> LiveCaseResult:
    retrieved = tuple(hit.chunk_id for hit in response.retrieval.hits)
    labels = {f"{hit.document_title} {hit.section}": hit.chunk_id for hit in response.retrieval.hits}
    cited = tuple(labels[label] for label in response.suggested_reply.citations if label in labels)
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
        ),
        response_text=response.suggested_reply.content,
        response_evidence=(ResponseEvidence(statement=response.suggested_reply.content, evidence_indexes=indexes),),
        latency_ms=latency_ms,
        usage=usage,
        cost=None,
        human_review=HumanReview(),
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
) -> bool:
    if evidence_required:
        return bool(cited) and set(cited) <= set(retrieved) and set(cited) <= set(allowed)
    return not cited and fallback_reason == FallbackReason.INSUFFICIENT_EVIDENCE


def build_live_report(
    dataset: LiveDataset,
    dataset_path: Path,
    settings: Settings,
    corpus: KnowledgeCorpus,
    cases: tuple[LiveCaseResult, ...],
) -> LiveEvaluationReport:
    store = EmbeddingArtifactStore(settings, corpus)
    artifact = store.load_active().manifest
    manifest_path = settings.embedding_artifact_root / artifact.artifact_id / "manifest.json"
    git_commit = _git(("rev-parse", "HEAD"))
    dirty = bool(_git(("status", "--porcelain")))
    config = {
        "chat_provider": provider_identity(settings.openai_base_url),
        "chat_model": settings.openai_chat_model,
        "embedding_provider": artifact.provider_identity,
        "embedding_model": artifact.embedding_model,
        "top_n": settings.retrieval_top_n,
        "top_k": settings.retrieval_top_k,
        "retrieval_min_score": settings.live_retrieval_min_score,
    }
    fingerprint = sha256(json.dumps(config, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    reviewed = sum(case.human_review.factual_support != "NOT_REVIEWED" for case in cases)
    summary = _summary(cases, reviewed)
    return LiveEvaluationReport(
        schema_version=1,
        report_kind="live-evaluation",
        run=RunProvenance(
            run_id=f"live-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}",
            timestamp=datetime.now(UTC),
            mode="live",
            dataset_id=dataset.dataset_id,
            dataset_version=dataset.version,
            dataset_checksum=file_sha256(dataset_path),
            git_commit=git_commit,
            worktree_dirty=dirty,
            prompt_version="ticket-analysis-v1",
            top_n=10,
            top_k=3,
            config_fingerprint=fingerprint,
        ),
        provenance=ProviderProvenance(
            knowledge_release_id=corpus.release_id,
            knowledge_release_version=corpus.release_version,
            semantic_corpus_checksum=corpus.corpus_checksum,
            embedding_artifact=EmbeddingArtifactProvenance(
                artifact_id=artifact.artifact_id,
                manifest_sha256=file_checksum(manifest_path),
                provider_identity=artifact.provider_identity,
                model=artifact.embedding_model,
                dimension=artifact.vector_dimension,
                chunking_version=artifact.chunking_version,
            ),
            chat_provider_identity=provider_identity(settings.openai_base_url),
            chat_model=settings.openai_chat_model or "unconfigured",
        ),
        cases=cases,
        summary=summary,
    )


def _summary(cases: tuple[LiveCaseResult, ...], reviewed: int) -> LiveSummary:
    total = len(cases)
    retrieval = sum(case.retrieval_success for case in cases)
    reciprocal_ranks = tuple(0.0 if case.first_relevant_rank is None else 1 / case.first_relevant_rank for case in cases)
    citations = sum(case.citation_valid for case in cases)
    no_evidence_cases = tuple(case for case in cases if not case.allowed_chunk_ids)
    no_evidence_safe = sum(case.mode == "fallback" and not case.cited_chunk_ids for case in no_evidence_cases)
    fallback = sum(case.mode == "fallback" for case in cases)
    latencies = sorted(case.latency_ms for case in cases)
    machine_pass = all(
        case.retrieval_success
        and case.citation_valid
        and (
            (case.status == "SUCCEEDED" and case.mode == "live")
            or (not case.allowed_chunk_ids and case.mode == "fallback")
        )
        for case in cases
    )
    reasons = () if machine_pass and reviewed == total else (("machine-gate-failed",) if not machine_pass else ("human-review-incomplete",))
    return LiveSummary(
        label="evaluation_results_for_this_dataset_run",
        total_cases=total,
        succeeded_cases=sum(case.status == "SUCCEEDED" for case in cases),
        retrieval_success_count=retrieval,
        retrieval_success_rate=retrieval / total,
        mean_reciprocal_rank=sum(reciprocal_ranks) / total,
        citation_valid_count=citations,
        citation_valid_rate=citations / total,
        no_evidence_safety_rate=no_evidence_safe / len(no_evidence_cases) if no_evidence_cases else 1.0,
        fallback_count=fallback,
        average_latency_ms=sum(latencies) / total,
        p95_latency_ms=latencies[min(total - 1, round((total - 1) * 0.95))],
        human_reviewed_count=reviewed,
        publishable=machine_pass and reviewed == total,
        gate_reasons=reasons,
    )


def _git(arguments: tuple[str, ...]) -> str:
    result = subprocess.run(("git", *arguments), check=True, capture_output=True, text=True)
    return result.stdout.strip()

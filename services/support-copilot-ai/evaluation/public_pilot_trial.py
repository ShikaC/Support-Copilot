"""One observable generation attempt using the existing production provider."""
from dataclasses import dataclass
from time import perf_counter
from typing import ClassVar, Literal

import anyio
from pydantic import BaseModel, ConfigDict

from app.errors import RecoverableAiError
from app.models import (
    AnalyzeRequest,
    KnowledgeAccess,
    ModelDraft,
    RetrievalHit,
    SupportScope,
    TicketInput,
)
from app.observability import safe_provider_failure_details
from app.openai_provider import OpenAIProvider
from evaluation.public_pilot_data import Chunk, PublicCase, citations_in_bounds


class Trial(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)
    case_id: str
    method: str
    source_url: str
    question: str
    trace_id: str
    status: Literal["COMPLETED", "INVALID_CITATIONS", "PROVIDER_ERROR", "DEADLINE_EXCEEDED"]
    retrieval_ms: float
    generation_ms: float
    input_tokens: int | None = None
    output_tokens: int | None = None
    evidence: list[Chunk]
    scores: list[float]
    draft: ModelDraft | None = None
    error: str | None = None
    diagnostics: dict[str, str | int] | None = None
    citation_structure_valid: bool | None = None
    human_review: Literal["NOT_REVIEWED"] = "NOT_REVIEWED"
    answer_correct: None = None


@dataclass(frozen=True, slots=True)
class TrialInput:
    case: PublicCase
    method: str
    chunks: list[Chunk]
    scores: list[float]
    retrieval_ms: float


def request_for(case: PublicCase, access: KnowledgeAccess) -> AnalyzeRequest:
    return AnalyzeRequest(trace_id=f"public-{case.id}", knowledge_access=access,
        ticket=TicketInput(id=case.id, subject=case.source.title[:240], language="en",
            description="Documentation is frozen at GitHub CLI 2.100.0. Explain current documented behaviour; do not claim historical versions were verified.\n" + case.input.question))


def hits_for(inputs: TrialInput) -> list[RetrievalHit]:
    return [RetrievalHit(chunk_id=chunk.id, document_id=chunk.document_id,
        document_title=f"GitHub CLI 2.100.0: {chunk.document_id}",
        section=f"lines {chunk.start_line}-{chunk.end_line}", content=chunk.content,
        source_uri=chunk.source_url, retrieval_method=inputs.method,
        initial_rank=index, initial_score=score, rerank_position=index,
        rerank_score=score, used_as_evidence=True)
        for index, (chunk, score) in enumerate(zip(inputs.chunks, inputs.scores, strict=True), start=1)]


async def run_trial(provider: OpenAIProvider, inputs: TrialInput, access: KnowledgeAccess) -> Trial:
    """Named failures remain recorded failures; unknown errors stop the experiment."""
    request = request_for(inputs.case, access).model_copy(update={"trace_id": f"public-{inputs.case.id}-{inputs.method}"})
    started = perf_counter()
    try:
        with anyio.fail_after(90):
            draft, incoming, outgoing = await provider.analyze(request, hits_for(inputs))
    except RecoverableAiError as exc:
        return Trial(case_id=inputs.case.id, method=inputs.method, source_url=inputs.case.source.url,
            question=inputs.case.input.question, trace_id=request.trace_id, status="PROVIDER_ERROR",
            retrieval_ms=inputs.retrieval_ms, generation_ms=(perf_counter()-started)*1000,
            evidence=inputs.chunks, scores=inputs.scores, error=exc.fallback_reason.value,
            diagnostics=safe_provider_failure_details(exc))
    except TimeoutError:
        return Trial(case_id=inputs.case.id, method=inputs.method, source_url=inputs.case.source.url,
            question=inputs.case.input.question, trace_id=request.trace_id, status="DEADLINE_EXCEEDED",
            retrieval_ms=inputs.retrieval_ms, generation_ms=(perf_counter()-started)*1000,
            evidence=inputs.chunks, scores=inputs.scores, error="experiment_generation_deadline_90s")
    valid = citations_in_bounds(draft.citation_indexes, len(inputs.chunks)) and (not draft.evidence_sufficient or bool(draft.citation_indexes))
    return Trial(case_id=inputs.case.id, method=inputs.method, source_url=inputs.case.source.url,
        question=inputs.case.input.question, trace_id=request.trace_id,
        status="COMPLETED" if valid else "INVALID_CITATIONS", retrieval_ms=inputs.retrieval_ms,
        generation_ms=(perf_counter()-started)*1000, evidence=inputs.chunks, scores=inputs.scores,
        draft=draft, input_tokens=incoming if incoming or outgoing else None,
        output_tokens=outgoing if incoming or outgoing else None, citation_structure_valid=valid)


def pilot_access(checksum: str) -> KnowledgeAccess:
    return KnowledgeAccess(release_id="public-gh-2.100.0-experiment", release_version=1,
        corpus_checksum=checksum, allowed_scopes=tuple(SupportScope))

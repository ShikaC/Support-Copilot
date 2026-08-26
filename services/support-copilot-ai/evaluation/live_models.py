from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic_core import PydanticCustomError

Sha256 = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
GitCommit = Annotated[str, Field(pattern=r"^[a-f0-9]{40,64}$")]
FactualSupport = Literal["SUPPORTED", "PARTIAL", "UNSUPPORTED", "NOT_REVIEWED"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class HumanReview(StrictModel):
    reviewer: str | None = None
    factual_support: FactualSupport = "NOT_REVIEWED"
    decision_note: str | None = None
    reviewed_at: datetime | None = None


class LiveTicket(StrictModel):
    subject: str = Field(min_length=1, max_length=240)
    description: str = Field(min_length=1, max_length=4000)
    customer_tier: str = "STANDARD"


class RetrievalExpectation(StrictModel):
    evidence_required: bool
    document_ids: tuple[str, ...] = ()
    chunk_ids: tuple[str, ...] = ()


class LiveEvaluationCase(StrictModel):
    id: str = Field(min_length=1)
    classification: Literal["SYNTHETIC", "REDACTED"]
    ticket: LiveTicket
    expected_retrieval: RetrievalExpectation
    allowed_chunk_ids: tuple[str, ...]
    human_review: HumanReview = HumanReview()


class LiveDataset(StrictModel):
    schema_version: Literal[1]
    dataset_id: str
    version: str
    classification: Literal["SYNTHETIC", "REDACTED"]
    cases: tuple[LiveEvaluationCase, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_case_ids(self) -> "LiveDataset":
        ids = tuple(case.id for case in self.cases)
        if len(ids) != len(set(ids)):
            raise PydanticCustomError("duplicate_live_case_id", "live evaluation case IDs must be unique")
        return self


class RunProvenance(StrictModel):
    run_id: str
    timestamp: datetime
    mode: Literal["live"]
    dataset_id: str
    dataset_version: str
    dataset_checksum: Sha256
    git_commit: GitCommit
    worktree_dirty: bool
    prompt_version: str
    top_n: int = Field(gt=0)
    top_k: int = Field(gt=0)
    config_fingerprint: Sha256


class EmbeddingArtifactProvenance(StrictModel):
    artifact_id: Sha256
    manifest_sha256: Sha256
    provider_identity: str
    model: str
    dimension: int = Field(gt=0)
    chunking_version: str


class ProviderProvenance(StrictModel):
    knowledge_release_id: str
    knowledge_release_version: int
    semantic_corpus_checksum: Sha256
    embedding_artifact: EmbeddingArtifactProvenance | None
    chat_provider_identity: str
    chat_model: str


class TokenUsage(StrictModel):
    availability: Literal["available", "unavailable"]
    input_tokens: int | None = Field(ge=0)
    output_tokens: int | None = Field(ge=0)
    total_tokens: int | None = Field(ge=0)


class CostRecord(StrictModel):
    amount: float
    currency: str
    pricing_source: str
    pricing_source_checksum: Sha256


class PricingConfig(StrictModel):
    schema_version: Literal[1]
    pricing_source: str
    currency: str
    chat_model: str
    input_per_million_tokens: float = Field(ge=0)
    output_per_million_tokens: float = Field(ge=0)


class ResponseEvidence(StrictModel):
    statement: str
    evidence_indexes: tuple[int, ...]


class LiveCaseResult(StrictModel):
    case_id: str
    status: Literal["SUCCEEDED", "FAILED", "FALLBACK"]
    mode: Literal["live", "fallback"]
    fallback_reason: str | None
    retrieval_success: bool
    first_relevant_rank: int | None = Field(default=None, gt=0)
    retrieved_chunk_ids: tuple[str, ...]
    allowed_chunk_ids: tuple[str, ...]
    cited_chunk_ids: tuple[str, ...]
    citation_valid: bool
    response_text: str
    response_evidence: tuple[ResponseEvidence, ...]
    latency_ms: int = Field(ge=0)
    usage: TokenUsage
    cost: CostRecord | None
    human_review: HumanReview


class LiveSummary(StrictModel):
    label: Literal["evaluation_results_for_this_dataset_run"]
    total_cases: int = Field(gt=0)
    succeeded_cases: int = Field(ge=0)
    retrieval_success_count: int = Field(ge=0)
    retrieval_success_rate: float = Field(ge=0, le=1)
    mean_reciprocal_rank: float = Field(ge=0, le=1)
    citation_valid_count: int = Field(ge=0)
    citation_valid_rate: float = Field(ge=0, le=1)
    no_evidence_safety_rate: float = Field(ge=0, le=1)
    fallback_count: int = Field(ge=0)
    average_latency_ms: float = Field(ge=0)
    p95_latency_ms: int = Field(ge=0)
    human_reviewed_count: int = Field(ge=0)
    publishable: bool
    gate_reasons: tuple[str, ...]


class LiveEvaluationReport(StrictModel):
    schema_version: Literal[1]
    report_kind: Literal["live-evaluation"]
    run: RunProvenance
    provenance: ProviderProvenance
    cases: tuple[LiveCaseResult, ...]
    summary: LiveSummary


class VerificationContext(StrictModel):
    dataset_id: str
    dataset_version: str
    dataset_checksum: Sha256
    release_id: str
    release_version: int
    corpus_checksum: Sha256
    artifact_id: Sha256 | None
    artifact_manifest_sha256: Sha256 | None
    git_commit: GitCommit
    worktree_dirty: bool
    known_chunk_ids: frozenset[str]


class ReviewEntry(StrictModel):
    case_id: str
    reviewer: str | None
    factual_support: FactualSupport
    decision_note: str | None
    reviewed_at: datetime | None


class ReviewWorksheet(StrictModel):
    schema_version: Literal[1]
    run_id: str
    report_sha256: Sha256
    reviews: tuple[ReviewEntry, ...]

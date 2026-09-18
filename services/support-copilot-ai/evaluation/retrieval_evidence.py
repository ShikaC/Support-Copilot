"""Load one recorded retrieval run without consulting the mutable active pointer."""

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, TypeAdapter

from app.config import Settings
from app.embedding_artifact import EmbeddingArtifactStore, LoadedEmbeddingArtifact
from app.embedding_artifact_models import EmbeddingArtifactManifest, SHA256_PATTERN
from app.knowledge_source import KnowledgeCorpus


class RetrievalEvidenceError(ValueError):
    def __init__(self, reason: str) -> None:
        super().__init__(f"Retrieval evidence unavailable: {reason}")


class RecordedQuery(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str = Field(alias="caseId", min_length=1)
    query: str


class RecordedPlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    artifact_id: str = Field(alias="artifactId", pattern=SHA256_PATTERN)
    corpus_sha256: str = Field(alias="corpusSha256", pattern=SHA256_PATTERN)
    embedding_model: str = Field(alias="embeddingModel", min_length=1)
    provider_identity: str = Field(alias="embeddingProviderIdentity", min_length=1)
    vector_dimension: int = Field(alias="vectorDimension", gt=0)
    chunking_version: str = Field(alias="chunkingVersion", min_length=1)
    queries: tuple[RecordedQuery, ...] = Field(min_length=1)


class RecordedHashes(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    plan_sha256: str | None = Field(default=None, alias="retrievalPlanSha256", pattern=SHA256_PATTERN)
    vectors_sha256: str | None = Field(default=None, alias="queryVectorsSha256", pattern=SHA256_PATTERN)


@dataclass(frozen=True, slots=True)
class RetrievalEvidence:
    artifact: LoadedEmbeddingArtifact
    plan: RecordedPlan
    corpus: KnowledgeCorpus
    vectors: dict[str, list[float]]


def load_retrieval_evidence(
    plan_path: Path,
    vectors_path: Path,
    corpus_path: Path,
    artifact_root: Path,
) -> RetrievalEvidence:
    """Reject mixed files before any ranking or report writing takes place.

    Old caches without execution-time hashes cannot prove vector provenance;
    retain their historical reports rather than adding retrospective hashes.
    """
    hashes = RecordedHashes.model_validate_json(
        (vectors_path.parent / "retrieval-only-manifest.json").read_bytes()
    )
    if hashes.plan_sha256 is None or hashes.vectors_sha256 is None:
        raise RetrievalEvidenceError("legacy cache has no execution-time plan/vector hashes")
    plan_bytes = plan_path.read_bytes()
    vectors_bytes = vectors_path.read_bytes()
    corpus_bytes = corpus_path.read_bytes()
    if sha256(plan_bytes).hexdigest() != hashes.plan_sha256:
        raise RetrievalEvidenceError("plan hash mismatch")
    if sha256(vectors_bytes).hexdigest() != hashes.vectors_sha256:
        raise RetrievalEvidenceError("query vector hash mismatch")
    plan = RecordedPlan.model_validate_json(plan_bytes)
    if sha256(corpus_bytes).hexdigest() != plan.corpus_sha256:
        raise RetrievalEvidenceError("corpus hash mismatch")

    manifest = EmbeddingArtifactManifest.model_validate_json(
        (artifact_root / plan.artifact_id / "manifest.json").read_bytes()
    )
    if manifest.provider_identity != plan.provider_identity:
        raise RetrievalEvidenceError("embedding provider mismatch")
    if manifest.chunking_version != plan.chunking_version:
        raise RetrievalEvidenceError("chunking version mismatch")
    provider_url = None if plan.provider_identity == "openai-default" else plan.provider_identity
    settings = Settings(
        ai_mode="mock",
        embedding_artifact_root=artifact_root,
        openai_base_url=provider_url,
        openai_embedding_base_url=provider_url,
        openai_embedding_model=plan.embedding_model,
        embedding_vector_dimension=plan.vector_dimension,
        embedding_chunking_version=plan.chunking_version,
        _env_file=None,
    )
    corpus = KnowledgeCorpus.model_validate_json(corpus_bytes)
    corpus = corpus.model_copy(update={
        "chunks": tuple(chunk for chunk in corpus.chunks if chunk.status == "PUBLISHED"),
    })
    artifact = EmbeddingArtifactStore(settings, corpus).load(plan.artifact_id)
    vectors = TypeAdapter(dict[str, list[FiniteFloat]]).validate_json(vectors_bytes)
    case_ids = [entry.case_id for entry in plan.queries]
    if len(case_ids) != len(set(case_ids)) or set(vectors) != set(case_ids):
        raise RetrievalEvidenceError("query vector case IDs do not match the plan")
    for case_id, vector in vectors.items():
        values = np.asarray(vector, dtype=np.float32)
        if values.shape != (plan.vector_dimension,) or not np.isfinite(values).all():
            raise RetrievalEvidenceError(f"query vector invalid for {case_id}")
    return RetrievalEvidence(artifact=artifact, plan=plan, corpus=corpus, vectors=vectors)

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models import SupportScope

SHA256_PATTERN = r"^[a-f0-9]{64}$"


class ArtifactChunkMetadata(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    row: int = Field(ge=0)
    chunk_id: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    content_checksum: str = Field(pattern=SHA256_PATTERN)
    categories: tuple[str, ...]
    allowed_scopes: tuple[SupportScope, ...]


class ArtifactDocumentRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    document_id: str = Field(min_length=1)
    checksum: str = Field(pattern=SHA256_PATTERN)
    chunk_ids: tuple[str, ...] = Field(min_length=1)


class EmbeddingArtifactManifest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[1]
    artifact_id: str = Field(pattern=SHA256_PATTERN)
    release_id: str = Field(min_length=1)
    release_version: int = Field(gt=0)
    corpus_checksum: str = Field(pattern=SHA256_PATTERN)
    provider_identity: str = Field(min_length=1)
    embedding_model: str = Field(min_length=1)
    input_format: Literal["legacy-tokenized-v1", "raw-text-v1"] = "legacy-tokenized-v1"
    vector_dimension: int = Field(gt=0)
    chunking_version: str = Field(min_length=1)
    row_count: int = Field(gt=0)
    matrix_sha256: str = Field(pattern=SHA256_PATTERN)
    metadata_sha256: str = Field(pattern=SHA256_PATTERN)
    documents: tuple[ArtifactDocumentRecord, ...] = Field(min_length=1)


class ActiveArtifactPointer(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[1]
    active_artifact_id: str = Field(pattern=SHA256_PATTERN)
    previous_artifact_id: str | None = Field(default=None, pattern=SHA256_PATTERN)

"""Request and durable response contracts for explicit rebuild tasks."""

from typing import ClassVar, Literal, Self, assert_never
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel
from pydantic_core import PydanticCustomError

from app.embedding_artifact_models import SHA256_PATTERN


class RebuildRequest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True, extra="forbid", alias_generator=to_camel, populate_by_name=True
    )

    max_embedding_calls: int = Field(gt=0, strict=True)
    expected_corpus_checksum: str = Field(pattern=SHA256_PATTERN)


FailureCode = Literal[
    "REBUILD_INTERRUPTED",
    "REBUILD_START_FAILED",
    "EMBEDDING_PROVIDER_FAILED",
    "ARTIFACT_BUILD_FAILED",
    "REBUILD_STORAGE_UNAVAILABLE",
    "REBUILD_INTERNAL_ERROR",
]


class RebuildStatus(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True, extra="forbid", alias_generator=to_camel, populate_by_name=True
    )

    task_id: UUID
    status: Literal["RUNNING", "SUCCEEDED", "FAILED"]
    total_chunks: int = Field(gt=0)
    completed_chunks: int = Field(default=0, ge=0)
    estimated_embedding_calls: int = Field(gt=0)
    max_embedding_calls: int = Field(gt=0)
    embedding_calls: int = Field(default=0, ge=0)
    artifact_id: str | None = Field(default=None, pattern=SHA256_PATTERN)
    corpus_checksum: str = Field(pattern=SHA256_PATTERN)
    trace_id: str
    started_at: AwareDatetime
    updated_at: AwareDatetime
    finished_at: AwareDatetime | None = None
    elapsed_seconds: float = Field(default=0, ge=0)
    estimated_duration_seconds: None = None
    failure_code: FailureCode | None = None

    @model_validator(mode="after")
    def coherent_progress(self) -> Self:
        if (
            self.completed_chunks > self.total_chunks
            or self.embedding_calls > self.max_embedding_calls
            or self.estimated_embedding_calls > self.max_embedding_calls
            or self.updated_at < self.started_at
            or (self.finished_at is not None and self.finished_at < self.started_at)
        ):
            raise PydanticCustomError(
                "invalid_rebuild_progress", "Rebuild progress is inconsistent"
            )
        match self.status:
            case "RUNNING":
                coherent = (
                    self.finished_at is None
                    and self.artifact_id is None
                    and self.failure_code is None
                )
            case "SUCCEEDED":
                coherent = (
                    self.finished_at is not None
                    and self.artifact_id is not None
                    and self.failure_code is None
                    and self.completed_chunks == self.total_chunks
                )
            case "FAILED":
                coherent = (
                    self.finished_at is not None
                    and self.failure_code is not None
                    and self.artifact_id is None
                )
            case unreachable:
                assert_never(unreachable)
        if not coherent:
            raise PydanticCustomError(
                "invalid_rebuild_state", "Rebuild state is inconsistent"
            )
        return self


class RebuildError(Exception):
    """Safe boundary error whose message contains no provider or filesystem input."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code: int = status_code
        self.code: str = code
        self.message: str = message
        super().__init__(message)

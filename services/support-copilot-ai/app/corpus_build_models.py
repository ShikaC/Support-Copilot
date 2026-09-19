"""Strict contracts for document-only corpus generation tasks."""

from typing import ClassVar, Literal, Self, assert_never
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel
from pydantic_core import PydanticCustomError

from app.knowledge_source import CHECKSUM_PATTERN


class CorpusBuildRequest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True,
        extra="forbid",
        alias_generator=to_camel,
        populate_by_name=True,
    )
    expected_source_checksum: str = Field(pattern=CHECKSUM_PATTERN)
    window: int = Field(strict=True, gt=0, le=8000)
    stride: int = Field(strict=True, gt=0, le=8000)

    @model_validator(mode="after")
    def contiguous_slices(self) -> Self:
        if self.stride > self.window:
            raise PydanticCustomError("chunking_gap", "Stride cannot exceed window")
        return self


class CorpusBuildResult(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True,
        extra="forbid",
        alias_generator=to_camel,
        populate_by_name=True,
    )
    source_checksum: str = Field(pattern=CHECKSUM_PATTERN)
    corpus_checksum: str = Field(pattern=CHECKSUM_PATTERN)
    corpus_file_checksum: str = Field(pattern=CHECKSUM_PATTERN)
    document_count: int = Field(strict=True, gt=0)
    chunk_count: int = Field(strict=True, gt=0, le=20000)
    window: int = Field(strict=True, gt=0, le=8000)
    stride: int = Field(strict=True, gt=0, le=8000)


FailureCode = Literal[
    "CORPUS_BUILD_INTERRUPTED",
    "CORPUS_BUILD_START_FAILED",
    "CORPUS_PROCESS_FAILED",
    "CORPUS_BUILD_TIMEOUT",
    "CORPUS_RESULT_INVALID",
    "CORPUS_STORAGE_UNAVAILABLE",
    "CORPUS_INTERNAL_ERROR",
]


class CorpusBuildStatus(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True,
        extra="forbid",
        alias_generator=to_camel,
        populate_by_name=True,
    )
    task_id: UUID
    request: CorpusBuildRequest
    status: Literal["RUNNING", "SUCCEEDED", "FAILED"] = "RUNNING"
    result: CorpusBuildResult | None = None
    failure_code: FailureCode | None = None
    trace_id: str
    started_at: AwareDatetime
    finished_at: AwareDatetime | None = None
    elapsed_seconds: float = Field(default=0, ge=0, allow_inf_nan=False)
    estimated_duration_seconds: None = None

    @model_validator(mode="after")
    def coherent_status(self) -> Self:
        result = self.result
        match self.status:
            case "RUNNING":
                coherent = (
                    self.finished_at is None
                    and result is None
                    and self.failure_code is None
                )
            case "SUCCEEDED":
                coherent = (
                    self.finished_at is not None
                    and result is not None
                    and self.failure_code is None
                    and result.source_checksum == self.request.expected_source_checksum
                    and result.window == self.request.window
                    and result.stride == self.request.stride
                )
            case "FAILED":
                coherent = (
                    self.finished_at is not None
                    and result is None
                    and self.failure_code is not None
                )
            case unreachable:
                assert_never(unreachable)
        if not coherent or (
            self.finished_at is not None and self.finished_at < self.started_at
        ):
            raise PydanticCustomError(
                "invalid_corpus_task", "Corpus task state is inconsistent"
            )
        return self


class CorpusBuildError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code: int = status_code
        self.code: str = code
        self.message: str = message
        super().__init__(message)

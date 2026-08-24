from datetime import date
from hashlib import sha256
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, RootModel, ValidationError, model_validator
from pydantic_core import PydanticCustomError


class KnowledgeChunk(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    chunk_id: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    document_title: str = Field(min_length=1)
    section: str = Field(min_length=1)
    content: str = Field(min_length=1)
    source_uri: str = Field(min_length=1)
    categories: tuple[str, ...] = Field(min_length=1)
    keywords: tuple[str, ...] = Field(min_length=1)
    document_version: str = Field(min_length=1)
    status: Literal["PUBLISHED", "ARCHIVED"]
    updated_at: date


class KnowledgeCorpus(RootModel[tuple[KnowledgeChunk, ...]]):
    model_config = ConfigDict(frozen=True)

    root: tuple[KnowledgeChunk, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def reject_duplicate_chunk_ids(self) -> Self:
        chunk_ids = [chunk.chunk_id for chunk in self.root]
        if len(chunk_ids) != len(set(chunk_ids)):
            raise PydanticCustomError(
                "duplicate_chunk_id",
                "Knowledge chunk IDs must be unique",
            )
        return self


class KnowledgeDocumentProvenance(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    path: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    document_version: str = Field(min_length=1)
    status: Literal["PUBLISHED", "ARCHIVED"]
    updated_at: date
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    chunk_ids: tuple[str, ...]


class KnowledgeProvenance(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[1]
    index_version: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    corpus_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    manifest_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    chunk_size: int = Field(gt=0)
    chunk_overlap: int = Field(ge=0)
    documents: tuple[KnowledgeDocumentProvenance, ...] = Field(min_length=1)


class KnowledgeSourceInvalidError(ValueError):
    def __init__(self, path: Path, issue_count: int) -> None:
        self.path = path
        self.issue_count = issue_count
        super().__init__(
            f"Knowledge source is invalid: {path} "
            f"({issue_count} validation error(s))"
        )


def load_knowledge_chunks(
    path: Path,
    provenance_path: Path | None = None,
) -> tuple[KnowledgeChunk, ...]:
    content = path.read_text(encoding="utf-8")

    try:
        chunks = KnowledgeCorpus.model_validate_json(content).root
    except ValidationError as exc:
        raise KnowledgeSourceInvalidError(
            path=path,
            issue_count=exc.error_count(),
        ) from None

    if provenance_path is not None:
        try:
            provenance_content = provenance_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            raise KnowledgeSourceInvalidError(
                path=provenance_path,
                issue_count=1,
            ) from None
        try:
            provenance = KnowledgeProvenance.model_validate_json(provenance_content)
        except ValidationError as exc:
            raise KnowledgeSourceInvalidError(
                path=provenance_path,
                issue_count=exc.error_count(),
            ) from None
        if provenance.corpus_sha256 != sha256(path.read_bytes()).hexdigest():
            raise KnowledgeSourceInvalidError(path=provenance_path, issue_count=1)

    published_chunks = tuple(chunk for chunk in chunks if chunk.status == "PUBLISHED")
    if not published_chunks:
        raise KnowledgeSourceInvalidError(path=path, issue_count=1)
    return published_chunks

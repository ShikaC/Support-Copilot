from datetime import date
from hashlib import sha256
import json
from pathlib import Path
from typing import Final, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from pydantic_core import PydanticCustomError

from app.models import SupportScope

CHECKSUM_PATTERN: Final = r"^[a-f0-9]{64}$"


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
    allowed_scopes: tuple[SupportScope, ...] = Field(min_length=1)
    document_version: str = Field(min_length=1)
    status: Literal["PUBLISHED", "ARCHIVED"]
    updated_at: date


class KnowledgeCorpus(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    release_id: str = Field(min_length=1, pattern=r".*\S.*")
    release_version: int = Field(gt=0)
    corpus_checksum: str = Field(pattern=CHECKSUM_PATTERN)
    chunks: tuple[KnowledgeChunk, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def reject_duplicate_chunk_ids(self) -> Self:
        chunk_ids = [chunk.chunk_id for chunk in self.chunks]
        if len(chunk_ids) != len(set(chunk_ids)):
            raise PydanticCustomError(
                "duplicate_chunk_id",
                "Knowledge chunk IDs must be unique",
            )
        if self.corpus_checksum != calculate_corpus_checksum(self.chunks):
            raise PydanticCustomError(
                "corpus_checksum_mismatch",
                "Knowledge corpus checksum does not match its chunks",
            )
        return self


def calculate_corpus_checksum(chunks: tuple[KnowledgeChunk, ...]) -> str:
    canonical = json.dumps(
        [chunk.model_dump(mode="json") for chunk in chunks],
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return sha256(canonical).hexdigest()


class KnowledgeDocumentProvenance(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    path: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    document_version: str = Field(min_length=1)
    status: Literal["PUBLISHED", "ARCHIVED"]
    updated_at: date
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    chunk_ids: tuple[str, ...]
    allowed_scopes: tuple[SupportScope, ...]


class KnowledgeProvenance(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[2]
    release_id: str = Field(min_length=1)
    release_version: int = Field(gt=0)
    corpus_checksum: str = Field(pattern=CHECKSUM_PATTERN)
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


def load_knowledge_corpus(
    path: Path,
    provenance_path: Path | None = None,
) -> KnowledgeCorpus:
    content = path.read_text(encoding="utf-8")

    try:
        corpus = KnowledgeCorpus.model_validate_json(content)
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
        if (
            provenance.release_id != corpus.release_id
            or provenance.release_version != corpus.release_version
            or provenance.corpus_checksum != corpus.corpus_checksum
        ):
            raise KnowledgeSourceInvalidError(path=provenance_path, issue_count=1)

    published_chunks = tuple(
        chunk for chunk in corpus.chunks if chunk.status == "PUBLISHED"
    )
    if not published_chunks:
        raise KnowledgeSourceInvalidError(path=path, issue_count=1)
    return corpus.model_copy(update={"chunks": published_chunks})


def load_knowledge_chunks(
    path: Path,
    provenance_path: Path | None = None,
) -> tuple[KnowledgeChunk, ...]:
    return load_knowledge_corpus(path, provenance_path).chunks

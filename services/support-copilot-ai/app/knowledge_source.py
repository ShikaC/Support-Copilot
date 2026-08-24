from dataclasses import dataclass
from pathlib import Path
from typing import Self

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


@dataclass(frozen=True, slots=True)
class KnowledgeSourceInvalidError(ValueError):
    path: Path
    issue_count: int

    def __str__(self) -> str:
        return (
            f"Knowledge source is invalid: {self.path} "
            f"({self.issue_count} validation error(s))"
        )


def load_knowledge_chunks(path: Path) -> tuple[KnowledgeChunk, ...]:
    content = path.read_text(encoding="utf-8")

    try:
        return KnowledgeCorpus.model_validate_json(content).root
    except ValidationError as exc:
        raise KnowledgeSourceInvalidError(
            path=path,
            issue_count=exc.error_count(),
        ) from None

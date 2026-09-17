"""Frozen input projections and source-preserving retrieval for a public pilot."""
import hashlib
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field


class InputProjection(BaseModel):
    """Read explicitly selected fields from the richer frozen curation artifacts."""
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="ignore")


class Question(InputProjection):
    question: str
    language: str


class Source(InputProjection):
    url: str
    title: str


class PublicCase(InputProjection):
    id: str
    source: Source
    input: Question


class Dataset(InputProjection):
    cases: list[PublicCase]


class Document(InputProjection):
    id: str = Field(pattern=r"^gh_[a-z0-9_-]+$")
    file: str = Field(pattern=r"^gh_[a-z0-9_-]+\.txt$")
    sha256: str


class Manifest(InputProjection):
    documents: list[Document]


class SourceSpan(InputProjection):
    document_id: str
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)


class Proposal(InputProjection):
    id: str
    references: list[SourceSpan]


class Proposals(InputProjection):
    cases: list[Proposal]


@dataclass(frozen=True, slots=True)
class CorpusIntegrityError(RuntimeError):
    document_id: str

class Chunk(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)
    id: str
    document_id: str
    source_url: str
    start_line: int
    end_line: int
    content: str

def split_document(document_id: str, content: str) -> list[Chunk]:
    """Use 24-line windows with four-line overlap; keep original line numbers."""
    lines = content.splitlines()
    chunks: list[Chunk] = []
    for start in range(0, len(lines), 20):
        end = min(start + 24, len(lines))
        text = "\n".join(lines[start:end])
        if text.strip():
            chunks.append(Chunk(id=f"{document_id}-L{start + 1}-{end}", document_id=document_id,
                source_url=f"https://cli.github.com/manual/{document_id}", start_line=start + 1,
                end_line=end, content=text))
        if end == len(lines):
            break
    return chunks

def bm25_scores(chunks: list[Chunk], query: str) -> list[float]:
    """BM25 with k1=1.2, b=.75; lowercase word tokens, no corpus-specific tuning."""
    tokens = [Counter(re.findall(r"[a-z0-9]+", f"{chunk.document_id} {chunk.content}".lower())) for chunk in chunks]
    lengths = [sum(document.values()) for document in tokens]
    average = sum(lengths) / len(lengths)
    scores = [0.0] * len(tokens)
    for term in {match.group(0) for match in re.finditer(r"[a-z0-9]+", query.lower())}:
        df = sum(term in document for document in tokens)
        idf = math.log(1 + (len(tokens) - df + 0.5) / (df + 0.5))
        for index, document in enumerate(tokens):
            frequency = document[term]
            denominator = frequency + 1.2 * (0.25 + 0.75 * lengths[index] / average)
            scores[index] += idf * frequency * 2.2 / denominator
    return scores

def citations_in_bounds(indexes: list[int], count: int) -> bool:
    return len(indexes) == len(set(indexes)) and all(1 <= index <= count for index in indexes)


def load_chunks(root: Path) -> list[Chunk]:
    """Only official text enters retrieval; the aggregate reference is excluded."""
    manifest = Manifest.model_validate_json((root / "corpus/manifest.json").read_text())
    chunks: list[Chunk] = []
    for document in manifest.documents:
        content = (root / "corpus" / document.file).read_bytes()
        if hashlib.sha256(content).hexdigest() != document.sha256:
            raise CorpusIntegrityError(document.id)
        if document.id != "gh_help_reference":
            chunks.extend(split_document(document.id, content.decode()))
    return chunks


def proposed_evidence(root: Path, proposal: Proposal) -> list[Chunk]:
    """Read AI-proposed source spans only, never proposed answers or rubric prose."""
    chunks: list[Chunk] = []
    for ref in proposal.references:
        path = root / "corpus" / f"{ref.document_id}.txt"
        lines = path.read_text().splitlines()
        if not 1 <= ref.start_line <= ref.end_line <= len(lines):
            raise CorpusIntegrityError(ref.document_id)
        chunks.append(Chunk(id=f"{ref.document_id}-L{ref.start_line}-{ref.end_line}",
            document_id=ref.document_id, source_url=f"https://cli.github.com/manual/{ref.document_id}",
            start_line=ref.start_line, end_line=ref.end_line,
            content="\n".join(lines[ref.start_line-1:ref.end_line])))
    return chunks

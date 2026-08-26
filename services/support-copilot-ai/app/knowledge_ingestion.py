import re
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from pathlib import Path
from typing import Final, Literal, Self, assert_never

from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from pydantic_core import PydanticCustomError
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.knowledge_source import (
    KnowledgeChunk,
    KnowledgeCorpus,
    KnowledgeDocumentProvenance,
    KnowledgeProvenance,
    calculate_corpus_checksum,
)
from app.models import SupportScope

MARKDOWN_HEADING: Final = re.compile(r"(?m)^#{1,6}[ \t]+(.+?)[ \t]*$")


class ChunkingConfiguration(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    chunk_size: int = Field(ge=80, le=4000)
    chunk_overlap: int = Field(ge=0, le=1000)

    @model_validator(mode="after")
    def require_smaller_overlap(self) -> Self:
        if self.chunk_overlap >= self.chunk_size:
            raise PydanticCustomError(
                "chunk_overlap_too_large",
                "chunk_overlap must be smaller than chunk_size",
            )
        return self


class SourceDocument(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    path: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    document_title: str = Field(min_length=1)
    source_uri: str = Field(min_length=1)
    categories: tuple[str, ...] = Field(min_length=1)
    keywords: tuple[str, ...] = Field(min_length=1)
    allowed_scopes: tuple[SupportScope, ...] = Field(min_length=1)
    document_version: str = Field(min_length=1)
    status: Literal["PUBLISHED", "ARCHIVED"]
    updated_at: date


class KnowledgeIngestionManifest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[2]
    release_id: str = Field(min_length=1, pattern=r".*\S.*")
    release_version: int = Field(gt=0)
    chunking: ChunkingConfiguration
    documents: tuple[SourceDocument, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def reject_duplicate_document_ids(self) -> Self:
        document_ids = [document.document_id for document in self.documents]
        if len(document_ids) != len(set(document_ids)):
            raise PydanticCustomError(
                "duplicate_document_id",
                "document IDs must be unique",
            )
        return self


@dataclass(frozen=True, slots=True)
class DocumentSection:
    name: str
    content: str


class KnowledgeIngestionError(Exception):
    def __init__(
        self,
        path: Path,
        reason: Literal[
            "manifest-invalid",
            "source-outside-manifest-directory",
            "source-unreadable",
            "source-empty",
            "unsupported-source-format",
            "no-published-content",
        ],
    ) -> None:
        self.path = path
        self.reason = reason
        super().__init__(f"Knowledge ingestion failed: {path} ({reason})")


@dataclass(frozen=True, slots=True)
class KnowledgeBuildResult:
    output_path: Path
    provenance_path: Path
    chunk_count: int
    index_version: str


def _load_manifest(path: Path) -> KnowledgeIngestionManifest:
    try:
        content = path.read_text(encoding="utf-8")
        return KnowledgeIngestionManifest.model_validate_json(content)
    except (OSError, UnicodeError, ValidationError):
        raise KnowledgeIngestionError(path=path, reason="manifest-invalid") from None


def _markdown_sections(path: Path, title: str) -> tuple[DocumentSection, ...]:
    try:
        content = path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        raise KnowledgeIngestionError(path=path, reason="source-unreadable") from None
    if not content:
        raise KnowledgeIngestionError(path=path, reason="source-empty")

    headings = tuple(MARKDOWN_HEADING.finditer(content))
    if not headings:
        return (DocumentSection(name=title, content=content),)

    sections: list[DocumentSection] = []
    introduction = content[: headings[0].start()].strip()
    if introduction:
        sections.append(DocumentSection(name=title, content=introduction))
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(content)
        section_content = content[heading.end() : end].strip()
        if section_content:
            sections.append(
                DocumentSection(name=heading.group(1).strip(), content=section_content)
            )
    if not sections:
        raise KnowledgeIngestionError(path=path, reason="source-empty")
    return tuple(sections)


def _pdf_sections(path: Path) -> tuple[DocumentSection, ...]:
    try:
        with path.open("rb") as stream:
            reader = PdfReader(stream)
            sections = tuple(
                DocumentSection(name=f"Page {page_number}", content=content)
                for page_number, page in enumerate(reader.pages, start=1)
                if (content := (page.extract_text() or "").strip())
            )
    except (OSError, PdfReadError):
        raise KnowledgeIngestionError(path=path, reason="source-unreadable") from None
    if not sections:
        raise KnowledgeIngestionError(path=path, reason="source-empty")
    return sections


def _source_path(manifest_path: Path, document: SourceDocument) -> Path:
    source_root = manifest_path.parent.resolve()
    source_path = (source_root / document.path).resolve()
    if not source_path.is_relative_to(source_root):
        raise KnowledgeIngestionError(
            path=source_path,
            reason="source-outside-manifest-directory",
        )
    return source_path


def _source_format(path: Path) -> Literal["markdown", "pdf"]:
    suffix = path.suffix.lower()
    if suffix in {".md", ".markdown"}:
        return "markdown"
    if suffix == ".pdf":
        return "pdf"
    raise KnowledgeIngestionError(path=path, reason="unsupported-source-format")


def _chunk_id(document: SourceDocument, section: str, content: str) -> str:
    identity = "\0".join(
        (document.document_id, document.document_version, section, content)
    )
    return f"{document.document_id}-{sha256(identity.encode()).hexdigest()[:16]}"


def build_knowledge_corpus(
    manifest_path: Path,
    output_path: Path,
) -> KnowledgeBuildResult:
    manifest = _load_manifest(manifest_path)
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=manifest.chunking.chunk_size,
        chunk_overlap=manifest.chunking.chunk_overlap,
        separators=("\n\n", "\n", "。", ". ", " ", ""),
    )
    chunks: list[KnowledgeChunk] = []
    provenance_documents: list[KnowledgeDocumentProvenance] = []

    for document in manifest.documents:
        source_path = _source_path(manifest_path, document)
        source_format = _source_format(source_path)
        match source_format:
            case "markdown":
                sections = _markdown_sections(source_path, document.document_title)
            case "pdf":
                sections = _pdf_sections(source_path)
            case unreachable:
                assert_never(unreachable)
        document_chunk_ids: list[str] = []
        if document.status == "PUBLISHED":
            for section in sections:
                for content in splitter.split_text(section.content):
                    chunk_id = _chunk_id(document, section.name, content)
                    document_chunk_ids.append(chunk_id)
                    chunks.append(
                        KnowledgeChunk(
                            chunk_id=chunk_id,
                            document_id=document.document_id,
                            document_title=document.document_title,
                            section=section.name,
                            content=content,
                            source_uri=document.source_uri,
                            categories=document.categories,
                            keywords=document.keywords,
                            allowed_scopes=document.allowed_scopes,
                            document_version=document.document_version,
                            status=document.status,
                            updated_at=document.updated_at,
                        )
                    )
        provenance_documents.append(
            KnowledgeDocumentProvenance(
                path=document.path,
                document_id=document.document_id,
                document_version=document.document_version,
                status=document.status,
                updated_at=document.updated_at,
                sha256=sha256(source_path.read_bytes()).hexdigest(),
                chunk_ids=tuple(document_chunk_ids),
                allowed_scopes=document.allowed_scopes,
            )
        )

    if not chunks:
        raise KnowledgeIngestionError(
            path=manifest_path,
            reason="no-published-content",
        )
    corpus_checksum = calculate_corpus_checksum(tuple(chunks))
    corpus_content = KnowledgeCorpus(
        release_id=manifest.release_id,
        release_version=manifest.release_version,
        corpus_checksum=corpus_checksum,
        chunks=tuple(chunks),
    ).model_dump_json(indent=2) + "\n"
    corpus_sha256 = sha256(corpus_content.encode()).hexdigest()
    provenance = KnowledgeProvenance(
        schema_version=2,
        release_id=manifest.release_id,
        release_version=manifest.release_version,
        corpus_checksum=corpus_checksum,
        index_version=f"sha256:{corpus_checksum}",
        corpus_sha256=corpus_sha256,
        manifest_sha256=sha256(manifest_path.read_bytes()).hexdigest(),
        chunk_size=manifest.chunking.chunk_size,
        chunk_overlap=manifest.chunking.chunk_overlap,
        documents=tuple(provenance_documents),
    )
    provenance_path = output_path.with_name(f"{output_path.stem}.provenance.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(corpus_content, encoding="utf-8")
    provenance_path.write_text(
        provenance.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    return KnowledgeBuildResult(
        output_path=output_path,
        provenance_path=provenance_path,
        chunk_count=len(chunks),
        index_version=provenance.index_version,
    )

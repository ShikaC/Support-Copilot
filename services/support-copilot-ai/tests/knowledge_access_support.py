from hashlib import sha256
import json
from pathlib import Path

from langchain_core.embeddings import Embeddings

from app.knowledge import KnowledgeRetriever, RetrievalRequest
from app.knowledge_source import (
    KnowledgeChunk,
    KnowledgeCorpus,
    calculate_corpus_checksum,
)
from app.models import KnowledgeAccess, SupportScope, TicketInput

CANARY_RELEASE_ID = "support-kb-test"


class CapturingEmbeddings(Embeddings):
    def __init__(self) -> None:
        self.documents: list[str] = []
        self.queries: list[str] = []

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.documents.extend(texts)
        return [[1.0, 0.0] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        self.queries.append(text)
        return [1.0, 0.0]


def write_canary_corpus(path: Path) -> str:
    chunks = [
        {
            "chunk_id": "billing-canary",
            "document_id": "billing-guide",
            "document_title": "Billing guide",
            "section": "Duplicate charge",
            "content": "COLLIDING_CANARY duplicate charge investigation",
            "source_uri": "kb://billing-guide/v1",
            "categories": ["BILLING"],
            "keywords": ["COLLIDING_CANARY", "duplicate charge"],
            "allowed_scopes": ["BILLING"],
            "document_version": "v1",
            "status": "PUBLISHED",
            "updated_at": "2026-08-27",
        },
        {
            "chunk_id": "privacy-forbidden-canary",
            "document_id": "privacy-guide",
            "document_title": "Private investigation guide",
            "section": "Duplicate charge",
            "content": "FORBIDDEN_CANARY duplicate charge investigation",
            "source_uri": "kb://privacy-guide/v1",
            "categories": ["BILLING"],
            "keywords": ["COLLIDING_CANARY", "duplicate charge"],
            "allowed_scopes": ["PRIVACY"],
            "document_version": "v1",
            "status": "PUBLISHED",
            "updated_at": "2026-08-27",
        },
    ]
    canonical = json.dumps(
        chunks,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    checksum = sha256(canonical).hexdigest()
    path.write_text(
        json.dumps(
            {
                "release_id": CANARY_RELEASE_ID,
                "release_version": 1,
                "corpus_checksum": checksum,
                "chunks": chunks,
            }
        ),
        encoding="utf-8",
    )
    return checksum


def write_test_corpus(path: Path, chunks: tuple[KnowledgeChunk, ...]) -> None:
    checksum = calculate_corpus_checksum(chunks)
    corpus = KnowledgeCorpus(
        release_id="support-kb-test",
        release_version=1,
        corpus_checksum=checksum,
        chunks=chunks,
    )
    path.write_text(corpus.model_dump_json(indent=2), encoding="utf-8")


def retrieval_request(
    retriever: KnowledgeRetriever,
    ticket: TicketInput,
    query: str,
    *,
    top_n: int = 10,
    top_k: int = 3,
    live: bool = False,
    scopes: tuple[SupportScope, ...] = tuple(SupportScope),
) -> RetrievalRequest:
    return RetrievalRequest(
        ticket=ticket,
        query=query,
        top_n=top_n,
        top_k=top_k,
        live=live,
        knowledge_access=KnowledgeAccess(
            release_id=retriever.corpus_metadata.release_id,
            release_version=retriever.corpus_metadata.release_version,
            corpus_checksum=retriever.corpus_metadata.corpus_checksum,
            allowed_scopes=scopes,
        ),
    )

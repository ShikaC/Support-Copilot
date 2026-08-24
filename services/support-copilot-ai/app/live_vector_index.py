from dataclasses import dataclass

import anyio
from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import OpenAIEmbeddings

from app.config import Settings
from app.data_redaction import redact_sensitive_text
from app.knowledge_source import KnowledgeChunk
from app.models import RetrievalHit, TicketInput


@dataclass(frozen=True, slots=True)
class RetrievalWindow:
    top_n: int
    top_k: int


class LiveVectorIndex:
    def __init__(
        self,
        settings: Settings,
        chunks: tuple[KnowledgeChunk, ...],
    ) -> None:
        self._settings = settings
        self._chunks = chunks
        self._vector_store: InMemoryVectorStore | None = None
        self._vector_lock = anyio.Lock()

    async def search(
        self,
        ticket: TicketInput,
        query: str,
        window: RetrievalWindow,
    ) -> list[RetrievalHit]:
        store = await self._get_vector_store()
        results = await store.asimilarity_search_with_score(
            redact_sensitive_text(query),
            k=min(window.top_n, len(self._chunks)),
        )
        category = ticket.current_category
        ranked = sorted(
            results,
            key=lambda item: (
                category not in item[0].metadata.get("categories", []),
                -float(item[1]),
            ),
        )[: window.top_k]

        hits: list[RetrievalHit] = []
        for rank, (document, score) in enumerate(ranked, start=1):
            metadata = document.metadata
            hits.append(
                RetrievalHit(
                    chunk_id=str(metadata["chunk_id"]),
                    document_id=str(metadata["document_id"]),
                    document_title=str(metadata["document_title"]),
                    section=str(metadata["section"]),
                    content=document.page_content,
                    source_uri=str(metadata["source_uri"]),
                    retrieval_method="VECTOR",
                    initial_rank=rank,
                    initial_score=round(float(score), 4),
                    rerank_position=rank,
                    rerank_score=round(float(score), 4),
                    used_as_evidence=True,
                )
            )
        return hits

    async def _get_vector_store(self) -> InMemoryVectorStore:
        if self._vector_store is not None:
            return self._vector_store

        async with self._vector_lock:
            if self._vector_store is not None:
                return self._vector_store

            embeddings = OpenAIEmbeddings(
                api_key=self._settings.openai_api_key,
                base_url=self._settings.openai_base_url,
                model=self._settings.openai_embedding_model,
                max_retries=self._settings.openai_max_retries,
                request_timeout=self._settings.openai_timeout_seconds,
            )
            documents = [self._as_document(chunk) for chunk in self._chunks]
            self._vector_store = await InMemoryVectorStore.afrom_documents(
                documents,
                embeddings,
            )
            return self._vector_store

    def _as_document(self, chunk: KnowledgeChunk) -> Document:
        return Document(
            page_content=redact_sensitive_text(chunk.content),
            metadata={
                "chunk_id": chunk.chunk_id,
                "document_id": chunk.document_id,
                "document_title": chunk.document_title,
                "section": chunk.section,
                "source_uri": chunk.source_uri,
                "categories": list(chunk.categories),
            },
        )

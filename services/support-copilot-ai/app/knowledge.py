import asyncio
import json
import re
from dataclasses import dataclass
from pathlib import Path

from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import OpenAIEmbeddings

from app.config import Settings
from app.models import RetrievalHit, TicketInput


@dataclass(frozen=True)
class KnowledgeChunk:
    chunk_id: str
    document_id: str
    document_title: str
    section: str
    content: str
    source_uri: str
    categories: tuple[str, ...]
    keywords: tuple[str, ...]


class KnowledgeRetriever:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._chunks = self._load_chunks()
        self._vector_store: InMemoryVectorStore | None = None
        self._vector_lock = asyncio.Lock()

    @property
    def chunk_count(self) -> int:
        return len(self._chunks)

    async def search(
        self,
        ticket: TicketInput,
        query: str,
        top_n: int,
        top_k: int,
        live: bool,
    ) -> list[RetrievalHit]:
        if live:
            return await self._vector_search(ticket, query, top_n, top_k)
        return self._local_search(ticket, query, top_k)

    async def _vector_search(
        self,
        ticket: TicketInput,
        query: str,
        top_n: int,
        top_k: int,
    ) -> list[RetrievalHit]:
        store = await self._get_vector_store()
        results = await asyncio.to_thread(
            store.similarity_search_with_score,
            query,
            k=min(top_n, len(self._chunks)),
        )
        category = ticket.current_category
        ranked = sorted(
            results,
            key=lambda item: (
                category not in item[0].metadata.get("categories", []),
                -float(item[1]),
            ),
        )[:top_k]

        return [
            self._hit_from_document(
                document,
                score=float(score),
                initial_rank=index,
                final_rank=index,
                method="VECTOR",
            )
            for index, (document, score) in enumerate(ranked, start=1)
        ]

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
            self._vector_store = await asyncio.to_thread(
                InMemoryVectorStore.from_documents,
                documents,
                embeddings,
            )
            return self._vector_store

    def _local_search(
        self,
        ticket: TicketInput,
        query: str,
        top_k: int,
    ) -> list[RetrievalHit]:
        scored = [
            (chunk, self._local_score(chunk, ticket, query))
            for chunk in self._chunks
        ]
        scored.sort(key=lambda item: item[1], reverse=True)
        filtered = [(chunk, score) for chunk, score in scored if score >= 0.18][:top_k]

        return [
            self._hit_from_chunk(
                chunk,
                score=score,
                initial_rank=index,
                final_rank=index,
                method="HYBRID_DEMO",
            )
            for index, (chunk, score) in enumerate(filtered, start=1)
        ]

    def _local_score(
        self,
        chunk: KnowledgeChunk,
        ticket: TicketInput,
        query: str,
    ) -> float:
        normalized_query = self._normalize(query)
        normalized_text = self._normalize(
            " ".join((chunk.document_title, chunk.section, chunk.content, *chunk.keywords))
        )
        query_tokens = self._tokens(normalized_query)
        exact_keyword_matches = sum(
            1 for keyword in chunk.keywords if self._normalize(keyword) in normalized_query
        )
        token_matches = sum(1 for token in query_tokens if token in normalized_text)
        category_bonus = 0.34 if ticket.current_category in chunk.categories else 0.0
        exact_bonus = min(0.35, exact_keyword_matches * 0.18)
        token_score = min(0.28, token_matches * 0.035)
        return min(0.99, 0.08 + category_bonus + exact_bonus + token_score)

    def _tokens(self, text: str) -> set[str]:
        latin_tokens = set(re.findall(r"[a-z0-9-]{2,}", text))
        chinese = "".join(re.findall(r"[\u4e00-\u9fff]", text))
        chinese_bigrams = {
            chinese[index : index + 2]
            for index in range(max(0, len(chinese) - 1))
        }
        return latin_tokens | chinese_bigrams

    def _normalize(self, value: str) -> str:
        return re.sub(r"\s+", " ", value.lower()).strip()

    def _as_document(self, chunk: KnowledgeChunk) -> Document:
        return Document(
            page_content=chunk.content,
            metadata={
                "chunk_id": chunk.chunk_id,
                "document_id": chunk.document_id,
                "document_title": chunk.document_title,
                "section": chunk.section,
                "source_uri": chunk.source_uri,
                "categories": list(chunk.categories),
            },
        )

    def _hit_from_document(
        self,
        document: Document,
        score: float,
        initial_rank: int,
        final_rank: int,
        method: str,
    ) -> RetrievalHit:
        metadata = document.metadata
        return RetrievalHit(
            chunk_id=str(metadata["chunk_id"]),
            document_id=str(metadata["document_id"]),
            document_title=str(metadata["document_title"]),
            section=str(metadata["section"]),
            content=document.page_content,
            source_uri=str(metadata["source_uri"]),
            retrieval_method=method,
            initial_rank=initial_rank,
            initial_score=round(score, 4),
            rerank_position=final_rank,
            rerank_score=round(score, 4),
            used_as_evidence=True,
        )

    def _hit_from_chunk(
        self,
        chunk: KnowledgeChunk,
        score: float,
        initial_rank: int,
        final_rank: int,
        method: str,
    ) -> RetrievalHit:
        return RetrievalHit(
            chunk_id=chunk.chunk_id,
            document_id=chunk.document_id,
            document_title=chunk.document_title,
            section=chunk.section,
            content=chunk.content,
            source_uri=chunk.source_uri,
            retrieval_method=method,
            initial_rank=initial_rank,
            initial_score=round(score, 4),
            rerank_position=final_rank,
            rerank_score=round(score, 4),
            used_as_evidence=True,
        )

    def _load_chunks(self) -> list[KnowledgeChunk]:
        path = Path(__file__).parent / "data" / "knowledge.json"
        raw_chunks = json.loads(path.read_text(encoding="utf-8"))
        return [
            KnowledgeChunk(
                chunk_id=item["chunk_id"],
                document_id=item["document_id"],
                document_title=item["document_title"],
                section=item["section"],
                content=item["content"],
                source_uri=item["source_uri"],
                categories=tuple(item["categories"]),
                keywords=tuple(item["keywords"]),
            )
            for item in raw_chunks
        ]

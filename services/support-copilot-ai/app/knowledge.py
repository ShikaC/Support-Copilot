import re

from openai import APITimeoutError, OpenAIError

from app.config import Settings
from app.errors import (
    EmbeddingApiError,
    embedding_timeout_error,
)
from app.knowledge_source import KnowledgeChunk, load_knowledge_chunks
from app.live_vector_index import LiveVectorIndex, RetrievalWindow
from app.models import RetrievalHit, TicketInput
from app.readiness import RuntimeDependencyReadiness


class KnowledgeRetriever:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._chunks = load_knowledge_chunks(
            settings.knowledge_path,
            settings.knowledge_provenance_path,
        )
        self._live_index = LiveVectorIndex(settings, tuple(self._chunks))
        self._readiness = RuntimeDependencyReadiness(
            provider_ready=settings.effective_mode == "mock" or settings.live_ready,
            index_ready=bool(self._chunks),
        )

    @property
    def chunk_count(self) -> int:
        return len(self._chunks)

    @property
    def readiness(self) -> RuntimeDependencyReadiness:
        return self._readiness

    async def search(
        self,
        ticket: TicketInput,
        query: str,
        top_n: int,
        top_k: int,
        live: bool,
    ) -> list[RetrievalHit]:
        # mock 模式使用确定性的本地打分器，方便演示和测试复现。
        # live 模式会构建 embedding，并使用向量检索。
        if live:
            try:
                hits = await self._live_index.search(
                    ticket,
                    query,
                    RetrievalWindow(top_n=top_n, top_k=top_k),
                )
            except APITimeoutError as exc:
                self._readiness.record_live_retrieval_failure()
                raise embedding_timeout_error(exc) from exc
            except OpenAIError as exc:
                self._readiness.record_live_retrieval_failure()
                raise EmbeddingApiError from exc
            self._readiness.record_live_retrieval_success()
            return hits
        return self._local_search(ticket, query, top_n, top_k)

    def _local_search(
        self,
        ticket: TicketInput,
        query: str,
        top_n: int,
        top_k: int,
    ) -> list[RetrievalHit]:
        known_categories = {
            category for chunk in self._chunks for category in chunk.categories
        }
        if (
            ticket.current_category != "UNCLASSIFIED"
            and ticket.current_category not in known_categories
        ):
            return []
        scored = [
            (chunk, self._local_candidate_score(chunk, query))
            for chunk in self._chunks
        ]
        scored.sort(key=lambda item: item[1], reverse=True)
        # 先按文本匹配召回 top_n，再用工单分类调整候选顺序并保留 top_k。
        candidates = [
            (chunk, score, initial_rank)
            for initial_rank, (chunk, score) in enumerate(scored, start=1)
            if self._local_final_score(chunk, ticket, score)
            >= self._settings.mock_retrieval_min_score
        ][:top_n]
        ranked = sorted(
            candidates,
            key=lambda item: self._local_final_score(item[0], ticket, item[1]),
            reverse=True,
        )[:top_k]

        return [
            self._hit_from_chunk(
                chunk,
                initial_score=initial_score,
                final_score=self._local_final_score(chunk, ticket, initial_score),
                initial_rank=initial_rank,
                final_rank=final_rank,
                method="HYBRID_DEMO",
            )
            for final_rank, (chunk, initial_score, initial_rank) in enumerate(
                ranked,
                start=1,
            )
        ]

    def _local_candidate_score(
        self,
        chunk: KnowledgeChunk,
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
        exact_bonus = min(0.35, exact_keyword_matches * 0.18)
        token_score = min(0.28, token_matches * 0.035)
        return min(0.99, 0.08 + exact_bonus + token_score)

    def _local_final_score(
        self,
        chunk: KnowledgeChunk,
        ticket: TicketInput,
        initial_score: float,
    ) -> float:
        category_bonus = 0.34 if ticket.current_category in chunk.categories else 0.0
        return min(0.99, initial_score + category_bonus)

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

    def _hit_from_chunk(
        self,
        chunk: KnowledgeChunk,
        initial_score: float,
        final_score: float,
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
            initial_score=round(initial_score, 4),
            rerank_position=final_rank,
            rerank_score=round(final_score, 4),
            used_as_evidence=True,
        )

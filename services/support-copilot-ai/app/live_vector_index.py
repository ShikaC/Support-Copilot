from dataclasses import dataclass
import logging

import anyio
import numpy as np

from app.config import Settings
from app.data_redaction import redact_sensitive_text
from app.embedding_artifact import EmbeddingArtifactError, EmbeddingArtifactStore, LoadedEmbeddingArtifact
from app.embedding_provider import EmbeddingProvider, OpenAIEmbeddingProvider
from app.knowledge_source import KnowledgeCorpus
from app.models import RetrievalHit, SupportScope, TicketInput

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RetrievalWindow:
    top_n: int
    top_k: int


class LiveVectorIndex:
    def __init__(self, settings: Settings, corpus: KnowledgeCorpus) -> None:
        self._settings = settings
        self._corpus = corpus
        self._store = EmbeddingArtifactStore(settings, corpus)
        self._provider: EmbeddingProvider | None = None
        self._artifact: LoadedEmbeddingArtifact | None = None
        self._load_lock = anyio.Lock()

    @property
    def artifact_store(self) -> EmbeddingArtifactStore:
        """进程内唯一的 artifact 存储：索引切换端点必须与检索用同一个实例与 root。"""
        return self._store

    async def search(
        self,
        ticket: TicketInput,
        query: str,
        window: RetrievalWindow,
        allowed_scopes: tuple[SupportScope, ...],
    ) -> list[RetrievalHit]:
        eligible_rows = self._eligible_rows(allowed_scopes)
        if not eligible_rows:
            return []
        artifact = await self._get_artifact()
        query_vector = np.asarray(
            await self._get_provider().embed_query(redact_sensitive_text(query)),
            dtype=np.float32,
        )
        if (
            query_vector.ndim != 1
            or query_vector.shape[0] != artifact.manifest.vector_dimension
            or not np.isfinite(query_vector).all()
        ):
            raise EmbeddingArtifactError("query-vector-invalid")
        scored = self._score_rows(artifact.matrix, query_vector, eligible_rows)
        candidates = [
            (row, score)
            for row, score in scored
            if score >= self._settings.live_retrieval_min_score
        ]
        if not candidates:
            logger.info(
                "retrieval.insufficient_evidence method=VECTOR best_score=%s min_score=%s",
                max((score for _, score in scored), default=None),
                self._settings.live_retrieval_min_score,
            )
            return []
        initial = sorted(candidates, key=lambda item: item[1], reverse=True)[
            : window.top_n
        ]
        category = ticket.current_category
        ranked = sorted(
            initial,
            key=lambda item: (
                category not in self._corpus.chunks[item[0]].categories,
                -item[1],
            ),
        )[: window.top_k]
        return [
            self._hit(row, score, rank)
            for rank, (row, score) in enumerate(ranked, start=1)
        ]

    def _eligible_rows(
        self,
        allowed_scopes: tuple[SupportScope, ...],
    ) -> tuple[int, ...]:
        scope_set = frozenset(allowed_scopes)
        return tuple(
            row
            for row, chunk in enumerate(self._corpus.chunks)
            if scope_set.intersection(chunk.allowed_scopes)
        )

    async def reload(self) -> LoadedEmbeddingArtifact:
        """只加载已准备的 active；失败保留缓存，绝不隐式构建或修改指针。"""
        async with self._load_lock:
            artifact = await anyio.to_thread.run_sync(self._store.load_active)
            self._artifact = artifact
            return artifact

    async def _get_artifact(self) -> LoadedEmbeddingArtifact:
        if self._artifact is not None:
            return self._artifact
        async with self._load_lock:
            if self._artifact is not None:
                return self._artifact
            try:
                artifact = self._store.load_active()
            except EmbeddingArtifactError as exc:
                if (
                    exc.reason != "active-pointer-invalid"
                    or self._settings.embedding_artifact_build_policy
                    != "build-if-missing"
                ):
                    raise
                manifest = await self._store.build(self._get_provider())
                self._store.activate(manifest.artifact_id)
                artifact = self._store.load_active()
            self._artifact = artifact
            return artifact

    def _get_provider(self) -> EmbeddingProvider:
        if self._provider is None:
            self._provider = OpenAIEmbeddingProvider(self._settings)
        return self._provider

    def _score_rows(
        self,
        matrix: np.ndarray,
        query: np.ndarray,
        rows: tuple[int, ...],
    ) -> list[tuple[int, float]]:
        eligible = matrix[np.asarray(rows)]
        denominators = np.linalg.norm(eligible, axis=1) * np.linalg.norm(query)
        scores = np.divide(
            eligible @ query,
            denominators,
            out=np.zeros(len(rows), dtype=np.float32),
            where=denominators != 0,
        )
        return [(row, float(score)) for row, score in zip(rows, scores, strict=True)]

    def _hit(self, row: int, score: float, rank: int) -> RetrievalHit:
        chunk = self._corpus.chunks[row]
        rounded = round(score, 4)
        return RetrievalHit(
            chunk_id=chunk.chunk_id,
            document_id=chunk.document_id,
            document_title=chunk.document_title,
            section=chunk.section,
            content=chunk.content,
            source_uri=chunk.source_uri,
            retrieval_method="VECTOR",
            initial_rank=rank,
            initial_score=rounded,
            rerank_position=rank,
            rerank_score=rounded,
            used_as_evidence=True,
        )

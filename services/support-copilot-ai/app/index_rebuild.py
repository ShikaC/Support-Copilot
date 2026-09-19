"""Durable task admission and execution for explicit index rebuilds."""

import logging
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Final, assert_never
from uuid import UUID, uuid4

import anyio
from anyio.abc import TaskGroup
from anyio.to_thread import run_sync
from openai import OpenAIError

from app.config import Settings
from app.embedding_artifact import EmbeddingArtifactError, EmbeddingArtifactStore
from app.index_rebuild_models import (
    FailureCode,
    RebuildError,
    RebuildRequest,
    RebuildStatus,
)
from app.index_rebuild_provider import (
    BATCH_SIZE,
    BatchedRebuildProvider,
    ProviderFactory,
    RebuildProgress,
    managed_embedding_provider,
)
from app.index_rebuild_source import select_rebuild_source
from app.index_rebuild_storage import RebuildStorage
from app.knowledge_source import KnowledgeCorpus

logger: Final = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class _PreparedRebuild:
    corpus: KnowledgeCorpus
    chunking_version: str
    progress: RebuildProgress
    ownership: ExitStack


class IndexRebuildManager:
    def __init__(
        self, settings: Settings, provider_factory: ProviderFactory | None = None
    ) -> None:
        self.settings: Settings = settings.model_copy(deep=True)
        self.storage: RebuildStorage = RebuildStorage(
            self.settings.embedding_artifact_root
        )
        self.provider_factory: ProviderFactory = (
            provider_factory or managed_embedding_provider
        )

    async def start(
        self, request: RebuildRequest, trace_id: str, task_group: TaskGroup
    ) -> RebuildStatus:
        """Persist admission before handing lock ownership to the lifespan worker."""
        # run_sync keeps cancellation shielded until preparation returns. Ownership
        # transfer below has no await, so cancellation cannot strand an acquired lock.
        prepared = await run_sync(self._prepare, request, trace_id)
        try:
            _ = task_group.start_soon(self._run, prepared)
        except RuntimeError as error:
            with prepared.ownership:
                self._fail(prepared.progress, "REBUILD_START_FAILED", error)
            raise RebuildError(
                503, "REBUILD_START_FAILED", "Rebuild worker could not start."
            ) from None
        return prepared.progress.status

    def _prepare(self, request: RebuildRequest, trace_id: str) -> _PreparedRebuild:
        settings = self.settings
        if (
            not settings.embedding_api_key
            or not settings.embedding_api_key.strip()
            or not settings.openai_embedding_model
            or not settings.openai_embedding_model.strip()
            or settings.embedding_vector_dimension is None
        ):
            raise RebuildError(
                409,
                "REBUILD_CONFIGURATION_INCOMPLETE",
                "Embedding configuration is incomplete.",
            )
        ownership = self.storage.acquire()
        if ownership is None:
            raise RebuildError(
                409, "REBUILD_ALREADY_RUNNING", "An index rebuild is already running."
            )
        with ownership:
            self.storage.recover()
            selected = select_rebuild_source(settings, request.corpus_build_task_id)
            corpus = selected.corpus
            if corpus.corpus_checksum != request.expected_corpus_checksum:
                raise RebuildError(
                    409,
                    "CORPUS_CHECKSUM_MISMATCH",
                    "Selected corpus differs from the authorized checksum.",
                )
            estimate = (len(corpus.chunks) + BATCH_SIZE - 1) // BATCH_SIZE
            if estimate > request.max_embedding_calls:
                raise RebuildError(
                    422,
                    "EMBEDDING_CALL_BUDGET_EXCEEDED",
                    "Embedding call estimate exceeds the authorized limit.",
                )
            now = datetime.now(timezone.utc)
            status = RebuildStatus(
                task_id=uuid4(),
                corpus_build_task_id=request.corpus_build_task_id,
                status="RUNNING",
                total_chunks=len(corpus.chunks),
                estimated_embedding_calls=estimate,
                max_embedding_calls=request.max_embedding_calls,
                corpus_checksum=corpus.corpus_checksum,
                trace_id=trace_id,
                started_at=now,
                updated_at=now,
            )
            self.storage.save(status)
            return _PreparedRebuild(
                corpus, selected.chunking_version,
                RebuildProgress(self.storage, status), ownership.pop_all()
            )

    async def get(self, task_id: UUID) -> RebuildStatus:
        return await run_sync(self._get, task_id)

    def _get(self, task_id: UUID) -> RebuildStatus:
        status = self.storage.read(task_id)
        match status.status:
            case "RUNNING":
                ownership = self.storage.acquire()
                if ownership is not None:
                    with ownership:
                        status = self.storage.recover_task(task_id)
            case "SUCCEEDED" | "FAILED":
                pass
            case unreachable:
                assert_never(unreachable)
        end = status.finished_at or datetime.now(timezone.utc)
        return status.model_copy(
            update={
                "elapsed_seconds": max(0.0, (end - status.started_at).total_seconds())
            }
        )

    async def _run(self, prepared: _PreparedRebuild) -> None:
        # Shielding keeps ownership until the thread truly stops, including shutdown.
        with anyio.CancelScope(shield=True):
            await run_sync(self._run_thread, prepared)

    def _run_thread(self, prepared: _PreparedRebuild) -> None:
        with prepared.ownership:
            try:
                anyio.run(self._build, prepared)
            except OpenAIError as error:
                self._fail(prepared.progress, "EMBEDDING_PROVIDER_FAILED", error)
            except EmbeddingArtifactError as error:
                self._fail(prepared.progress, "ARTIFACT_BUILD_FAILED", error)
            except (OSError, RebuildError) as error:
                self._fail(prepared.progress, "REBUILD_STORAGE_UNAVAILABLE", error)
            # This task boundary records unknown failures without hiding their type.
            except Exception as error:  # noqa: BROAD_EXCEPT_OK
                self._fail(prepared.progress, "REBUILD_INTERNAL_ERROR", error)

    async def _build(self, prepared: _PreparedRebuild) -> None:
        provider = BatchedRebuildProvider(
            self.settings, prepared.progress, self.provider_factory
        )
        build_settings = self.settings.model_copy(
            update={"embedding_chunking_version": prepared.chunking_version}
        )
        store = EmbeddingArtifactStore(build_settings, prepared.corpus)
        manifest = await store.build(
            provider,
            candidate_directory=self.storage.directory(prepared.progress.status.task_id)
            / "candidate",
        )
        prepared.progress.finish(manifest.artifact_id)

    def _fail(
        self, progress: RebuildProgress, code: FailureCode, error: Exception
    ) -> None:
        logger.error(
            "index_rebuild_failed",
            extra={
                "trace_id": progress.status.trace_id,
                "error_code": code,
                "error_type": type(error).__name__,
                "status": "FAILED",
            },
        )
        try:
            progress.finish(None, code)
        except RebuildError:
            logger.error(
                "index_rebuild_status_write_failed",
                extra={
                    "trace_id": progress.status.trace_id,
                    "error_code": "REBUILD_STORAGE_UNAVAILABLE",
                    "error_type": "RebuildError",
                    "status": "FAILED",
                },
            )

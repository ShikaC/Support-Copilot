"""Own one bounded, durable corpus generation task per configured local root."""

import logging
import shutil
import subprocess
from collections.abc import Callable
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from uuid import UUID, uuid4

import anyio
from anyio.abc import TaskGroup
from anyio.to_thread import run_sync

from app.config import Settings
from app.corpus_build_models import (
    CorpusBuildError,
    CorpusBuildRequest,
    CorpusBuildResult,
    CorpusBuildStatus,
    FailureCode,
)
from app.corpus_build_process import (
    GENERATOR,
    MAX_SOURCE_BYTES,
    CorpusBuildInput,
    build_corpus,
)
from app.corpus_build_storage import CorpusBuildStorage

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PreparedCorpusBuild:
    status: CorpusBuildStatus
    inputs: CorpusBuildInput
    ownership: ExitStack


class CorpusBuildManager:
    def __init__(
        self,
        settings: Settings,
        builder: Callable[[CorpusBuildInput], CorpusBuildResult] = build_corpus,
    ) -> None:
        self.settings: Settings = settings.model_copy(deep=True)
        self.storage: CorpusBuildStorage = CorpusBuildStorage(
            settings.knowledge_corpus_build_root.resolve()
        )
        self.builder: Callable[[CorpusBuildInput], CorpusBuildResult] = builder

    async def start(
        self, request: CorpusBuildRequest, trace_id: str, task_group: TaskGroup
    ) -> CorpusBuildStatus:
        prepared = await run_sync(self._prepare, request, trace_id)
        try:
            _ = task_group.start_soon(self._run, prepared)
        except RuntimeError:
            with prepared.ownership:
                self._finish(prepared.status, None, "CORPUS_BUILD_START_FAILED")
            raise CorpusBuildError(
                503, "CORPUS_BUILD_START_FAILED", "Corpus worker could not start."
            ) from None
        return prepared.status

    def _prepare(
        self, request: CorpusBuildRequest, trace_id: str
    ) -> PreparedCorpusBuild:
        source_path = self.settings.knowledge_corpus_source_path
        node = shutil.which(self.settings.knowledge_corpus_node_command)
        if source_path is None or node is None or not GENERATOR.is_file():
            raise CorpusBuildError(
                503,
                "CORPUS_CONFIGURATION_INCOMPLETE",
                "Corpus generator configuration is incomplete.",
            )
        lease = self.storage.acquire()
        if lease is None:
            raise CorpusBuildError(
                409,
                "CORPUS_BUILD_ALREADY_RUNNING",
                "A corpus build is already running.",
            )
        with lease.ownership:
            try:
                if not source_path.is_file():
                    raise CorpusBuildError(
                        409,
                        "CORPUS_SOURCE_INVALID",
                        "Configured document source is unavailable.",
                    )
                with source_path.open("rb") as stream:
                    source = stream.read(MAX_SOURCE_BYTES + 1)
            except OSError:
                raise CorpusBuildError(
                    409,
                    "CORPUS_SOURCE_INVALID",
                    "Configured document source is unavailable.",
                ) from None
            if not source or len(source) > MAX_SOURCE_BYTES:
                raise CorpusBuildError(
                    422,
                    "CORPUS_SOURCE_SIZE_EXCEEDED",
                    "Document source exceeds the size limit.",
                )
            if sha256(source).hexdigest() != request.expected_source_checksum:
                raise CorpusBuildError(
                    409,
                    "CORPUS_SOURCE_CHECKSUM_MISMATCH",
                    "Document source differs from the expected checksum.",
                )
            for path in self.storage.root.glob("*/status.json"):
                try:
                    previous_id = UUID(path.parent.name)
                except ValueError:
                    continue
                _ = self.storage.recover(previous_id)
            status = CorpusBuildStatus(
                task_id=uuid4(),
                request=request,
                trace_id=trace_id,
                started_at=datetime.now(timezone.utc),
            )
            self.storage.save(status)
            return PreparedCorpusBuild(
                status,
                CorpusBuildInput(
                    source,
                    request,
                    self.storage.directory(status.task_id),
                    str(Path(node).resolve()),
                    self.settings.knowledge_corpus_build_timeout_seconds,
                    lease.descriptor,
                ),
                lease.ownership.pop_all(),
            )

    async def get(self, task_id: UUID) -> CorpusBuildStatus:
        return await run_sync(self._get, task_id)

    def _get(self, task_id: UUID) -> CorpusBuildStatus:
        status = self.storage.read(task_id)
        if status.finished_at is None:
            lease = self.storage.acquire()
            if lease is not None:
                with lease.ownership:
                    status = self.storage.recover(task_id)
        end = status.finished_at or datetime.now(timezone.utc)
        return status.model_copy(
            update={
                "elapsed_seconds": max(0.0, (end - status.started_at).total_seconds())
            }
        )

    async def _run(self, prepared: PreparedCorpusBuild) -> None:
        # Keep the lock until the Node child has exited and terminal status is durable.
        with anyio.CancelScope(shield=True):
            await run_sync(self._run_thread, prepared)

    def _run_thread(self, prepared: PreparedCorpusBuild) -> None:
        with prepared.ownership:
            try:
                result = self.builder(prepared.inputs)
                self._finish(prepared.status, result, None)
            except subprocess.TimeoutExpired:
                self._finish(prepared.status, None, "CORPUS_BUILD_TIMEOUT")
            except CorpusBuildError as error:
                failures: dict[str, FailureCode] = {
                    "CORPUS_BUILD_TIMEOUT": "CORPUS_BUILD_TIMEOUT",
                    "CORPUS_PROCESS_FAILED": "CORPUS_PROCESS_FAILED",
                    "CORPUS_RESULT_INVALID": "CORPUS_RESULT_INVALID",
                    "CORPUS_STORAGE_UNAVAILABLE": "CORPUS_STORAGE_UNAVAILABLE",
                }
                code = failures.get(error.code, "CORPUS_INTERNAL_ERROR")
                self._finish(prepared.status, None, code)
            except OSError:
                self._finish(prepared.status, None, "CORPUS_STORAGE_UNAVAILABLE")
            except Exception as error:  # noqa: BROAD_EXCEPT_OK
                logger.error(
                    "corpus_build_failed",
                    extra={
                        "trace_id": prepared.status.trace_id,
                        "error_type": type(error).__name__,
                        "error_code": "CORPUS_INTERNAL_ERROR",
                    },
                )
                self._finish(prepared.status, None, "CORPUS_INTERNAL_ERROR")

    def _finish(
        self,
        status: CorpusBuildStatus,
        result: CorpusBuildResult | None,
        failure_code: FailureCode | None,
    ) -> None:
        now = datetime.now(timezone.utc)
        terminal = status.model_copy(
            update={
                "status": "SUCCEEDED" if result is not None else "FAILED",
                "result": result,
                "failure_code": failure_code,
                "finished_at": now,
                "elapsed_seconds": max(0.0, (now - status.started_at).total_seconds()),
            }
        )
        try:
            self.storage.save(terminal)
        except CorpusBuildError:
            logger.error(
                "corpus_status_write_failed",
                extra={
                    "trace_id": status.trace_id,
                    "error_code": "CORPUS_STORAGE_UNAVAILABLE",
                },
            )

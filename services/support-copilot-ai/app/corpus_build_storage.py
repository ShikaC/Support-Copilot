"""Local task ownership and durable records for corpus candidates."""

import fcntl
import os
import tempfile
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from pydantic import ValidationError

from app.corpus_build_models import CorpusBuildError, CorpusBuildStatus
from app.embedding_artifact_identity import fsync_directory


@dataclass(frozen=True, slots=True)
class CorpusBuildLease:
    ownership: ExitStack
    descriptor: int


class CorpusBuildStorage:
    def __init__(self, root: Path) -> None:
        self.root: Path = root

    def directory(self, task_id: UUID) -> Path:
        return self.root / str(task_id)

    def acquire(self) -> CorpusBuildLease | None:
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            with ExitStack() as ownership:
                stream = ownership.enter_context((self.root / "build.lock").open("a+b"))
                try:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    return None
                return CorpusBuildLease(ownership.pop_all(), stream.fileno())
        except OSError:
            raise self.unavailable() from None

    def save(self, status: CorpusBuildStatus) -> None:
        directory = self.directory(status.task_id)
        try:
            directory.mkdir(exist_ok=True)
            fsync_directory(self.root.parent)
            fsync_directory(self.root)
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=directory,
                prefix=".status-",
                delete=False,
            ) as stream:
                _ = stream.write(status.model_dump_json(by_alias=True) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
                temporary = stream.name
            os.replace(temporary, directory / "status.json")
            fsync_directory(directory)
        except OSError:
            raise self.unavailable() from None

    def read(self, task_id: UUID) -> CorpusBuildStatus:
        try:
            record = CorpusBuildStatus.model_validate_json(
                (self.directory(task_id) / "status.json").read_bytes()
            )
        except FileNotFoundError:
            raise CorpusBuildError(
                404, "CORPUS_TASK_NOT_FOUND", "Corpus task was not found."
            ) from None
        except (OSError, ValidationError):
            raise self.unavailable() from None
        if record.task_id != task_id:
            raise self.unavailable()
        return record

    def recover(self, task_id: UUID) -> CorpusBuildStatus:
        record = self.read(task_id)
        if record.finished_at is None:
            now = datetime.now(timezone.utc)
            record = record.model_copy(
                update={
                    "status": "FAILED",
                    "failure_code": "CORPUS_BUILD_INTERRUPTED",
                    "finished_at": now,
                    "elapsed_seconds": max(
                        0.0, (now - record.started_at).total_seconds()
                    ),
                }
            )
            self.save(record)
        return record

    @staticmethod
    def unavailable() -> CorpusBuildError:
        return CorpusBuildError(
            503, "CORPUS_STORAGE_UNAVAILABLE", "Corpus task storage is unavailable."
        )

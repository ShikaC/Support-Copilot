"""Filesystem ownership and atomic status persistence for local rebuild tasks."""

import fcntl
import os
import tempfile
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from typing import assert_never
from uuid import UUID

from pydantic import ValidationError

from app.embedding_artifact_identity import fsync_directory
from app.index_rebuild_models import RebuildError, RebuildStatus


class RebuildStorage:
    def __init__(self, artifact_root: Path) -> None:
        self.root: Path = artifact_root / ".rebuild-tasks"

    def acquire(self) -> ExitStack | None:
        """Return owned flock lifetime; None means another API rebuild owns it."""
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            with ExitStack() as resources:
                lock = resources.enter_context((self.root / "rebuild.lock").open("a+b"))
                try:
                    fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    return None
                return resources.pop_all()
        except OSError:
            raise self.unavailable() from None

    def directory(self, task_id: UUID) -> Path:
        return self.root / str(task_id)

    def save(self, status: RebuildStatus) -> None:
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

    def read(self, task_id: UUID) -> RebuildStatus:
        try:
            status = RebuildStatus.model_validate_json(
                (self.directory(task_id) / "status.json").read_bytes()
            )
        except FileNotFoundError:
            raise RebuildError(
                404, "REBUILD_TASK_NOT_FOUND", "Rebuild task was not found."
            ) from None
        except (OSError, ValidationError):
            raise self.unavailable() from None
        if status.task_id != task_id:
            raise self.unavailable()
        return status

    def recover(self) -> None:
        """Caller must own flock, proving no API worker can still write a status."""
        try:
            for path in self.root.glob("*/status.json"):
                try:
                    task_id = UUID(path.parent.name)
                except ValueError:
                    continue
                _ = self.recover_task(task_id)
        except OSError:
            raise self.unavailable() from None

    def recover_task(self, task_id: UUID) -> RebuildStatus:
        status = self.read(task_id)
        match status.status:
            case "RUNNING":
                now = datetime.now(timezone.utc)
                status = status.model_copy(
                    update={
                        "status": "FAILED",
                        "failure_code": "REBUILD_INTERRUPTED",
                        "updated_at": now,
                        "finished_at": now,
                        "elapsed_seconds": max(
                            0.0, (now - status.started_at).total_seconds()
                        ),
                    }
                )
                self.save(status)
            case "SUCCEEDED" | "FAILED":
                pass
            case unreachable:
                assert_never(unreachable)
        return status

    @staticmethod
    def unavailable() -> RebuildError:
        return RebuildError(
            503, "REBUILD_STORAGE_UNAVAILABLE", "Rebuild status storage is unavailable."
        )

# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Hold H2-compatible POSIX locks throughout offline database file operations.

Run through scripts/workspace-data.sh, which owns path and manifest validation.
This helper requires Python 3.11+ on a local POSIX filesystem.
"""

from __future__ import annotations

import errno
import fcntl
import hashlib
import os
import shutil
import stat
import sys
import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO


class WorkspaceDataError(RuntimeError):
    """An offline operation cannot safely access the requested database."""


@contextmanager
def database_lock(path: Path) -> Generator[BinaryIO]:
    """Keep one descriptor open: closing a second descriptor can drop POSIX locks."""
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "r+b") as database:
        if not stat.S_ISREG(os.fstat(database.fileno()).st_mode):
            raise WorkspaceDataError(f"Database is not a regular file: {path}")
        try:
            fcntl.lockf(database, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            if error.errno in (errno.EACCES, errno.EAGAIN):
                raise WorkspaceDataError(
                    "Database is locked by another process; no files were copied or replaced."
                ) from error
            raise
        identity = os.fstat(database.fileno())
        if (identity.st_dev, identity.st_ino) != (
            path.stat().st_dev,
            path.stat().st_ino,
        ):
            raise WorkspaceDataError("Database path changed while acquiring its lock.")
        try:
            yield database
        finally:
            if (
                identity.st_size == 0
                and path.exists()
                and path.stat().st_ino == identity.st_ino
            ):
                path.unlink()


def sync_directory(path: Path) -> None:
    """Persist a completed rename before releasing database locks."""
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def snapshot(database: BinaryIO, backup_root: Path, prefix: str) -> Path:
    """Copy exclusively through the locked descriptor, then publish the snapshot."""
    pending = Path(tempfile.mkdtemp(prefix=".pending-", dir=backup_root))
    try:
        _ = database.seek(0)
        with (pending / "support-copilot.mv.db").open("xb") as output:
            shutil.copyfileobj(database, output)
            output.flush()
            os.fsync(output.fileno())
        with (pending / "support-copilot.mv.db").open("rb") as saved:
            digest = hashlib.file_digest(saved, "sha256").hexdigest()
        with (pending / "SHA256SUMS").open("x") as manifest:
            _ = manifest.write(f"{digest}  support-copilot.mv.db\n")
            manifest.flush()
            os.fsync(manifest.fileno())
        destination = (
            backup_root
            / f"{prefix}-{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{pending.name[9:]}"
        )
        sync_directory(pending)
        os.replace(pending, destination)
        sync_directory(backup_root)
        return destination
    finally:
        if pending.exists():
            shutil.rmtree(pending)


def backup(path: Path, backup_root: Path) -> Path:
    """Back up a stopped H2 database while excluding independent H2 openers."""
    with database_lock(path) as database:
        if os.fstat(database.fileno()).st_size == 0:
            raise WorkspaceDataError("No persistent workspace database exists yet.")
        return snapshot(database, backup_root, "backup")


def restore(path: Path, source: Path, expected_digest: str) -> Path | None:
    """Lock both old and replacement inodes through copy, fsync, and replacement."""
    with database_lock(path) as database:
        source_identity = source.stat(follow_symlinks=False)
        if not stat.S_ISREG(source_identity.st_mode) or source_identity.st_nlink != 1:
            raise WorkspaceDataError(
                "Backup source must be a regular file without hard links."
            )
        with tempfile.NamedTemporaryFile(
            mode="w+b", prefix=".restore-", dir=path.parent, delete=False
        ) as replacement:
            temporary = Path(replacement.name)
            try:
                fcntl.lockf(replacement, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with source.open("rb") as saved:
                    if os.fstat(saved.fileno()).st_ino != source_identity.st_ino:
                        raise WorkspaceDataError("Backup source changed before copy.")
                    shutil.copyfileobj(saved, replacement)
                replacement.flush()
                _ = replacement.seek(0)
                digest = hashlib.sha256()
                while chunk := replacement.read(1024 * 1024):
                    digest.update(chunk)
                if digest.hexdigest() != expected_digest:
                    raise WorkspaceDataError(
                        "Backup checksum changed; database was not replaced."
                    )
                os.fsync(replacement.fileno())
                previous = (
                    snapshot(database, path.parent.parent / "backups", "before-restore")
                    if os.fstat(database.fileno()).st_size
                    else None
                )
                os.replace(temporary, path)
                sync_directory(path.parent)
                return previous
            finally:
                temporary.unlink(missing_ok=True)


def main(arguments: list[str]) -> int:
    """Internal CLI; the shell entry point supplies validated fixed workspace paths."""
    try:
        match arguments:
            case ["backup", database, backup_root]:
                print(backup(Path(database), Path(backup_root)))
            case ["restore", database, source, digest]:
                previous = restore(Path(database), Path(source), digest)
                if previous is not None:
                    print(f"Preserved previous database:\n{previous}")
                print(
                    f"Restored {Path(source).parent}. Start ./scripts/dev-workspace.sh to validate migrations."
                )
            case _:
                raise WorkspaceDataError(
                    "Internal usage: backup <db> <backup-root> | restore <db> <source-file> <sha256>"
                )
    except (WorkspaceDataError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

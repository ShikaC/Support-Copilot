"""Exercise OS locks at actual file-copy and atomic-replacement boundaries."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

import pytest

from scripts import workspace_data as storage


@dataclass(frozen=True, slots=True)
class Workspace:
    database: Path
    backups: Path


@pytest.fixture
def workspace(tmp_path: Path) -> Workspace:
    data = tmp_path / "data"
    data.mkdir()
    backups = tmp_path / "backups"
    backups.mkdir()
    database = data / "support-copilot.mv.db"
    _ = database.write_bytes(b"original database")
    return Workspace(database, backups)


def independent_lock_attempt(path: Path) -> int:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import fcntl,sys; f=open(sys.argv[1],'r+b');\n"
                "try: fcntl.lockf(f,fcntl.LOCK_EX|fcntl.LOCK_NB)\n"
                "except BlockingIOError: sys.exit(73)\n"
            ),
            str(path),
        ],
        check=False,
        capture_output=True,
        timeout=5,
    )
    return result.returncode


def test_backup_excludes_independent_opener_after_preflight(
    workspace: Workspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    copy = shutil.copyfileobj
    attempts: list[int] = []

    def copy_while_opener_starts(source: BinaryIO, destination: BinaryIO) -> None:
        attempts.append(independent_lock_attempt(workspace.database))
        copy(source, destination)

    monkeypatch.setattr(shutil, "copyfileobj", copy_while_opener_starts)
    saved = storage.backup(workspace.database, workspace.backups)
    assert attempts == [73]
    assert (saved / "support-copilot.mv.db").read_bytes() == b"original database"
    assert independent_lock_attempt(workspace.database) == 0


def test_restore_locks_old_and_new_inodes_through_replacement(
    workspace: Workspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    saved = storage.backup(workspace.database, workspace.backups)
    source = saved / "support-copilot.mv.db"
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    _ = workspace.database.write_bytes(b"state after backup")
    copy = shutil.copyfileobj
    replace = os.replace
    attempts: list[int] = []

    def copy_while_opener_starts(source_file: BinaryIO, destination: BinaryIO) -> None:
        attempts.append(independent_lock_attempt(workspace.database))
        copy(source_file, destination)

    def replace_while_opener_starts(source_file: Path, destination: Path) -> None:
        if destination == workspace.database:
            attempts.append(independent_lock_attempt(workspace.database))
            replace(source_file, destination)
            attempts.append(independent_lock_attempt(workspace.database))
        else:
            replace(source_file, destination)

    monkeypatch.setattr(shutil, "copyfileobj", copy_while_opener_starts)
    monkeypatch.setattr(os, "replace", replace_while_opener_starts)
    previous = storage.restore(workspace.database, source, digest)
    assert attempts == [73, 73, 73, 73]
    assert workspace.database.read_bytes() == b"original database"
    assert previous is not None
    assert (previous / "support-copilot.mv.db").read_bytes() == b"state after backup"
    assert independent_lock_attempt(workspace.database) == 0


def test_locked_database_refuses_before_any_copy(workspace: Workspace) -> None:
    with subprocess.Popen(
        [
            sys.executable,
            "-u",
            "-c",
            (
                "import fcntl,sys; f=open(sys.argv[1],'r+b'); "
                "fcntl.lockf(f,fcntl.LOCK_EX); print('locked'); sys.stdin.readline()"
            ),
            str(workspace.database),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    ) as owner:
        assert owner.stdout is not None
        assert owner.stdout.readline() == "locked\n"
        try:
            with pytest.raises(
                storage.WorkspaceDataError, match="locked by another process"
            ):
                _ = storage.backup(workspace.database, workspace.backups)
            assert list(workspace.backups.iterdir()) == []
        finally:
            _ = owner.communicate("release\n", timeout=5)
    assert workspace.database.read_bytes() == b"original database"

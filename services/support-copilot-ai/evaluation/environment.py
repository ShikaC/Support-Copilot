from __future__ import annotations

import hashlib
import platform
import subprocess
from pathlib import Path

from evaluation.models import EvaluationEnvironment


def capture_environment(
    dataset_path: Path,
    knowledge_path: Path,
) -> EvaluationEnvironment:
    return EvaluationEnvironment(
        git_commit=_git_commit(),
        worktree_dirty=_worktree_dirty(),
        python_version=platform.python_version(),
        java_version=_command_version(("java", "-version")),
        node_version=_command_version(("node", "--version")),
        dataset_sha256=_sha256(dataset_path),
        knowledge_sha256=_sha256(knowledge_path),
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_commit() -> str:
    try:
        result = subprocess.run(
            ("git", "rev-parse", "HEAD"),
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return result.stdout.strip()


def _worktree_dirty() -> bool:
    try:
        result = subprocess.run(
            ("git", "status", "--porcelain"),
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return True
    return bool(result.stdout.strip())


def _command_version(command: tuple[str, ...]) -> str | None:
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    output = f"{result.stdout}\n{result.stderr}".strip().splitlines()
    return output[0] if output else None

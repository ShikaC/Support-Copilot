"""A dead Python owner must not free admission while its Node builder still runs."""

import os
import shutil
import signal
import subprocess
import sys
from contextlib import suppress
from hashlib import sha256
from pathlib import Path
from threading import Event
from time import monotonic
from typing import Final
from uuid import UUID

import app.corpus_build_process as process_module
from app.config import Settings
from app.corpus_build import CorpusBuildManager
from app.corpus_build_models import CorpusBuildRequest

SERVICE: Final = Path(__file__).resolve().parents[1]


def run_owner(directory: Path) -> None:
    """Use the real manager/adapter with a copied generator blocked during parsing."""
    setattr(process_module, "GENERATOR", directory / "build-corpus.mjs")
    source = directory / "source.json"
    manager = CorpusBuildManager(
        Settings(
            knowledge_corpus_source_path=source,
            knowledge_corpus_build_root=directory / "builds",
            knowledge_corpus_build_timeout_seconds=2,
            _env_file=None,
        )
    )
    prepared = manager._prepare(
        CorpusBuildRequest(
            expectedSourceChecksum=sha256(source.read_bytes()).hexdigest(),
            window=4,
            stride=3,
        ),
        "parent-death-test",
    )
    manager._run_thread(prepared)


def test_parent_death_keeps_lock_until_node_deadline_then_recovers(
    tmp_path: Path,
) -> None:
    # Given the actual Node entry with a deterministic synchronous hang in its parser.
    script = process_module.GENERATOR.read_text()
    original = "const source = fs.readFileSync(0);"
    assert original in script
    blocked = (
        "fs.writeFileSync(path.join(output, 'pid'), String(process.pid)); "
        "Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0); " + original
    )
    (tmp_path / "build-corpus.mjs").write_text(script.replace(original, blocked))
    (tmp_path / "doc2dial-corpus.mjs").write_bytes(
        (process_module.GENERATOR.parent / "doc2dial-corpus.mjs").read_bytes()
    )
    (tmp_path / "source.json").write_text('{"doc_data":{}}')
    # Resolve Node from the invoking test environment, without passing its credentials.
    node = shutil.which("node")
    assert node is not None
    environment = {
        "PYTHONPATH": str(SERVICE),
        "PATH": os.defpath,
        "KNOWLEDGE_CORPUS_NODE_COMMAND": node,
    }
    with (tmp_path / "owner.log").open("w") as log:
        owner = subprocess.Popen(
            [
                sys.executable,
                "-c",
                "from pathlib import Path; import sys; "
                "from tests.test_corpus_build_parent_death import run_owner; run_owner(Path(sys.argv[1]))",
                str(tmp_path),
            ],
            cwd=tmp_path,
            env=environment,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            deadline = monotonic() + 10
            while not (pids := list((tmp_path / "builds").glob("*/candidate/pid"))):
                assert owner.poll() is None, (tmp_path / "owner.log").read_text()
                assert monotonic() < deadline
                Event().wait(0.02)
            task_id = UUID(pids[0].parents[1].name)
            child_pid = int(pids[0].read_text())
            # When Python dies, Node must still exclude another builder on the root.
            owner.kill()
            owner.wait(timeout=5)
            os.kill(child_pid, 0)
            manager = CorpusBuildManager(
                Settings(
                    knowledge_corpus_build_root=tmp_path / "builds", _env_file=None
                )
            )
            lease = manager.storage.acquire()
            if lease is not None:
                with lease.ownership:
                    raise AssertionError(
                        "Node survived its Python owner but the build lock was released"
                    )
            # Then Node's own deadline frees ownership, and recovery persists failure.
            deadline = monotonic() + 6
            while manager._get(task_id).finished_at is None:
                assert monotonic() < deadline, (
                    "Node remained unbounded after Python died"
                )
                Event().wait(0.02)
            status = manager._get(task_id)
            assert status.failure_code == "CORPUS_BUILD_INTERRUPTED"
            assert not (tmp_path / "builds" / str(task_id) / "result").exists()
        finally:
            with suppress(ProcessLookupError):
                os.killpg(owner.pid, signal.SIGKILL)
            owner.wait(timeout=5)

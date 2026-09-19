"""Run the repository's fixed Node generator without shell or inherited credentials."""

import os
import subprocess
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Final

from pydantic import ValidationError

from app.corpus_build_models import (
    CorpusBuildError,
    CorpusBuildRequest,
    CorpusBuildResult,
)
from app.embedding_artifact_identity import fsync_directory
from app.knowledge_source import KnowledgeCorpus

GENERATOR: Final = (
    Path(__file__).resolve().parents[1] / "knowledge-tools" / "build-corpus.mjs"
)
MAX_SOURCE_BYTES: Final = 64 * 1024 * 1024
MAX_RESULT_BYTES: Final = 64 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class CorpusBuildInput:
    source: bytes
    request: CorpusBuildRequest
    directory: Path
    node: str
    timeout_seconds: float
    lock_descriptor: int


def build_corpus(inputs: CorpusBuildInput) -> CorpusBuildResult:
    candidate = inputs.directory / "candidate"
    candidate.mkdir()
    request = inputs.request
    # run() kills and reaps this fixed, non-spawning Node child on timeout.
    completed = subprocess.run(
        [
            inputs.node,
            "--max-old-space-size=512",
            str(GENERATOR),
            str(request.window),
            str(request.stride),
            str(candidate),
            str(inputs.timeout_seconds),
        ],
        input=inputs.source,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=candidate,
        env={"LANG": "C.UTF-8"},
        timeout=inputs.timeout_seconds,
        check=False,
        pass_fds=(inputs.lock_descriptor,),
    )
    if completed.returncode == 124:
        raise CorpusBuildError(
            500, "CORPUS_BUILD_TIMEOUT", "Corpus generator timed out."
        )
    if completed.returncode != 0:
        raise CorpusBuildError(500, "CORPUS_PROCESS_FAILED", "Corpus generator failed.")
    try:
        with (candidate / "corpus.json").open("rb") as stream:
            content = stream.read(MAX_RESULT_BYTES + 1)
        if len(content) > MAX_RESULT_BYTES:
            raise CorpusBuildError(
                500, "CORPUS_RESULT_INVALID", "Generated corpus is invalid."
            )
        corpus = KnowledgeCorpus.model_validate_json(content)
        result = CorpusBuildResult.model_validate_json(
            (candidate / "manifest.json").read_bytes()
        )
        if (
            result.source_checksum != request.expected_source_checksum
            or result.corpus_checksum != corpus.corpus_checksum
            or result.corpus_file_checksum != sha256(content).hexdigest()
            or result.chunk_count != len(corpus.chunks)
            or result.window != request.window
            or result.stride != request.stride
        ):
            raise CorpusBuildError(
                500, "CORPUS_RESULT_INVALID", "Generated corpus is invalid."
            )
    except ValidationError:
        raise CorpusBuildError(
            500, "CORPUS_RESULT_INVALID", "Generated corpus is invalid."
        ) from None
    for file in candidate.iterdir():
        with file.open("rb") as stream:
            os.fsync(stream.fileno())
    fsync_directory(candidate)
    _ = candidate.rename(inputs.directory / "result")
    fsync_directory(inputs.directory)
    return result

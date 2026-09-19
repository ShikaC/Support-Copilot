"""Select a configured corpus or an immutable verified corpus-task result."""

from dataclasses import dataclass
from hashlib import sha256
from uuid import UUID

from pydantic import ValidationError

from app.config import Settings
from app.corpus_build_process import MAX_RESULT_BYTES
from app.corpus_build_storage import CorpusBuildStorage
from app.index_rebuild_models import RebuildError
from app.knowledge_source import (
    KnowledgeCorpus,
    KnowledgeSourceInvalidError,
    load_knowledge_corpus,
)


@dataclass(frozen=True, slots=True)
class RebuildSource:
    corpus: KnowledgeCorpus
    chunking_version: str


def select_rebuild_source(settings: Settings, task_id: UUID | None) -> RebuildSource:
    if task_id is None:
        try:
            corpus = load_knowledge_corpus(
                settings.knowledge_path, settings.knowledge_provenance_path
            )
        except KnowledgeSourceInvalidError:
            raise RebuildError(
                409,
                "KNOWLEDGE_SOURCE_INVALID",
                "Configured knowledge corpus is unavailable.",
            ) from None
        return RebuildSource(corpus, settings.embedding_chunking_version)

    storage = CorpusBuildStorage(settings.knowledge_corpus_build_root.resolve())
    status = storage.read(task_id)
    result = status.result
    # CorpusBuildStatus permits a result only in a coherent SUCCEEDED record.
    if result is None:
        raise RebuildError(
            409, "CORPUS_CANDIDATE_NOT_READY", "Corpus candidate has not succeeded."
        )
    try:
        # Match B1's per-file limit; parse exactly the bytes whose digest we verified.
        with (storage.directory(task_id) / "result" / "corpus.json").open(
            "rb"
        ) as stream:
            content = stream.read(MAX_RESULT_BYTES + 1)
        if (
            len(content) > MAX_RESULT_BYTES
            or sha256(content).hexdigest() != result.corpus_file_checksum
        ):
            raise RebuildError(
                409,
                "CORPUS_CANDIDATE_INVALID",
                "Corpus candidate differs from its saved result.",
            )
        corpus = KnowledgeCorpus.model_validate_json(content)
    except (OSError, ValidationError):
        raise RebuildError(
            409,
            "CORPUS_CANDIDATE_INVALID",
            "Corpus candidate is unavailable or invalid.",
        ) from None
    if (
        corpus.corpus_checksum != result.corpus_checksum
        or len(corpus.chunks) != result.chunk_count
    ):
        raise RebuildError(
            409,
            "CORPUS_CANDIDATE_INVALID",
            "Corpus candidate differs from its saved result.",
        )
    return RebuildSource(
        corpus, f"doc2dial-codepoints-{result.window}-{result.stride}-v1"
    )

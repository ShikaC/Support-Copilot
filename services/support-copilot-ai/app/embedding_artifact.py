from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

import anyio
import numpy as np
from pydantic import ValidationError

from app.config import Settings
from app.data_redaction import redact_sensitive_text
from app.embedding_artifact_models import (
    ActiveArtifactPointer,
    ArtifactChunkMetadata,
    ArtifactDocumentRecord,
    EmbeddingArtifactManifest,
)
from app.embedding_artifact_identity import (
    canonical_bytes,
    chunk_checksum,
    file_checksum,
    fsync_directory,
    provider_identity,
)
from app.embedding_provider import EmbeddingProvider
from app.knowledge_source import KnowledgeChunk, KnowledgeCorpus


class EmbeddingArtifactError(RuntimeError):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"Embedding artifact unavailable: {reason}")


@dataclass(frozen=True, slots=True)
class LoadedEmbeddingArtifact:
    manifest: EmbeddingArtifactManifest
    matrix: np.ndarray
    metadata: tuple[ArtifactChunkMetadata, ...]


class EmbeddingArtifactStore:
    def __init__(self, settings: Settings, corpus: KnowledgeCorpus) -> None:
        self._root = settings.embedding_artifact_root
        self._pointer = self._root / settings.embedding_artifact_pointer
        self._provider_identity = provider_identity(settings.embedding_base_url)
        self._model = settings.openai_embedding_model or "unconfigured"
        self._chunking_version = settings.embedding_chunking_version
        self._expected_dimension = settings.embedding_vector_dimension
        self._corpus = corpus
        self._build_lock = anyio.Lock()

    async def build(self, provider: EmbeddingProvider) -> EmbeddingArtifactManifest:
        dimension = self._expected_dimension
        if dimension is None:
            raise EmbeddingArtifactError("embedding-dimension-required")
        metadata = tuple(
            ArtifactChunkMetadata(
                row=row,
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                content_checksum=chunk_checksum(chunk),
                categories=chunk.categories,
                allowed_scopes=chunk.allowed_scopes,
            )
            for row, chunk in enumerate(self._corpus.chunks)
        )
        documents = self._document_records(metadata)
        artifact_id = self._artifact_id(dimension, metadata, documents)
        final_path = self._root / artifact_id
        if final_path.exists():
            return self.load(artifact_id).manifest

        async with self._build_lock:
            if final_path.exists():
                return self.load(artifact_id).manifest
            texts = [redact_sensitive_text(chunk.content) for chunk in self._corpus.chunks]
            matrix = np.asarray(await provider.embed_documents(texts), dtype=np.float32)
            if matrix.ndim != 2 or matrix.shape[0] != len(texts) or matrix.shape[1] == 0:
                raise EmbeddingArtifactError("provider-shape-mismatch")
            if not np.isfinite(matrix).all():
                raise EmbeddingArtifactError("provider-non-finite-vector")
            if matrix.shape[1] != dimension:
                raise EmbeddingArtifactError("provider-dimension-mismatch")
            self._root.mkdir(parents=True, exist_ok=True)
            temporary = Path(tempfile.mkdtemp(prefix=".candidate-", dir=self._root))
            try:
                matrix_path = temporary / "matrix.npy"
                with matrix_path.open("wb") as stream:
                    np.save(stream, matrix, allow_pickle=False)
                    stream.flush()
                    os.fsync(stream.fileno())
                metadata_path = temporary / "metadata.json"
                self._write_bytes(metadata_path, self._metadata_bytes(metadata))
                manifest = EmbeddingArtifactManifest(
                    schema_version=1,
                    artifact_id=artifact_id,
                    release_id=self._corpus.release_id,
                    release_version=self._corpus.release_version,
                    corpus_checksum=self._corpus.corpus_checksum,
                    provider_identity=self._provider_identity,
                    embedding_model=self._model,
                    vector_dimension=matrix.shape[1],
                    chunking_version=self._chunking_version,
                    row_count=matrix.shape[0],
                    matrix_sha256=file_checksum(matrix_path),
                    metadata_sha256=file_checksum(metadata_path),
                    documents=documents,
                )
                self._write_bytes(
                    temporary / "manifest.json",
                    (manifest.model_dump_json(indent=2) + "\n").encode(),
                )
                self._verify_path(temporary, artifact_id)
                try:
                    os.replace(temporary, final_path)
                except OSError:
                    if not final_path.exists():
                        raise
                    return self.load(artifact_id).manifest
                fsync_directory(self._root)
                return manifest
            finally:
                if temporary.exists():
                    shutil.rmtree(temporary)

    def load_active(self) -> LoadedEmbeddingArtifact:
        pointer = self._load_pointer()
        return self.load(pointer.active_artifact_id)

    def load(self, artifact_id: str) -> LoadedEmbeddingArtifact:
        if re.fullmatch(r"[a-f0-9]{64}", artifact_id) is None:
            raise EmbeddingArtifactError("artifact-id-invalid")
        return self._verify_path(self._root / artifact_id, artifact_id)

    def activate(self, artifact_id: str) -> ActiveArtifactPointer:
        self.load(artifact_id)
        previous = None
        if self._pointer.exists():
            current = self._load_pointer()
            if current.active_artifact_id == artifact_id:
                return current
            previous = current.active_artifact_id
        pointer = ActiveArtifactPointer(
            schema_version=1,
            active_artifact_id=artifact_id,
            previous_artifact_id=previous if previous != artifact_id else None,
        )
        self._atomic_pointer(pointer)
        return pointer

    def rollback(self) -> ActiveArtifactPointer:
        current = self._load_pointer()
        previous = current.previous_artifact_id
        if previous is None:
            raise EmbeddingArtifactError("previous-artifact-missing")
        self.load(previous)
        pointer = ActiveArtifactPointer(
            schema_version=1,
            active_artifact_id=previous,
            previous_artifact_id=current.active_artifact_id,
        )
        self._atomic_pointer(pointer)
        return pointer

    def _verify_path(self, path: Path, artifact_id: str) -> LoadedEmbeddingArtifact:
        try:
            manifest = EmbeddingArtifactManifest.model_validate_json(
                (path / "manifest.json").read_text(encoding="utf-8")
            )
            metadata = tuple(
                ArtifactChunkMetadata.model_validate(item)
                for item in json.loads((path / "metadata.json").read_text(encoding="utf-8"))
            )
            with (path / "matrix.npy").open("rb") as stream:
                matrix = np.load(stream, allow_pickle=False)
        except (OSError, UnicodeError, ValidationError, json.JSONDecodeError, ValueError):
            raise EmbeddingArtifactError("artifact-corrupt") from None
        if manifest.artifact_id != artifact_id:
            raise EmbeddingArtifactError("artifact-identity-mismatch")
        if file_checksum(path / "matrix.npy") != manifest.matrix_sha256 or file_checksum(path / "metadata.json") != manifest.metadata_sha256:
            raise EmbeddingArtifactError("artifact-hash-mismatch")
        self._require_compatible(manifest, metadata, matrix)
        return LoadedEmbeddingArtifact(manifest=manifest, matrix=matrix, metadata=metadata)

    def _require_compatible(self, manifest: EmbeddingArtifactManifest, metadata: tuple[ArtifactChunkMetadata, ...], matrix: np.ndarray) -> None:
        expected = (self._corpus.release_id, self._corpus.release_version, self._corpus.corpus_checksum, self._provider_identity, self._model, self._chunking_version)
        actual = (manifest.release_id, manifest.release_version, manifest.corpus_checksum, manifest.provider_identity, manifest.embedding_model, manifest.chunking_version)
        if actual != expected:
            raise EmbeddingArtifactError("artifact-incompatible")
        if matrix.ndim != 2 or matrix.shape != (manifest.row_count, manifest.vector_dimension) or not np.isfinite(matrix).all():
            raise EmbeddingArtifactError("matrix-invalid")
        if self._expected_dimension is not None and manifest.vector_dimension != self._expected_dimension:
            raise EmbeddingArtifactError("artifact-dimension-mismatch")
        chunk_pairs = tuple((item.row, item.chunk_id, item.content_checksum) for item in metadata)
        expected_pairs = tuple((row, chunk.chunk_id, chunk_checksum(chunk)) for row, chunk in enumerate(self._corpus.chunks))
        if chunk_pairs != expected_pairs or len(metadata) != manifest.row_count:
            raise EmbeddingArtifactError("chunk-order-mismatch")
        if self._artifact_id(
            manifest.vector_dimension,
            metadata,
            manifest.documents,
        ) != manifest.artifact_id:
            raise EmbeddingArtifactError("artifact-identity-mismatch")

    def _artifact_id(
        self,
        dimension: int,
        metadata: tuple[ArtifactChunkMetadata, ...],
        documents: tuple[ArtifactDocumentRecord, ...],
    ) -> str:
        identity = {
            "schema_version": 1,
            "release_id": self._corpus.release_id,
            "release_version": self._corpus.release_version,
            "corpus_checksum": self._corpus.corpus_checksum,
            "provider_identity": self._provider_identity,
            "embedding_model": self._model,
            "vector_dimension": dimension,
            "chunking_version": self._chunking_version,
            "metadata_sha256": sha256(self._metadata_bytes(metadata)).hexdigest(),
            "documents_sha256": sha256(canonical_bytes([item.model_dump(mode="json") for item in documents])).hexdigest(),
        }
        return sha256(canonical_bytes(identity)).hexdigest()

    def _document_records(self, metadata: tuple[ArtifactChunkMetadata, ...]) -> tuple[ArtifactDocumentRecord, ...]:
        ordered_ids = tuple(dict.fromkeys(item.document_id for item in metadata))
        records = []
        for document_id in ordered_ids:
            chunks = tuple(item for item in metadata if item.document_id == document_id)
            checksum = sha256("".join(item.content_checksum for item in chunks).encode()).hexdigest()
            records.append(ArtifactDocumentRecord(document_id=document_id, checksum=checksum, chunk_ids=tuple(item.chunk_id for item in chunks)))
        return tuple(records)

    def _metadata_bytes(self, metadata: tuple[ArtifactChunkMetadata, ...]) -> bytes:
        return canonical_bytes([item.model_dump(mode="json") for item in metadata]) + b"\n"

    def _load_pointer(self) -> ActiveArtifactPointer:
        try:
            return ActiveArtifactPointer.model_validate_json(self._pointer.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValidationError):
            raise EmbeddingArtifactError("active-pointer-invalid") from None

    def _atomic_pointer(self, pointer: ActiveArtifactPointer) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(prefix=".active-", dir=self._root)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write((pointer.model_dump_json(indent=2) + "\n").encode())
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_name, self._pointer)
            fsync_directory(self._root)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)

    def _write_bytes(self, path: Path, content: bytes) -> None:
        with path.open("wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())

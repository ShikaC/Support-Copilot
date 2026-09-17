import json
import subprocess
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from app.config import Settings
from app.embedding_artifact import EmbeddingArtifactStore
from app.embedding_artifact_identity import file_checksum, provider_identity
from app.embedding_artifact_models import EmbeddingArtifactManifest
from app.knowledge_source import KnowledgeCorpus, load_knowledge_corpus
from app.models import CURRENT_PROMPT_VERSION
from evaluation.live_dataset import file_sha256, load_live_dataset
from evaluation.live_models import LiveConfiguration, LiveDataset, VerificationContext


@dataclass(frozen=True, slots=True)
class VerifiedLiveInputs:
    dataset: LiveDataset
    dataset_checksum: str
    corpus: KnowledgeCorpus
    artifact: EmbeddingArtifactManifest
    artifact_manifest_sha256: str
    configuration: LiveConfiguration


@dataclass(frozen=True, slots=True)
class GitState:
    commit: str
    dirty: bool


def load_verified_live_inputs(
    dataset_path: Path,
    settings: Settings,
) -> VerifiedLiveInputs:
    dataset = load_live_dataset(dataset_path)
    corpus = load_knowledge_corpus(
        settings.knowledge_path,
        settings.knowledge_provenance_path,
    )
    artifact = EmbeddingArtifactStore(settings, corpus).load_active().manifest
    manifest_path = (
        settings.embedding_artifact_root / artifact.artifact_id / "manifest.json"
    )
    return VerifiedLiveInputs(
        dataset=dataset,
        dataset_checksum=file_sha256(dataset_path),
        corpus=corpus,
        artifact=artifact,
        artifact_manifest_sha256=file_checksum(manifest_path),
        configuration=expected_live_configuration(settings, artifact),
    )


def expected_live_configuration(
    settings: Settings,
    artifact: EmbeddingArtifactManifest,
) -> LiveConfiguration:
    return LiveConfiguration(
        prompt_version=CURRENT_PROMPT_VERSION,
        top_n=settings.retrieval_top_n,
        top_k=settings.retrieval_top_k,
        config_fingerprint=config_fingerprint(settings, artifact),
        runtime_source_sha256=runtime_source_sha256(),
        chat_provider_identity=provider_identity(settings.openai_base_url),
        chat_model=settings.openai_chat_model or "unconfigured",
        chat_protocol=settings.openai_chat_protocol,
        embedding_provider_identity=artifact.provider_identity,
        embedding_model=artifact.embedding_model,
        embedding_dimension=artifact.vector_dimension,
        embedding_chunking_version=artifact.chunking_version,
    )


def config_fingerprint(
    settings: Settings,
    artifact: EmbeddingArtifactManifest,
) -> str:
    config = {
        "chat_provider": provider_identity(settings.openai_base_url),
        "chat_model": settings.openai_chat_model,
        "chat_protocol": settings.openai_chat_protocol,
        "embedding_provider": artifact.provider_identity,
        "embedding_model": artifact.embedding_model,
        "embedding_dimension": artifact.vector_dimension,
        "embedding_chunking_version": artifact.chunking_version,
        "prompt_version": CURRENT_PROMPT_VERSION,
        "runtime_source_sha256": runtime_source_sha256(),
        "top_n": settings.retrieval_top_n,
        "top_k": settings.retrieval_top_k,
        "retrieval_min_score": settings.live_retrieval_min_score,
    }
    payload = json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
    return sha256(payload).hexdigest()


def build_verification_context(
    inputs: VerifiedLiveInputs,
    repo_root: Path,
) -> VerificationContext:
    git = read_git_state(repo_root)
    return VerificationContext(
        dataset_id=inputs.dataset.dataset_id,
        dataset_version=inputs.dataset.version,
        dataset_checksum=inputs.dataset_checksum,
        release_id=inputs.corpus.release_id,
        release_version=inputs.corpus.release_version,
        corpus_checksum=inputs.corpus.corpus_checksum,
        artifact_id=inputs.artifact.artifact_id,
        artifact_manifest_sha256=inputs.artifact_manifest_sha256,
        git_commit=git.commit,
        worktree_dirty=git.dirty,
        known_chunk_ids=frozenset(
            chunk.chunk_id for chunk in inputs.corpus.chunks
        ),
        configuration=inputs.configuration,
        expected_cases=inputs.dataset.cases,
    )


def read_git_state(repo_root: Path) -> GitState:
    return GitState(
        commit=_git(repo_root, ("rev-parse", "HEAD")),
        dirty=bool(_git(repo_root, ("status", "--porcelain"))),
    )


def _git(repo_root: Path, arguments: tuple[str, ...]) -> str:
    result = subprocess.run(
        ("git", *arguments),
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def runtime_source_sha256(runtime_root: Path | None = None) -> str:
    """Bind dirty runtime behavior, schemas and prompt sources without recording secrets."""
    root = runtime_root or Path(__file__).parents[1] / "app"
    files = tuple(sorted(path for path in root.rglob("*") if path.is_file() and path.suffix in (".py", ".json")))
    if not files:
        raise FileNotFoundError(root)
    digest = sha256()
    for source in files:
        digest.update(source.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(sha256(source.read_bytes()).digest())
    return digest.hexdigest()

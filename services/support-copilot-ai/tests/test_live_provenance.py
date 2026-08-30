from pathlib import Path
import subprocess
from typing import Never

import pytest

from app.config import Settings
from app.embedding_artifact_models import (
    ArtifactDocumentRecord,
    EmbeddingArtifactManifest,
)
from app.knowledge_source import load_knowledge_corpus
from app.models import AnalyzeOptions, AnalyzeRequest
from evaluation.live_dataset import load_live_dataset
from evaluation.live_provenance import (
    GitState,
    VerifiedLiveInputs,
    config_fingerprint,
    expected_live_configuration,
    read_git_state,
)
from evaluation.live_runner import run_live_cases

DATASET = Path(__file__).parents[1] / "evaluation" / "data" / "live-v1.json"
SERVICE_DIR = Path(__file__).parents[1]
VENV_PYTHON = SERVICE_DIR / ".venv" / "bin" / "python"
REPO_ROOT = Path(__file__).parents[3]
SHA = "a" * 64
ARTIFACT = "b" * 64


def _artifact() -> EmbeddingArtifactManifest:
    return EmbeddingArtifactManifest(
        schema_version=1,
        artifact_id=ARTIFACT,
        release_id="support-copilot-bundled-v1",
        release_version=1,
        corpus_checksum=SHA,
        provider_identity="compatible:embedding.example.invalid",
        embedding_model="embedding-model",
        vector_dimension=3,
        chunking_version="knowledge-corpus-v2",
        row_count=1,
        matrix_sha256=SHA,
        metadata_sha256=SHA,
        documents=(
            ArtifactDocumentRecord(
                document_id="identity-guide",
                checksum=SHA,
                chunk_ids=("kb-sso-login-001",),
            ),
        ),
    )


def test_live_config_fingerprint_distinguishes_chat_protocol() -> None:
    manifest = _artifact()
    responses = Settings(openai_chat_protocol="responses", _env_file=None)
    chat_completions = Settings(
        openai_chat_protocol="chat_completions",
        _env_file=None,
    )

    assert config_fingerprint(responses, manifest) != config_fingerprint(
        chat_completions,
        manifest,
    )


@pytest.mark.asyncio
async def test_live_runner_uses_current_retrieval_settings() -> None:
    manifest = _artifact()
    settings = Settings(retrieval_top_n=7, retrieval_top_k=2, _env_file=None)
    inputs = VerifiedLiveInputs(
        dataset=load_live_dataset(DATASET),
        dataset_checksum=SHA,
        corpus=load_knowledge_corpus(settings.knowledge_path, None),
        artifact=manifest,
        artifact_manifest_sha256=SHA,
        configuration=expected_live_configuration(settings, manifest),
    )
    observed: list[AnalyzeOptions] = []

    async def capture(request: AnalyzeRequest) -> Never:
        observed.append(request.options)
        raise RuntimeError

    with pytest.raises(RuntimeError):
        await run_live_cases(inputs, capture)

    assert observed[0].top_n == 7
    assert observed[0].top_k == 2


def test_git_state_is_read_from_explicit_repo_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected_commit = subprocess.run(
        ("git", "rev-parse", "HEAD"),
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    expected_dirty = bool(
        subprocess.run(
            ("git", "status", "--porcelain"),
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    monkeypatch.chdir(tmp_path)

    assert read_git_state(REPO_ROOT) == GitState(
        commit=expected_commit,
        dirty=expected_dirty,
    )


@pytest.mark.parametrize(
    "entrypoint",
    (
        SERVICE_DIR / "evaluation" / "run_live_evaluation.py",
        SERVICE_DIR / "evaluation" / "verify_live_evaluation.py",
    ),
)
def test_live_entrypoints_show_help_from_external_cwd(
    tmp_path: Path,
    entrypoint: Path,
) -> None:
    result = subprocess.run(
        (str(VENV_PYTHON), str(entrypoint), "--help"),
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "Usage:" in result.stdout

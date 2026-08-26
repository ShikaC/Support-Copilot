from pathlib import Path
import subprocess
from typing import Annotated

import typer

from app.config import Settings
from app.embedding_artifact import EmbeddingArtifactStore
from app.embedding_artifact_identity import file_checksum
from app.knowledge_source import load_knowledge_corpus
from evaluation.live_dataset import file_sha256, load_live_dataset
from evaluation.live_models import LiveEvaluationReport, VerificationContext
from evaluation.live_verifier import verify_live_report


def current_context(dataset_path: Path, settings: Settings) -> VerificationContext:
    dataset = load_live_dataset(dataset_path)
    corpus = load_knowledge_corpus(settings.knowledge_path, settings.knowledge_provenance_path)
    artifact = EmbeddingArtifactStore(settings, corpus).load_active().manifest
    manifest_path = settings.embedding_artifact_root / artifact.artifact_id / "manifest.json"
    return VerificationContext(
        dataset_id=dataset.dataset_id,
        dataset_version=dataset.version,
        dataset_checksum=file_sha256(dataset_path),
        release_id=corpus.release_id,
        release_version=corpus.release_version,
        corpus_checksum=corpus.corpus_checksum,
        artifact_id=artifact.artifact_id,
        artifact_manifest_sha256=file_checksum(manifest_path),
        git_commit=_git(("rev-parse", "HEAD")),
        worktree_dirty=bool(_git(("status", "--porcelain"))),
        known_chunk_ids=frozenset(chunk.chunk_id for chunk in corpus.chunks),
    )


def main(
    report_path: Annotated[Path, typer.Option("--report", exists=True)],
    dataset_path: Annotated[Path, typer.Option("--dataset", exists=True)],
    require_human: Annotated[bool, typer.Option("--require-human")] = False,
) -> None:
    report = LiveEvaluationReport.model_validate_json(report_path.read_text(encoding="utf-8"))
    reasons = verify_live_report(
        report,
        current_context(dataset_path, Settings()),
        require_human=require_human,
    )
    if reasons:
        typer.echo(f"live-evaluation-invalid={','.join(reasons)}", err=True)
        raise typer.Exit(code=1)
    typer.echo("live-evaluation-valid=true")


def _git(arguments: tuple[str, ...]) -> str:
    result = subprocess.run(("git", *arguments), check=True, capture_output=True, text=True)
    return result.stdout.strip()


if __name__ == "__main__":
    typer.run(main)

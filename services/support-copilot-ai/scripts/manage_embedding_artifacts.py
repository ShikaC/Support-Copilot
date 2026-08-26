from pathlib import Path
from typing import Annotated

import anyio
from openai import OpenAIError
import typer

from app.config import Settings
from app.embedding_artifact import EmbeddingArtifactError, EmbeddingArtifactStore
from app.embedding_provider import OpenAIEmbeddingProvider
from app.knowledge_source import KnowledgeSourceInvalidError, load_knowledge_corpus

app = typer.Typer(add_completion=False)


def _settings(
    knowledge: Path,
    provenance: Path | None,
    artifact_root: Path,
    model: str,
    base_url: str | None,
    dimension: int | None,
    chunking_version: str,
) -> Settings:
    return Settings(
        ai_mode="mock",
        knowledge_path=knowledge,
        knowledge_provenance_path=provenance,
        embedding_artifact_root=artifact_root,
        openai_embedding_model=model,
        openai_embedding_base_url=base_url,
        embedding_vector_dimension=dimension,
        embedding_chunking_version=chunking_version,
    )


def _store(settings: Settings) -> EmbeddingArtifactStore:
    corpus = load_knowledge_corpus(
        settings.knowledge_path,
        settings.knowledge_provenance_path,
    )
    return EmbeddingArtifactStore(settings, corpus)


def _fail(exc: EmbeddingArtifactError | KnowledgeSourceInvalidError) -> None:
    reason = exc.reason if isinstance(exc, EmbeddingArtifactError) else "knowledge-source-invalid"
    typer.echo(f"embedding-artifact-error: {reason}", err=True)
    raise typer.Exit(code=1)


@app.command()
def build(
    knowledge: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    artifact_root: Annotated[Path, typer.Option(file_okay=False)],
    model: Annotated[str, typer.Option()],
    provenance: Annotated[Path | None, typer.Option(exists=True, dir_okay=False)] = None,
    base_url: Annotated[str | None, typer.Option()] = None,
    dimension: Annotated[int | None, typer.Option(min=1)] = None,
    chunking_version: Annotated[str, typer.Option()] = "knowledge-corpus-v2",
    activate: Annotated[bool, typer.Option()] = False,
) -> None:
    settings = _settings(knowledge, provenance, artifact_root, model, base_url, dimension, chunking_version)

    async def run() -> None:
        store = _store(settings)
        manifest = await store.build(OpenAIEmbeddingProvider(settings))
        if activate:
            store.activate(manifest.artifact_id)
        typer.echo(f"artifactId={manifest.artifact_id}")
        typer.echo(f"rows={manifest.row_count}")
        typer.echo(f"dimension={manifest.vector_dimension}")

    try:
        anyio.run(run)
    except (EmbeddingArtifactError, KnowledgeSourceInvalidError) as exc:
        _fail(exc)
    except OpenAIError:
        typer.echo("embedding-artifact-error: embedding-provider-failure", err=True)
        raise typer.Exit(code=1) from None


def _lifecycle_store(
    knowledge: Path,
    artifact_root: Path,
    model: str,
    provenance: Path | None,
    base_url: str | None,
    dimension: int | None,
    chunking_version: str,
) -> EmbeddingArtifactStore:
    return _store(_settings(knowledge, provenance, artifact_root, model, base_url, dimension, chunking_version))


@app.command("inspect")
def inspect_artifact(
    artifact_id: Annotated[str, typer.Option()],
    knowledge: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    artifact_root: Annotated[Path, typer.Option(file_okay=False)],
    model: Annotated[str, typer.Option()],
    provenance: Annotated[Path | None, typer.Option(exists=True, dir_okay=False)] = None,
    base_url: Annotated[str | None, typer.Option()] = None,
    dimension: Annotated[int | None, typer.Option(min=1)] = None,
    chunking_version: Annotated[str, typer.Option()] = "knowledge-corpus-v2",
) -> None:
    try:
        artifact = _lifecycle_store(knowledge, artifact_root, model, provenance, base_url, dimension, chunking_version).load(artifact_id)
    except (EmbeddingArtifactError, KnowledgeSourceInvalidError) as exc:
        _fail(exc)
    typer.echo(f"artifactId={artifact.manifest.artifact_id}")
    typer.echo(f"release={artifact.manifest.release_id}:v{artifact.manifest.release_version}")
    typer.echo(f"rows={artifact.manifest.row_count}")
    typer.echo(f"dimension={artifact.manifest.vector_dimension}")


@app.command()
def verify(
    artifact_id: Annotated[str, typer.Option()],
    knowledge: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    artifact_root: Annotated[Path, typer.Option(file_okay=False)],
    model: Annotated[str, typer.Option()],
    provenance: Annotated[Path | None, typer.Option(exists=True, dir_okay=False)] = None,
    base_url: Annotated[str | None, typer.Option()] = None,
    dimension: Annotated[int | None, typer.Option(min=1)] = None,
    chunking_version: Annotated[str, typer.Option()] = "knowledge-corpus-v2",
) -> None:
    inspect_artifact(artifact_id, knowledge, artifact_root, model, provenance, base_url, dimension, chunking_version)
    typer.echo("verified=true")


@app.command()
def activate(
    artifact_id: Annotated[str, typer.Option()],
    knowledge: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    artifact_root: Annotated[Path, typer.Option(file_okay=False)],
    model: Annotated[str, typer.Option()],
    provenance: Annotated[Path | None, typer.Option(exists=True, dir_okay=False)] = None,
    base_url: Annotated[str | None, typer.Option()] = None,
    dimension: Annotated[int | None, typer.Option(min=1)] = None,
    chunking_version: Annotated[str, typer.Option()] = "knowledge-corpus-v2",
) -> None:
    try:
        pointer = _lifecycle_store(knowledge, artifact_root, model, provenance, base_url, dimension, chunking_version).activate(artifact_id)
    except (EmbeddingArtifactError, KnowledgeSourceInvalidError) as exc:
        _fail(exc)
    typer.echo(f"activeArtifactId={pointer.active_artifact_id}")


@app.command()
def rollback(
    knowledge: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    artifact_root: Annotated[Path, typer.Option(file_okay=False)],
    model: Annotated[str, typer.Option()],
    provenance: Annotated[Path | None, typer.Option(exists=True, dir_okay=False)] = None,
    base_url: Annotated[str | None, typer.Option()] = None,
    dimension: Annotated[int | None, typer.Option(min=1)] = None,
    chunking_version: Annotated[str, typer.Option()] = "knowledge-corpus-v2",
) -> None:
    try:
        pointer = _lifecycle_store(knowledge, artifact_root, model, provenance, base_url, dimension, chunking_version).rollback()
    except (EmbeddingArtifactError, KnowledgeSourceInvalidError) as exc:
        _fail(exc)
    typer.echo(f"activeArtifactId={pointer.active_artifact_id}")


if __name__ == "__main__":
    app()

from pathlib import Path
from typing import Annotated

import typer

from app.knowledge_ingestion import KnowledgeIngestionError, build_knowledge_corpus

app = typer.Typer(add_completion=False)


@app.command()
def build(
    manifest: Annotated[
        Path,
        typer.Option(exists=True, dir_okay=False, readable=True),
    ],
    output: Annotated[Path, typer.Option(dir_okay=False)],
) -> None:
    try:
        result = build_knowledge_corpus(manifest, output)
    except KnowledgeIngestionError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from None

    typer.echo(f"Knowledge corpus: {result.output_path}")
    typer.echo(f"Provenance: {result.provenance_path}")
    typer.echo(f"Chunks: {result.chunk_count}")
    typer.echo(f"Index version: {result.index_version}")


if __name__ == "__main__":
    app()

"""Build a separate artifact through the production embedding store."""
import json
from pathlib import Path
from time import perf_counter

import anyio
import typer
from openai import OpenAIError

from app.config import Settings
from app.embedding_artifact import EmbeddingArtifactError, EmbeddingArtifactStore
from app.embedding_provider import EmbeddingProvider, OpenAIEmbeddingProvider
from app.knowledge_source import load_knowledge_corpus
from app.observability import safe_provider_failure_details


class BatchedDocuments:
    def __init__(self, provider: EmbeddingProvider) -> None:
        self.provider: EmbeddingProvider = provider

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        rows: list[list[float]] = []
        for offset in range(0, len(texts), 16):
            rows.extend(await self.provider.embed_documents(texts[offset:offset + 16]))
            typer.echo(f"embedded {len(rows)}/{len(texts)}")
        return rows

    async def embed_query(self, text: str) -> list[float]:
        return await self.provider.embed_query(text)


async def build(corpus_path: Path, artifact_root: Path) -> None:
    settings = Settings(ai_mode="live", knowledge_path=corpus_path,
        embedding_artifact_root=artifact_root, embedding_vector_dimension=1024,
        embedding_chunking_version="doc2dial-codepoints-2000-1600-v1")
    corpus = load_knowledge_corpus(corpus_path)
    store = EmbeddingArtifactStore(settings, corpus)
    started = perf_counter()
    try:
        manifest = await store.build(BatchedDocuments(OpenAIEmbeddingProvider(settings)))
    except OpenAIError as exc:
        typer.echo(json.dumps(safe_provider_failure_details(exc)))
        raise typer.Exit(1) from None
    except EmbeddingArtifactError as exc:
        typer.echo(f"artifact-error: {exc.reason}")
        raise typer.Exit(1) from None
    _ = store.activate(manifest.artifact_id)
    _ = (corpus_path.parent / "index-build.json").write_text(json.dumps({
        "artifact_id": manifest.artifact_id, "rows": manifest.row_count,
        "dimension": manifest.vector_dimension, "duration_ms": (perf_counter()-started)*1000,
        "model": settings.openai_embedding_model, "batch_size": 16, "sdk_retries": 0,
        "usage_tokens": None, "cost": None,
    }, indent=2))
    typer.echo(f"active artifact: {manifest.artifact_id}")


def main(corpus_path: Path, artifact_root: Path) -> None:
    anyio.run(build, corpus_path.resolve(), artifact_root.resolve())


if __name__ == "__main__":
    typer.run(main)

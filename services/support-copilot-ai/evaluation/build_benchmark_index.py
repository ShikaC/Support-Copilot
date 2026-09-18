"""Build a separate artifact through the production embedding store.

切片身份来自 corpus 目录里的 `chunking.json`（由 scripts/benchmark/prepare-doc2dial.mjs 写出），
不再硬编码：不同切片参数会得到不同的 chunking_version，从而得到不同的 artifact。

注意 artifact_root 是隔离边界：同一个 root 下多次 build 后 activate 会切换 active artifact，
因此为新切片做实验时应使用新的 root，避免影响正在使用的检索。
"""
import json
import os
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


def describe_path(path: Path) -> str:
    """记录可移植的相对路径；跨出工作目录时退回绝对路径，避免把本机路径写进证据。"""
    relative = os.path.relpath(path, Path.cwd())
    return path.as_posix() if relative.startswith("..") else relative


def resolve_chunking_version(corpus_path: Path, override: str | None) -> str:
    """Fail closed：读不到切片身份就拒绝构建，避免把语料建成错误的版本。"""
    if override:
        return override
    descriptor = corpus_path.parent / "chunking.json"
    if not descriptor.exists():
        typer.echo(
            f"chunking-descriptor-missing: {descriptor} 不存在；"
            "请用 prepare-doc2dial.mjs 重新生成 corpus，或显式传 --chunking-version"
        )
        raise typer.Exit(1)
    return str(json.loads(descriptor.read_text(encoding="utf-8"))["chunking_version"])


async def build(corpus_path: Path, artifact_root: Path, chunking_version: str | None) -> None:
    resolved_version = resolve_chunking_version(corpus_path, chunking_version)
    settings = Settings(ai_mode="live", knowledge_path=corpus_path,
        embedding_artifact_root=artifact_root, embedding_vector_dimension=1024,
        embedding_chunking_version=resolved_version)
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
        "chunking_version": resolved_version, "release_id": corpus.release_id,
        "artifact_root": describe_path(artifact_root),
    }, indent=2))
    typer.echo(f"chunking-version: {resolved_version}")
    typer.echo(f"active artifact: {manifest.artifact_id}")


def main(corpus_path: Path, artifact_root: Path, chunking_version: str = "") -> None:
    anyio.run(build, corpus_path.resolve(), artifact_root.resolve(), chunking_version or None)


if __name__ == "__main__":
    typer.run(main)

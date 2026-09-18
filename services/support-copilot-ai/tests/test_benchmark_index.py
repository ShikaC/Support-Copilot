import json
from pathlib import Path

import pytest
import typer

from evaluation.build_benchmark_index import BatchedDocuments, describe_path, resolve_chunking_version


class CountingProvider:
    """Deterministic provider recording submitted batch sizes."""
    def __init__(self, fail: bool = False) -> None:
        self.sizes: list[int] = []
        self.fail: bool = fail

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.sizes.append(len(texts))
        if self.fail:
            raise ConnectionError
        return [[float(text)] for text in texts]

    async def embed_query(self, text: str) -> list[float]:
        return [float(text)]


@pytest.mark.anyio
async def test_batches_preserve_every_row_and_input_order() -> None:
    # Given more documents than one provider batch supports.
    provider = CountingProvider()
    # When embedding through the experiment adapter.
    rows = await BatchedDocuments(provider).embed_documents([str(i) for i in range(33)])
    # Then no input is lost or reordered and each request is bounded.
    assert rows == [[float(i)] for i in range(33)]
    assert provider.sizes == [16, 16, 1]


@pytest.mark.anyio
async def test_batch_failure_propagates_without_retry_or_partial_success() -> None:
    # Given an external failure in the first batch.
    provider = CountingProvider(fail=True)
    # When starting an index build.
    with pytest.raises(ConnectionError):
        _ = await BatchedDocuments(provider).embed_documents(["1"] * 33)
    # Then failure stays visible and later batches are not attempted.
    assert provider.sizes == [16]


def test_resolve_chunking_version_reads_the_corpus_descriptor(tmp_path: Path) -> None:
    # Given a corpus directory carrying the slicing identity written by the prepare step.
    corpus = tmp_path / "corpus.json"
    corpus.write_text("{}", encoding="utf-8")
    (tmp_path / "chunking.json").write_text(
        json.dumps({"chunking_version": "doc2dial-codepoints-1000-800-v1"}), encoding="utf-8")
    # When resolving without an override.
    resolved = resolve_chunking_version(corpus, None)
    # Then the descriptor wins over any hardcoded default.
    assert resolved == "doc2dial-codepoints-1000-800-v1"


def test_resolve_chunking_version_fails_closed_without_a_descriptor(tmp_path: Path) -> None:
    # Given a corpus directory with no slicing identity at all.
    corpus = tmp_path / "corpus.json"
    corpus.write_text("{}", encoding="utf-8")
    # When resolving without an override.
    # Then the build is refused instead of inventing a version.
    with pytest.raises(typer.Exit):
        resolve_chunking_version(corpus, None)


def test_resolve_chunking_version_prefers_an_explicit_override(tmp_path: Path) -> None:    # Given a descriptor that disagrees with the operator.
    corpus = tmp_path / "corpus.json"
    corpus.write_text("{}", encoding="utf-8")
    (tmp_path / "chunking.json").write_text(
        json.dumps({"chunking_version": "doc2dial-codepoints-1000-800-v1"}), encoding="utf-8")
    # When an explicit version is supplied.
    resolved = resolve_chunking_version(corpus, "doc2dial-codepoints-2000-1600-v1")
    # Then the explicit value is honoured (useful for rebuilding frozen corpora).
    assert resolved == "doc2dial-codepoints-2000-1600-v1"


def test_describe_path_keeps_paths_inside_the_working_directory_relative(tmp_path: Path, monkeypatch) -> None:
    # Given a path below the current working directory.
    monkeypatch.chdir(tmp_path)
    nested = tmp_path / "artifacts" / "run-1"
    # Then the recorded value stays portable instead of embedding the home directory.
    assert describe_path(nested) == "artifacts/run-1"


def test_describe_path_falls_back_to_absolute_outside_the_working_directory(tmp_path: Path, monkeypatch) -> None:
    # Given a path that does not live below the current working directory.
    monkeypatch.chdir(tmp_path)
    outside = tmp_path.parent / "elsewhere"
    # Then it keeps the absolute form rather than a chain of parent hops.
    assert describe_path(outside) == outside.as_posix()

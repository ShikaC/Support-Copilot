import pytest

from evaluation.build_benchmark_index import BatchedDocuments


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

"""Single-worker benchmark adapter; production business behavior is unchanged."""
import os
from hashlib import sha256
from pathlib import Path
from typing import final

from app import main
from app.analysis_runner import AnalysisRunner
from app.config import Settings
from app.embedding_provider import OpenAIEmbeddingProvider
from app.knowledge import KnowledgeRetriever, RetrievalRequest
from app.knowledge_source import KnowledgeCorpus, load_knowledge_corpus
from app.live_vector_index import LiveVectorIndex
from app.models import AnalyzeRequest, AnalyzeResponse, ModelDraft, RetrievalHit
from app.openai_provider import OpenAIProvider
from app.workflow import AnalysisWorkflow
from typing_extensions import override

from evaluation.isolated_observation import AttemptLedger, trace

output = Path(os.environ["ISOLATED_BENCHMARK_OUTPUT"])
ledger = AttemptLedger(output / "attempts.jsonl", int(os.environ["ISOLATED_PROVIDER_LIMIT"]))


class ObservedEmbedding(OpenAIEmbeddingProvider):
    @override
    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("Document embedding is prohibited in this benchmark")

    @override
    async def embed_query(self, text: str) -> list[float]:
        with ledger.attempt("query_embedding"):
            return await super().embed_query(text)


class ObservedGeneration(OpenAIProvider):
    @override
    async def analyze(self, request: AnalyzeRequest, evidence: list[RetrievalHit]) -> tuple[ModelDraft, int, int]:
        with ledger.attempt("generation"):
            return await super().analyze(request, evidence)


@final
class ObservedIndex(LiveVectorIndex):
    def __init__(self, settings: Settings, corpus: KnowledgeCorpus) -> None:
        super().__init__(settings, corpus)
        self._provider = ObservedEmbedding(settings)
        self._artifact = self._store.load_active()


@final
class ObservedRetriever(KnowledgeRetriever):
    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self._live_index = ObservedIndex(settings, load_knowledge_corpus(settings.knowledge_path))

    @override
    async def search(self, request: RetrievalRequest) -> list[RetrievalHit]:
        hits = await super().search(request)
        key = sha256(trace.get().encode()).hexdigest()
        file = output / "retrieval" / f"{key}.jsonl"
        ledger.persist_retrieval(file, '[' + ','.join(hit.model_dump_json(by_alias=True) for hit in hits) + ']')
        return hits


class ObservedWorkflow(AnalysisWorkflow):
    def __init__(self, settings: Settings, retriever: KnowledgeRetriever) -> None:
        super().__init__(settings, retriever)
        self._provider: OpenAIProvider | None = ObservedGeneration(settings)

    @override
    async def run(self, request: AnalyzeRequest) -> AnalyzeResponse:
        token = trace.set(request.trace_id)
        try:
            with ledger.failure_boundary():
                return await super().run(request)
        finally:
            trace.reset(token)


main.retriever = ObservedRetriever(main.settings)
main.workflow = ObservedWorkflow(main.settings, main.retriever)
main.runner = AnalysisRunner(main.settings, main.workflow)
app = main.app

"""Production HTTP app with a benchmark-only live retrieval evidence recorder."""
import hashlib
import os
from pathlib import Path
from time import perf_counter
from typing import ClassVar

from pydantic import BaseModel, ConfigDict
from typing_extensions import override

from app import main
from app.analysis_runner import AnalysisRunner
from app.knowledge import KnowledgeRetriever, RetrievalRequest
from app.models import RetrievalHit
from app.workflow import AnalysisWorkflow


class RetrievalRecord(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)
    ticket_id: str
    query: str
    duration_ms: float
    hits: list[RetrievalHit]


class RecordedRetriever(KnowledgeRetriever):
    @override
    async def search(self, request: RetrievalRequest) -> list[RetrievalHit]:
        started = perf_counter()
        hits = await super().search(request)
        if request.live:
            record = RetrievalRecord(ticket_id=request.ticket.id, query=request.query,
                duration_ms=(perf_counter()-started)*1000, hits=hits)
            directory = Path(os.environ["BENCHMARK_RETRIEVAL_OUTPUT"])
            name = hashlib.sha256(request.ticket.id.encode()).hexdigest()
            _ = (directory / f"{name}.json").write_text(record.model_dump_json(indent=2))
        return hits


main.retriever = RecordedRetriever(main.settings)
main.workflow = AnalysisWorkflow(main.settings, main.retriever)
main.runner = AnalysisRunner(main.settings, main.workflow)
app = main.app

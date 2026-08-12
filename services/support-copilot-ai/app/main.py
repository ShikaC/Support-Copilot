import logging

from fastapi import FastAPI

from app.config import get_settings
from app.knowledge import KnowledgeRetriever
from app.models import AnalyzeRequest, AnalyzeResponse
from app.workflow import AnalysisWorkflow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

settings = get_settings()
retriever = KnowledgeRetriever(settings)
workflow = AnalysisWorkflow(settings, retriever)

app = FastAPI(
    title="Support Copilot AI",
    version="0.1.0",
    description="Ticket classification, knowledge retrieval, and grounded reply service.",
)


@app.get("/health")
async def health() -> dict[str, object]:
    return {
        "status": "up",
        "service": settings.app_name,
        "mode": settings.effective_mode,
        "liveReady": settings.live_ready,
        "knowledgeChunks": retriever.chunk_count,
    }


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    # FastAPI 会先用 AnalyzeRequest 校验传入 JSON，
    # 工作流返回后再用 AnalyzeResponse 校验响应结构。
    return await workflow.run(request)

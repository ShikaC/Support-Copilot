from pathlib import Path
from typing import Final

import pytest

from app.config import Settings
from app.knowledge import KnowledgeRetriever
from app.models import AnalyzeOptions
from app.workflow import AnalysisWorkflow
from evaluation.dataset import load_evaluation_cases
from evaluation.runner import analyze_cases

DATASET_PATH: Final = (
    Path(__file__).parents[1] / "evaluation" / "data" / "tickets.jsonl"
)


@pytest.mark.asyncio
async def test_analyze_cases_continues_after_an_earlier_answer_mismatch() -> None:
    first_case, second_case = load_evaluation_cases(DATASET_PATH)[:2]
    mismatched_first_case = first_case.model_copy(
        update={"expected_category": "SUBSCRIPTION"}
    )
    settings = Settings(ai_mode="mock")
    workflow = AnalysisWorkflow(settings, KnowledgeRetriever(settings))

    responses = await analyze_cases(
        (mismatched_first_case, second_case),
        workflow.run,
        AnalyzeOptions(topN=10, topK=3),
    )

    assert tuple(response.trace_id for response in responses) == (
        f"eval_{first_case.id}",
        f"eval_{second_case.id}",
    )

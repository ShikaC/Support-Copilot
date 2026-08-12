from pathlib import Path
from typing import Final

import pytest

from app.config import Settings
from app.knowledge import KnowledgeRetriever
from app.models import AnalyzeOptions
from app.workflow import AnalysisWorkflow
from evaluation.dataset import load_evaluation_cases
from evaluation.markdown import render_markdown
from evaluation.report import build_evaluation_report
from evaluation.runner import analyze_cases

DATASET_PATH: Final = (
    Path(__file__).parents[1] / "evaluation" / "data" / "tickets.jsonl"
)
KNOWLEDGE_PATH: Final = Path(__file__).parents[1] / "app" / "data" / "knowledge.json"
OPTIONS: Final = AnalyzeOptions(topN=10, topK=3)


@pytest.mark.asyncio
async def test_build_report_preserves_current_mock_baseline() -> None:
    # Given: 评估集包含两条超过标准的案例，以及一条恰好等于标准的案例。
    cases = load_evaluation_cases(DATASET_PATH)
    settings = Settings(ai_mode="mock")
    workflow = AnalysisWorkflow(settings, KnowledgeRetriever(settings))
    responses = await analyze_cases(cases, workflow.run, OPTIONS)
    durations = (2_001, 2_001, 2_000, *(100 for _ in responses[3:]))
    responses = tuple(
        response.model_copy(
            update={
                "model_name": "model-x" if index == 0 else "model-y",
                "usage": response.usage.model_copy(
                    update={"duration_ms": duration_ms},
                ),
            },
        )
        for index, (response, duration_ms) in enumerate(
            zip(responses, durations, strict=True)
        )
    )

    # When: 根据工作流的实际响应生成完整评估报告。
    report = build_evaluation_report(
        cases=cases,
        responses=responses,
        dataset_path=DATASET_PATH,
        knowledge_path=KNOWLEDGE_PATH,
        top_n=OPTIONS.top_n,
        top_k=OPTIONS.top_k,
        mode="mock",
    )

    # Then: 报告保留批次指标、案例模型归属和分模型慢案例统计。
    assert report.dataset_name == "tickets.jsonl"
    assert report.mode == "mock"
    assert report.model_names == ("model-x", "model-y")
    assert report.cases[0].model_name == "model-x"
    assert report.cases[1].model_name == "model-y"
    assert report.model_performance[0].model_name == "model-x"
    assert report.model_performance[0].total_cases == 1
    assert report.model_performance[0].slow_case_count == 1
    assert report.model_performance[0].slow_case_rate == pytest.approx(1.0)
    assert report.model_performance[1].model_name == "model-y"
    assert report.model_performance[1].total_cases == 17
    assert report.model_performance[1].slow_case_count == 1
    assert report.model_performance[1].slow_case_rate == pytest.approx(1 / 17)
    assert report.metrics.total_cases == 18
    assert report.metrics.classification_accuracy == pytest.approx(1.0)
    assert report.metrics.hit_rate_at_k == pytest.approx(1.0)
    assert report.metrics.no_evidence_safety_rate == pytest.approx(1.0)
    assert report.passed is True
    assert report.failed_case_ids == ()
    assert report.metrics.slow_case_threshold_ms == 2_000
    assert report.metrics.slow_case_count == 2
    assert report.metrics.slow_case_rate == pytest.approx(2 / 18)
    markdown = render_markdown(report)
    assert "> 模型：model-x, model-y" in markdown
    assert "| model-x | 1 | 1 | 1.000 |" in markdown
    assert "| model-y | 17 | 1 | 0.059 |" in markdown
    assert "| 慢案例标准（毫秒） | > 2000 |" in markdown
    assert "| 慢案例数量 | 2 |" in markdown
    assert "| 慢案例比例 | 0.111 |" in markdown
    assert report.cases[0].retrieved_evidence_ids == tuple(
        hit.chunk_id for hit in responses[0].retrieval.hits
    )

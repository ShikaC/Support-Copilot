from pathlib import Path
from typing import Final

import pytest

from app.config import Settings
from app.knowledge import KnowledgeRetriever
from app.models import AnalyzeOptions, Priority
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
async def test_report_fails_when_one_high_risk_priority_downgrade_occurs() -> None:
    # Given: 评估集包含两条超过标准的案例，以及一条恰好等于标准的案例。
    cases = load_evaluation_cases(DATASET_PATH)
    settings = Settings(ai_mode="mock")
    workflow = AnalysisWorkflow(settings, KnowledgeRetriever(settings))
    responses = await analyze_cases(cases, workflow.run, OPTIONS)
    durations = (2_001, 2_001, 2_000, *(100 for _ in responses[3:]))
    responses = tuple(
        response.model_copy(
            update={
                "model_name": "model-x" if index < 2 else "model-y",
                "prompt_version": (
                    "ticket-analysis-v1" if index == 0 else "ticket-analysis-v2"
                ),
                "classification": response.classification.model_copy(
                    update={
                        "category": (
                            "ACCOUNT_ACCESS"
                            if index in (1, 2)
                            else response.classification.category
                        ),
                        "priority": (
                            Priority.LOW
                            if index == 1
                            else response.classification.priority
                        ),
                    },
                ),
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

    # Then: 相同模型使用不同提示词时，报告仍按完整配置分别统计。
    assert report.dataset_name == "tickets.jsonl"
    assert report.mode == "mock"
    assert report.model_names == ("model-x", "model-y")
    assert report.prompt_versions == ("ticket-analysis-v1", "ticket-analysis-v2")
    assert report.cases[0].model_name == "model-x"
    assert report.cases[1].model_name == "model-x"
    assert report.cases[0].prompt_version == "ticket-analysis-v1"
    assert report.cases[1].prompt_version == "ticket-analysis-v2"
    performance = report.configuration_performance
    assert performance[0].model_name == "model-x"
    assert performance[0].prompt_version == "ticket-analysis-v1"
    assert performance[0].total_cases == 1
    assert performance[0].classification_accuracy == pytest.approx(1.0)
    assert performance[0].priority_accuracy == pytest.approx(1.0)
    assert performance[0].high_risk_priority_downgrade_count == 0
    assert performance[0].high_risk_priority_downgrade_rate == pytest.approx(0.0)
    assert performance[0].slow_case_count == 1
    assert performance[0].slow_case_rate == pytest.approx(1.0)
    assert performance[1].model_name == "model-x"
    assert performance[1].prompt_version == "ticket-analysis-v2"
    assert performance[1].total_cases == 1
    assert performance[1].classification_accuracy == pytest.approx(0.0)
    assert performance[1].priority_accuracy == pytest.approx(0.0)
    assert performance[1].high_risk_priority_downgrade_count == 1
    assert performance[1].high_risk_priority_downgrade_rate == pytest.approx(1.0)
    assert performance[1].slow_case_count == 1
    assert performance[1].slow_case_rate == pytest.approx(1.0)
    assert performance[2].model_name == "model-y"
    assert performance[2].prompt_version == "ticket-analysis-v2"
    assert performance[2].total_cases == 16
    assert performance[2].classification_accuracy == pytest.approx(15 / 16)
    assert performance[2].priority_accuracy == pytest.approx(1.0)
    assert performance[2].high_risk_priority_downgrade_count == 0
    assert performance[2].high_risk_priority_downgrade_rate == pytest.approx(0.0)
    assert performance[2].slow_case_count == 0
    assert performance[2].slow_case_rate == pytest.approx(0.0)
    assert report.metrics.total_cases == 18
    assert report.metrics.classification_accuracy == pytest.approx(16 / 18)
    assert report.metrics.priority_accuracy == pytest.approx(17 / 18)
    assert report.metrics.high_risk_priority_downgrade_count == 1
    assert report.metrics.high_risk_priority_downgrade_rate == pytest.approx(1 / 18)
    assert report.thresholds.max_high_risk_priority_downgrade_count == 0
    assert report.metrics.hit_rate_at_k == pytest.approx(1.0)
    assert report.metrics.no_evidence_safety_rate == pytest.approx(1.0)
    assert report.passed is False
    assert tuple(failure.metric for failure in report.threshold_failures) == (
        "classification_accuracy",
        "high_risk_priority_downgrade_count",
    )
    assert report.threshold_failures[0].actual == pytest.approx(16 / 18)
    assert report.threshold_failures[0].comparison == "at_least"
    assert report.threshold_failures[0].threshold == pytest.approx(0.90)
    assert report.threshold_failures[1].actual == 1
    assert report.threshold_failures[1].comparison == "at_most"
    assert report.threshold_failures[1].threshold == 0
    assert report.failed_case_ids == ("billing-details-002", "billing-refund-003")
    assert report.metrics.slow_case_threshold_ms == 2_000
    assert report.metrics.slow_case_count == 2
    assert report.metrics.slow_case_rate == pytest.approx(2 / 18)
    markdown = render_markdown(report)
    assert "> 模型：model-x, model-y" in markdown
    assert "> 提示词版本：ticket-analysis-v1, ticket-analysis-v2" in markdown
    assert "> 结论：未通过" in markdown
    assert "| model-x | ticket-analysis-v1 | 1 | 1.000 | 1.000 | 0 | 0.000 | 1 | 1.000 |" in markdown
    assert "| model-x | ticket-analysis-v2 | 1 | 0.000 | 0.000 | 1 | 1.000 | 1 | 1.000 |" in markdown
    assert "| model-y | ticket-analysis-v2 | 16 | 0.938 | 1.000 | 0 | 0.000 | 0 | 0.000 |" in markdown
    assert "| 慢案例标准（毫秒） | > 2000 |" in markdown
    assert "| 高风险优先级降级数量 | 1 |" in markdown
    assert "| 高风险优先级降级比例 | 0.056 |" in markdown
    assert "| 允许最大高风险降级数量 | 0 |" in markdown
    assert "| 慢案例数量 | 2 |" in markdown
    assert "| 慢案例比例 | 0.111 |" in markdown
    assert "- 分类准确率：实际 0.889，要求至少 0.900" in markdown
    assert "- 高风险优先级降级数量：实际 1，要求最多 0" in markdown
    assert (
        "### billing-details-002 - 支付争议需要补充什么资料" in markdown
    )
    assert "- 分类：预期 BILLING，实际 ACCOUNT_ACCESS" in markdown
    assert "- 优先级：预期 HIGH，实际 LOW" in markdown
    assert "### billing-refund-003 - 退款审核通过后多久到账" in markdown
    assert "billing-details-002、billing-refund-003" not in markdown
    assert report.cases[0].retrieved_evidence_ids == tuple(
        hit.chunk_id for hit in responses[0].retrieval.hits
    )


@pytest.mark.asyncio
async def test_report_passes_when_no_high_risk_priority_downgrade_occurs() -> None:
    # Given: 确定性 mock 基线不会把任何工单的优先级降低两级或以上。
    cases = load_evaluation_cases(DATASET_PATH)
    settings = Settings(ai_mode="mock")
    workflow = AnalysisWorkflow(settings, KnowledgeRetriever(settings))
    responses = await analyze_cases(cases, workflow.run, OPTIONS)

    # When: 使用未经篡改的实际 mock 响应生成报告。
    report = build_evaluation_report(
        cases=cases,
        responses=responses,
        dataset_path=DATASET_PATH,
        knowledge_path=KNOWLEDGE_PATH,
        top_n=OPTIONS.top_n,
        top_k=OPTIONS.top_k,
        mode="mock",
    )

    # Then: 零高风险降级满足最大允许数量为零的发布门槛。
    assert report.metrics.high_risk_priority_downgrade_count == 0
    assert report.threshold_failures == ()
    assert report.passed is True
    assert "## 失败样例\n\n无" in render_markdown(report)

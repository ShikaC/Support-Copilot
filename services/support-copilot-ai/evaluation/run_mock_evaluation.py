from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import anyio

from app.config import Settings
from app.knowledge import KnowledgeRetriever
from app.models import AnalyzeOptions
from app.workflow import AnalysisWorkflow
from evaluation.dataset import load_evaluation_cases
from evaluation.markdown import render_markdown
from evaluation.report import build_evaluation_report
from evaluation.runner import analyze_cases

SERVICE_DIR = Path(__file__).parents[1]
DATASET_PATH = SERVICE_DIR / "evaluation" / "data" / "tickets.jsonl"
KNOWLEDGE_PATH = SERVICE_DIR / "app" / "data" / "knowledge.json"
REPORT_DIR = SERVICE_DIR / "evaluation" / "reports"
OPTIONS = AnalyzeOptions(topN=10, topK=3)


async def run_evaluation() -> int:
    settings = Settings(ai_mode="mock")
    cases = load_evaluation_cases(DATASET_PATH)
    workflow = AnalysisWorkflow(settings, KnowledgeRetriever(settings))
    responses = await analyze_cases(cases, workflow.run, OPTIONS)
    report = build_evaluation_report(
        cases=cases,
        responses=responses,
        dataset_path=DATASET_PATH,
        knowledge_path=KNOWLEDGE_PATH,
        top_n=OPTIONS.top_n,
        top_k=OPTIONS.top_k,
        mode="mock",
    )

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = REPORT_DIR / f"mock-{timestamp}.json"
    markdown_path = REPORT_DIR / f"mock-{timestamp}.md"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")

    print(f"JSON report: {json_path}")
    print(f"Markdown report: {markdown_path}")
    print(f"Cases: {report.metrics.total_cases}")
    print(f"Passed: {report.passed}")
    print(f"Failed cases: {', '.join(report.failed_case_ids) or 'none'}")
    return 0 if report.passed else 1


def main() -> None:
    raise SystemExit(anyio.run(run_evaluation))


if __name__ == "__main__":
    main()

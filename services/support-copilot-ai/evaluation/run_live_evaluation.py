from datetime import UTC, datetime
from pathlib import Path
import sys
from typing import Annotated

import anyio
import typer

SERVICE_DIR = Path(__file__).resolve().parents[1]
if str(SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICE_DIR))

from app.analysis_runner import AnalysisRunner
from app.config import Settings
from app.knowledge import KnowledgeRetriever
from app.workflow import AnalysisWorkflow
from evaluation.live_markdown import render_live_markdown
from evaluation.live_provenance import load_verified_live_inputs
from evaluation.live_review import create_review_worksheet
from evaluation.live_pricing import apply_pricing
from evaluation.live_runner import build_live_report, run_live_cases

REPO_ROOT = SERVICE_DIR.parents[1]
DEFAULT_DATASET = SERVICE_DIR / "evaluation" / "data" / "live-v1.json"
DEFAULT_REPORT_DIR = SERVICE_DIR / "evaluation" / "reports"


async def run(dataset_path: Path, report_dir: Path, pricing_path: Path | None) -> int:
    settings = Settings(ai_mode="live")
    inputs = load_verified_live_inputs(dataset_path, settings)
    retriever = KnowledgeRetriever(settings)
    workflow = AnalysisWorkflow(settings, retriever)
    runner = AnalysisRunner(settings, workflow)
    cases = await run_live_cases(inputs, runner.run)
    cases = apply_pricing(cases, pricing_path, settings.openai_chat_model or "unconfigured")
    report = build_live_report(inputs, REPO_ROOT, cases)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    report_dir.mkdir(parents=True, exist_ok=True)
    json_path = report_dir / f"live-evaluation-{stamp}.json"
    markdown_path = report_dir / f"live-evaluation-{stamp}.md"
    worksheet_path = report_dir / f"live-evaluation-{stamp}-review.json"
    latest_path = report_dir / "live-latest.json"
    json = report.model_dump_json(indent=2)
    json_path.write_text(json, encoding="utf-8")
    latest_path.write_text(json, encoding="utf-8")
    markdown_path.write_text(render_live_markdown(report), encoding="utf-8")
    worksheet_path.write_text(create_review_worksheet(report).model_dump_json(indent=2), encoding="utf-8")
    typer.echo(f"report={json_path}")
    typer.echo(f"markdown={markdown_path}")
    typer.echo(f"worksheet={worksheet_path}")
    typer.echo(f"cases={report.summary.total_cases} publishable={str(report.summary.publishable).lower()}")
    return 0 if report.summary.succeeded_cases == report.summary.total_cases else 1


def main(
    dataset: Annotated[Path, typer.Option(exists=True)] = DEFAULT_DATASET,
    report_dir: Annotated[Path, typer.Option()] = DEFAULT_REPORT_DIR,
    pricing: Annotated[Path | None, typer.Option(exists=True)] = None,
) -> None:
    raise typer.Exit(anyio.run(run, dataset, report_dir, pricing))


if __name__ == "__main__":
    typer.run(main)

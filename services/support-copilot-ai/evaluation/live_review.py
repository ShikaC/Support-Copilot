from hashlib import sha256
from pathlib import Path
from typing import Annotated

import typer

from evaluation.live_models import (
    HumanReview,
    LiveEvaluationReport,
    ReviewEntry,
    ReviewWorksheet,
)
from evaluation.live_summary import summarize_live_cases

app = typer.Typer(add_completion=False)


class ReviewWorksheetError(Exception):
    pass


def _report_checksum(report: LiveEvaluationReport) -> str:
    return sha256(report.model_dump_json().encode()).hexdigest()


def create_review_worksheet(report: LiveEvaluationReport) -> ReviewWorksheet:
    return ReviewWorksheet(
        schema_version=1,
        run_id=report.run.run_id,
        report_sha256=_report_checksum(report),
        reviews=tuple(
            ReviewEntry(case_id=case.case_id, reviewer=case.human_review.reviewer,
                        factual_support=case.human_review.factual_support,
                        decision_note=case.human_review.decision_note,
                        reviewed_at=case.human_review.reviewed_at)
            for case in report.cases
        ),
    )


def apply_review_worksheet(
    report: LiveEvaluationReport,
    worksheet: ReviewWorksheet,
) -> LiveEvaluationReport:
    if worksheet.run_id != report.run.run_id or worksheet.report_sha256 != _report_checksum(report):
        raise ReviewWorksheetError("review worksheet does not match raw report")
    reviews = {review.case_id: review for review in worksheet.reviews}
    if set(reviews) != {case.case_id for case in report.cases}:
        raise ReviewWorksheetError("review worksheet case IDs do not match raw report")
    cases = tuple(
        case.model_copy(update={
            "human_review": HumanReview.model_validate(
                reviews[case.case_id].model_dump(exclude={"case_id"})
            )
        })
        for case in report.cases
    )
    return report.model_copy(
        update={"cases": cases, "summary": summarize_live_cases(cases, p95_method=report.summary.p95_method)}
    )


@app.command()
def worksheet(
    report_path: Annotated[Path, typer.Option("--report", exists=True)],
    output: Annotated[Path, typer.Option()],
) -> None:
    report = LiveEvaluationReport.model_validate_json(report_path.read_text(encoding="utf-8"))
    _ = output.write_text(create_review_worksheet(report).model_dump_json(indent=2), encoding="utf-8")
    typer.echo(f"worksheet={output}")


@app.command()
def apply(
    report_path: Annotated[Path, typer.Option("--report", exists=True)],
    worksheet_path: Annotated[Path, typer.Option("--worksheet", exists=True)],
    output: Annotated[Path, typer.Option()],
) -> None:
    report = LiveEvaluationReport.model_validate_json(report_path.read_text(encoding="utf-8"))
    sheet = ReviewWorksheet.model_validate_json(worksheet_path.read_text(encoding="utf-8"))
    _ = output.write_text(apply_review_worksheet(report, sheet).model_dump_json(indent=2), encoding="utf-8")
    typer.echo(f"reviewed_report={output}")


if __name__ == "__main__":
    app()

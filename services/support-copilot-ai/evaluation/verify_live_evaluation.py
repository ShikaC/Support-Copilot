from pathlib import Path
import sys
from typing import Annotated

import typer

SERVICE_DIR = Path(__file__).resolve().parents[1]
if str(SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICE_DIR))

from app.config import Settings
from evaluation.live_models import LiveEvaluationReport, VerificationContext
from evaluation.live_provenance import (
    build_verification_context,
    load_verified_live_inputs,
)
from evaluation.live_verifier import verify_live_report

REPO_ROOT = SERVICE_DIR.parents[1]


def current_context(
    dataset_path: Path,
    settings: Settings,
    repo_root: Path,
) -> VerificationContext:
    return build_verification_context(
        load_verified_live_inputs(dataset_path, settings),
        repo_root,
    )


def main(
    report_path: Annotated[Path, typer.Option("--report", exists=True)],
    dataset_path: Annotated[Path, typer.Option("--dataset", exists=True)],
    require_human: Annotated[bool, typer.Option("--require-human")] = False,
) -> None:
    report = LiveEvaluationReport.model_validate_json(report_path.read_text(encoding="utf-8"))
    reasons = verify_live_report(
        report,
        current_context(dataset_path, Settings(), REPO_ROOT),
        require_human=require_human,
    )
    if reasons:
        typer.echo(f"live-evaluation-invalid={','.join(reasons)}", err=True)
        raise typer.Exit(code=1)
    typer.echo("live-evaluation-valid=true")

if __name__ == "__main__":
    typer.run(main)

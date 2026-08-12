from pathlib import Path
from typing import Final

from pydantic import TypeAdapter, ValidationError

from evaluation.models import EvaluationCase

CASE_ADAPTER: Final = TypeAdapter(EvaluationCase)


class EvaluationDatasetError(Exception):
    def __init__(self, path: Path, line_number: int) -> None:
        self.path = path
        self.line_number = line_number
        super().__init__(f"Invalid evaluation case at {path}:{line_number}")


def load_evaluation_cases(path: Path) -> tuple[EvaluationCase, ...]:
    cases: list[EvaluationCase] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not line.strip():
            continue
        try:
            cases.append(CASE_ADAPTER.validate_json(line))
        except ValidationError as exc:
            raise EvaluationDatasetError(path, line_number) from exc
    return tuple(cases)

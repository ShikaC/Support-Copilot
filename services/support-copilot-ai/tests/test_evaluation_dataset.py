from pathlib import Path
from typing import Final

import pytest

from evaluation.dataset import EvaluationDatasetError, load_evaluation_cases

DATASET_PATH: Final = (
    Path(__file__).parents[1] / "evaluation" / "data" / "tickets.jsonl"
)


def test_fixed_dataset_loads_unique_cases() -> None:
    cases = load_evaluation_cases(DATASET_PATH)
    case_ids = [case.id for case in cases]

    assert len(cases) >= 15
    assert len(case_ids) == len(set(case_ids))


def test_invalid_case_reports_its_line_number(tmp_path: Path) -> None:
    dataset = tmp_path / "invalid-tickets.jsonl"
    dataset.write_text(
        "\n"
        '{"id":"invalid-001","subject":"测试工单",'
        '"description":"缺少人工期望分类",'
        '"expected_priority":"MEDIUM","expected_escalation":false,'
        '"evidence_required":false}\n',
        encoding="utf-8",
    )

    with pytest.raises(EvaluationDatasetError) as error:
        load_evaluation_cases(dataset)

    assert error.value.line_number == 2
